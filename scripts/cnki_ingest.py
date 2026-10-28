#!/usr/bin/env python3
"""把知网/万方/维普的导出文件，转成本仓库流水线能直接吃的结构化文献池。

用法：
  python scripts/cnki_ingest.py --inputs <文件或目录>... --out <输出目录>
  python scripts/cnki_ingest.py --selftest

支持的导出格式（自动识别，可混着给）：
  RIS          .ris   —— CNKI「导出文献 → RIS」、万方、维普、Zotero、EndNote 通用
  EndNote      .enw   —— CNKI「EndNote」，%A %T %J 前缀
  NoteExpress  .net   —— CNKI「NoteExpress」，{Title}: 前缀
  CNKI 自有一行一款 —— 「参考文献」文本 / 「自定义」导出，GB/T 7714 格式纯文本
  MEDLINE      .nbib  —— 顺带支持，PubMed 用

输出（写到 --out）：
  records.json    结构化题录（含 GB/T 7714-2015 预生成引文）
  records.md      人读清单，带缺字段标记，直接贴给作者看
  issues.md       质检报告：缺页码/缺卷期/缺 DOI/疑似重复/年份可疑
  sources.json    每个输入文件解析出几条，便于核对「导出是不是漏了」

设计原则：
  1. 不联网。知网没有公开 API，任何「自动查元数据」的承诺都是假的。
  2. 缺字段就标缺，不猜、不补、不四舍五入。
  3. 重复判定只做能解释的三种：DOI 相同 / 标题+首作者+年相同 / 标题高度相似。
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import re
import sys

# ---------------------------------------------------------------- 基础工具


def _utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _clean(s):
    if s is None:
        return ""
    s = str(s).replace("\ufeff", "").replace("\u00a0", " ")
    s = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", s)  # 零宽与方向控制符
    return re.sub(r"\s+", " ", s).strip()


def _first(lst):
    return lst[0] if lst else ""


# ---------------------------------------------------------------- 各种格式解析

RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  - ?(.*)$")
ENW_LINE = re.compile(r"^%([A-Z0-9@!$&()*+^~#])\s?(.*)$")
NE_LINE = re.compile(r"^\{(.+?)\}:\s?(.*)$")

# CNKI / 通用 RIS 类型映射到中文文献类型标识
RIS_TO_CN_TYPE = {
    "JOUR": "J", "JFULL": "J", "MGZN": "J", "NEWS": "N", "BOOK": "M",
    "CHAP": "M", "CONF": "C", "CPAPER": "C", "THES": "D", "RPRT": "R",
    "ELEC": "EB", "GEN": "Z", "UNPB": "Z", "PAT": "P", "STAND": "S",
}

# EndNote(%0) / NoteExpress({Reference Type}) 的自由文本类型名 → 类型标识
KIND_WORDS_TO_CN_TYPE = [
    ("thesis", "D"), ("dissertation", "D"), ("学位论文", "D"), ("博士论文", "D"),
    ("硕士论文", "D"),
    ("journal", "J"), ("article", "J"), ("期刊", "J"), ("报纸", "N"),
    ("newspaper", "N"), ("magazine", "J"),
    ("book section", "M"), ("chapter", "M"), ("book", "M"), ("专著", "M"),
    ("图书", "M"),
    ("conference", "C"), ("proceedings", "C"), ("会议", "C"),
    ("report", "R"), ("报告", "R"),
    ("patent", "P"), ("standard", "S"), ("web", "EB"), ("electronic", "EB"),
]


def kind_word_to_cn_type(word):
    """把 'Journal Article' / '博士学位论文' 之类映射成 J/M/D/..."""
    w = (word or "").strip().lower()
    if not w:
        return ""
    for needle, t in KIND_WORDS_TO_CN_TYPE:
        if needle in w:
            return t
    return ""


def parse_ris(text):
    """解析 RIS。返回 [ {tag: [values]}, ... ] —— 保留原始多值。"""
    recs, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        m = RIS_LINE.match(line)
        if m:
            tag, val = m.group(1), _clean(m.group(2))
            if tag == "TY":
                if cur:
                    recs.append(cur)
                cur = collections.OrderedDict()
            elif tag == "ER":
                if cur:
                    recs.append(cur)
                cur = None
                continue
            if cur is not None:
                # 每个 tag 单独一条（AU 会出现多次）；真正的续行是没有 tag 的行，见下方分支
                cur.setdefault(tag, []).append(val)
        elif line.strip() and cur:
            # 没有 tag 的续行，接到上一个 tag
            last = next(reversed(cur))
            cur[last][-1] = _clean(cur[last][-1] + " " + line)
    if cur:
        recs.append(cur)
    return recs


def parse_enw(text):
    """解析 EndNote 导出（%A %T %J ...）。"""
    recs, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        m = ENW_LINE.match(line)
        if not m:
            if cur is not None:
                last = next(reversed(cur))
                cur[last][-1] = _clean(cur[last][-1] + " " + line)
            continue
        tag, val = m.group(1), _clean(m.group(2))
        if tag == "0":
            if cur:
                recs.append(cur)
            cur = collections.OrderedDict()
            cur["_KIND"] = [val]
            continue
        if cur is None:
            cur = collections.OrderedDict()
        cur.setdefault(tag, []).append(val)
    if cur:
        recs.append(cur)
    return recs


def parse_noteexpress(text):
    """解析 NoteExpress 导出（{Reference Type}: {Title}: ...）。"""
    recs, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        m = NE_LINE.match(line)
        if m:
            key, val = m.group(1).strip(), _clean(m.group(2))
            if key.lower().startswith("reference type"):
                if cur:
                    recs.append(cur)
                cur = collections.OrderedDict()
                cur["_KIND"] = [val]
                continue
            if cur is None:
                cur = collections.OrderedDict()
            cur.setdefault(key, []).append(val)
        elif line.strip() and cur:
            last = next(reversed(cur))
            cur[last][-1] = _clean(cur[last][-1] + " " + line)
    if cur:
        recs.append(cur)
    return recs


GB_LINE = re.compile(
    r"^\s*(?:\[\d+\])?\s*(?P<body>.+?)\s*(?P<kind>\[[A-Z]{1,2}(?:/[A-Z]{1,2})?\])\s*\.?\s*(?P<rest>.*)$"
)


def parse_gb_text(text):
    """解析「参考文献」样式的纯文本（CNKI 自定义导出 / 复制题录）。

    识别形如：
      [1] 张三, 李四. 论文题目[J]. 中国工业经济, 2024, 41(3): 5-22.
    或
      [1] 张三. 书名[M]. 北京: 人民出版社, 2020: 15-20.
    返回的每条只保证【作者/标题/类型标识】可靠，其余字段尽力而为。
    """
    recs = []
    for raw in text.splitlines():
        m = GB_LINE.match(raw)
        if not m:
            continue
        body = _clean(m.group("body"))
        kind = m.group("kind").strip("[]").split("/")[0]
        # 作者与标题以第一个 ". " 为界（中文题录里标题后跟 [J]）。
        # 中英文混排时作者可能用英文句点分隔，优先取最后一个「句点+空格」。
        if ". " in body:
            authors, title = body.rsplit(". ", 1)
        elif "." in body:
            authors, title = body.split(".", 1)
        else:
            authors, title = "", body
        rest = _clean(m.group("rest"))
        rec = collections.OrderedDict()
        rec["_KIND"] = ["JOUR" if kind == "J" else "GEN"]
        rec["_CN_TYPE"] = [kind]
        rec["_RAW"] = [_clean(raw)]
        if authors.strip():
            rec["AU"] = [a.strip() for a in re.split(r"[,，;；]", authors) if a.strip()]
        if title.strip():
            rec["TI"] = [title.strip()]
        # 「刊名, 年, 卷(期): 起-止页」——只对期刊/报纸有意义
        m2 = re.search(
            r"(?P<j>[^,，]+)[,，]\s*(?P<y>(?:19|20)\d{2})\s*(?:[,，]\s*(?P<v>\d+)\s*)?"
            r"(?:\((?P<i>[^)]*)\))?\s*[:：]\s*(?P<p>\d+\s*[-–—~]\s*\d+|\d+)?",
            rest,
        )
        if kind in ("J", "N") and m2:
            rec["JO"] = [_clean(m2.group("j"))]
            rec["PY"] = [m2.group("y")]
            if m2.group("v"):
                rec["VL"] = [m2.group("v")]
            if m2.group("i"):
                rec["IS"] = [m2.group("i")]
            if m2.group("p"):
                rec["SP"] = [_clean(m2.group("p"))]
        elif kind in ("J", "N"):
            m2b = re.search(r"(?P<j>[^,，]+)[,，]\s*(?P<y>(?:19|20)\d{2})", rest)
            if m2b:
                rec["JO"] = [_clean(m2b.group("j"))]
                rec["PY"] = [m2b.group("y")]
        m3 = re.search(r"DOI[:：]\s*([^\s.]+)", raw, re.I)
        if m3:
            rec["DO"] = [m3.group(1)]
        # 专著/学位论文/报告：「出版地: 出版者, 年: 页码」
        if kind in ("M", "D", "R", "S", "C"):
            m4 = re.search(
                r"(?:(?P<city>[\u4e00-\u9fa5]{2,12})\s*[:：]\s*)?"
                r"(?P<pub>[^,，:：]{2,40}?(?:出版社|印书馆|书局|大学出版社|"
                r"研究院|研究所|大学|学院|中心|委员会|协会|部|厅|局))",
                rest,
            )
            if m4:
                if m4.group("city"):
                    rec["CY"] = [_clean(m4.group("city"))]
                rec["PB"] = [_clean(m4.group("pub"))]
            my = re.search(r"[,，]\s*((?:19|20)\d{2})", rest)
            if my:
                rec["PY"] = [my.group(1)]
            mp = re.search(r"[:：]\s*(\d+\s*[-–—~]\s*\d+|\d+)\s*\.?$", rest)
            if mp:
                rec["SP"] = [_clean(mp.group(1))]
        recs.append(rec)
    return recs


def detect_and_parse(path):
    """按内容嗅探格式，返回 (格式名, 记录列表)。"""
    with open(path, "rb") as fh:
        raw = fh.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    head = text[:8000]
    if re.search(r"(?m)^TY  - ", head):
        return "RIS", parse_ris(text)
    if re.search(r"(?m)^%0 ", head):
        return "EndNote", parse_enw(text)
    if re.search(r"(?m)^\{Reference Type\}:", head):
        return "NoteExpress", parse_noteexpress(text)
    if re.search(r"(?m)^PMID- ", head):
        from_srlib = _try_srlib_medline(text)
        return "MEDLINE", from_srlib
    recs = parse_gb_text(text)
    if recs:
        return "GB/T 7714 文本", recs
    return "未知", []


def _try_srlib_medline(text):
    """复用 sr-screener 的 MEDLINE 解析器（存在就用，不存在就退化）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, "..", "skills", "academic-research-skills",
                        "sr-screener", "scripts")
    try:
        sys.path.insert(0, os.path.abspath(cand))
        import srlib  # noqa: WPS433
        return srlib.parse_medline(text)
    except Exception:
        return []


# ---------------------------------------------------------------- 归一化


def to_record(rec, fmt):
    """把各格式的原始记录压成统一结构。"""
    g = lambda *keys: _first([_first(rec.get(k, [])) for k in keys if rec.get(k)])

    authors = []
    if fmt in ("RIS",):
        authors = rec.get("AU", []) or rec.get("A1", [])
    elif fmt == "EndNote":
        authors = rec.get("A", [])
    elif fmt == "NoteExpress":
        authors = rec.get("Author", [])
    else:
        authors = rec.get("AU", [])
    # 半角分号/逗号挤在一格里时拆开（NoteExpress 与部分 RIS 导出会这样）
    flat = []
    for a in authors:
        a = _clean(a)
        if not a:
            continue
        parts = [p.strip() for p in re.split(r"[;；]", a) if p.strip()]
        flat.extend(parts or [a])
    authors = flat
    title = g("TI", "T1", "T", "Title")
    journal = g("JO", "T2", "JF", "JA", "J", "Journal")
    year = g("PY", "Y1", "Y", "D", "DA", "Year")
    volume = g("VL", "V", "Volume")
    issue = g("IS", "N", "Issue", "Number")
    pages = g("SP", "P", "Pages", "Page")
    if fmt == "RIS" and rec.get("EP"):
        sp = _first(rec.get("SP", []))
        ep = _first(rec.get("EP", []))
        if sp and ep and ep != sp:
            pages = f"{sp}-{ep}"
        elif sp:
            pages = sp
    doi = g("DO", "R", "DOI")
    abstract = g("AB", "X", "Abstract", "N2")
    keywords = g("KW", "K", "Keywords")
    publisher = g("PB", "Publisher")
    place = g("CY", "City")

    raw_kind = (_first(rec.get("_KIND", [])) or _first(rec.get("TY", [])) or "").upper()
    cn_type = _first(rec.get("_CN_TYPE", []))
    if not cn_type:
        # _KIND 是 EndNote/NoteExpress 的自由文本（"Journal Article"），要翻译；
        # TY 是 RIS 的三字母码，查表。两者都认不出来才落 Z。
        cn_type = kind_word_to_cn_type(raw_kind) or RIS_TO_CN_TYPE.get(raw_kind, "Z")

    # 年份清洗：RIS 里可能是 2024/// 或 2024/05/06
    ym = re.search(r"(19|20)\d{2}", year or "")
    year = ym.group(0) if ym else ""

    # 页码清洗：「5-22」保留，「5」也保留但标记为仅起始页
    pages = _clean(re.sub(r"[^\d\-–—~+]+$", "", pages or ""))

    return {
        "title": _clean(title),
        "authors": [_clean(a) for a in authors if _clean(a)],
        "journal": _clean(journal),
        "year": year,
        "volume": _clean(volume),
        "issue": _clean(issue),
        "pages": pages,
        "doi": _clean(doi),
        "abstract": _clean(abstract),
        "keywords": _clean(keywords),
        "publisher": _clean(publisher),
        "place": _clean(place),
        "cn_type": cn_type,
        "raw_type": raw_kind,
        "raw": _first(rec.get("_RAW", [])),
        "source_format": fmt,
    }


def gbt_citation(r):
    """按 GB/T 7714-2015 顺序编码制生成引文（缺项自动省略，不做占位）。"""
    au = ", ".join(r["authors"][:3])
    if len(r["authors"]) > 3:
        au += ", 等"
    parts = []
    if au:
        parts.append(au)
    if r["title"]:
        parts.append(r["title"])
    t = r["cn_type"] or "Z"
    head = ""
    if parts:
        head = ". ".join(parts) + f"[{t}]"
    else:
        head = f"[{t}]"

    tail = []
    if t == "J":
        seg = r["journal"]
        if seg and r["year"]:
            seg += f", {r['year']}"
            if r["volume"] and r["volume"] != "0":
                seg += f", {r['volume']}"
            if r["issue"]:
                seg += f"({r['issue']})"
            if r["pages"]:
                seg += f": {r['pages']}"
        elif seg:
            pass
        if seg:
            tail.append(seg)
    elif t in ("M", "D", "R"):
        seg = ""
        if r["place"] and r["publisher"]:
            seg = f"{r['place']}: {r['publisher']}"
        elif r["publisher"]:
            seg = r["publisher"]
        if seg and r["year"]:
            seg += f", {r['year']}"
        if seg:
            tail.append(seg)
        if r["pages"]:
            tail.append(f"{r['pages']}")
    else:
        seg = r["journal"] or r["publisher"]
        if seg and r["year"]:
            seg = f"{seg}, {r['year']}"
        if seg:
            tail.append(seg)

    if r["doi"]:
        tail.append(f"DOI: {r['doi']}")
    body = head
    if tail:
        body += ". " + ", ".join(tail)
    return re.sub(r"\s+", " ", body).strip().rstrip(".") + "."


# ---------------------------------------------------------------- 质检


def check(r):
    """返回该条的问题列表（字符串）。"""
    out = []
    t = r["cn_type"]
    if not r["title"]:
        out.append("缺标题")
    if not r["authors"]:
        out.append("缺作者")
    if not r["year"]:
        out.append("缺年份")
    if t == "J":
        if not r["journal"]:
            out.append("期刊论文缺刊名")
        if not r["issue"] and not r["volume"]:
            out.append("缺卷或期")
        if not r["pages"]:
            out.append("缺页码（GB/T 7714 期刊条目必需）")
        elif "-" not in r["pages"] and "–" not in r["pages"]:
            out.append("页码只有起始页")
    elif t in ("M", "D"):
        if not r["publisher"]:
            out.append("专著/学位论文缺出版者")
    elif t in ("EB", "OL"):
        out.append("电子文献需人工补 [引用日期] 与 URL")
    if r["year"]:
        y = int(r["year"])
        if y < 1900 or y > 2100:
            out.append(f"年份可疑：{r['year']}")
    return out


def find_duplicates(recs):
    """三种可解释的重复判定，返回 [(i, j, 理由)]。"""
    pairs = []
    seen_doi, seen_key = {}, {}
    for i, r in enumerate(recs):
        if r["doi"]:
            k = r["doi"].lower()
            if k in seen_doi:
                pairs.append((seen_doi[k], i, f"DOI 相同（{r['doi']}）"))
            else:
                seen_doi[k] = i
        if r["title"]:
            key = (re.sub(r"[^\w\u4e00-\u9fa5]", "", r["title"]).lower(),
                   (r["authors"][0] if r["authors"] else ""), r["year"])
            if key in seen_key and key[0]:
                pairs.append((seen_key[key], i, "标题+首作者+年 相同"))
            else:
                seen_key[key] = i
    # 标题高度相似（人工复核提示，不自动合并）
    for i in range(len(recs)):
        if not recs[i]["title"]:
            continue
        for j in range(i + 1, len(recs)):
            if not recs[j]["title"]:
                continue
            ratio = difflib.SequenceMatcher(None, recs[i]["title"],
                                            recs[j]["title"]).ratio()
            if ratio >= 0.92 and recs[i]["title"] != recs[j]["title"]:
                pairs.append((i, j, f"标题相似度 {ratio:.2f}，需人工判断"))
    # 去重（同一对可能被多个规则命中）
    uniq, seen = [], set()
    for a, b, why in pairs:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        uniq.append((a, b, why))
    return uniq


# ---------------------------------------------------------------- 主流程


def run(inputs, out_dir):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            for ext in (".ris", ".RIS", ".enw", ".ENW", ".net", ".NET",
                        ".nbib", ".NBIB", ".txt", ".TXT"):
                for name in sorted(os.listdir(p)):
                    if name.endswith(ext):
                        files.append(os.path.join(p, name))
        elif os.path.isfile(p):
            files.append(p)
        else:
            raise SystemExit(f"输入不存在：{p}")
    if not files:
        raise SystemExit("没有找到可解析的文件（.ris/.enw/.net/.nbib/.txt）")

    all_recs, sources = [], []
    for f in files:
        fmt, raw_recs = detect_and_parse(f)
        recs = [to_record(x, fmt) for x in raw_recs]
        recs = [r for r in recs if r["title"] or r["raw"]]
        sources.append({"file": os.path.basename(f), "format": fmt,
                        "records": len(recs)})
        for r in recs:
            r["_source_file"] = os.path.basename(f)
        all_recs.extend(recs)

    if not all_recs:
        raise SystemExit("解析出 0 条记录——请确认导出的是 RIS/EndNote/NoteExpress 格式，"
                         "而不是网页另存的 HTML。")

    os.makedirs(out_dir, exist_ok=True)

    # records.json
    out_json = []
    for i, r in enumerate(all_recs, 1):
        rec = dict(r)
        rec["id"] = f"R{i:05d}"
        rec["citation_gbt7714"] = gbt_citation(r)
        rec["issues"] = check(r)
        out_json.append(rec)
    with open(os.path.join(out_dir, "records.json"), "w", encoding="utf-8") as fh:
        json.dump(out_json, fh, ensure_ascii=False, indent=2)

    # records.md
    lines = ["# 文献池（由导出文件解析）", "",
             f"> 共 {len(out_json)} 条，来自 {len(sources)} 个导出文件。",
             "> **缺字段一律标出，不猜不补。** 带 ⚠ 的条目在进综述前必须补齐。", ""]
    for f in sources:
        lines.append(f"- `{f['file']}`（{f['format']}）→ {f['records']} 条")
    lines += ["", "---", ""]
    for r in out_json:
        flag = " ⚠" if r["issues"] else ""
        lines.append(f"## {r['id']}{flag} {r['title'] or '（无标题）'}")
        meta = []
        if r["authors"]:
            meta.append("作者：" + "、".join(r["authors"]))
        if r["journal"]:
            meta.append("出处：" + r["journal"])
        yvi = " ".join(x for x in [r["year"], r["volume"], r["issue"]]
                       if x and x != "0")
        if yvi:
            meta.append("年卷期：" + yvi)
        if r["pages"]:
            meta.append("页码：" + r["pages"])
        if r["doi"]:
            meta.append("DOI：" + r["doi"])
        if r["keywords"]:
            meta.append("关键词：" + r["keywords"])
        for m in meta:
            lines.append(f"- {m}")
        lines.append(f"- 引文：`{r['citation_gbt7714']}`")
        if r["issues"]:
            lines.append(f"- ⚠ **待补**：{'；'.join(r['issues'])}")
        if r["abstract"]:
            lines.append(f"- 摘要：{r['abstract'][:200]}{'…' if len(r['abstract']) > 200 else ''}")
        lines.append("")

    # issues.md
    dup = find_duplicates(out_json)
    bad = [r for r in out_json if r["issues"]]
    ilines = ["# 质检报告", "",
              f"- 总条数：**{len(out_json)}**",
              f"- 有问题的条目：**{len(bad)}**",
              f"- 疑似重复：**{len(dup)}** 组", "", "---", ""]
    ilines += ["## 一、字段缺口", ""]
    if not bad:
        ilines.append("无。全部条目字段齐全。")
    else:
        ilines += ["| ID | 标题 | 缺什么 |", "|---|---|---|"]
        for r in bad:
            ilines.append(f"| {r['id']} | {r['title'][:40]} | {'；'.join(r['issues'])} |")
    ilines += ["", "## 二、疑似重复", ""]
    if not dup:
        ilines.append("无。")
    else:
        ilines += ["| A | B | 理由 |", "|---|---|---|"]
        for a, b, why in dup:
            ilines.append(f"| {out_json[a]['id']} | {out_json[b]['id']} | {why} |")
        ilines += ["", "> **不要自动合并。** 逐条打开原页确认后再决定删哪条。"]
    ilines += ["", "## 三、下一步", "",
               "1. 补齐 `issues.md` 里列出的缺项（回知网题录页抄，不要凭记忆）。",
               "2. 处理重复项。",
               "3. 把 `records.json` 交给 t2 `corpus-archivist` 逐篇建读档。", ""]

    for name, content in (("records.md", lines), ("issues.md", ilines)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write("\n".join(content))
    with open(os.path.join(out_dir, "sources.json"), "w", encoding="utf-8") as fh:
        json.dump(sources, fh, ensure_ascii=False, indent=2)

    # 控制台汇总
    print(f"解析 {len(files)} 个文件 → {len(out_json)} 条记录")
    for f in sources:
        print(f"  {f['file']:<40s} {f['format']:<14s} {f['records']:>4d} 条")
    print(f"\n字段缺口 {len(bad)} 条，疑似重复 {len(dup)} 组")
    print(f"输出目录：{os.path.abspath(out_dir)}")
    print("  records.json / records.md / issues.md / sources.json")
    if bad:
        print("\n先看 issues.md，补齐缺项再进综述。")
    return 0 if not bad and not dup else 0  # 有缺口不算失败，是正常情况


# ---------------------------------------------------------------- 自检

RIS_SAMPLE = """TY  - JOUR
AU  - 张三
AU  - 李四
TI  - 数字化转型与企业绿色创新
JO  - 中国工业经济
PY  - 2024
VL  - 41
IS  - 3
SP  - 5
EP  - 22
DO  - 10.19581/j.cnki.ciejournal.2024.03.001
KW  - 数字化转型;绿色创新
AB  - 本文研究数字化转型对企业绿色创新的影响。
ER  - 

TY  - JOUR
AU  - 王五
TI  - 缺页码的测试条目
JO  - 管理世界
PY  - 2023
ER  - 
"""

ENW_SAMPLE = """%0 Journal Article
%A Smith, John
%A Doe, Jane
%T Testing the export pipeline
%J Journal of Tests
%D 2022
%V 10
%N 2
%P 100-110
%R 10.1000/test.2022
%K testing;export
%X An abstract here.
"""

NE_SAMPLE = """{Reference Type}: Journal Article
{Title}: 碳普惠机制建设与青年碳行为
{Author}: 齐晓亮;刘宜卓
{Journal}: 中国社会科学院大学学报
{Year}: 2024
{Issue}: 9
{Pages}: 55-70
"""

GB_SAMPLE = """[1] 张三, 李四. 数字化转型与企业绿色创新[J]. 中国工业经济, 2024, 41(3): 5-22.
[2] 陈万柏. 思想政治教育学原理[M]. 北京: 高等教育出版社, 2020: 15-20.
"""


def selftest():
    checks = []

    def ok(name, cond, extra=""):
        checks.append((name, bool(cond), extra))

    fmt, recs = "RIS", parse_ris(RIS_SAMPLE)
    rec = to_record(recs[0], fmt)
    ok("RIS 解析出 2 条", len(recs) == 2, f"实际 {len(recs)}")
    ok("RIS 标题", rec["title"] == "数字化转型与企业绿色创新", rec["title"])
    ok("RIS 作者 2 个", len(rec["authors"]) == 2, str(rec["authors"]))
    ok("RIS 刊名", rec["journal"] == "中国工业经济", rec["journal"])
    ok("RIS 页码合并", rec["pages"] == "5-22", rec["pages"])
    ok("RIS 类型 J", rec["cn_type"] == "J", rec["cn_type"])
    ok("RIS DOI", rec["doi"].endswith("03.001"), rec["doi"])

    rec2 = to_record(recs[1], fmt)
    ok("缺页码被查出", any("页码" in x for x in check(rec2)), str(check(rec2)))
    ok("缺卷期被查出", any("卷或期" in x for x in check(rec2)), str(check(rec2)))

    cit = gbt_citation(rec)
    ok("GB/T 引文含 [J]", "[J]" in cit, cit)
    ok("GB/T 引文含卷期页", "41(3): 5-22" in cit, cit)
    ok("GB/T 引文不含多余空格", "  " not in cit, cit)

    enw = to_record(parse_enw(ENW_SAMPLE)[0], "EndNote")
    ok("EndNote 标题", enw["title"] == "Testing the export pipeline", enw["title"])
    ok("EndNote 作者", len(enw["authors"]) == 2, str(enw["authors"]))
    ok("EndNote 年", enw["year"] == "2022", enw["year"])

    ne = to_record(parse_noteexpress(NE_SAMPLE)[0], "NoteExpress")
    ok("NoteExpress 标题", ne["title"] == "碳普惠机制建设与青年碳行为", ne["title"])
    ok("NoteExpress 作者", len(ne["authors"]) == 2, str(ne["authors"]))
    ok("NoteExpress 期", ne["issue"] == "9", ne["issue"])
    ok("NoteExpress 类型 J", ne["cn_type"] == "J", ne["cn_type"])
    ok("EndNote 类型 J", enw["cn_type"] == "J", enw["cn_type"])
    ok("类型词翻译", kind_word_to_cn_type("Journal Article") == "J"
       and kind_word_to_cn_type("博士学位论文") == "D"
       and kind_word_to_cn_type("Book") == "M", "类型词映射错误")

    gb = [to_record(x, "GB") for x in parse_gb_text(GB_SAMPLE)]
    ok("GB 文本解析 2 条", len(gb) == 2, f"实际 {len(gb)}")
    ok("GB 文本类型 J", gb[0]["cn_type"] == "J", gb[0]["cn_type"])
    ok("GB 文本类型 M", gb[1]["cn_type"] == "M", gb[1]["cn_type"])
    ok("GB 文本刊名", gb[0]["journal"] == "中国工业经济", gb[0]["journal"])
    ok("GB 专著出版者", "高等教育出版社" in (gb[1]["publisher"] + gb[1]["place"]), gb[1])

    dup_recs = [
        to_record(recs[0], "RIS"),
        to_record(recs[0], "RIS"),
    ]
    ok("重复能查出", len(find_duplicates(dup_recs)) >= 1, str(find_duplicates(dup_recs)))

    # 页码清洗
    r3 = to_record({"TY": ["JOUR"], "TI": ["X"], "SP": ["5-22."], "PY": ["2024///"]}, "RIS")
    ok("页码尾部标点被清", r3["pages"] == "5-22", r3["pages"])
    ok("年份 /// 被清", r3["year"] == "2024", r3["year"])

    print("自检：")
    bad = 0
    for name, passed, extra in checks:
        print(f"  [{'OK  ' if passed else 'FAIL'}] {name}" + (f"  ← {extra}" if not passed else ""))
        bad += 0 if passed else 1
    print(f"\n{len(checks) - bad}/{len(checks)} 通过")
    return 1 if bad else 0


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser(
        description="把知网/万方/维普导出文件转成结构化文献池",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--inputs", nargs="+", help="导出文件或目录")
    ap.add_argument("--out", help="输出目录，如 paper/<slug>/10-literature/")
    ap.add_argument("--selftest", action="store_true", help="跑内置自检")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.inputs or not a.out:
        ap.error("需要 --inputs 与 --out（或 --selftest）")
    return run(a.inputs, a.out)


if __name__ == "__main__":
    sys.exit(main())

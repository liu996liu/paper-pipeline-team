#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文交付前的可自动核验项。

四个子命令对应四类反复出现的编辑部退稿原因，都是人眼查不可靠、又不需要
外部服务的检查。只用标准库，不装任何东西。

    python scripts/verify_paper.py stats     paper/<slug>/50-draft/v3/manuscript.md
    python scripts/verify_paper.py numbers   paper/<slug>/50-draft/v3/manuscript.md --results paper/<slug>/30-analysis/results
    python scripts/verify_paper.py counts    paper/<slug>/50-draft/v3/manuscript.md --results paper/<slug>/30-analysis/results
    python scripts/verify_paper.py citations paper/<slug>/50-draft/v3/manuscript.md
    python scripts/verify_paper.py all       paper/<slug>/50-draft/v3/manuscript.md --results paper/<slug>/30-analysis/results

  加 --json 输出机器可读结果；有 FAIL 时退出码 1，可接进 CI 或 t11 闸门。

为什么是这四个：
  · stats     —— 报出的 t/F/χ²/Z 与 p 值对不上，是实证论文最高频的硬伤。
                 statcheck 等现成工具只认英文半角写法（t(120)=2.45, p=0.016），
                 中文常用的「t=2.45，p<0.01」「t（120）＝2.45」全部漏检，故自建。
  · numbers   —— 正文、表、图注里的同一个数不一致（改了表忘了改正文）。
  · counts    —— 数量断言与数据不符：「9 个题项全部显著」「8 题为 5 级计分」
                 「36 组两两组合」。这类错误比数字错误更隐蔽——那个 9 不在
                 任何结果表里，数字检查碰不到，统计检查也碰不到，但它决定了
                 读者对整节结果的信任。
  · citations —— GB/T 7714-2015 的必备要素缺项（缺版次、缺卷期、缺引用日期）。
                 这几项都能规则化判定，不依赖任何数据库查证。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

FAIL, WARN, OK = "FAIL", "WARN", "OK"

# ---------------------------------------------------------------- 统计分布
# 不依赖 scipy。t / F / χ² 的尾概率用正则化不完全 beta / gamma 函数算，
# 精度对 p 值判定（差 0.001 量级）足够。


def _gammaln(x: float) -> float:
    return math.lgamma(x)


def _betacf(a: float, b: float, x: float) -> float:
    """不完全 beta 函数的连分式（Lentz 法）。"""
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """正则化不完全 beta 函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = _gammaln(a + b) - _gammaln(a) - _gammaln(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _gser(a: float, x: float) -> float:
    ap, s, delta = a, 1.0 / a, 1.0 / a
    for _ in range(500):
        ap += 1.0
        delta *= x / ap
        s += delta
        if abs(delta) < abs(s) * 3e-12:
            break
    return s * math.exp(-x + a * math.log(x) - _gammaln(a))


def _gcf(a: float, x: float) -> float:
    tiny = 1e-30
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b if abs(b) > tiny else 1.0 / tiny
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return math.exp(-x + a * math.log(x) - _gammaln(a)) * h


def gammainc_P(a: float, x: float) -> float:
    """正则化下不完全 gamma 函数 P(a, x)。"""
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        return _gser(a, x)
    return 1.0 - _gcf(a, x)


def p_from_t(t: float, df: float) -> float:
    """双尾 p。"""
    t = abs(t)
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def p_from_f(f: float, d1: float, d2: float) -> float:
    """F 检验右尾 p。"""
    if f <= 0:
        return 1.0
    return betainc(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * f))


def p_from_chi2(chi2: float, df: float) -> float:
    """χ² 右尾 p。"""
    if chi2 <= 0:
        return 1.0
    return 1.0 - gammainc_P(df / 2.0, chi2 / 2.0)


def p_from_z(z: float) -> float:
    """正态双尾 p。"""
    return math.erfc(abs(z) / math.sqrt(2.0))


# ---------------------------------------------------------------- 预处理

FULLWIDTH = {
    "（": "(", "）": ")", "＝": "=", "，": ",", "＜": "<", "＞": ">",
    "χ": "X", "²": "2", "。": ".", "；": ";", "：": ":", "　": " ",
    "－": "-", "—": "-", "±": "+-",
}


def normalize(text: str) -> str:
    """全角转半角、常见符号归一。保留原始偏移用于回显行号。"""
    out = []
    for ch in text:
        out.append(FULLWIDTH.get(ch, ch))
    s = "".join(out)
    s = s.replace("χ2", "X2").replace("x2", "X2")
    s = re.sub(r"[ \t]+", " ", s)
    return s


NUM = r"[-+]?\d+(?:\.\d+)?"


def parse_pvalue(fragment: str):
    """从片段里取出 p 的比较符与数值。返回 (op, value) 或 None。"""
    m = re.search(
        rf"p\s*(<=|>=|<|>|=|≈|≤|≥)\s*({NUM})", fragment, re.I
    )
    if not m:
        return None
    op = m.group(1).replace("≤", "<=").replace("≥", ">=").replace("≈", "=")
    try:
        return op, float(m.group(2))
    except ValueError:
        return None


def verdict_p(reported_op, reported_p, computed) -> tuple[str, str]:
    """判断报出的写法与重算值是否相容。"""
    if reported_op == "=":
        ok = abs(reported_p - computed) <= max(0.0011, computed * 0.05)
    elif reported_op == "<":
        ok = computed < reported_p
    elif reported_op == "<=":
        ok = computed <= reported_p + 1e-9
    elif reported_op == ">":
        ok = computed > reported_p
    elif reported_op == ">=":
        ok = computed >= reported_p - 1e-9
    else:
        return WARN, f"无法识别的比较符 {reported_op}"
    detail = f"报 {reported_op}{reported_p}，重算 {computed:.4f}"
    return (OK, detail) if ok else (FAIL, detail)


# ---------------------------------------------------------------- stats

# 中文/英文混排下统计量的常见写法。df 可省略（省略时不校验 p，只提示）。
WINDOW = 60  # p 值通常跟在统计量后同一句里


def check_stats(text: str) -> list[dict]:
    results = []
    lines = text.splitlines()
    for lineno, raw in enumerate(lines, 1):
        line = normalize(raw)
        if not re.search(r"[pP]\s*[=<>≤≥]", line):
            continue
        # t 检验
        for m in re.finditer(rf"(?<![a-zA-Z])t\s*\(\s*({NUM})\s*\)\s*=\s*({NUM})", line):
            df, tval = float(m.group(1)), float(m.group(2))
            seg = line[m.end(): m.end() + WINDOW]
            pv = parse_pvalue(seg)
            if df < 1:
                continue
            computed = p_from_t(tval, df)
            results.append(_mk(lineno, raw, f"t({m.group(1)})={m.group(2)}", pv, computed))
        # F 检验
        for m in re.finditer(rf"(?<![a-zA-Z])F\s*\(\s*({NUM})\s*,\s*({NUM})\s*\)\s*=\s*({NUM})", line):
            d1, d2, fval = float(m.group(1)), float(m.group(2)), float(m.group(3))
            seg = line[m.end(): m.end() + WINDOW]
            pv = parse_pvalue(seg)
            if d1 < 1 or d2 < 1:
                continue
            computed = p_from_f(fval, d1, d2)
            results.append(_mk(lineno, raw, f"F({m.group(1)},{m.group(2)})={m.group(3)}", pv, computed))
        # χ²
        for m in re.finditer(rf"(?:X2|卡方)\s*\(\s*({NUM})\s*\)\s*=\s*({NUM})", line):
            df, cval = float(m.group(1)), float(m.group(2))
            seg = line[m.end(): m.end() + WINDOW]
            pv = parse_pvalue(seg)
            if df < 1:
                continue
            computed = p_from_chi2(cval, df)
            results.append(_mk(lineno, raw, f"χ²({m.group(1)})={m.group(2)}", pv, computed))
        # χ²=N，df=M 这种把自由度另写的常见中文写法。
        # 不处理它，正文里写成「χ²=19.21，df=3，p<0.001」的卡方就完全不会被重算，
        # 检查器会安静地报「不通过 0」——看起来像通过，其实一个数都没算。
        for m in re.finditer(rf"X2\s*=\s*({NUM})", line):
            seg = line[m.end(): m.end() + 2 * WINDOW]
            d = re.search(rf"(?:\bdf|自由度)\s*[=＝]\s*({NUM})", seg)
            pv = parse_pvalue(seg)
            if not d or pv is None:
                continue
            cval, df = float(m.group(1)), float(d.group(1))
            if df < 1:
                continue
            computed = p_from_chi2(cval, df)
            results.append(_mk(lineno, raw, f"χ²={m.group(1)},df={d.group(1)}", pv, computed))
        # Brant 检验的 W 统计量同样服从卡方，必须带自由度才可重算
        for m in re.finditer(rf"(?<![a-zA-Z])W\s*=\s*({NUM})", line):
            seg = line[m.end(): m.end() + 2 * WINDOW]
            d = re.search(rf"(?:\bdf|自由度)\s*[=＝]\s*({NUM})", seg)
            pv = parse_pvalue(seg)
            if not d or pv is None:
                continue
            wval, df = float(m.group(1)), float(d.group(1))
            if df < 1:
                continue
            computed = p_from_chi2(wval, df)
            results.append(_mk(lineno, raw, f"W={m.group(1)},df={d.group(1)}", pv, computed))
        # z
        for m in re.finditer(rf"(?<![a-zA-Z])z\s*=\s*({NUM})", line):
            zval = float(m.group(1))
            seg = line[m.end(): m.end() + WINDOW]
            pv = parse_pvalue(seg)
            computed = p_from_z(zval)
            results.append(_mk(lineno, raw, f"z={m.group(1)}", pv, computed))
    if results:
        results[0]["checked"] = len(results)
    else:
        # 一条统计量都没解析出来，不能报成「通过」。必须显式说明检查范围为空，
        # 否则作者会以为统计一致性已被验证。
        results.append({"line": 0, "status": WARN,
                        "detail": "全文未发现可重算的统计量（形如 t(df)=x / F(d1,d2)=x / "
                                  "χ²(df)=x / χ²=x，df=n / W=x，df=n / z=x 且带配对 p 值），"
                                  "本项检查未覆盖任何内容",
                        "text": ""})
    return results


def _mk(lineno, raw, expr, pv, computed):
    if pv is None:
        return {"line": lineno, "expr": expr, "status": WARN,
                "detail": "未找到配对的 p 值", "text": raw.strip()[:120]}
    op, val = pv
    status, detail = verdict_p(op, val, computed)
    return {"line": lineno, "expr": expr, "status": status,
            "detail": detail, "text": raw.strip()[:120]}


# ---------------------------------------------------------------- numbers

NUMTOK = re.compile(r"(?<![\w.])(\d+\.\d+)(?![\w.])")


def load_result_numbers(results_dir: Path | None) -> dict[str, set[float]]:
    """把 results/ 下所有 CSV 的数值收进集合，用于比对。"""
    pool: set[float] = set()
    if not results_dir or not results_dir.exists():
        return {"all": pool}
    for p in results_dir.rglob("*.csv"):
        try:
            with p.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.reader(fh):
                    for cell in row:
                        cell = cell.strip()
                        try:
                            pool.add(round(float(cell.replace(",", "")), 6))
                            continue
                        except ValueError:
                            pass
                        # 统计串里的数（chi2=19.2112, p=0.000247）也算结果来源，
                        # 否则这些值只能靠正文自证，检查会误判。
                        for num in NUMTOK.findall(cell):
                            try:
                                pool.add(round(float(num), 6))
                            except ValueError:
                                continue
        except OSError:
            continue
    return {"all": pool}


def strip_tables(text: str) -> tuple[str, str]:
    """分离 markdown 表格区与正文区，返回 (正文, 表格)。"""
    prose, tables = [], []
    for block in re.split(r"(\n\s*\n)", text):
        if re.search(r"^\s*\|", block, re.M) and block.count("|") >= 4:
            tables.append(block)
        else:
            prose.append(block)
    return "".join(prose), "".join(tables)


def _num_tokens(line: str) -> list[str]:
    """抽出一行里「像统计结果」的小数。

    只查两位及以上小数的数——年份、样本量、整数百分比这类误报太多，
    而「正文抄错表里的系数」几乎必然带两位以上小数。同时排除：
      * 节号 / 章节引用（2.1、4.3.1 这类位数递减的编号）
      * DOI（10.1207 等）与带前缀的编号
    """
    out = []
    for m in NUMTOK.finditer(line):
        tok = m.group(1)
        head = line[: m.start()]
        # DOI / 版本号 / 页码串
        if re.search(r"(?:(?:DOI|doi)\s*[:：]?|https?://|10\.)\s*$", head):
            continue
        if re.search(r"[A-Za-z]", line[max(0, m.start() - 1): m.start()]):
            continue
        # 节号：2.1、3.4、4.5 这种「个位数.个位数」，且前后不是统计语境
        if re.fullmatch(r"\d{1,2}\.\d{1,2}", tok) and not re.search(
                r"(?:=|＝|p|r|OR|β|均值|占比|%|人|分)", line[max(0, m.start() - 6): m.start() + len(tok) + 6]
        ):
            continue
        out.append(tok)
    return out


def _decode_tolerance(tok: str) -> float:
    """按书写精度决定容差：允许「正文四舍五入、源数据保留四位」的差异。

    正文写 4.53、CSV 存 4.5256，差值 0.0044，落在两位小数的半个末位内。
    固定用 5e-4 会把全部此类正常舍入判成错，检查就失去信噪比。
    """
    dec = len(tok.split(".")[1]) if "." in tok else 0
    return 0.5 * 10 ** (-dec) + 1e-9


def check_numbers(text: str, results_dir: Path | None) -> list[dict]:
    """正文里的小数若在表格与 results/ 里都找不到同值，标为需核对。

    比对时按正文书写精度给容差（两位小数 = ±0.005），并把负号归一，
    这样 r=-0.42 能对上 CSV 里的 -0.4217。
    """
    # 参考文献区里的 DOI / 期卷页不是统计结果，混进来只会制造误报
    ref = re.search(r"^#{1,3}\s*(?:参考文献|References)\s*$", text, re.M | re.I)
    if ref:
        text = text[: ref.start()]
    prose, tables = strip_tables(text)
    pool = load_result_numbers(results_dir)["all"]
    table_nums: set[float] = set()
    for tok in NUMTOK.findall(tables):
        try:
            table_nums.add(abs(round(float(tok), 6)))
        except ValueError:
            pass
    pool_abs = {abs(x) for x in pool}

    findings = []
    checked = 0
    for lineno, raw in enumerate(prose.splitlines(), 1):
        if re.match(r"^\s*\|", raw):
            continue
        unmatched = []
        for tok in _num_tokens(raw):
            checked += 1
            val = abs(round(float(tok), 6))
            tol = _decode_tolerance(tok)
            if any(abs(val - x) <= tol for x in table_nums):
                continue
            if pool_abs and any(abs(val - x) <= tol for x in pool_abs):
                continue
            if tok not in unmatched:
                unmatched.append(tok)
        if unmatched:
            findings.append({
                "line": lineno, "values": unmatched, "status": WARN,
                "detail": f"{len(unmatched)} 个正文数值在本稿表格与 results/ 中均未找到同值："
                          + "、".join(unmatched[:6]),
                "text": raw.strip()[:120],
            })
    # 检查过的数量本身就是结论的一部分：0 条待核对若无对照，无法区分
    # 「全部对上」与「一个数都没抓到」。
    if findings:
        findings[0]["checked"] = checked
    else:
        findings.append({"line": 0, "status": OK,
                         "detail": f"正文 {checked} 个数值均能在表格或 results/ 中找到同值",
                         "text": ""})
    return findings


# ---------------------------------------------------------------- citations

# GB/T 7714-2015 必备要素的粗检。不做文献存在性核验（那需要数据库），
# 只查「格式上缺什么」，这正是编辑部初审会打回的。
CITATION_RULES = [
    ("文献类型标识", re.compile(r"\[(?:M|J|N|D|C|R|S|P|G|EB/OL|M//|J/OL|N/OL|DB/OL|C/OL)\]"),
     "条目缺少文献类型标识 [M]/[J]/[N]/[EB/OL] 等"),
]


def check_citations(text: str) -> list[dict]:
    findings = []
    # 找参考文献区
    m = re.search(r"^#{1,3}\s*(?:参考文献|References)\s*$", text, re.M | re.I)
    if not m:
        return [{"line": 0, "status": WARN,
                 "detail": "未找到「参考文献 / References」标题，跳过引文格式检查",
                 "text": ""}]
    body = text[m.end():]
    lines = body.splitlines()
    entries = 0
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            break
        if not re.match(r"^\[\d+\]|^\d+[.、]", s):
            if entries == 0:
                continue
            continue
        entries += 1
        lineno = text[: m.end()].count("\n") + i
        tag = s.split("]", 1)[-1].strip() if s.startswith("[") else s

        has_type = bool(re.search(r"\[[A-Z/]{1,6}\]", tag))
        if not has_type:
            findings.append({"line": lineno, "status": FAIL,
                             "detail": "缺少文献类型标识（如 [J] / [M] / [EB/OL]）",
                             "text": s[:120]})
            continue

        kind = re.search(r"\[([A-Z/]{1,6})\]", tag)
        kind = kind.group(1) if kind else ""

        if kind.startswith("J"):
            if not re.search(r"\d{4}", tag):
                findings.append({"line": lineno, "status": FAIL,
                                 "detail": "期刊文献缺年份", "text": s[:120]})
            elif not re.search(r"\d+\s*(?:\(\s*\d+\s*\))?\s*[:：]\s*\d", tag):
                findings.append({"line": lineno, "status": WARN,
                                 "detail": "期刊文献似缺「卷(期): 起止页」", "text": s[:120]})
        elif kind.startswith("M"):
            if "//" not in tag and not re.search(r"\d{4}", tag):
                findings.append({"line": lineno, "status": FAIL,
                                 "detail": "专著缺出版年", "text": s[:120]})
            if "//" not in tag and not re.search(r":\s*\d+", tag):
                findings.append({"line": lineno, "status": WARN,
                                 "detail": "专著似缺页码", "text": s[:120]})
        elif kind.startswith("N"):
            if not re.search(r"\d{4}-\d{1,2}-\d{1,2}", tag):
                findings.append({"line": lineno, "status": FAIL,
                                 "detail": "报纸文献缺「年-月-日」", "text": s[:120]})
            if not re.search(r"\(\s*\d+\s*\)", tag):
                findings.append({"line": lineno, "status": WARN,
                                 "detail": "报纸文献缺版次 (01) 形式", "text": s[:120]})
        elif kind.startswith("EB"):
            if not re.search(r"\d{4}-\d{1,2}-\d{1,2}", tag):
                findings.append({"line": lineno, "status": FAIL,
                                 "detail": "电子文献缺发布日期", "text": s[:120]})
            if tag.count("20") + tag.count("19") < 2 and not re.search(
                    r"\[\s*\d{4}-\d{1,2}-\d{1,2}\s*\]\s*$", tag):
                findings.append({"line": lineno, "status": WARN,
                                 "detail": "电子文献似缺引用日期 [YYYY-MM-DD]", "text": s[:120]})
            if not re.search(r"https?://|www\.", tag):
                findings.append({"line": lineno, "status": FAIL,
                                 "detail": "电子文献缺可访问路径", "text": s[:120]})
    if entries == 0:
        findings.append({"line": 0, "status": WARN,
                         "detail": "参考文献区未解析出条目（需以 [1] 或 1. 开头）", "text": ""})
    elif not findings:
        # 全部合规时也要留一条 OK 记录。否则报告显示「通过 0」，
        # 与「一条都没解析出来」在输出上完全一样，作者无法判断是否真的查过。
        findings.append({"line": 0, "status": OK,
                         "detail": f"参考文献 {entries} 条，GB/T 7714-2015 必备要素齐全",
                         "text": ""})
    return findings


# ---------------------------------------------------------------- counts

# 数量断言：中文论文里极常见、又几乎不被任何检查器覆盖的一类错误。
# 「9 个题项全部显著」里那个 9，如果实际是 8 个，正文读起来毫无破绽，
# 数字检查也查不出来——因为 9 这个数不会出现在任何结果表里。
# 这里只查能被数据直接反驳的少数几种句式，查不到的宁可放过，不猜。
CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10}
NUMWORD = r"(?:\d+|[一二两三四五六七八九十])"


def _to_int(tok: str) -> int | None:
    if tok.isdigit():
        return int(tok)
    return CN_NUM.get(tok)


def _max_of(row: dict) -> int | None:
    """A1_descriptives 一行里的最高分（用来判断该题是几级计分）。"""
    v = row.get("最大值") or row.get("max")
    try:
        return int(float(str(v)))
    except (TypeError, ValueError):
        return None


def load_type_counts(dictionary: Path | None) -> dict[str, int] | None:
    """从 data-dictionary.md 的变量表数出各类变量有几个。

    问卷构成陈述（「5 题为多选题」）不在任何结果表里，只能回到数据字典核对。
    """
    if dictionary is None or not dictionary.exists():
        return None
    counts: dict[str, int] = {}
    for line in dictionary.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not cells[0].startswith("`q"):
            continue
        kind = cells[3]
        key = "多选" if "多选" in kind else ("名义" if "名义" in kind else None)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts or None


def check_counts(text: str, results: Path | None) -> list[dict]:
    findings = []
    if results is None or not results.is_dir():
        return [{"line": 0, "status": WARN,
                 "detail": "未提供 --results，跳过数量断言核对", "text": ""}]
    checked = 0

    def load(name):
        p = results / name
        if not p.exists():
            return None
        with p.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def add(lineno, raw, status, detail):
        findings.append({"line": lineno, "status": status,
                         "detail": detail, "text": raw.strip()[:120]})

    a4 = load("A4_group_tests.csv")
    a6 = load("A6_correlation.csv")
    a1 = load("A1_descriptives.csv")
    a9 = load("A9_bootstrap_ci.csv")
    dictionary = results / ".." / ".." / "20-data" / "data-dictionary.md"
    type_counts = load_type_counts(dictionary)
    groups_a4 = []
    if a4:
        for r in a4:
            g = r.get("分组变量")
            if g and g not in groups_a4:
                groups_a4.append(g)

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = normalize(raw)
        # 「N 个题项……全部显著 / 全部不显著」
        for m in re.finditer(rf"({NUMWORD})\s*个(?:可比的)?题项[^。；\n]{{0,24}}?(全部显著|全部不显著|均显著|均不显著|全部不显著)", line):
            n = _to_int(m.group(1))
            claim_all = "不显著" not in m.group(2)
            if n is None or a4 is None:
                continue
            checked += 1
            # 找该句在讲哪个分组：回溯本段内出现过的分组名
            ctx = line[max(0, m.start() - 40): m.start()]
            group = None
            for g in groups_a4:
                if g in ctx:
                    group = g
            if group is None:
                for g in groups_a4:
                    if g in line:
                        group = g
            if group is None:
                add(lineno, raw, WARN,
                    f"数量断言「{m.group(1)} 个题项…{m.group(2)}」无法判断所属分组，未核对")
                continue
            sub = [r for r in a4 if r["分组变量"] == group]
            n_items = len(sub)
            n_sig = sum(1 for r in sub if r["显著(Holm 0.05)"] == "是")
            if claim_all:
                ok = (n == n_items) and (n_sig == n_items)
                detail = (f"「{m.group(1)} 个题项全部显著」：{group}组实际有 {n_items} 个题项、"
                          f"{n_sig} 个显著")
            else:
                ok = n_sig == 0
                detail = (f"「{m.group(1)} 个题项全部不显著」：{group}组实际 {n_sig} 个显著")
            add(lineno, raw, OK if ok else FAIL, detail)

        # 「N 组两两组合 / N 组变量对」
        for m in re.finditer(rf"({NUMWORD})\s*组(?:两两)?(?:变量)?(?:组合|配对)", line):
            n = _to_int(m.group(1))
            if n is None or a6 is None:
                continue
            checked += 1
            actual = len(a6)
            add(lineno, raw, OK if n == actual else FAIL,
                f"「{m.group(1)} 组两两组合」：A6 实际 {actual} 组")

        # 「N 个 1—5 分题项」这类图注/正文里的量表题项数。
        # 口径：A9 里除 1—4 分题项（s_q08_heard_before）之外的条目数，
        # 因为图 1 画的就是这批。用 A1 的总行数会把 1—4 分题算进去。
        for m in re.finditer(rf"({NUMWORD})\s*个\s*1[—\-–]5\s*分", line):
            n = _to_int(m.group(1))
            if n is None or a9 is None:
                continue
            checked += 1
            actual = sum(1 for r in a9 if r.get("变量") != "s_q08_heard_before")
            add(lineno, raw, OK if n == actual else FAIL,
                f"「{m.group(1)} 个 1—5 分题项」：A9 中 1—5 分题项实际 {actual} 项")

        # 「8 题为 5 级计分的有序题项」这类问卷构成陈述。
        # 这是审稿人一读就会去对的数字，而它藏在一句描述问卷的话里，
        # 改过编码规则或增删题目后极易与结果表脱节，任何数字检查都碰不到。
        for m in re.finditer(rf"({NUMWORD})\s*题为\s*({NUMWORD})\s*级计分", line):
            n = _to_int(m.group(1))
            k = _to_int(m.group(2))
            if n is None or k is None or a1 is None:
                continue
            checked += 1
            actual = sum(1 for r in a1 if _max_of(r) == k)
            add(lineno, raw, OK if n == actual else FAIL,
                f"「{m.group(1)} 题为 {m.group(2)} 级计分」：A1 中最高分为 {k} 的题项实际 {actual} 项")

        # 「5 题为多选题」「4 题为名义变量」——用变量类型表核对
        for m in re.finditer(rf"({NUMWORD})\s*题为\s*(多选题|多选|名义变量|名义)", line):
            n = _to_int(m.group(1))
            want = "多选" if "多选" in m.group(2) else "名义"
            if n is None or type_counts is None:
                continue
            checked += 1
            actual = type_counts.get(want, 0)
            add(lineno, raw, OK if n == actual else FAIL,
                f"「{m.group(1)} 题为{m.group(2)}」：数据字典中该类型实际 {actual} 项")

    if not findings:
        findings.append({"line": 0, "status": OK,
                         "detail": f"未发现可自动核对的数量断言（共识别 {checked} 处）",
                         "text": ""})
    return findings


# ---------------------------------------------------------------- 主流程

def run(kind: str, path: Path, results: Path | None) -> tuple[list[dict], int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[dict] = []
    if kind in ("stats", "all"):
        out += check_stats(text)
    if kind in ("numbers", "all"):
        out += check_numbers(text, results)
    if kind in ("counts", "all"):
        out += check_counts(text, results)
    if kind in ("citations", "all"):
        out += check_citations(text)
    return out, len(text.splitlines())


def report(name: str, findings: list[dict], as_json: bool) -> int:
    fails = [f for f in findings if f["status"] == FAIL]
    warns = [f for f in findings if f["status"] == WARN]
    passes = [f for f in findings if f["status"] == OK]

    if as_json:
        print(json.dumps({"check": name, "fail": fails, "warn": warns,
                          "ok": len(passes)}, ensure_ascii=False, indent=2))
    else:
        print(f"\n===== {name} =====")
        for f in fails:
            loc = f"L{f['line']}" if f.get("line") else "-"
            print(f"[FAIL] {loc}  {f['detail']}")
            if f.get("text"):
                print(f"        {f['text']}")
        for f in warns:
            loc = f"L{f['line']}" if f.get("line") else "-"
            print(f"[WARN] {loc}  {f['detail']}  {f.get('text', '')}")
        print(f"通过 {len(passes)} ｜ 待核对 {len(warns)} ｜ 不通过 {len(fails)}")
    return 1 if fails else 0


def selftest() -> int:
    """对已知临界值重算 p，用于 CI 防止分布实现被改坏。"""
    cases = [
        ("t(28)=2.20", p_from_t(2.20, 28), 0.036225),
        ("t(120)=2.45", p_from_t(2.45, 120), 0.015729),
        ("t(1)=12.706", p_from_t(12.706, 1), 0.050000),
        ("F(1,118)=0.87", p_from_f(0.87, 1, 118), 0.352860),
        ("F(2,45)=3.204", p_from_f(3.204, 2, 45), 0.050000),
        ("chi2(3)=7.815", p_from_chi2(7.815, 3), 0.050000),
        ("chi2(1)=3.841", p_from_chi2(3.841, 1), 0.050000),
        ("z=1.96", p_from_z(1.96), 0.050000),
        ("z=2.576", p_from_z(2.576), 0.010000),
    ]
    # numbers 检查的容差与正负号归一：这些是最容易被「优化」掉的规则，
    # 一旦回归，正文就会被成片误报，检查等于失效。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        Path(td, "r.csv").write_text(
            "变量,均值,p值,统计量串\n"
            "a,4.5256,0.000247237,\"chi2=19.2112, df=3, p=0.000247237\"\n"
            "b,-0.4217,0.0003,x\n", encoding="utf-8")
        probe = (
            "再次听讲意愿 4.53；效应量 r=-0.42；卡方 chi2=19.21。\n"
            "#### 2.1 小节标题\n"
            "参考文献 DOI: 10.1207/s15326985ep4102_1\n"
        )
        got = check_numbers(probe, Path(td))
        # 4.53 对 4.5256（两位小数容差 0.005）、-0.42 对 -0.4217、19.21 对 19.2112 都应命中；
        # 2.1 是节号、10.1207 是 DOI，都不该报。
        # 注意：命中时 check_numbers 会追加一条 OK 记录说明覆盖量，所以这里数的是
        # 「真正的问题条目」，不是返回列表长度。
        problems = [g for g in got if g["status"] != OK]
        ok = len(problems) == 0 and any(g["status"] == OK for g in got)
        bad = 0 if ok else 1
        print(f"[{'OK  ' if ok else 'FAIL'}] numbers 容差/归一/排除  误报 {len(problems)} 条"
              + ("" if ok else f"：{[g.get('values') for g in problems]}"))

    # stats 的三种「自由度另写」写法：如果正则回归，检查器会静默地一个数都不重算，
    # 对外仍报「不通过 0」，这是最危险的失败形态，必须有回归用例钉住。
    stats_probe = (
        "与是否开课显著相关（χ²=19.21，df=3，p<0.001）。\n"
        "平行回归假设检验 W=14.45，df=18，p=0.699。\n"
        "χ²(3)=19.2112，p=0.000247。\n"
    )
    n_stats = len(check_stats(stats_probe))
    ok = n_stats == 3
    bad += 0 if ok else 1
    print(f"[{'OK  ' if ok else 'FAIL'}] stats  χ²=x,df=n / W=x,df=n / χ²(n)=x  解析出 {n_stats}/3 条")

    for name, got, want in cases:
        ok = abs(got - want) < 5e-4
        bad += 0 if ok else 1
        print(f"[{'OK  ' if ok else 'FAIL'}] {name:16s} 重算 {got:.6f}  期望 {want:.6f}")
    # counts：数量断言最容易「看起来没问题」——正文里一个 8 写成 7，
    # 数字检查碰不到（7 不在任何结果表里），stats 碰不到（不是统计量），
    # 只有这里能钉住。正反两个方向都要测，否则检查器可能只是没匹配上。
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "A4_group_tests.csv").write_text(
            "分组变量,因变量,显著(Holm 0.05)\n"
            "性别,a,是\n性别,b,是\n学段,a,否\n学段,b,否\n", encoding="utf-8")
        (d / "A1_descriptives.csv").write_text(
            "变量,最大值\nq1,5\nq2,5\nq3,4\n", encoding="utf-8")
        (d / "A9_bootstrap_ci.csv").write_text(
            "变量,含义\nq1,x\nq2,x\n", encoding="utf-8")
        good = ("性别 2 个题项全部显著；学段 2 个题项全部不显著。"
                "共 2 个 1—5 分题项，另有 1 题为 4 级计分。")
        wrong = ("性别 3 个题项全部显著；学段 1 个题项全部显著。"
                 "共 3 个 1—5 分题项，另有 2 题为 4 级计分。")
        g_ok = [f for f in check_counts(good, d) if f["status"] != OK]
        g_bad = [f for f in check_counts(wrong, d) if f["status"] != OK]
        ok = len(g_ok) == 0 and len(g_bad) == 4
        bad += 0 if ok else 1
        print(f"[{'OK  ' if ok else 'FAIL'}] counts  正确断言误报 {len(g_ok)} 条"
              f"｜错误断言应报 4 条实报 {len(g_bad)} 条")

    total = len(cases) + 3
    print(f"\n{total - bad}/{total} 通过")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="论文交付前的可自动核验项")
    ap.add_argument("check", nargs="?", choices=["stats", "numbers", "counts", "citations", "all"])
    ap.add_argument("manuscript", type=Path, nargs="?")
    ap.add_argument("--results", type=Path, default=None,
                    help="results/ 目录，numbers 检查时用于比对")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="校验分布实现的数值精度")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.check or not args.manuscript:
        ap.error("需要 check 与 manuscript 参数（或用 --selftest）")
    if not args.manuscript.exists():
        print(f"文件不存在：{args.manuscript}", file=sys.stderr)
        return 2

    rc = 0
    for kind in (["stats", "numbers", "counts", "citations"] if args.check == "all" else [args.check]):
        findings, _ = run(kind, args.manuscript, args.results)
        rc |= report(kind, findings, args.json)
    return rc


if __name__ == "__main__":
    sys.exit(main())

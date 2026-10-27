# -*- coding: utf-8 -*-
"""把文本底本（md/txt）与 PDF 逐页对齐，用于「某条引文在原书第几页」这类内部核对。

产物：<输出目录>/<slug>.json  —— 页号 → {start, end, head, anchored, md_text_head}
      <输出目录>/index.json   —— 各篇概览（尾残差应为 0）

用法：
    python align_pages.py --pdf <PDF目录> --md <文本目录> [--out <输出目录>]
    python align_pages.py --pdf <PDF目录> --md <文本目录> --locate 篇名关键词 15
                          打印该书第 15 页在文本中的开头（用于核对引文页码）

说明：成稿不印页码时，这个对齐仍值得做——写总论要判断某句话出自哪一节，
      有时需要知道它在原书的哪一段位置。
"""
import json
import os
import re
import sys

from pypdf import PdfReader

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002ffff]")


def cjk(s):
    return "".join(CJK.findall(s))


def slug(name):
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name)
    return s[:60].strip("_")


def pages_of(pdf_path):
    return [cjk(p.extract_text() or "") for p in PdfReader(pdf_path).pages]


def _anchor(M, probe, lo, hi):
    """在 M[lo:hi] 内找 probe 的落点；逐级放宽 probe。找不到返回 -1。"""
    for k in (30, 24, 16, 10):
        p = probe[:k]
        if len(p) < 6:
            break
        j = M.find(p, lo, hi)
        if j >= 0:
            return j
    return -1


def align_one(pdf_path, md_path):
    """以「下一页页首文本」为锚点反推本页末界。

    按字数顺序累加在双栏排版上会漂移（PDF 读序与文本不同），
    所以每页起点取该页页首文本在文本汉字流中的实际落点，页末取下一页锚点。
    """
    pdf_pages = pages_of(pdf_path)
    M = cjk(open(md_path, encoding="utf-8", errors="ignore").read())
    n = len(pdf_pages)
    body = [p for p in pdf_pages if p]
    avg = (sum(len(p) for p in body) / len(body)) if body else 1

    anchors = [0]
    weak = []
    for i in range(1, n):
        ptxt = pdf_pages[i]
        if not ptxt:
            anchors.append(None)
            continue
        expect = int(i * len(M) / n)
        win = int(avg * 2.2) + 300
        pos = _anchor(M, ptxt, max(0, expect - win), min(len(M), expect + win))
        if pos < 0:
            pos = _anchor(M, ptxt, 0, len(M))
            if pos >= 0:
                weak.append(i + 1)
        anchors.append(pos)

    clean, last = [0], 0
    for i in range(1, n):
        a = anchors[i]
        if a is None or a <= last:
            clean.append(None)
        else:
            clean.append(a)
            last = a
    for i in range(1, n):
        if clean[i] is None:
            j = i + 1
            while j < n and clean[j] is None:
                j += 1
            nxt = clean[j] if j < n and clean[j] is not None else len(M)
            prev = clean[i - 1]
            clean[i] = prev + int((nxt - prev) / (j - i + 1))

    pages = {}
    for i in range(n):
        start = clean[i]
        end = clean[i + 1] if i + 1 < n else len(M)
        end = max(start, min(end, len(M)))
        pages[i + 1] = {
            "start": start, "end": end, "head": pdf_pages[i][:24],
            "len": len(pdf_pages[i]), "span": end - start,
            "anchored": True if i == 0 else anchors[i] is not None,
            "text_head": M[start:start + 30],
        }
    return {
        "pdf": pdf_path, "md": md_path, "pages_n": n,
        "pdf_cjk": sum(len(p) for p in pdf_pages), "md_cjk": len(M),
        "tail_drift": len(M) - pages[n]["end"] if n else 0,
        "weak_anchors": weak, "pages": pages,
    }


def find_text_for(base, md_dir):
    p = os.path.join(md_dir, base + ".md")
    if os.path.exists(p):
        return p
    p = os.path.join(md_dir, base + ".txt")
    if os.path.exists(p):
        return p
    cand = [x for x in os.listdir(md_dir) if x.startswith(base[:12])]
    return os.path.join(md_dir, cand[0]) if cand else None


def main():
    argv = sys.argv[1:]
    def opt(name, default=None):
        if name in argv:
            return argv[argv.index(name) + 1]
        return default
    pdf_dir = opt("--pdf")
    md_dir = opt("--md")
    out_dir = opt("--out", os.path.join(os.getcwd(), "_align"))
    locate = "--locate" in argv
    if not pdf_dir or not md_dir:
        print(__doc__)
        return 1
    os.makedirs(out_dir, exist_ok=True)
    want = []
    if locate:
        i = argv.index("--locate")
        want = [argv[i + 1]] if len(argv) > i + 1 else []

    index = {}
    pdfs = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf"))
    for f in pdfs:
        base = os.path.splitext(f)[0]
        if want and not any(w in base for w in want):
            continue
        md_path = find_text_for(base, md_dir)
        if not md_path:
            print(f"[跳过] 无对应文本：{base}")
            continue
        a = align_one(os.path.join(pdf_dir, f), md_path)
        s = slug(base)
        with open(os.path.join(out_dir, s + ".json"), "w", encoding="utf-8") as fp:
            json.dump(a, fp, ensure_ascii=False, indent=1)
        index[s] = {k: a[k] for k in ("pdf", "md", "pages_n", "pdf_cjk", "md_cjk",
                                      "tail_drift", "weak_anchors")}
        flag = "" if a["tail_drift"] == 0 and not a["weak_anchors"] else "  ← 需查"
        print(f"{base[:40]:42s} 页={a['pages_n']:>3} PDF汉字={a['pdf_cjk']:>7} "
              f"文本汉字={a['md_cjk']:>7} 尾残差={a['tail_drift']:>5}{flag}")
        if locate and len(argv) > i + 2 and argv[i + 2].isdigit():
            pg = a["pages"].get(int(argv[i + 2]))
            if pg:
                print(f"    第 {argv[i+2]} 页开头：{pg['text_head']}")
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as fp:
        json.dump(index, fp, ensure_ascii=False, indent=1)
    print(f"\n共 {len(index)} 篇，索引写入 {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""核验读档里的引文能否回到底本。

两级判定（详见 references/quote-verification.md）：
  1. 整句命中：han(引文) in han(底本)
  2. 8 字滑窗（允许每两字间 0–2 杂字）命中率 ≥0.8 → 跨栏/跨行断裂，成立但要加注
  3. 其余 → 需查（伪造或改写，删掉或降为间接转述）

用法：
    # 单篇：与某一或两个底本比对
    python quote_check.py check _archive/03_xxx.md --src 底本/03_xxx.md [--src2 _pdftxt/03_xxx.txt]

    # 全档：扫描目录，自动为每份读档挑命中最多的底本
    python quote_check.py scan _archive --src 底本目录 [--src2 _pdftxt目录]

    # 只核某一节（默认核「七、原文直引」，也可 --sec "核心主张"）
    python quote_check.py check 读档.md --src 底本.md --sec 原文直引

退出码：全部通过 0，存在「需查」条目 2。
"""
import os
import re
import sys

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002ffff]")
# 弯引号开闭不同形，可以直接配对
CURLY = re.compile(r"[“]([^“”\n]{12,400})[”]")


def han(s):
    return "".join(CJK.findall(s))


def straight_quotes(block):
    """直引号开闭同形，不能用正则配对。

    写成 `...以"甲""乙"为...` 时，正则会把第二个引号当开引号、吞掉后文，
    抽出来的东西首字常是标点。按出现顺序奇数段即引文内部，是唯一可靠的分法。
    """
    parts = block.split('"')
    return parts[1::2]


def noisy(quote_han, src_han):
    """8 字滑窗，允许每两字间插 0–2 杂字；返回命中窗口占比。"""
    h = quote_han
    if len(h) < 8:
        return 0.0
    wins = [h[k:k + 8] for k in range(0, len(h) - 7)]
    hit = 0
    for w in wins:
        pat = ".{0,2}".join(re.escape(c) for c in w)
        if re.search(pat, src_han):
            hit += 1
    return hit / len(wins) if wins else 0.0


def load_sources(paths):
    out = []
    for p in paths:
        if p and os.path.exists(p):
            out.append((p, han(open(p, encoding="utf-8", errors="ignore").read())))
    return out


def section_of(text, name):
    """取 ## <name> 到下一个 ## 之间的内容；name 为空则全文。"""
    if not name:
        return text
    i = text.find(name)
    if i < 0:
        return ""
    j = text.find("\n## ", i + 1)
    return text[i:j if j > 0 else len(text)]


def quotes_of(text, sec=None):
    """抽引文。

    读档里长引文常被折成多行，逐行抽会得到一堆断头断尾的碎片，全部误判成「需查」；
    但整节一律并成一段又会让引号跨过项目符号，把术语表的几条串成一条。
    折中：普通续行直接拼接，列表项与标题处插入换行当屏障（QUOTE 不允许换行）。
    """
    body = section_of(text, sec)
    buf = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(("#", ">", "-", "*", "•", "|")) or re.match(r"^\d+[.、]", s):
            buf.append("\n")
        buf.append(s)
    block = "".join(buf)
    return CURLY.findall(block) + straight_quotes(block)


def judge(q, sources):
    h = han(q)
    if len(h) < 12:
        return "过短", None
    best = 0.0
    for _, s in sources:
        if h in s:
            return "精确", None
        best = max(best, noisy(h, s))
    return ("容噪" if best >= 0.8 else "需查"), best


def check_one(md_path, src_paths, sec, quiet=False):
    sources = load_sources(src_paths)
    if not sources:
        print(f"[跳过] {md_path}：无可用底本")
        return 0, 0, 0
    text = open(md_path, encoding="utf-8", errors="ignore").read()
    qs = quotes_of(text, sec)
    exact = soft = bad = 0
    rows = []
    for q in qs:
        verdict, ratio = judge(q, sources)
        if verdict == "精确":
            exact += 1
        elif verdict == "容噪":
            soft += 1
            rows.append(("容噪", ratio, q))
        elif verdict == "需查":
            bad += 1
            rows.append(("需查", ratio, q))
    if not quiet:
        name = os.path.basename(md_path)
        print(f"{name[:38]:40s} 引文 {len(qs):>3}  精确 {exact:>3}  容噪 {soft:>3}  需查 {bad:>3}")
    for v, r, q in rows:
        print(f"    [{v}{'' if r is None else f' {r:.2f}'}] {q[:60]}")
    return exact, soft, bad


def pick_source(md_path, src_dirs):
    """为读档挑命中最多的底本文件（按题名片段匹配）。

    题名里有引号、破折号、括号，直接用会匹配不上——一律先只留汉字数字再比。
    """
    base = os.path.basename(md_path)
    stem = re.sub(r"^\d+_", "", base)
    stem = os.path.splitext(stem)[0]
    stem_key = re.sub(r"[^\u4e00-\u9fff]", "", stem)
    cands = []
    for d in src_dirs:
        if not d or not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.lower().endswith((".md", ".txt")):
                cands.append(os.path.join(d, f))
    scored = []
    for c in cands:
        cb = re.sub(r"[^\u4e00-\u9fff]", "", os.path.basename(c))
        # 最长公共子串长度当相似度，避免题名里多一个「的」就压过另一个
        best, cur = 0, 0
        for ch in stem_key:
            if ch in cb:
                cur += 1
                best = max(best, cur) if cur > 4 else best
            else:
                cur = 0
        common = sum(min(stem_key.count(ch), cb.count(ch)) for ch in set(stem_key))
        scored.append((best + common / max(len(stem_key), 1), c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:2]]


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        return 1
    mode = argv[0]
    target = argv[1]

    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None

    sec = opt("--sec") or "原文直引"
    src = opt("--src")
    src2 = opt("--src2")
    if not src:
        print("需要 --src（底本文本或目录）")
        return 1

    totals = [0, 0, 0]
    if mode == "check":
        totals = list(check_one(target, [src, src2], sec))
    elif mode == "scan":
        files = sorted(
            os.path.join(target, f) for f in os.listdir(target)
            if f.endswith(".md") and not f.startswith("_")
        )
        for i, f in enumerate(files, 1):
            print(f"--- {i}/{len(files)} ---")
            dirs = [src, src2]
            if os.path.isdir(src):
                paths = pick_source(f, dirs)
            else:
                paths = [src, src2]
            e, s, b = check_one(f, paths, sec)
            totals[0] += e
            totals[1] += s
            totals[2] += b
    else:
        print(__doc__)
        return 1

    e, s, b = totals
    print(f"\n合计：精确 {e}  容噪 {s}  需查 {b}")
    if b:
        print("需查条目必须逐条处理：删掉，或改写为间接转述（“作者大意是……”）。")
        return 2
    if s:
        print("容噪条目成立，但应在读档中加一句说明该处底本为跨栏/跨行断裂。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

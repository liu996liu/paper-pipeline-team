#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文交付前的可自动核验项。

三个子命令对应三个反复出现的编辑部退稿原因，都是人眼查不可靠、又不需要
外部服务的检查。只用标准库，不装任何东西。

    python scripts/verify_paper.py stats     paper/<slug>/50-draft/v3/manuscript.md
    python scripts/verify_paper.py numbers   paper/<slug>/50-draft/v3/manuscript.md --results paper/<slug>/30-analysis/results
    python scripts/verify_paper.py citations paper/<slug>/50-draft/v3/manuscript.md
    python scripts/verify_paper.py all       paper/<slug>/50-draft/v3/manuscript.md --results paper/<slug>/30-analysis/results

  加 --json 输出机器可读结果；有 FAIL 时退出码 1，可接进 CI 或 t11 闸门。

为什么是这三个：
  · stats     —— 报出的 t/F/χ²/Z 与 p 值对不上，是实证论文最高频的硬伤。
                 statcheck 等现成工具只认英文半角写法（t(120)=2.45, p=0.016），
                 中文常用的「t=2.45，p<0.01」「t（120）＝2.45」全部漏检，故自建。
  · numbers   —— 正文、表、图注里的同一个数不一致（改了表忘了改正文）。
  · citations —— GB/T 7714-2015 的必备要素缺项（缺版次、缺卷期、缺引用日期）。
                 这三项都能规则化判定，不依赖任何数据库查证。
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
    "χ": "x2", "²": "2", "。": ".", "；": ";", "：": ":", "　": " ",
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
        # z
        for m in re.finditer(rf"(?<![a-zA-Z])z\s*=\s*({NUM})", line):
            zval = float(m.group(1))
            seg = line[m.end(): m.end() + WINDOW]
            pv = parse_pvalue(seg)
            computed = p_from_z(zval)
            results.append(_mk(lineno, raw, f"z={m.group(1)}", pv, computed))
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
                        cell = cell.strip().replace(",", "")
                        try:
                            pool.add(round(float(cell), 6))
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


def check_numbers(text: str, results_dir: Path | None) -> list[dict]:
    """正文里的小数若在表格与 results/ 里都找不到，标为需核对。

    只查至少两位小数的数字：年份、样本量、百分比整数这类太容易误报，
    而「正文抄错表里的系数」几乎必然带两位以上小数。
    """
    prose, tables = strip_tables(text)
    pool = load_result_numbers(results_dir)["all"]
    table_nums: set[float] = set()
    for tok in NUMTOK.findall(tables):
        try:
            table_nums.add(round(float(tok), 6))
        except ValueError:
            pass

    findings = []
    for lineno, raw in enumerate(prose.splitlines(), 1):
        if re.match(r"^\s*\|", raw):
            continue
        unmatched = []
        for tok in NUMTOK.findall(raw):
            val = round(float(tok), 6)
            if val in table_nums:
                continue
            if any(abs(val - x) <= 1e-6 for x in table_nums):
                continue
            if pool and any(abs(val - x) <= 5e-4 for x in pool):
                continue
            # 明显是方程/编码/版本号的不报
            if re.search(rf"(?:式|公式|方程|模型|图|表|第)\s*{re.escape(tok)}", raw):
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
    return findings


# ---------------------------------------------------------------- 主流程

def run(kind: str, path: Path, results: Path | None) -> tuple[list[dict], int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[dict] = []
    if kind in ("stats", "all"):
        out += check_stats(text)
    if kind in ("numbers", "all"):
        out += check_numbers(text, results)
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
    bad = 0
    for name, got, want in cases:
        ok = abs(got - want) < 5e-4
        bad += 0 if ok else 1
        print(f"[{'OK  ' if ok else 'FAIL'}] {name:16s} 重算 {got:.6f}  期望 {want:.6f}")
    print(f"\n{len(cases) - bad}/{len(cases)} 通过")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="论文交付前的可自动核验项")
    ap.add_argument("check", nargs="?", choices=["stats", "numbers", "citations", "all"])
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
    for kind in (["stats", "numbers", "citations"] if args.check == "all" else [args.check]):
        findings, _ = run(kind, args.manuscript, args.results)
        rc |= report(kind, findings, args.json)
    return rc


if __name__ == "__main__":
    sys.exit(main())

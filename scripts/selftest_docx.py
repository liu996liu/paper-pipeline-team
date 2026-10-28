#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docx_build_submission.py 的冒烟测试。

为什么要单独测：这个脚本在 CI 里跑不了「真实稿件」（稿件是私有资产不入库），
但它一旦坏了，交稿环节就整个断掉，而且坏的方式往往很安静——
输出的 .docx 能打开、却不含三线表或题名页。所以用一份最小合成稿件
把它跑一遍，并校验产出的字节数与 OOXML 内部结构。

用法：
  python scripts/selftest_docx.py
退出码 0 = 通过。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "docx_build_submission.py"


def _use_utf8_stdio() -> None:
    """Windows 控制台默认 GBK，打印子进程的 UTF-8 输出会抛 UnicodeEncodeError。

    这会让一个本该「通过」的冒烟测试以退出码 1 结束，CI 上看起来像脚本坏了，
    实际只是编码问题。所以在任何打印之前把 stdout/stderr 切成 UTF-8。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # 非 TextIOWrapper（被重定向/嵌入）时跳过
            pass

SAMPLE = """# 引言

数字化转型显著提升了企业绿色创新水平（李某某，2023）。表 1 报告基准回归结果。

| 变量 | (1) | (2) |
|---|---|---|
| DID | 0.152*** | 0.143*** |
|      | (0.041) | (0.039) |
| N    | 3120 | 3120 |

注：括号内为聚类稳健标准误，*** p<0.01。

## 稳健性检验

替换被解释变量后结论依然成立。
"""


def main() -> int:
    _use_utf8_stdio()
    tmp = Path(tempfile.mkdtemp(prefix="docx-selftest-"))
    md = tmp / "manuscript.md"
    md.write_text(SAMPLE, encoding="utf-8")
    out = tmp / "submission.docx"

    r = subprocess.run(
        [sys.executable, str(BUILDER), str(md), "--out", str(out),
         "--title", "数字化转型与企业绿色创新",
         "--author", "张三", "--affil", "XX大学商学院",
         "--abstract", "本文考察数字化转型对企业绿色创新的影响。",
         "--keywords", "数字化转型;绿色创新;中介效应",
         "--clc", "F272", "--doccode", "A"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        print("[FAIL] 生成脚本退出码非 0", r.returncode, file=sys.stderr)
        return 1

    if not out.exists():
        print("[FAIL] 未生成 docx", file=sys.stderr)
        return 1

    size = out.stat().st_size
    if size < 10_000:
        print(f"[FAIL] docx 只有 {size} 字节，疑似空文档", file=sys.stderr)
        return 1

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        for part in ("word/document.xml", "[Content_Types].xml"):
            if part not in names:
                print(f"[FAIL] docx 缺少 {part}", file=sys.stderr)
                return 1
        doc = z.read("word/document.xml").decode("utf-8", "replace")

    # 三线表意味着至少有一个真表格
    if "<w:tbl>" not in doc:
        print("[FAIL] 文档里没有表格节点，markdown 表格未转成真表格", file=sys.stderr)
        return 1
    # 题名页意味着题名进了文档
    if "数字化转型与企业绿色创新" not in doc:
        print("[FAIL] 题名未出现在文档中", file=sys.stderr)
        return 1
    # 中图分类号
    if "F272" not in doc:
        print("[FAIL] 中图分类号未出现在文档中", file=sys.stderr)
        return 1

    print(f"[OK  ] docx 冒烟测试通过：{size} 字节，含表格与题名页")
    return 0


if __name__ == "__main__":
    sys.exit(main())

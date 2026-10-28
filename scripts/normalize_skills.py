#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正规化 skills/ 下全部 SKILL.md 的 YAML frontmatter。

修三类可机读性问题（不改变任何技能正文）：
  1. description 中未加引号的 ": " 导致 YAML 解析失败 → 整体加双引号
  2. description 超过 1024 字符（部分 harness 会截断）→ 压缩到 1024 以内
  3. name 与目录名不一致 → 统一成目录名

用法：
  python scripts/normalize_skills.py --check   # 只报告，不写
  python scripts/normalize_skills.py           # 就地修复
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("需要 PyYAML：pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
DESC_LIMIT = 1024


def split_frontmatter(text: str):
    """返回 (frontmatter_str, body_str)；无 frontmatter 返回 (None, text)。"""
    if not text.startswith("---"):
        return None, text
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def iter_skills():
    for dirpath, _dirnames, filenames in os.walk(SKILLS):
        if "SKILL.md" in filenames:
            yield os.path.join(dirpath, "SKILL.md")


def yaml_quote(value: str) -> str:
    """把字符串写成 YAML 双引号标量（JSON 风格的双引号是合法 YAML）。"""
    return json.dumps(value, ensure_ascii=False)


def shrink_desc(desc: str, limit: int = DESC_LIMIT) -> str:
    """把过长的 description 压到 limit 以内，尽量断在句子边界。"""
    if len(desc) <= limit:
        return desc
    # 优先在中文句末标点处截断
    cut = desc[: limit - 1]
    for sep in ("。", "；", ". ", "; "):
        idx = cut.rfind(sep)
        if idx > limit * 0.55:
            return cut[: idx + len(sep)].rstrip()
    return cut.rstrip() + "…"


BLOCK_MARKS = (">-", ">", "|-", "|", ">+", "|+")


def _field_span(fm: str, field: str):
    """定位 field 在 frontmatter 中的 (起始行号, 结束行号) —— 半开区间 [start, end)。

    结束行的判定：跳过紧随其后的缩进续行（YAML block scalar）与空行。
    """
    lines = fm.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{field}:[ \t]", line) or line.rstrip() == f"{field}:":
            start = i
            break
    if start is None:
        return None
    raw = lines[start].split(":", 1)[1].strip()
    end = start + 1
    if raw in BLOCK_MARKS or raw == "":
        # block scalar / 换行开始的标量：吃掉所有缩进续行
        while end < len(lines):
            nxt = lines[end]
            if nxt.strip() == "":
                # 空行：只有当后面还有缩进行时才属于本字段
                j = end
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
                    end = j
                    continue
                break
            if nxt.startswith(" ") or nxt.startswith("\t"):
                end += 1
            else:
                break
    return start, end, raw


def extract_field(fm: str, field: str):
    """从原始 frontmatter 文本里取出某字段的值（容忍引号、多行、block scalar）。"""
    span = _field_span(fm, field)
    if span is None:
        return None
    start, end, raw = span
    lines = fm.split("\n")
    if raw in BLOCK_MARKS:
        body = [ln.strip() for ln in lines[start + 1:end]]
        folded = " " if raw.startswith(">") else "\n"
        return folded.join(x for x in body if x).strip()
    if raw == "":
        body = [ln.strip() for ln in lines[start + 1:end]]
        return " ".join(x for x in body if x).strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) > 1:
        try:
            return json.loads(raw)
        except Exception:
            return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) > 1:
        return raw[1:-1].replace("''", "'")
    return raw


def replace_field(fm: str, field: str, value: str) -> str:
    """把 frontmatter 中某字段（含其 block scalar 续行）替换为单行 JSON 字符串。"""
    span = _field_span(fm, field)
    new_line = f"{field}: {yaml_quote(value)}"
    lines = fm.split("\n")
    if span is None:
        return new_line + "\n" + fm
    start, end, _raw = span
    return "\n".join(lines[:start] + [new_line] + lines[end:])


def process(path: str, write: bool):
    dir_name = os.path.basename(os.path.dirname(path))
    text = open(path, encoding="utf-8").read()
    fm, body = split_frontmatter(text)
    if fm is None:
        return ("no-frontmatter", dir_name, [])

    notes = []

    # ---- 1. 先拿到 description / name 的原始值（即使 YAML 已坏）----
    desc = extract_field(fm, "description")
    name = extract_field(fm, "name")

    if desc is None:
        return ("no-description", dir_name, [])

    orig_len = len(desc)

    # ---- 2. 过长的 description 先压缩 ----
    if len(desc) > DESC_LIMIT:
        desc = shrink_desc(desc)
        notes.append(f"description {orig_len} -> {len(desc)}")

    # ---- 3. 重写 name / description 两行（引号化，修 YAML）----
    new_fm = replace_field(fm, "name", dir_name)
    new_fm = replace_field(new_fm, "description", desc)
    if name != dir_name:
        notes.append(f"name {name!r} -> {dir_name!r}")

    new_text = "---\n" + new_fm.rstrip("\n") + "\n---\n" + body

    # ---- 4. 校验新 frontmatter 能解析 ----
    try:
        parsed = yaml.safe_load(new_fm)
    except Exception as exc:  # noqa: BLE001
        return ("still-broken", dir_name, [str(exc)[:100]])
    if not isinstance(parsed, dict):
        return ("not-a-dict", dir_name, [])
    if parsed.get("name") != dir_name:
        return ("name-write-failed", dir_name, [])

    changed = new_fm != fm
    if changed and write:
        open(path, "w", encoding="utf-8", newline="\n").write(new_text)
    return ("ok", dir_name, notes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报告不写入")
    args = ap.parse_args()

    problems = 0
    for path in sorted(iter_skills()):
        status, dir_name, notes = process(path, write=not args.check)
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        if status != "ok":
            problems += 1
            print(f"[FAIL] {status:16s} {rel}")
            for n in notes:
                print(f"         {n}")
        elif notes:
            print(f"[FIX ] {rel}")
            for n in notes:
                print(f"         {n}")

    print()
    print(f"检查完成：{'发现问题 %d 个' % problems if problems else '全部通过'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

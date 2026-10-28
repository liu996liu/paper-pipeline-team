#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验技能库与团队引用的一致性。

四处必须指向同一批技能：
  1. skills/**/SKILL.md 的真实目录名（唯一事实来源）
  2. skills/**/SKILL.md 的 YAML frontmatter 能被解析，且 name 与目录名一致
  3. team.json 每个成员 skills 数组里的技能名
  4. agents/*.md 技能表里的 `skills/...` 路径

为什么第 2 条要单独查：frontmatter 里 description 若含未加引号的 ": "，
YAML 直接解析失败，客户端会把整个技能当无效条目跳过——技能文件在、但装不上。
历史上有 2 个技能就是这样静默失效的（de-aigc-skills、01-phack-taxonomy）。

用法：
  python scripts/check_skills.py            # 只校验，有错退出码 1
  python scripts/check_skills.py --fix      # 把 team.json 里能唯一映射的旧名改成目录名
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DESC_HARD_LIMIT = 1024  # Anthropic Agent Skills 规范对 description 的长度上限


def index_skills():
    """返回 {技能名: 相对路径}。技能名 = 目录名。"""
    out = {}
    for p in glob.glob(os.path.join(ROOT, "skills", "**", "SKILL.md"), recursive=True):
        name = os.path.basename(os.path.dirname(p))
        rel = os.path.relpath(os.path.dirname(p), ROOT).replace("\\", "/")
        out[name] = rel
    return out


def parse_frontmatter(path):
    """返回 (dict, 错误信息)。优先用 PyYAML；没有就退化成正则提取，仍能报警。"""
    text = open(path, encoding="utf-8", errors="replace").read()
    if not text.startswith("---"):
        return None, "缺少 YAML frontmatter（文件未以 --- 开头）"
    end = text.find("\n---", 3)
    if end < 0:
        return None, "frontmatter 未闭合（找不到结束的 ---）"
    block = text[3:end]
    try:
        import yaml
    except ImportError:
        return _fallback_parse(block), None
    try:
        data = yaml.safe_load(block)
    except Exception as exc:  # noqa: BLE001 - 要把原始报错给用户看
        return None, f"YAML 解析失败：{str(exc).splitlines()[0]}"
    if not isinstance(data, dict):
        return None, "frontmatter 不是映射（key: value 形式）"
    return data, None


def _fallback_parse(block):
    """没有 PyYAML 时用正则凑出 name / description，只够做基本检查。"""
    data = {}
    for key in ("name", "description"):
        m = re.search(rf"^{key}:\s*(.+)$", block, re.M)
        if m:
            v = m.group(1).strip()
            if v[:1] in "\"'":
                v = v[1:]
                if v.endswith(v[0] if v else ""):
                    v = v[:-1]
            data[key] = v
    return data


def check_frontmatter(skills):
    """检查所有 SKILL.md 的 frontmatter。返回问题数。"""
    problems = 0
    long_desc = []
    name_mismatch = []
    broken = []
    for name, rel in sorted(skills.items(), key=lambda kv: kv[1]):
        path = os.path.join(ROOT, rel.replace("/", os.sep), "SKILL.md")
        data, err = parse_frontmatter(path)
        if err:
            problems += 1
            broken.append(f"[FAIL] {rel}/SKILL.md: {err}")
            continue
        fm_name = (data or {}).get("name")
        if fm_name != name:
            problems += 1
            name_mismatch.append(f"[FAIL] {rel}/SKILL.md: name={fm_name!r} 与目录名 {name!r} 不一致")
        desc = (data or {}).get("description") or ""
        if len(desc) > DESC_HARD_LIMIT:
            long_desc.append((rel, len(desc), DESC_HARD_LIMIT))

    for line in broken + name_mismatch:
        print(line)
    if long_desc:
        print(f"[WARN] {len(long_desc)} 个 description 超过 {DESC_HARD_LIMIT} 字符"
              f"（不会被 YAML 拒绝，但部分客户端会截断触发词）：")
        for rel, n, _ in sorted(long_desc, key=lambda x: -x[1]):
            print(f"         {rel}  {n} 字符")
    return problems


def strip_prefix(name: str) -> str:
    """去掉编号前缀与 phack- 家族前缀，用于宽松匹配。"""
    s = re.sub(r"^\d+[-_]", "", name)
    s = re.sub(r"^phack[-_]", "", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()

    skills = index_skills()
    by_stripped = {}
    for name in skills:
        by_stripped.setdefault(strip_prefix(name), []).append(name)

    problems = 0

    # ---- 0. frontmatter 可解析 / name 与目录一致 / 描述长度 ----
    problems += check_frontmatter(skills)

    # ---- 1. team.json ----
    team_path = os.path.join(ROOT, "team.json")
    team = json.load(open(team_path, encoding="utf-8"))
    changed = False

    for m in team["members"]:
        fixed = []
        for s in m.get("skills", []):
            if s in skills:
                fixed.append(s)
                continue
            cands = by_stripped.get(strip_prefix(s), [])
            if len(cands) == 1:
                fixed.append(cands[0])
                changed = True
                print(f"[FIX ] team.json {m['name']}: {s!r} -> {cands[0]!r}")
            else:
                problems += 1
                print(f"[FAIL] team.json {m['name']}: 未定义的技能 {s!r}"
                      f"（候补: {cands or '无'}）")
                fixed.append(s)
        m["skills"] = fixed

    # ---- 2. agents/*.md 里的路径 ----
    for f in sorted(glob.glob(os.path.join(ROOT, "agents", "*.md"))):
        text = open(f, encoding="utf-8").read()
        for path in re.findall(r"`(skills/[^`]+)`", text):
            target = os.path.join(ROOT, path.replace("/", os.sep))
            if not os.path.isdir(target):
                problems += 1
                print(f"[FAIL] {os.path.relpath(f, ROOT)}: 路径不存在 {path}")

    # ---- 3. 技能是否被至少一个成员引用 ----
    used = {s for m in team["members"] for s in m.get("skills", [])}
    orphans = sorted(set(skills) - used)
    if orphans:
        print(f"[WARN] {len(orphans)} 个技能未被任何成员引用（不一定是错误）：")
        for o in orphans:
            print(f"         {o}")

    if args.fix and changed:
        json.dump(team, open(team_path, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=2)
        open(team_path, "a", encoding="utf-8").write("\n")
        print("\nteam.json 已写回。")

    print()
    print(f"技能总数 {len(skills)} ｜ 被引用 {len(used)} ｜ 问题 {problems} 个")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

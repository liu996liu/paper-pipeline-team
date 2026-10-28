#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 team.json 的结构完整性与内部一致性。

CI 用。检查的是「配置本身能不能跑起来」，不是技能内容：
  - 顶层必需字段在不在
  - 每个成员的 owner 是否都有对应 agents/<name>.md
  - 每个任务的 owner 是否是已定义成员
  - dependsOn / conditionalDependsOn 是否指向已定义任务
  - dependsOn 是否成环
  - 每个成员被引用的技能名是否都在 skills/ 下真实存在
  - 审查类任务是否都带 acceptance（没有验收标准的审查等于没审）
  - modelPolicy.roles 是否覆盖全部成员

用法：
  python scripts/check_team.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_TOP = ("name", "description", "members", "tasks", "flowRules", "modelPolicy")
REQUIRED_TASK_FIELDS = ("id", "name", "owner")
REVIEW_KINDS = ("requirements", "review", "verification")
QUALITY_KINDS = ("requirements", "implementation", "verification", "review", "repair", "integration")


def skill_names():
    out = set()
    for p in glob.glob(os.path.join(ROOT, "skills", "**", "SKILL.md"), recursive=True):
        out.add(os.path.basename(os.path.dirname(p)))
    return out


def skill_family_of():
    """技能名 → 它实际所在的技能族目录名。"""
    out = {}
    for p in glob.glob(os.path.join(ROOT, "skills", "**", "SKILL.md"), recursive=True):
        # skills/<族>/.../<技能>/SKILL.md
        rel = os.path.relpath(p, os.path.join(ROOT, "skills"))
        parts = rel.split(os.sep)
        out[os.path.basename(os.path.dirname(p))] = parts[0]
    return out


def main():
    errors = []
    warns = []

    team = json.load(open(os.path.join(ROOT, "team.json"), encoding="utf-8"))

    # ---- 顶层字段 ----
    for key in REQUIRED_TOP:
        if key not in team:
            errors.append(f"team.json 缺少顶层字段 {key!r}")

    members = team.get("members", [])
    tasks = team.get("tasks", [])
    member_names = {m["name"] for m in members}
    task_ids = {t["id"] for t in tasks}

    # ---- 成员 ----
    agent_files = {
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(ROOT, "agents", "*.md"))
    }
    for name in sorted(member_names - agent_files):
        errors.append(f"成员 {name!r} 没有对应的 agents/{name}.md")
    for name in sorted(agent_files - member_names):
        warns.append(f"agents/{name}.md 存在但不在 team.json 的 members 里")

    skills = skill_names()
    skill_family = skill_family_of()
    for m in members:
        for s in m.get("skills", []):
            if s not in skills:
                errors.append(f"成员 {m['name']!r} 引用了不存在的技能 {s!r}")

        # skillFamilies 是给人看的「我挂了几族」，skills 是真正加载的清单。
        # 两者不一致时，文档会替成员宣称它其实没有的能力（或漏报已有能力），
        # 而这种偏差不会让任何东西报错——只会让人按错误的印象派活。
        declared = set(m.get("skillFamilies", []))
        actual = {skill_family[s] for s in m.get("skills", []) if s in skill_family}
        if declared != actual:
            missing = sorted(actual - declared)
            extra = sorted(declared - actual)
            msg = f"成员 {m['name']!r} 的 skillFamilies 与实际挂载的技能族不符"
            if missing:
                msg += f"；漏声明 {missing}"
            if extra:
                msg += f"；多声明 {extra}"
            errors.append(msg)

    # ---- 任务 ----
    for t in tasks:
        for f in REQUIRED_TASK_FIELDS:
            if f not in t or not str(t.get(f, "")).strip():
                errors.append(f"任务 {t.get('id', '?')!r} 缺少必需字段 {f!r}")
        owner = t.get("owner")
        if owner and owner not in member_names:
            errors.append(f"任务 {t['id']!r} 的 owner={owner!r} 不是已定义成员")
        for dep in t.get("dependsOn", []) + t.get("conditionalDependsOn", []):
            if dep not in task_ids:
                errors.append(f"任务 {t['id']!r} 依赖了不存在的任务 {dep!r}")

        kind = t.get("kind", "work")
        if kind in QUALITY_KINDS and not t.get("acceptance"):
            errors.append(f"质量类任务 {t['id']!r}（kind={kind}）缺少 acceptance 验收标准")
        if kind in ("implementation", "repair"):
            if not t.get("objective"):
                errors.append(f"{kind} 任务 {t['id']!r} 缺少 objective")
            if not t.get("verify"):
                errors.append(f"{kind} 任务 {t['id']!r} 缺少 verify 验证命令")

        # ---- 条件剪枝（本仓库扩展字段，平台不解释，故必须自检） ----
        # dependsOnPolicy="all" 时，degrade 列出的是「上游被跳过后的替代依赖集」。
        # 每条替代集必须是原 dependsOn 的子集，否则剪枝会引入新的依赖边。
        degrade = t.get("degrade")
        if degrade is not None:
            branch_list = degrade if isinstance(degrade, list) else [degrade]
            if not isinstance(degrade, list):
                errors.append(
                    f"任务 {t['id']!r} 的 degrade 是对象；"
                    "有多个分支时必须写成数组，否则分支会被逐一覆盖"
                )
            base = set(t.get("dependsOn", []))
            for i, br in enumerate(branch_list, 1):
                if not isinstance(br, dict):
                    errors.append(f"任务 {t['id']!r} 的 degrade 第 {i} 项不是对象")
                    continue
                if not br.get("when"):
                    errors.append(f"任务 {t['id']!r} 的 degrade 第 {i} 项缺少 when 说明")
                sub = set(br.get("dependsOn", []))
                extra = sub - base
                if extra:
                    errors.append(
                        f"任务 {t['id']!r} 的 degrade 第 {i} 项引入原 dependsOn 之外的依赖 "
                        f"{sorted(extra)}；剪枝只允许删除，不允许新增"
                    )
                if not sub:
                    errors.append(f"任务 {t['id']!r} 的 degrade 第 {i} 项 dependsOn 为空")
            if t.get("dependsOnPolicy") != "all":
                errors.append(
                    f"任务 {t['id']!r} 带 degrade 但 dependsOnPolicy 不是 'all'；"
                    "degrade 的语义只在 all 策略下成立"
                )

    # ---- 依赖成环 ----
    graph = {t["id"]: set(t.get("dependsOn", [])) for t in tasks}
    state = {}  # 0=未访问 1=访问中 2=完成

    def visit(node, path):
        st = state.get(node, 0)
        if st == 2:
            return
        if st == 1:
            errors.append("任务依赖成环：" + " -> ".join(path + [node]))
            return
        state[node] = 1
        for dep in graph.get(node, ()):
            visit(dep, path + [node])
        state[node] = 2

    for tid in graph:
        visit(tid, [])

    # ---- modelPolicy ----
    policy = team.get("modelPolicy", {})
    roles = policy.get("roles", {})
    tiers = policy.get("tiers", {})
    for name in sorted(member_names - set(roles)):
        errors.append(f"modelPolicy.roles 未覆盖成员 {name!r}")
    for name, r in roles.items():
        tier = r.get("tier")
        if tier not in tiers:
            errors.append(f"modelPolicy.roles[{name!r}].tier={tier!r} 不在 tiers 里")
    for tier, cfg in tiers.items():
        eff = cfg.get("reasoningEffort")
        if eff == "":
            errors.append(
                f"modelPolicy.tiers[{tier!r}].reasoningEffort 是空字符串；"
                "空字符串不是合法推理强度，应直接省略该字段"
            )

    # ---- 描述里的数字与配置对不上 ----
    # description 是团队卡片上要显示给人看的那句话，最容易过期：
    # 加了任务/删了成员之后没人记得回头改它。
    desc = team.get("description", "")
    import re as _re
    for m_ in _re.finditer(r"(\d+)\s*(个任务|名成员|个成员|个技能)", desc):
        claimed, unit = int(m_.group(1)), m_.group(2)
        actual_n = {"个任务": len(tasks), "名成员": len(members),
                    "个成员": len(members), "个技能": len(skills)}[unit]
        if claimed != actual_n:
            errors.append(
                f"team.json 的 description 声称「{claimed} {unit}」，"
                f"实际是 {actual_n}；卡片上显示的数字会误导使用者"
            )

    for w in warns:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")

    print()
    print(f"成员 {len(members)} ｜ 任务 {len(tasks)} ｜ 技能 {len(skills)} ｜ "
          f"错误 {len(errors)} ｜ 警告 {len(warns)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

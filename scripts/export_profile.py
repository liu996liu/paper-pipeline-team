#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 team.json 编译成 DeepSeek Harness 的 AgentTeams profile 片段。

为什么需要它
------------
`team.json` 是本仓库自有的清单格式（9 个成员、13 个任务、13 条 flowRules、
objective / acceptance / verify / degrade / retryPolicy …）。DeepSeek Harness
的 AgentTeams 插件只认识其中很小一部分，而且**校验是严格的**——源码里
`lib/profiles.js` 的 `assertAllowedKeys` 遇到未知键直接抛错（不是警告）：

    profile 允许：description / protocol / executionPrompt / fallback /
                  members / tasks / taskPlanning / reviewPolicy
    member  允许：name / role / provider / model / reasoning_effort /
                  executionPrompt / fallback / tool_policy
    task    允许：id / subject / description / assignee / dependencies

所以「原样导入 team.json」是跑不通的：`members` 在 team.json 里是对象数组，
`tasks` 里有 kind / objective / acceptance / verify / degrade 等全部未知键。
手工抄一遍又必然漂移（成员数、任务数、模型名三处最容易漏改）。

这个脚本做的是**单向编译**：team.json → 合法的 profile YAML。
它保留拓扑顺序、模型档位、角色一句话描述，并把 team.json 里那些平台不认识的
契约字段（objective / acceptance / verify / degrade / retryPolicy / flowRules）
压缩成一段人读的 protocol 文本 + 每个任务的 description 前缀，让 captain
在开设团队时仍能看到它们，而不是悄悄丢掉。

用法
----
    python scripts/export_profile.py                 # 打印 YAML 到 stdout
    python scripts/export_profile.py --out dsh-profile.yml
    python scripts/export_profile.py --check         # 与 --out 文件比对，CI 用
    python scripts/export_profile.py --name paper-pipeline-team
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAM = ROOT / "team.json"
DEFAULT_OUT = ROOT / "docs" / "dsh-profile.yml"

# 平台侧的硬限制（取自 dsh-agent-teams 插件源码，改版本时要同步）
MAX_PROFILE_TASKS = 32
MAX_PROFILE_MEMBERS = 8
PROTOCOL_LIMIT = 600  # 平台会把 protocol 截到 240 字符进提示词，这里留余量写完整版

# team.json 里 kind 与平台语义的对应，用于把契约写成人读文本
KIND_LABEL = {
    "requirements": "需求/开题",
    "work": "普通工作",
    "implementation": "实现/分析",
    "verification": "校验",
    "review": "评审门禁",
    "repair": "返修",
    "integration": "集成",
}


def load_team() -> dict:
    return json.loads(TEAM.read_text(encoding="utf-8"))


def protocol_text(team: dict) -> str:
    """把 flowRules / retryPolicy 压成 captain 能读的一段话。

    这些规则平台不认识，但它们是这套流程真正的价值所在——丢了就等于退化成
    一个普通的多角色对话。所以写进 protocol，让它随 profile 一起进入 captain
    的系统提示词（平台会截断到 240 字符进提示词，完整文本仍可从配置读取）。
    """
    lines = []
    desc = team.get("description", "").strip()
    if desc:
        lines.append(desc)
    rules = team.get("flowRules") or []
    if rules:
        lines.append("")
        lines.append("【流程硬规则】")
        for i, r in enumerate(rules, 1):
            text = r if isinstance(r, str) else r.get("rule") or r.get("text") or ""
            text = " ".join(str(text).split())
            if text:
                lines.append(f"{i}. {text}")
    rp = team.get("retryPolicy") or {}
    if rp:
        lines.append("")
        lines.append("【失败与代执行】")
        if rp.get("maxRounds") is not None:
            lines.append(f"- 同一评审环节最多返工 {rp['maxRounds']} 轮。")
        if rp.get("consecutiveFailuresBeforeReassign") is not None:
            lines.append(
                f"- 成员连续失败 {rp['consecutiveFailuresBeforeReassign']} 次，"
                "由 captain 改派同族次优成员。"
            )
        if rp.get("captainTakeoverLimit") is not None:
            lines.append(
                f"- captain 亲自代做同一任务最多 {rp['captainTakeoverLimit']} 次，"
                "再次失败即转人工裁决。"
            )
        if rp.get("deputyAnnotation"):
            lines.append(f"- 代执行标注：{rp['deputyAnnotation']}")
        if rp.get("escalation"):
            lines.append(f"- 升级：{rp['escalation']}")
    text = "\n".join(lines).strip()
    if len(text) > PROTOCOL_LIMIT:
        text = text[: PROTOCOL_LIMIT - 24].rstrip() + "\n…（完整规则见 team.json）"
    return text


def task_description(task: dict) -> str:
    """任务描述：把平台不认识的契约字段降维成文本，而不是丢掉。"""
    parts = []
    kind = task.get("kind")
    if kind:
        parts.append(f"【类型】{KIND_LABEL.get(kind, kind)}（{kind}）")
    obj = (task.get("objective") or "").strip()
    if obj:
        parts.append(f"【目标】{obj}")
    acceptance = task.get("acceptance") or []
    if acceptance:
        parts.append("【验收标准】")
        parts.extend(f"  {i}. {a}" for i, a in enumerate(acceptance, 1))
    deliverables = task.get("deliverables") or []
    if deliverables:
        parts.append("【交付物】" + "；".join(deliverables))
    in_scope = task.get("inScope") or []
    if in_scope:
        parts.append("【可改动范围】" + "；".join(in_scope))
    non_goals = task.get("nonGoals") or []
    if non_goals:
        parts.append("【不要做】" + "；".join(non_goals))
    verify = task.get("verify") or []
    if verify:
        parts.append("【校验命令】" + "；".join(verify))
    forbidden = task.get("forbidden") or []
    if forbidden:
        parts.append("【禁止】" + "；".join(forbidden))
    condition = task.get("condition")
    if condition:
        parts.append(f"【启用条件】{condition}")
    reviews = task.get("reviews")
    if reviews:
        parts.append(f"【被审任务】{reviews}")
    rnd = task.get("round")
    if rnd is not None:
        parts.append(f"【评审轮次】第 {rnd} 轮")
    mr = task.get("maxRounds")
    if mr is not None:
        parts.append(f"【最多返工】{mr} 轮")
    degrade = task.get("degrade")
    if degrade:
        cases = degrade if isinstance(degrade, list) else [degrade]
        parts.append("【依赖剪枝】按 t1 的路径判定，dependsOn 改为以下之一：")
        for case in cases:
            if not isinstance(case, dict):
                continue
            when = case.get("when", "其他情况")
            deps = case.get("dependsOn", [])
            parts.append(f"  · {when} → {deps}")
    policy = task.get("dependsOnPolicy")
    if policy:
        parts.append(f"【依赖策略】{policy}（全部上游完成才开工）")
    note = task.get("note")
    if note:
        parts.append(f"【备注】{note}")
    return "\n".join(parts)


def topo_order(tasks: list[dict]) -> list[dict]:
    """拓扑排序，保证 dependencies 里的 id 先出现。

    平台要求 seed 任务的依赖必须是已出现的任务 id，乱序会直接报
    「unknown dependency」。team.json 目前本来就有序，但不要依赖这个巧合。
    """
    by_id = {t["id"]: t for t in tasks}
    done: set[str] = set()
    out: list[dict] = []
    pending = [t["id"] for t in tasks]
    guard = 0
    while pending:
        guard += 1
        if guard > len(tasks) * len(tasks) + 10:
            raise SystemExit("依赖成环，无法拓扑排序：" + ", ".join(pending))
        progressed = False
        for tid in list(pending):
            deps = [d for d in (by_id[tid].get("dependsOn") or []) if d in by_id]
            if all(d in done for d in deps):
                out.append(by_id[tid])
                done.add(tid)
                pending.remove(tid)
                progressed = True
        if not progressed:
            raise SystemExit("依赖成环，无法拓扑排序：" + ", ".join(pending))
    return out


def yaml_scalar(value: str) -> str:
    """把任意文本安全地写成 YAML 标量。

    统一用双引号 + JSON 转义：JSON 字符串是 YAML 双引号标量的子集，
    中文、换行、冒号、引号都能原样往返，不用赌缩进和 `|` 块的缩进宽度。
    """
    return json.dumps(value, ensure_ascii=False)


def build_profile(team: dict, name: str) -> tuple[str, list[str]]:
    """返回 (YAML 文本, 警告列表)。警告是给人看的，不阻断生成。"""
    warnings: list[str] = []
    members = team.get("members") or []
    tasks = topo_order(team.get("tasks") or [])
    if not members:
        raise SystemExit("team.json 没有 members")
    # 平台默认 maxMembers=8，可在插件配置里调大；本仓库 9 人，所以只警告不阻断
    if len(members) > MAX_PROFILE_MEMBERS:
        warnings.append(
            f"成员 {len(members)} 人，超过插件默认上限 maxMembers={MAX_PROFILE_MEMBERS}。"
            f"安装时必须在该 profile 的插件配置里加 maxMembers: {len(members)}，"
            "否则 agent_teams_create(--profile) 会直接报错。"
        )
    if len(tasks) > MAX_PROFILE_TASKS:
        warnings.append(f"任务 {len(tasks)} 个，超过平台上限 {MAX_PROFILE_TASKS}，需要拆分团队。")

    lines: list[str] = []
    lines.append("# 由 scripts/export_profile.py 从 team.json 生成，请勿手改。")
    lines.append("# 重新生成：python scripts/export_profile.py --out docs/dsh-profile.yml")
    lines.append("# 装法：把下面 profiles: 的内容合并进 ~/.dsh/profiles/<你的 profile>/cordis.patch.yml")
    lines.append(f"# 调用：/agent-teams --profile {name} <你的研究目标>")
    lines.append("")
    lines.append("# 安装前必读：本团队 9 人，超出 AgentTeams 插件默认 maxMembers=8。")
    lines.append("# 在同一个 cordis.patch.yml 的 agent-teams 条目里加上 maxMembers: 9，")
    lines.append("# 否则 --profile 创建团队时报「has 9 members but maxMembers is 8」。")
    lines.append("# 示例：")
    lines.append("#   - id: agent-teams")
    lines.append('#     name: "@nanmicoder/dsh-agent-teams"')
    lines.append("#     config:")
    lines.append("#       maxMembers: 9")
    lines.append("")
    lines.append("profiles:")
    lines.append(f"  {name}:")
    lines.append(f"    description: {yaml_scalar(team.get('description', name))}")
    lines.append("    protocol: " + yaml_scalar(protocol_text(team)))
    lines.append("    taskPlanning: seed")
    lines.append("    members:")
    for m in members:
        lines.append(f"      - name: {yaml_scalar(m['name'])}")
        if m.get("role"):
            lines.append(f"        role: {yaml_scalar(m['role'])}")
        if m.get("model"):
            lines.append(f"        model: {yaml_scalar(m['model'])}")
        effort = m.get("reasoningEffort")
        # 平台对空字符串不做清洗，空串会被当成一个非法强度传下去，直接省略
        if effort:
            lines.append(f"        reasoning_effort: {yaml_scalar(effort)}")
    lines.append("    tasks:")
    for t in tasks:
        lines.append(f"      - id: {yaml_scalar(t['id'])}")
        lines.append(f"        subject: {yaml_scalar(t['name'])}")
        lines.append(f"        assignee: {yaml_scalar(t['owner'])}")
        desc = task_description(t)
        if desc:
            lines.append(f"        description: {yaml_scalar(desc)}")
        deps = t.get("dependsOn") or []
        if deps:
            lines.append("        dependencies:")
            for d in deps:
                lines.append(f"          - {yaml_scalar(d)}")
    lines.append("")
    return "\n".join(lines), warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default=None, help="profile 名，默认取 team.json 的 name 并做 sanitize")
    ap.add_argument("--out", default=None, help="写文件；省略则打印到 stdout")
    ap.add_argument("--check", action="store_true", help="只比对，不一致退出码 1（CI 用）")
    args = ap.parse_args()

    team = load_team()
    name = args.name or "".join(
        c if (c.isalnum() or c in "-_") else "-" for c in (team.get("name") or "paper-team")
    ).strip("-").lower()
    text, warnings = build_profile(team, name)
    for w in warnings:
        print(f"[警告] {w}", file=sys.stderr)

    out = Path(args.out) if args.out else None
    if args.check:
        target = out or DEFAULT_OUT
        if not target.exists():
            print(f"[不一致] {target} 不存在，请先跑 python scripts/export_profile.py --out {target}")
            return 1
        current = target.read_text(encoding="utf-8")
        if current != text:
            print(f"[不一致] {target} 与 team.json 不同步，请重新生成")
            return 1
        print(f"[一致] {target} 与 team.json 同步")
        return 0

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        n_members = len(team.get("members") or [])
        n_tasks = len(team.get("tasks") or [])
        print(f"[已生成] {out}（{n_members} 成员 / {n_tasks} 任务）")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

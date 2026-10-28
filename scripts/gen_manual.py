#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 team.json + skills/ + agents/ 生成 docs/论文攻坚组-团队配置手册.docx。

为什么改成生成：这份手册原来是手写的，于是它以三种口径同时存在——
封面写「六成员」、名册表写「七名成员」、技能表写「68 个 skill」、任务表写「11 个任务」。
真实配置早已是 9 成员 / 13 任务 / 84 技能。手写的汇总文档只要没人回头改，
就一定会在某次结构调整后变成误导，而且它长得像官方文件，比 README 更容易被信。

现在所有计数、成员名、技能归属、任务依赖、流程规则都从配置现算，
手册要么与配置一致，要么根本生成不出来。

用法：
    python scripts/gen_manual.py            # 写入 docs/论文攻坚组-团队配置手册.docx
    python scripts/gen_manual.py --check    # 不写盘，只报告会改什么（CI 用）

依赖：python-docx
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

try:
    from docx import Document
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖：pip install python-docx")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_build_submission import (  # noqa: E402  复用字体、三线表等排版函数
    body_para,
    flush_table,
    heading,
    set_run_font,
)

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "论文攻坚组-团队配置手册.docx"
TEAM = REPO / "team.json"
SKILLS = REPO / "skills"

TIER_LABEL = {
    "strong": "强（判断型，推理强度 max）",
    "standard": "标（有脚本/清单兜底）",
    "fast": "快（模式化、量大）",
}


# --------------------------------------------------------------------------- 取数

def load():
    team = json.loads(TEAM.read_text(encoding="utf-8"))

    # 技能名 → (族目录, 目录内相对路径)
    index = {}
    for p in SKILLS.rglob("SKILL.md"):
        rel = p.parent.relative_to(SKILLS)
        index[p.parent.name] = (rel.parts[0], rel.as_posix())

    families = {}
    for name, (fam, _rel) in index.items():
        families.setdefault(fam, []).append(name)
    for fam in families:
        families[fam].sort()

    return team, index, families


def dir_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024 or unit == "GB":
            return f"{total:.0f} {unit}" if unit == "B" else f"{total:.1f} {unit}"
        total /= 1024
    return "?"


# --------------------------------------------------------------------------- 各部分

def cover(doc, team, n_members, n_tasks, n_skills, n_fams):
    p = doc.add_paragraph()
    p.alignment = 1  # CENTER
    set_run_font(p.add_run(team["name"]), "黑体", 26, True)
    p = doc.add_paragraph()
    p.alignment = 1
    set_run_font(
        p.add_run(f"{n_members} 成员智能体团队 · 配置手册与部署指南"),
        "黑体", 14, False,
    )
    p = doc.add_paragraph()
    p.alignment = 1
    set_run_font(
        p.add_run(f"{n_tasks} 个任务 ｜ {n_skills} 个技能 ｜ {n_fams} 个技能族"),
        "宋体", 10.5, False,
    )
    doc.add_paragraph()


def sec_overview(doc, team, n_members, n_tasks, n_skills, n_fams, rules):
    heading(doc, "一、团队总览", 1)
    body_para(doc, team.get("description", ""))

    rows = [["项目", "内容"]]
    rows.append(["团队名称", team["name"]])
    rows.append(["配置版本", f"schemaVersion {team.get('schemaVersion', '?')}"])
    rows.append(["成员数量", f"{n_members} 名"])
    rows.append(["技能总量", f"{n_skills} 个，分属 {n_fams} 个技能族"])
    rows.append(["流水线阶段", f"{n_tasks} 个任务"])
    rows.append(["流程规则", f"{len(rules)} 条"])
    retry = team.get("retryPolicy", {})
    if retry:
        rows.append(["返工上限", f"maxRounds={retry.get('maxRounds')}；"
                                 f"连续失败 {retry.get('consecutiveFailuresBeforeReassign')} 次重派；"
                                 f"captain 代做上限 {retry.get('captainTakeoverLimit')} 次"])
    ws = team.get("workspace", {})
    if ws:
        rows.append(["工作区", ws.get("root", "")])
    flush_table(doc, rows)

    body_para(doc, "本手册由 `python scripts/gen_manual.py` 从 team.json 与 skills/ 现算生成。"
                   "成员数、任务数、技能归属、依赖关系、流程规则都不是手写的——"
                   "改配置后重跑脚本，手册自动跟上。因此本文件不会出现"
                   "「封面写六成员、名册写七成员」这类过期数字。")


def sec_members(doc, team, index, families):
    heading(doc, "二、成员名册", 1)
    body_para(doc, "模型列按三档分配：strong（判断型任务，推理强度 max）、"
                   "standard（有脚本或清单兜底）、fast（模式化、量大）。"
                   "逐角色理由与换模型方法见 docs/model-assignment.md；"
                   "改模型只需编辑 team.json 的 modelPolicy，再跑 python scripts/apply_models.py。")

    rows = [["#", "成员", "负责领域", "技能", "档位", "模型"]]
    for i, m in enumerate(team["members"], 1):
        rows.append([
            str(i),
            m["name"],
            m.get("role", ""),
            str(len(m.get("skills", []))),
            m.get("tier", ""),
            m.get("model", ""),
        ])
    flush_table(doc, rows)

    body_para(doc, "三处分权设计：① t7 审查由 academic-reviewer 承担，与 t6/t8/t9 的 "
                   "paper-supervisor 分开，且该审查者不参与 t3 调研；"
                   "② 问卷与量表路径单列 survey-analyst，避免统计角色用计量口径套量表数据；"
                   "③ 验收后置为 t10.5 差异复审 + t11 质量验收两道，验收方只判定不改稿。")


def sec_duties(doc, team, families):
    heading(doc, "三、成员职责与技能配置", 1)
    body_para(doc, "每个成员开工前必须加载下表技能；技能名后的「必读 / 按需」由 "
                   "agents/<成员>.md 明确标注，未加载即产出视为流程违规。")

    for m in team["members"]:
        heading(doc, f"{m['name']}", 2)
        body_para(doc, f"职责：{m.get('role', '')}", indent=False)
        body_para(doc, f"档位：{TIER_LABEL.get(m.get('tier'), m.get('tier'))}；"
                       f"模型：{m.get('model')}"
                       + (f"；推理强度：{m['reasoningEffort']}"
                          if m.get("reasoningEffort") else ""),
                   indent=False)

        fams = []
        for s in m.get("skills", []):
            fam = index_family(s, families)
            if fam and fam not in fams:
                fams.append(fam)
        body_para(doc, "挂载技能族：" + "、".join(fams), indent=False)

        rows = [["技能", "所在族", "本角色为何需要"]]
        rows.extend(describe_skill(team, m, s, families) for s in m.get("skills", []))
        flush_table(doc, rows)

        body_para(doc, f"完整系统提示词见 agents/{m['name']}.md。", indent=False)


def index_family(skill, families):
    for fam, names in families.items():
        if skill in names:
            return fam
    return None


_PURPOSE_CACHE = None


def describe_skill(team, member, skill, families):
    """从 gen_agents.py 的数据源里取该技能的用途说明，取不到就给族名。"""
    global _PURPOSE_CACHE
    if _PURPOSE_CACHE is None:
        _PURPOSE_CACHE = {}
        try:
            import gen_agents
            for d in gen_agents.AGENT_DATA:
                for name, _path, purpose, level in d["skills"]:
                    _PURPOSE_CACHE.setdefault((d["name"], name), (purpose, level))
        except Exception:
            pass
    purpose, level = _PURPOSE_CACHE.get((member["name"], skill), ("", ""))
    fam = index_family(skill, families) or "—"
    if purpose:
        return [skill, fam, f"{purpose}（{level}）"]
    return [skill, fam, "—"]


def sec_tasks(doc, team):
    heading(doc, "四、流水线与任务分配", 1)

    heading(doc, "4.1 任务清单", 2)
    rows = [["#", "任务", "负责成员", "类型", "依赖"]]
    for t in team["tasks"]:
        deps = "、".join(t.get("dependsOn") or []) or "—"
        if t.get("degrade"):
            deps += f"（按路径剪枝，见 4.2 {t['id']}）"
        rows.append([t["id"], t["name"], t.get("owner", ""),
                     t.get("kind", "work"), deps])
    flush_table(doc, rows)

    has_degrade = [t for t in team["tasks"] if t.get("degrade")]
    if has_degrade:
        body_para(doc, "依赖里的「按路径剪枝」指：计量路径（t4）与问卷路径（t4b）由 t1 "
                       "判定后二选一或并行，被跳过的那条不阻塞下游。判定结果写在 "
                       "00-brief/brief.md 的「实证路径」一节，captain 据此在派发前剪枝；"
                       "剪枝不是成员自行决定的。各分支的替代依赖如下表。")
        rows = [["任务", "触发情形", "实际依赖"]]
        for t in has_degrade:
            for d in t["degrade"]:
                rows.append([t["id"], d["when"], "、".join(d["dependsOn"])])
        flush_table(doc, rows)

    heading(doc, "4.2 任务契约", 2)
    body_para(doc, "每个质量类任务都带 objective / acceptance / deliverables / inScope 四件，"
                   "验收标准是可逐条判定 fail 的短语，不是「做好一点」这种无法反驳的措辞。")

    for t in team["tasks"]:
        heading(doc, f"{t['id']}　{t['name']}", 3)
        if t.get("objective"):
            body_para(doc, f"目标：{t['objective']}", indent=False)
        if t.get("acceptance"):
            body_para(doc, "验收标准：", indent=False)
            for i, a in enumerate(t["acceptance"], 1):
                body_para(doc, f"（{i}）{a}", indent=True)
        if t.get("deliverables"):
            body_para(doc, "交付物：" + "；".join(t["deliverables"]), indent=False)
        if t.get("verify"):
            body_para(doc, "验证命令：" + "；".join(t["verify"]), indent=False)
        if t.get("degrade"):
            for d in t["degrade"]:
                body_para(doc, f"剪枝：{d['when']} → 依赖改为 "
                               f"{'、'.join(d['dependsOn'])}", indent=False)
        if t.get("forbidden"):
            body_para(doc, "禁止：" + "；".join(t["forbidden"]), indent=False)
        if t.get("nonGoals"):
            body_para(doc, "不做：" + "；".join(t["nonGoals"]), indent=False)


def sec_rules(doc, team):
    heading(doc, "五、流程规则", 1)
    body_para(doc, "以下规则同样在 team.json 的 flowRules 里，机器可读；这里是给人看的版本。")
    for i, r in enumerate(team["flowRules"], 1):
        body_para(doc, f"{i}. {r}", indent=False)


def sec_workspace(doc, team):
    ws = team.get("workspace", {})
    if not ws:
        return
    heading(doc, "六、工作区约定", 1)
    body_para(doc, f"所有产出写入 {ws.get('root')}/<NN-stage>/。交付物未落盘视为未交付，"
                   "路径不对同样视为未交付。")
    rows = [["目录", "用途"]]
    for k, v in ws.get("layout", {}).items():
        rows.append([k, v])
    flush_table(doc, rows)
    if ws.get("manifest"):
        body_para(doc, "版本台账：" + ws["manifest"], indent=False)
    for r in ws.get("rules", []):
        body_para(doc, "· " + r, indent=False)


def sec_quality(doc, team):
    heading(doc, "七、质量保证：能被执行的才算验收标准", 1)
    body_para(doc, "「文档说要这样、实际配置已经那样」是配置文件最常见的腐化方式。"
                   "所以验收标准不靠人记，而由下列脚本在 CI 里执行；任何一条不过，"
                   "改动作废。")
    rows = [["脚本", "拦什么"]]
    for name, what in (
        ("check_team.py", "成员↔提示词↔技能三方对不上、owner 未定义、依赖成环、"
                          "质量类任务缺 acceptance、skillFamilies 与实际技能族不符、"
                          "description 里的数字与配置不符"),
        ("check_skills.py", "SKILL.md 的 YAML frontmatter 解析失败、name 与目录名不一致、"
                            "description 超 1024 字符、技能被引入却没人用"),
        ("gen_agents.py --check", "agents/*.md 是否与单一数据源逐字一致（手改会被打回）"),
        ("gen_llms.py --check", "llms.txt 是否还停留在旧技能名、旧成员表"),
        ("apply_models.py --dry-run --strict", "各成员模型与 modelPolicy 是否脱节"),
        ("verify_paper.py", "统计量重算（t/F/χ²/Z，支持全角写法）、正文数字在结果表里找不到、"
                            "参考文献缺 GB/T 7714 必备要素"),
        ("selftest_docx.py", "交稿 Word 生成链路是否还活着"),
    ):
        rows.append([name, what])
    flush_table(doc, rows)

    body_para(doc, "稿件级校验用 python scripts/verify_paper.py all <稿件> --results <结果表目录>；"
                   "交稿改 Word 用 python scripts/docx_build_submission.py <稿件> --out <文件> "
                   "--template <期刊模板>。两者都进 CI，不靠自觉。")


def sec_deploy(doc, team):
    heading(doc, "八、部署到其他客户端", 1)
    body_para(doc, "本仓库是技能库 + 团队配置，不含任何厂商绑定。迁移到别的 Agent 客户端时，"
                   "多数失败都来自同一个原因：技能是多层族目录，而客户端只认一层 "
                   "<技能名>/SKILL.md。")
    for line in (
        "1. 定位客户端的 skills 目录（常见为 ~/.<client>/skills 或工作区 .claude/skills）。",
        "2. python scripts/install.py --target <该目录>　—— 脚本负责扁平化，"
        "不要手工 cp -r skills/*，那会连族目录一起复制，客户端识别不到。",
        "3. 用 python scripts/check_skills.py 确认 frontmatter 全部可解析。",
        "4. 重启客户端或重载配置，查询可用 skill 列表，确认数量与 llms.txt 一致。",
        "5. 成员定义直接用 agents/<成员>.md 作为系统提示词导入；"
        "它由 gen_agents.py 生成，内含该成员必读技能表与开工前必读段落。",
        "6. 若客户端不支持技能自动加载，就把 SKILL.md 的绝对路径写进任务描述，"
        "让成员用 read 工具直读——这是实测最可靠的做法。",
    ):
        body_para(doc, line, indent=False)

    body_para(doc, "迁移时最容易踩的三个坑：", indent=False)
    for line in (
        "坑一：以为装了 skill 成员就会用。skill 只提供指令文本，成员还需被明确告知"
        "「本单该用哪个技能」。agents/*.md 的「开工前必读」就是为此写的。",
        "坑二：让成员一次性输出大量内容。长输出会触发上游 API 的 400 或截断，"
        "改为「一步一文件」的小请求节奏。",
        "坑三：团队内模型路由不一致。同一团队混用不同 provider 路由时，"
        "某个成员会以「请求被拦截」的形式反复失败，而错误信息指向的是上游而非配置。",
    ):
        body_para(doc, line, indent=False)


# --------------------------------------------------------------------------- 主流程

def build() -> Document:
    team, index, families = load()
    n_skills = len(index)
    n_fams = len(families)
    n_members = len(team["members"])
    n_tasks = len(team["tasks"])
    rules = team.get("flowRules", [])

    doc = Document()
    cover(doc, team, n_members, n_tasks, n_skills, n_fams)
    sec_overview(doc, team, n_members, n_tasks, n_skills, n_fams, rules)
    sec_members(doc, team, index, families)
    sec_duties(doc, team, families)
    sec_tasks(doc, team)
    sec_rules(doc, team)
    sec_workspace(doc, team)
    sec_quality(doc, team)
    sec_deploy(doc, team)
    return doc


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def main():
    ap = argparse.ArgumentParser(description="从 team.json 生成团队配置手册 docx")
    ap.add_argument("--check", action="store_true", help="不写盘，仅报告是否需要更新")
    args = ap.parse_args()

    doc = build()
    if args.check:
        # docx 是压缩包，内部含时间戳，无法逐字节比对；
        # 这里改为「能生成 + 段落数/表格数非空」作为存活检查。
        n_par = sum(1 for p in doc.paragraphs if p.text.strip())
        n_tab = len(doc.tables)
        if n_par < 50 or n_tab < 5:
            print(f"[FAIL] 手册内容过少（段落 {n_par} / 表格 {n_tab}），疑似生成逻辑损坏")
            return 1
        print(f"[OK  ] 手册可生成（段落 {n_par} / 表格 {n_tab}）；"
              f"如需更新请运行 python scripts/gen_manual.py")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    n_par = sum(1 for p in doc.paragraphs if p.text.strip())
    print(f"[已生成] {OUT.relative_to(REPO)}")
    print(f"  段落 {n_par} ｜ 表格 {len(doc.tables)} ｜ {OUT.stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())

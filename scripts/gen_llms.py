"""由 team.json + skills/ 生成 llms.txt，避免手写索引与实际结构不一致。

之前 llms.txt 是手写的，技能改名后索引里还留着旧名字（如 `Full-empirical-analysis-skill`），
外部智能体照着索引找不到文件。改为生成式：结构变了就重新生成，别手改。

用法：
    python scripts/gen_llms.py            # 写入 llms.txt
    python scripts/gen_llms.py --check    # 只比对，不一致退出码 1（供 CI 用）
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEAM = REPO / "team.json"
SKILLS = REPO / "skills"
OUT = REPO / "llms.txt"

FAMILY_NOTE = {
    "academic-research-skills": "选题、框架、期刊规范、审稿",
    "supervisor-skills": "写作、润色、审稿、图表重建",
    "auto-empirical-research-skills": "数据清洗、计量、稳健性、p-hacking 自检",
    "socialscience-zh": "信效度、EFA/CFA、ANOVA、回归、中介调节、SEM、SPSS",
    "academic-figure-skills": "学术图表设计与绘制",
    "ai-research-skills": "研究全景与方法对比",
    "deep-research-skills": "深度调研流程编排",
    "corpus-paper-archiving": "逐篇精读与读档规范",
}


def frontmatter(path):
    """只解析 frontmatter 里的 name / description，不引入 yaml 依赖。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None, None
    end = text.find("\n---", 3)
    if end < 0:
        return None, None
    block = text[3:end]
    name = desc = None
    for key in ("name", "description"):
        m = re.search(rf"^{key}:\s*(.+)$", block, re.M)
        if not m:
            continue
        v = m.group(1).strip()
        if v[:1] in "\"'":
            q = v[0]
            v = v[1:]
            if v.endswith(q):
                v = v[:-1]
        if key == "name":
            name = v
        else:
            desc = v
    return name, desc


def collect():
    found = []
    for p in sorted(SKILLS.rglob("SKILL.md")):
        name, desc = frontmatter(p)
        rel = p.parent.relative_to(SKILLS).as_posix()
        family = rel.split("/")[0]
        found.append(
            {
                "family": family,
                "dir": p.parent.name,
                "rel": p.relative_to(REPO).as_posix(),
                "name": name or p.parent.name,
                "desc": (desc or "").replace("\n", " "),
            }
        )
    return found


def short(desc, limit=110):
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc if len(desc) <= limit else desc[:limit].rstrip() + "…"


def build(team, skills):
    L = []
    members = team["members"]
    tasks = team["tasks"]
    rules = team["flowRules"]

    L.append("# 论文攻坚组 paper-pipeline")
    L.append("")
    L.append(
        f"> {len(members)} 名成员的学术论文写作流水线（{len(tasks)} 个任务），"
        f"每名成员绑定一组专用技能库（{len(skills)} 个 SKILL）。"
    )
    L.append("> 写作与审查分离；质量验收独立且须 pass 才交付；每个成员开工前须加载自己绑定的技能。")
    L.append("> 适用于实证类中文学术论文（北大核心 / CSSCI），覆盖计量路径与问卷量表路径。")
    L.append("")
    L.append("## 如何取用（按顺序，成功即止）")
    L.append("")
    L.append(
        "1. `git clone --depth 1 https://github.com/liu996liu/paper-pipeline-team.git` "
        "—— **推荐**。HTTPS 与 SSH 稳定，一次拿全库。"
    )
    L.append(
        "2. `curl -L https://github.com/liu996liu/paper-pipeline-team/archive/refs/heads/main.zip -o repo.zip` "
        "—— 只要文件、不要历史时用。"
    )
    L.append("3. 读取本地文件：下列路径均为仓库内相对路径，clone 后直接可用。")
    L.append("")
    L.append("注意：`raw.githubusercontent.com` 与 jsDelivr 在中国大陆网络通常不通（实测 TLS 握手失败），")
    L.append("不要把 raw 链接作为首选；执行环境有代理时可正常使用。")
    L.append("")
    L.append("## 核心文件")
    L.append("")
    L.append("- `README.md`：项目说明与安装方式")
    L.append(
        f"- `team.json`：成员、{len(tasks)} 个任务（含 objective / acceptance / deliverables / inScope）、"
        f"依赖关系、{len(rules)} 条流程规则、工作区约定、重试策略（机器可读）"
    )
    L.append("- `docs/论文攻坚组-团队配置手册.docx`：完整配置手册")
    L.append("- `docs/workspace-convention.md`：工作区目录约定与交付物落盘规则")
    L.append("- `docs/citation-check-template.md`：引注核对表模板（GB/T 7714-2015）")
    L.append("- `docs/portable-usage.md`：在其他 Agent 客户端接入的方法")
    L.append(f"- `scripts/install.py`：技能库扁平化安装脚本（只装 `skills/` 下 {len(skills)} 个论文技能）")
    L.append("- `scripts/check_skills.py`：技能库自检（frontmatter 可解析 / name 与目录一致 / 描述长度 / 是否有人用）")
    L.append("- `scripts/check_team.py`：team.json 结构校验（成员↔提示词↔技能三方一致、依赖成环、质量契约字段）")
    L.append("- `scripts/gen_agents.py`：由单一数据源生成全部 `agents/*.md`")
    L.append("- `scripts/gen_llms.py`：生成本文件")
    L.append("- `scripts/verify_paper.py`：稿件校验（统计量重算 / 正文数字 vs 结果表 / GB/T 7714 引文要素），`--selftest` 自检")
    L.append("- `scripts/docx_build_submission.py`：Markdown → 中文期刊交稿 Word（三线表、题名页、套刊模板）")
    L.append("- `docs/cnki-workflow.md`：CNKI / 万方 / 维普 文献获取规程（合规路线与禁区）")
    L.append(
        "- `vendor/agent-teams/SKILL.md`：运行平台（DeepSeek Harness）团队协作协议，"
        "**不属于论文流水线技能，不被安装脚本复制**"
    )
    L.append("")
    L.append("## 成员（系统提示词）")
    L.append("")
    for m in sorted(members, key=lambda x: x["name"]):
        L.append(f"- `agents/{m['name']}.md` — **{m['name']}**：{m.get('role', '')}")
    L.append("")
    L.append("## 任务链")
    L.append("")
    L.append("```")
    L.append("t1 选题开题(research-orchestrator)")
    L.append(" ├── t2 文献精读(corpus-archivist)")
    L.append(" ├── t3 深度调研(deep-researcher)")
    L.append(" ├── t4  计量实证(empirical-analyst)      [条件：t1 判定走计量路径]")
    L.append(" └── t4b 问卷量表分析(survey-analyst)     [条件：t1 判定走问卷路径]")
    L.append("→ t5 图表设计(figure-designer) → t6 全文写作(paper-supervisor)")
    L.append("→ t7 独立审查(academic-reviewer) → t8 修订(paper-supervisor)")
    L.append("→ t9 去 AI 痕迹(paper-supervisor) → t10 候选定稿(research-orchestrator)")
    L.append("→ t10.5 差异复审(quality-gatekeeper) → t11 质量验收(quality-gatekeeper)")
    L.append("```")
    L.append("")
    L.append(f"硬规则（`team.json` 的 `flowRules` 共 {len(rules)} 条，以下为摘要）：")
    for i, r in enumerate(rules, 1):
        L.append(f"{i}. {r}")
    L.append("")
    L.append(f"## 技能库（{len(skills)} 个）")
    L.append("")
    L.append("目录为 `skills/<技能族>/<技能>/SKILL.md`。安装到其他客户端前须扁平化为 `<技能>/SKILL.md`，")
    L.append("用 `python scripts/install.py --target <目录>`（支持 --dry-run / --force）。")
    L.append("")
    by_family = {}
    for s in skills:
        by_family.setdefault(s["family"], []).append(s)
    for family in sorted(by_family):
        note = FAMILY_NOTE.get(family)
        L.append(f"### {family}" + (f"　—— {note}" if note else ""))
        L.append("")
        for s in sorted(by_family[family], key=lambda x: x["rel"]):
            L.append(f"- `{s['rel']}` — **{s['name']}**：{short(s['desc'])}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写盘")
    args = ap.parse_args()

    team = json.loads(TEAM.read_text(encoding="utf-8"))
    content = build(team, collect())
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""

    if args.check:
        if content != old:
            print("llms.txt 与 team.json / skills/ 不一致，请运行 python scripts/gen_llms.py")
            sys.exit(1)
        print("llms.txt 一致")
        return

    changed = content != old
    if changed:
        OUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"[{'已更新' if changed else '无变化'}] llms.txt  ({len(content)} 字符)")


if __name__ == "__main__":
    main()

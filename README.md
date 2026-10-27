# 论文攻坚组 · paper-pipeline

一套面向**实证类学术论文**的多智能体协作团队配置。7 名成员按「选题 → 文献 → 深度调研 → 实证 → 图表 → 写作 → 独立审查 → 修订 → 去 AI 痕迹 → 候选定稿 → 质量验收」排成一条端到端流水线，每个成员绑定一组专用技能库（skill），由队长（captain）统一派单。

适用于问卷/面板数据驱动的行为类实证研究，尤其擅长**中文社科核心期刊**（北大核心 / CSSCI）的写作规范与思政教育、管理学交叉选题。

---

## 团队成员

| 成员 | 职责 | 绑定技能库 | 模型 |
|---|---|---|---|
| `research-orchestrator` | 研究总控：选题开题、流程编排、完整性核查与定稿 | `academic-research-skills` | strong · max |
| `corpus-archivist` | 文献精读与归档：逐篇精读建可核对读档、写文献综述 | `corpus-paper-archiving` | fast |
| `deep-researcher` | 深度调研与独立审查：研究全景、方法对比、创新点核查；成稿后做内容层面独立审查 | `ai-research-skills` + `deep-research-skills` | strong · max |
| `empirical-analyst` | 实证分析：数据清洗、计量模型、结果表格、识别假设检验 | `auto-empirical-research-skills` | standard |
| `figure-designer` | 图表设计：图表规划、绘制、PPT 版图转换 | `academic-figure-skills` | fast |
| `paper-supervisor` | 写作与修订：全文写作、引言专项、润色；按审查意见逐条修订 | `supervisor-skills` | strong · max |
| `quality-gatekeeper` | 质量与合规验收：引注合规（GB/T 7714）、格式与编号、复现包完整性、引文真实性抽核 | `academic-research-skills` + `supervisor-skills` | standard |

> `quality-gatekeeper` 独立于写作环节：写作与内容审查由 `paper-supervisor` 完成，格式与合规由它判定，避免"自己检查自己"的假通过。它的四项闸门为——引注合规、格式编号一致性、复现包可复算、引文真实性抽核。其中领导人著作与讲话（毛泽东、邓小平、江泽民、胡锦涛、习近平等各时期，含选集／文选、文集单篇、报纸讲话、官方网络发布四类形态）执行**逐条核对、不抽样**，硬规则是「只引原始出处、摘引须完整、版次须统一、核不到标未核实」，核对表见 [`docs/citation-check-template.md`](docs/citation-check-template.md)。

成员的系统提示词（system prompt）完整保存在 `agents/<name>.md`，可直接导入支持 agent 定义的客户端。

---

## 目录结构

```
paper-pipeline-team/
├── README.md            # 本文件
├── llms.txt             # 给其他智能体用的全库索引（单文件掌握结构）
├── LICENSE              # 许可总览（各部分许可不同）
├── team.json            # 团队清单（成员、职责、技能绑定）
├── agents/              # 7 名成员的系统提示词（YAML frontmatter + prompt）
├── skills/              # 8 组技能库
│   ├── academic-research-skills/          选题、框架、期刊规范
│   ├── supervisor-skills/                 写作、润色、审稿、图表重建
│   ├── auto-empirical-research-skills/    数据清洗、计量、稳健性
│   ├── academic-figure-skills/            学术图表设计与绘制
│   ├── ai-research-skills/                研究全景与方法对比
│   ├── deep-research-skills/              深度调研流程编排
│   ├── corpus-paper-archiving/            逐篇精读与读档规范
│   └── agent-teams/                       团队协作协议
├── scripts/
│   ├── install.py                       技能库扁平化安装脚本
│   └── apply_models.py                  按 modelPolicy 同步各成员模型
└── docs/
    ├── 论文攻坚组-团队配置手册.docx        团队搭建与使用的完整手册
    ├── portable-usage.md                  在其他 Agent 客户端接入的说明
    ├── model-assignment.md                模型分配（角色级）与换模型方法
    ├── citation-check-template.md         引注核对表模板（GB/T 7714-2015）
    └── skill-audit-report.md              技能库审计报告
```

---

## 使用方式

**给其他智能体读取**：`llms.txt` 是本仓库的单文件索引（成员、任务链、69 个技能及仓库内相对路径）。取用方式以 `git clone` 优先 —— 实测在中国大陆网络 `raw.githubusercontent.com` 与 jsDelivr 不通，raw 链接仅作备用。让别的智能体先抓这一个文件，就能定位到需要的具体文件，不必遍历仓库。

**0. 先扁平化（重要）**

本仓库技能是 `skills/<技能族>/<技能>/SKILL.md` 两层（部分嵌到第 4 层），而多数客户端只认一层。用脚本一次装好：

```bash
python scripts/install.py --target ~/.claude/skills
python scripts/install.py --target ~/.workbuddy/skills --dry-run   # 先看会复制什么
```

在其他客户端（Codex CLI、Cursor、Cline、DeepSeek Harness 等）的接入方式、frontmatter 兼容性问题，见 [docs/portable-usage.md](docs/portable-usage.md)。

**1. 导入技能库**

把 `skills/` 下的每个目录复制到客户端的 skills 目录。以 WorkBuddy / Claude Code 为例：

```bash
# WorkBuddy（用户级）
cp -r skills/* ~/.workbuddy/skills/

# Claude Code（项目级）
cp -r skills/* ./.claude/skills/
```

> 注意：多数客户端只识别**一层** `<skill-name>/SKILL.md` 结构。若 `skills/<族>/` 下还有嵌套子目录，需按客户端要求扁平化。

**2. 导入成员定义**

`agents/*.md` 的 YAML frontmatter 含 `name` / `description` / `model`，正文即系统提示词。按所用客户端的 agent 格式导入；若客户端不支持多智能体，可把单个 `agents/<name>.md` 当作 system prompt 使用。

**3. 启动流水线**

队长 `research-orchestrator` 负责拆解任务与派单，其余成员按依赖顺序执行。典型任务链：

```
选题开题 → 文献精读归档 → 深度调研(GAP) → 实证分析 → 图表 → 全文写作 → 独立审查 → 修订 → 去 AI 痕迹 → 候选定稿 → 质量验收
```

---

## 模型分配

7 个角色各自有独立的 `model` 与 `reasoningEffort`，按三档分配：

| 档位 | 角色 | 依据 |
|---|---|---|
| `strong · max` | research-orchestrator、deep-researcher、paper-supervisor | 判断型任务：选题、审查、写作 |
| `standard` | empirical-analyst、quality-gatekeeper | 有脚本或核对清单兜底 |
| `fast` | corpus-archivist、figure-designer | 模式化、量大、输出为结构化字段 |

配置集中在 `team.json` 的 `modelPolicy`，改完运行 `python scripts/apply_models.py` 一次同步到 7 个成员定义。逐角色理由、换模型步骤与各客户端兼容性见 [docs/model-assignment.md](docs/model-assignment.md)。

---

## 流水线设计规则

三条规则写进了 team.json 的 flowRules，是这套配置与「一个人从头写到尾」的关键差别：

1. **写作与审查分离** — 全文写作由 `paper-supervisor` 负责（t6），内容审查由 `deep-researcher` 独立执行（t7）。同一成员不得兼任，否则等于自审。
2. **验收独立且后置** — `quality-gatekeeper` 在候选定稿之后（t11）做格式、引注、复现包与引文真实性的判定；判 fail 时退回修订环节（t8），不在验收环节改稿。
3. **条件分支显式建模** — t4 是否执行由 t1 的「是否需要实证」判定决定。判定为不需要时，t5 与 t6 的依赖中移除 t4，避免等待一个永远不会发生的任务。

前两条解决「谁来判断好坏」，第三条解决「流程空转」。

---

## 未包含的内容

以下内容**未纳入本仓库**，请自行准备：

- **论文数据与稿件**：原始问卷数据、清洗结果、投稿稿件均属私有研究资产，不入库。
- **运行时状态**：团队会话 ID、任务队列、成员间消息日志（`inbox/*.jsonl`）属于本地运行态，不入库。
- **插件二进制**：`dsh-plugins/` 体积达 292 MB，按需自行安装。

---

## 许可

本仓库是多个来源的技能库整合发行版，**不适用单一许可证**。逐目录的许可清单见 [NOTICE.md](NOTICE.md)，要点：

- **MIT**（`aer-skills`、`p-hacking-skills`、`drawio-reconstruction` 等）：可自由再分发，须保留版权声明。
- **CC-BY-4.0**（6 个写作/图表类技能）：可再分发，须署名原作者。
- **CC-BY-NC-SA-4.0**（`paper-writer`、`paper-polish`、`intro-drafter`、`supervisor-deep-research`）：**禁止商业使用**，衍生版本须以相同许可发布。因此**本仓库整体不可用于商业用途**。
- 部分目录未声明许可证，版权归原作者，本仓库仅作技术聚合与迁移示例。

## 引用

若本配置对你的研究有帮助，请按以下任一方式引用（GitHub 页面右侧「Cite this repository」可一键导出）：

```
liu996liu. 论文攻坚组 paper-pipeline：六成员学术论文协作智能体团队[CP/OL].
GitHub, 2026. https://github.com/liu996liu/paper-pipeline-team.
```

BibTeX：

```bibtex
@misc{paperpipeline2026,
  author       = {liu996liu},
  title        = {论文攻坚组 paper-pipeline：六成员学术论文协作智能体团队},
  year         = {2026},
  publisher    = {GitHub},
  howpublished = {\url{https://github.com/liu996liu/paper-pipeline-team}}
}
```

## 说明

- 团队成员模型配置为示例值，实际使用时请替换为你所用客户端支持的模型。
- 本仓库仅保留团队结构与成员职责，不含任何具体论文的数据、稿件或研究过程记录。
- `skills/agent-teams/` 为运行平台的团队协作协议，其文件路径示例中的用户目录已做占位化处理。

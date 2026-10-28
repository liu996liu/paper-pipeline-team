# 论文攻坚组 · paper-pipeline

一套面向**实证类学术论文**的多智能体协作团队配置。9 名成员按「选题 → 文献 → 深度调研 → 计量实证 / 问卷量表 → 图表 → 写作 → 独立审查 → 修订 → 去 AI 痕迹 → 候选定稿 → 差异复审 → 质量验收」排成一条 13 个任务的端到端流水线，每个成员绑定一组专用技能库（skill），由队长（captain）统一派单。

适用于问卷／面板／二手数据驱动的行为类实证研究，尤其擅长**中文社科核心期刊**（北大核心 / CSSCI）的写作规范与思政教育、管理学、教育学交叉选题。

---

## 团队成员

| 成员 | 职责 | 绑定技能库 | 模型 |
|---|---|---|---|
| `research-orchestrator` | 研究总控：选题开题、实证路径判定、完整性核查与候选定稿 | `academic-research-skills` + `supervisor-skills` | strong · max |
| `corpus-archivist` | 文献精读与归档：逐篇精读建可核对读档、写文献综述、引文落库 | `corpus-paper-archiving` | fast |
| `deep-researcher` | 深度调研：领域全景、方法对比、创新点核查、GAP 定位（**只做调研，不做审查**） | `ai-research-skills` + `deep-research-skills` | strong · max |
| `empirical-analyst` | 计量实证：数据清洗、识别策略、稳健性、结果表格、复现包（二手/面板/宏观数据路径） | `auto-empirical-research-skills` | standard |
| `survey-analyst` | 问卷与量表分析：数据清理、信效度、因子分析、方差分析、回归、中介调节、SPSS/lavaan 实现（问卷路径） | `socialscience-zh` + `auto-empirical-research-skills` | standard |
| `figure-designer` | 图表设计：图表规划、绘制、三线表、PPT 版图（**依赖实际结果，不画占位图**） | `academic-figure-skills` + `supervisor-skills` | fast |
| `paper-supervisor` | 写作、修订与文体处置：全文写作、引言专项、润色、按审查意见修订、去 AI 痕迹 | `supervisor-skills` + `academic-research-skills` | strong · max |
| `academic-reviewer` | 独立学术审查：**只审不写**。对成稿做内容、逻辑、方法、创新性的对抗式评审并给出可执行缺陷清单 | `academic-research-skills` + `auto-empirical-research-skills` | strong · max |
| `quality-gatekeeper` | 合规验收与差异复审：引注合规、格式编号、表文数字一致、差异漂移、复现包、引文真实性 | `academic-research-skills` + `supervisor-skills` | standard |

三个关键的分权设计：

- **审查与调研分家**。原设计里 `deep-researcher` 既做 t3 深度调研又做 t7 独立审查，等于自己审自己提出的创新点。现在 t7 由新增的 `academic-reviewer` 专职承担，它手上没有任何 t3 的产出，只有成稿和文献。
- **问卷路径单独立角色**。计量模型（DID/RD/IV/面板）与问卷量表（信效度/EFA-CFA/中介调节/SEM）是两套完全不同的方法论，前者靠 `full-empirical-*` 系列，后者靠新增的 `socialscience-zh` 系列。合成一个 `empirical-analyst` 会两头都不专业，所以拆成 t4 与 t4b 两条并行支线，由 t1 的开题判定走哪条。
- **验收后置且分两道**。t10 候选定稿之后先过 t10.5 差异复审（比对 t9→t10 到底改了什么，抓数值/单位/引注/结论的漂移），再过 t11 四道合规闸门。前者管「改错了」，后者管「不合规」。

> `quality-gatekeeper` 的四项闸门为——引注合规、格式编号一致性、表文数字一致、复现包可复算、引文真实性抽核。其中领导人著作与讲话（毛泽东、邓小平、江泽民、胡锦涛、习近平等各时期，含选集／文选、文集单篇、报纸讲话、官方网络发布四类形态）执行**逐条核对、不抽样**，硬规则是「只引原始出处、摘引须完整、版次须统一、核不到标未核实」，核对表见 [`docs/citation-check-template.md`](docs/citation-check-template.md)。

成员的系统提示词（system prompt）完整保存在 `agents/<name>.md`，由 `scripts/gen_agents.py` 统一生成，可直接导入支持 agent 定义的客户端。

---

## 目录结构

```
paper-pipeline-team/
├── README.md            # 本文件
├── llms.txt             # 给其他智能体用的全库索引（单文件掌握结构）
├── LICENSE              # 许可总览（各部分许可不同）
├── team.json            # 团队清单（成员、13 个任务、依赖、流程规则、工作区约定、重试策略）
├── agents/              # 9 名成员的系统提示词（YAML frontmatter + prompt）
├── skills/              # 8 组技能库（论文流水线用，共 84 个技能）
│   ├── academic-research-skills/          选题、框架、期刊规范、审稿
│   ├── supervisor-skills/                 写作、润色、审稿、图表重建
│   ├── auto-empirical-research-skills/    数据清洗、计量、稳健性、p-hacking 自检
│   ├── socialscience-zh/                  信效度、EFA/CFA、ANOVA、回归、中介调节、SEM、SPSS、质性编码、选刊投稿、交稿排版、中文修回、研究伦理、文献计量
│   ├── academic-figure-skills/            学术图表设计与绘制
│   ├── ai-research-skills/                研究全景与方法对比
│   ├── deep-research-skills/              深度调研流程编排
│   └── corpus-paper-archiving/            逐篇精读与读档规范
├── vendor/              # 运行平台配套，非论文流水线技能
│   └── agent-teams/                       团队协作协议（DeepSeek Harness 用，不进 skills 安装）
├── scripts/
│   ├── install.py                       技能库扁平化安装脚本
│   ├── check_skills.py                  技能库自检（frontmatter 可解析 / name 与目录一致 / 描述长度）
│   ├── check_team.py                    team.json 自检（成员↔提示词 ↔技能、依赖成环、质量契约字段）
│   ├── gen_agents.py                    由单一数据源生成全部 agents/*.md
│   ├── gen_llms.py                      由 team.json + skills/ 生成 llms.txt 索引
│   ├── normalize_skills.py              批量规范化 frontmatter（一次性修复用）
│   ├── apply_models.py                  按 modelPolicy 同步各成员模型
│   ├── verify_paper.py                  稿件校验：统计量重算 / 正文数字 vs 结果表 / GB/T 7714 引文要素
│   ├── selftest_docx.py                 交稿 Word 生成脚本的冒烟测试（CI 用）
│   ├── cnki_ingest.py                   解析知网/万方/维普导出的 RIS·EndNote·NoteExpress·GB/T 7714 文本
│   ├── export_profile.py                由 team.json 编译出合法的 DSH AgentTeams profile
│   └── docx_build_submission.py         由 Markdown 生成投稿用 Word（三线表、OMML、套刊模板）
└── docs/
    ├── 论文攻坚组-团队配置手册.docx        团队搭建与使用的完整手册（生成物，由 gen_manual.py 现算）
    ├── portable-usage.md                  在其他 Agent 客户端接入的说明
    ├── dsh-profile.yml                    可直接粘贴进 cordis.patch.yml 的 AgentTeams profile（生成物）
    ├── model-assignment.md                模型分配（角色级）与换模型方法
    ├── workspace-convention.md            工作区目录约定与交付物落盘规则
    ├── citation-check-template.md         引注核对表模板（GB/T 7714-2015）
    ├── cnki-workflow.md                   CNKI / 万方 / 维普 文献获取规程（含「AI 进不去知网」的实测证据与作者代理检索协议）
    └── skill-audit-report.md              DSH 插件 skill 审计报告（历史文档，与本仓库论文技能无关）
```

---

## 使用方式

**给其他智能体读取**：`llms.txt` 是本仓库的单文件索引（成员、任务链、84 个技能及仓库内相对路径）。取用方式以 `git clone` 优先 —— 实测在中国大陆网络 `raw.githubusercontent.com` 与 jsDelivr 不通，raw 链接仅作备用。让别的智能体先抓这一个文件，就能定位到需要的具体文件，不必遍历仓库。

**0. 先扁平化（重要）**

本仓库技能按技能族分层，最深到第 6 层（如 `skills/auto-empirical-research-skills/aer-skills/skills/<技能>/SKILL.md`），而多数客户端只认一层 `<技能名>/SKILL.md`。**不要手动 `cp -r`**——按族目录整体复制会把多层结构原样搬过去，客户端识别不到。

用脚本一次装好（脚本会遍历全部层级，只复制含 `SKILL.md` 的目录）：

```bash
python scripts/check_skills.py                                    # 装之前先自检一遍
python scripts/install.py --target ~/.claude/skills
python scripts/install.py --target ~/.workbuddy/skills --dry-run   # 先看会复制什么
```

脚本行为：
- 目标已存在同名技能时**跳过并逐个列出**，要覆盖须显式加 `--force`；
- `--force` 采用「先复制到临时目录、成功后再原子替换」，复制失败时旧版本原样保留，不会出现旧版已删、新版不全的中间态；
- 拒绝写入仓库内部路径，也拒绝把已存在的普通文件当目标目录。

在其他客户端（Codex CLI、Cursor、Cline、DeepSeek Harness 等）的接入方式、frontmatter 兼容性问题，见 [docs/portable-usage.md](docs/portable-usage.md)。

> **DeepSeek Harness 用户注意**：`team.json` 的字段平台不认识，不能原样导入。用 `python scripts/export_profile.py --out docs/dsh-profile.yml` 编译出合法 profile，再粘进 `cordis.patch.yml`（本团队 9 人，还需把 `maxMembers` 调到 9）。细节见 [portable-usage 第 5 节](docs/portable-usage.md)。

**1. 导入技能库**

用第 0 步的脚本导入，不要手动复制族目录。以 WorkBuddy / Claude Code 为例：

```bash
# WorkBuddy（用户级）
python scripts/install.py --target ~/.workbuddy/skills

# Claude Code（项目级）
python scripts/install.py --target ./.claude/skills
```

> 各客户端都只识别**一层** `<技能名>/SKILL.md` 结构。脚本已处理好扁平化；若你要自己复制，须自行保证每个技能目录直接位于 skills 根下。

**2. 导入成员定义**

`agents/*.md` 的 YAML frontmatter 含 `name` / `description` / `model`，正文即系统提示词。按所用客户端的 agent 格式导入；若客户端不支持多智能体，可把单个 `agents/<name>.md` 当作 system prompt 使用。

> 这 9 个文件由 `scripts/gen_agents.py` 从同一份数据生成。要改职责或技能表，改脚本再 `python scripts/gen_agents.py` 重新生成，别手改 md —— 手改会在下次生成时被覆盖，而且 9 个文件很容易改漏一个。

**3. 启动流水线**

队长 `research-orchestrator` 负责拆解任务与派单，其余成员按依赖顺序执行。典型任务链：

```
t1 选题开题（判定实证路径，锁定目标刊）
 ├── t2 文献精读归档
 ├── t3 深度调研(GAP)
 ├── t4  计量实证      [条件：t1 判定走计量路径]
 └── t4b 问卷量表分析  [条件：t1 判定走问卷路径]
→ t5 图表设计（依赖 t3 + t4 或 t4b 的实际结果，两者都不跑时只依赖 t3）
→ t6 全文写作 → t7 独立审查
→ t8 修订 → t9 去 AI 痕迹 → t10 候选定稿
→ t10.5 差异复审 → t11 质量验收
```

> **两条实证路径可以都跑，也可以都不跑。** t1 的 `00-brief/empirical-path.md` 明确写走哪条；
> 被跳过的任务必须同时从 t5 / t6 的依赖里剪掉（`team.json` 里每个分支都配了 `degrade`，
> 由 `check_team.py` 校验「剪枝只能删、不能加」）。纯理论或综述型论文两条都不跑，
> t5/t6 退化为只依赖 t3。

**4. 工作区约定**

所有产出写到 `paper/<slug>/<NN-stage>/`，八个阶段目录的含义见 [docs/workspace-convention.md](docs/workspace-convention.md)。交付物未落盘视为未交付，路径不对也视为未交付；稿件版本不可原地覆盖，`t8/t9/t10` 各建 v1/v2/v3。

---

## 模型分配

9 个角色各自有独立的 `model` 与 `reasoningEffort`，按三档分配：

| 档位 | 角色 | 依据 |
|---|---|---|
| `strong · max` | research-orchestrator、deep-researcher、paper-supervisor、academic-reviewer | 判断型任务：选题、审查、写作 |
| `standard` | empirical-analyst、survey-analyst、quality-gatekeeper | 有脚本或核对清单兜底 |
| `fast` | corpus-archivist、figure-designer | 模式化、量大、输出为结构化字段 |

配置集中在 `team.json` 的 `modelPolicy`，改完运行 `python scripts/apply_models.py` 一次同步到 9 个成员定义。逐角色理由、换模型步骤与各客户端兼容性见 [docs/model-assignment.md](docs/model-assignment.md)。

> ⚠️ 三档目前只用到两个真实模型（`deepseek-v4.1-flash-sg` 与 `deepseek-v4.1-flash`），`strong` 与 `standard` 的模型 ID 相同、仅 `reasoningEffort` 不同。若你的账号里有更强模型，改 `modelPolicy.tiers` 一处即可。

---

## 流水线设计规则

十三条规则写进了 `team.json` 的 `flowRules`，是这套配置与「一个人从头写到尾」的关键差别。分组看：

**分权（谁来判断好坏）**

1. **写作与审查分离** — t6/t8/t9 由 `paper-supervisor` 承担，t7 由 `academic-reviewer` 承担，两者不得为同一成员；t7 的审查者也不得是 t3 的调研者。
2. **验收独立且后置** — `quality-gatekeeper` 在候选定稿之后（t11）做判定；判 fail 时退回 t8，不在验收环节改稿。
3. **模型不得自审** — 同一模型实例不得同时承担同一稿件的写作与审查；换模型替代成员时，审查方必须换到不同模型或不同成员。
4. **技能加载** — 每个成员接单第一步必须按自己 `agent.md` 的「开工前必读」加载对应技能；未加载即产出视为流程违规，审查环节有权直接退回。

**闭环（改坏了能不能退回去）**

5. **返工闭环** — t7 verdict 非 pass 时回到 t6 重写，重走 t6→t7，而不是直接进 t8。t8 只在 t7 给出 `needs_revision` 且缺陷可局部修补时承接。
6. **轮次上限** — `maxRounds=2`。第 2 轮 t7 仍 fail，captain 停止自动重跑，转人工裁决，全部 fail 记录汇总到 `60-review/escalation.md`，不得开第 3 轮。
7. **t11 回退路径** — t11 fail 回 t8，重走 t8→t9→t10→t10.5→t11，同样受 `maxRounds=2` 约束。
8. **差异复审闸门** — t10 之后必须经 t10.5 比对 t9→t10 的实际改动；任何数值、单位、引注、结论的漂移必须逐条说明来源或回退，未通过不得进 t11。

**分支与降级（跑不下去怎么办）**

9. **条件分支** — t4 与 t4b 是否执行由 t1 判定：计量路径跑 t4，问卷路径跑 t4b，两者皆需则都跑，纯理论/综述型两条都不跑。`team.json` 的 t5 与 t6 因此各配了三条 `degrade` 分支，把被跳过的任务从依赖里剪掉，避免等待永不发生的任务。`check_team.py` 强制校验「剪枝只能删依赖、不能加依赖」，且 `degrade` 必须是数组——写成单个对象会让多个分支互相覆盖。
10. **失败重派** — 成员连续 2 次失败，captain 重派给同族次优成员，并在交付物首行标注「代执行人 / 原责任人 / 代执行原因 / 授权来源」。
11. **代做上限** — 同一任务不得由 captain 连续代做超过 1 次；第 2 次仍失败必须换成员或转人工裁决。

**交付纪律（产物在哪、能不能改）**

12. **工作区约定** — 所有产出写入 `paper/<slug>/<NN-stage>/`；交付物未落盘或路径不对均视为未交付。
13. **版本不可覆盖** — t8/t9/t10 不得原地覆盖上一版，必须新建 v2/v3/v4；修订必须有逐条对照表。

---

## 质量方差从哪来

这套配置最容易出问题的地方不是「模型不够强」，而是**任务描述太粗**。原版本 11 个任务只有 `id/name/owner/dependsOn`，没有任何验收标准，成员做到什么程度算完成全靠自觉——同一个选题跑两次，一次交 3000 字一次交 8000 字，谁都说不清哪个对。

现在每个任务都补齐了六个字段：

| 字段 | 作用 |
|---|---|
| `objective` | 这个任务到底要解决什么问题（一句话说清交付物的用途） |
| `acceptance` | 逐条可判定的验收标准，审查者照此打 pass/fail |
| `deliverables` | 具体文件路径，落到约定目录才算交付 |
| `inScope` / `outOfScope` | 允许改动和禁止改动的路径，防止顺手改别的 |
| `kind` | `requirements` / `implementation` / `review` / `repair` / `integration`，决定审查方式 |
| `nonGoals` | 明确不做什么，避免成员自由发挥扩大范围 |

审查类任务（t1 / t7 / t10.5 / t11）必须给出 `verdict=pass` 才算完成，给 `needs_revision` 或 `reject` 一律判失败并附缺陷清单。

### 但这些字段靠人记是记不住的

配置文件最容易腐化的地方，是「文档说要这样，实际配置已经那样」。所以验收标准不是口头承诺，而是八个能被 CI 执行的脚本：

| 脚本 | 拦什么 |
|---|---|
| `scripts/check_team.py` | 成员↔提示词↔技能三方对不上、owner 未定义、依赖悬空、依赖成环、质量类任务缺 acceptance、implementation/repair 缺 objective 与 verify、`degrade` 剪枝引入新依赖、`reasoningEffort` 写成空字符串 |
| `scripts/check_skills.py` | SKILL.md 的 YAML frontmatter 解析失败、`name` 与目录名不一致、description 超 1024 字符、team.json 引用了不存在的技能、技能被引入却没人用（WARN） |
| `scripts/gen_agents.py --check` | `agents/*.md` 是否与单一数据源 `gen_agents.py` 逐字一致（手改会被 CI 打回） |
| `scripts/gen_llms.py --check` | `llms.txt` 是否还停留在旧技能名、旧成员表 |
| `scripts/apply_models.py --dry-run --strict` | 各成员 frontmatter 里的模型与 `modelPolicy` 是否脱节 |
| `scripts/verify_paper.py` | 稿件级的：统计量重算（t/F/χ²/Z 的自实现分布，支持全角写法）、正文小数在结果表里找不到、参考文献缺 GB/T 7714 必备要素 |
| `scripts/selftest_docx.py` | 交稿 Word 生成链路是否还活着（能不能生成含三线表与题名页的 .docx） |
| `scripts/cnki_ingest.py --selftest` | 中文文献导出解析链路是否还活着（RIS / EndNote / NoteExpress / GB/T 7714 文本四种格式的解析、去重、缺项质检） |
| `scripts/gen_manual.py --check` | `docs/论文攻坚组-团队配置手册.docx` 是否还是从 team.json 现算的版本（手写的汇总文档迟早与配置脱节，而它长得像官方文件） |
| `scripts/export_profile.py --check` | `docs/dsh-profile.yml` 是否与 team.json 同步 |

> **为什么 frontmatter 要单独查**：description 里若出现未加引号的 `": "`，YAML 整个解析失败，
> 客户端会把该技能当无效条目静默跳过——文件在，但装不上。仓库里曾经有两个技能就是这么失效的。

> **为什么统计量要自己重算**：现成的 `statcheck` 只认英文半角写法，中文期刊常见的
> `t（120）＝2.45` 一个都解析不出来，且它的 Python 移植版在新版 pandas/numpy 下直接抛错。
> `verify_paper.py` 内置全角归一化 + 自实现的 t/F/χ²/Z 分布函数，不依赖 scipy。

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

> **声明覆盖率**：84 个论文流水线技能中，`socialscience-zh/` 下 16 个为原创（随本仓库以 CC-BY-NC-SA-4.0 发布），其余 68 个中仅 20 个在 `SKILL.md` frontmatter 或族目录下带有明确许可声明（MIT 10、CC-BY-4.0 6、CC-BY-NC-SA-4.0 4），**48 个无任何许可声明**，按著作权法默认规则版权归原作者，本仓库不构成对其的再分发授权。族级 `LICENSE` 文件仅存在于 4 处（`aer-skills`、`p-hacking-skills`、`replication-package-skeleton`、`drawio-reconstruction`）。`vendor/agent-teams/` 同样未声明许可。使用、再分发或商用前须自行确认各技能来源的授权状况。

## 引用

若本配置对你的研究有帮助，请按以下任一方式引用（GitHub 页面右侧「Cite this repository」可一键导出）：

```
liu996liu. 论文攻坚组 paper-pipeline：九成员学术论文协作智能体团队[CP/OL].
GitHub, 2026. https://github.com/liu996liu/paper-pipeline-team.
```

BibTeX：

```bibtex
@misc{paperpipeline2026,
  author       = {liu996liu},
  title        = {论文攻坚组 paper-pipeline：九成员学术论文协作智能体团队},
  year         = {2026},
  publisher    = {GitHub},
  howpublished = {\url{https://github.com/liu996liu/paper-pipeline-team}}
}
```

## 说明

- 团队成员模型配置为示例值，实际使用时请替换为你所用客户端支持的模型。
- 本仓库仅保留团队结构与成员职责，不包含任何具体论文的数据、稿件或研究过程记录。
- `vendor/agent-teams/` 为运行平台的团队协作协议，**不属于论文流水线的技能库**，`scripts/install.py` 不会安装它；它只在 DeepSeek Harness 的 agent-teams 插件环境下起作用，其他客户端可忽略。其文件路径示例中的用户目录已做占位化处理。真正可用的导入形式是 `docs/dsh-profile.yml`（由 `team.json` 编译生成），`vendor/` 里的协议仅作阅读参考。

# 本次改造说明（v1.0.0 → v2.0.0）

> 逐条对应「九条改造指令」，并列出你未提到、但我在审计中确认必须一起修的问题。
> 改动全部落在 `D:\WorkBuddy\paper-pipeline-team\repo`，由 9 个 CI 脚本守住，不是口头承诺。

## 一、九条指令的落地情况

| # | 你的指令 | 落地形态 | 可验证点 |
|---|---|---|---|
| 1 | t10 之后加一道差异复审 | 新增 **t10.5 差异复审**（`quality-gatekeeper`，`kind=review`），比对 t9→t10 的实际改动 | `team.json` 有 t10.5；flowRule 5 定义闸门；`check_team.py` 校验其必须带 acceptance |
| 2 | 每个 agent.md 加「开工前必读」 | 9 份 `agents/*.md` 统一注入 6 条固定段落（读团队约定 → 装技能 → 逐份加载 → 加载判定 → 失败上报 → 只读相关） | 6 条在 9 份文件里**逐字一致**，由 `gen_agents.py` 单一数据源生成，手改会被 CI 打回 |
| 3 | t7 新增纯审查角色 | 新增 **`academic-reviewer`**（9 人团队），与 `deep-researcher` 彻底分家；flowRule 1 禁止审查者兼调研者 | `check_skills.py` 报「技能 84 ｜ 被引用 84 ｜ 问题 0」 |
| 4 | t5 依赖 t3+t4，t4 跳过才退化为 t3 | t5/t6 各配 3 条 `degrade` 分支（只计量 / 只问卷 / 都不跑）；新增 `dependsOnPolicy` | `check_team.py` 强制「剪枝只能删依赖、不能加依赖」 |
| 5 | 显式 maxRounds=2 + t7 fail → t6 | `retryPolicy.maxRounds=2`；flowRule 3 写明 t7 fail 回 t6 而非 t8；flowRule 4 写明第 2 轮仍 fail 转人工 | `docs/workspace-convention.md` 定义 `60-review/escalation.md` |
| 6 | 每个 task 补 objective/acceptance/deliverables/inScope | 13 个任务**全部**具备四字段（t1 另有 nonGoals） | `check_team.py` 对质量类任务强制要求 |
| 7 | 失败重派规则 + 工作区目录约定 | `retryPolicy` 五项（重派阈值 2、代做上限 1、代执行标注格式、升级路径）；`workspace` 九目录 + 三条硬规矩 | flowRule 8/9/10/11；`docs/workspace-convention.md` |
| 8 | 重新检索高星/权威项目，补 CNKI | 新增 `docs/cnki-workflow.md`；结论见下方「三」 | 文档里写死了「知网无公开 API」与四条合规路线 |
| 9 | 实证统计全谱系（信效度/方差/回归…） | 新建 **`skills/socialscience-zh/`（16 个原创技能，3722 行）** | `check_skills.py` 全部通过 YAML 校验且被引用 |

## 二、你未提到、但我修掉的硬问题

### 致命级

1. **68 个技能全是死代码**。`grep -rn 'SKILL.md\|skills/' agents/` 原返回 **0 条命中**——没有任何一个 agent 提示词告诉成员去加载技能。成员被 spawn 出来时手上只有一份通用 AgentTeams 模板，技能库形同虚设。现在是 84 个技能、**被引用 84 个、0 个闲置**。

2. **7 个 agent 提示词是同一份模板**。除 `quality-gatekeeper` 外，其余 6 个文件逐字相同，只是换了角色名，4103–4271 字符、39–41 行，全部不含角色职责。现在每份都是角色专属的 5000+ 字符，含技能表 + 职责 + 协作规则 + 交付契约。

3. **2 个技能因 YAML 语法静默失效**。`de-aigc-skills`（正是 t9 要去 AI 痕迹要用的那个）和 `01-phack-taxonomy` 的 description 里有未加引号的 `": "`，PyYAML 直接解析失败，客户端会把该技能当无效条目**静默跳过**——文件在，但装不上、永远加载不到。已全量规范化 68 个 frontmatter。

### 流程级

4. **最后改稿无人审**。原设计中 t9（去 AI 痕迹，全文文体重写）发生在唯一一次内容审查 t7 之后，t10 定稿再改一次，而 t11 只做脚本化核对。等于最后两轮改动没有任何人类/独立角色看过。→ 补 t10.5 差异复审。

5. **去 AI 痕迹派给了错误的角色**。原 t9 交给 `empirical-analyst`（统计角色），现在归 `paper-supervisor`。

6. **审查者审自己的贡献**。原 t7 由 `deep-researcher` 执行，而它同时是 t3 的调研者。→ 新增独立 `academic-reviewer`。

7. **先画图后出数**。原 t5 只依赖 t3 调研，不依赖 t4 实证，图表会基于调研结论而非实际结果，出现「图里的数是编的」。→ t5 依赖 `[t3, t4, t4b]`。

8. **返工闭环只写在文字里**。原 flowRules 说「t11 fail 退 t8」，但没有轮次上限、没有 t7 fail 的路径、没有升级机制，实际会无限循环或直接卡死。→ `retryPolicy` 显式化 + 新增 flowRule 6。

9. **无降级/重派策略**。真实跑动里 `figure-designer` 因上游 API 400 连续失败，最后由 `deep-researcher` 代做并在交付物首行自述代执行——这是成员自觉，不是制度。→ flowRule 8/9 把它写成硬规则。

10. **11 个任务零验收标准**。原 `tasks` 只有 `id/name/owner/dependsOn/condition/conditionalDependsOn` 五个字段。同一选题跑两次，一次交 3000 字一次交 8000 字，谁都说不清哪个对。→ 13 个任务全部补齐 4 个契约字段。

### 工程级

11. **文档会骗人**。`portable-usage.md` 原文写「原样导入 `team.json` 即可，它认识 `members`、`tasks`、`flowRules` 三个字段」——**实测是假的**。AgentTeams 插件源码 `lib/profiles.js` 的 `assertAllowedKeys` 遇到未知键直接抛错，`kind`/`objective`/`acceptance`/`verify`/`degrade` 全是未知键，原样导入第一步就炸。→ 新建 `scripts/export_profile.py` 做单向编译，产出 `docs/dsh-profile.yml`，并用插件真实 `resolveTeamProfile()` 验过（9 成员 / 13 任务 / 拓扑序正确）。

12. **9 人超出平台默认上限**。插件 `maxMembers` 默认 8。→ 生成文件顶部写明必须改成 9，`export_profile.py` 每次运行都警告。

13. **`reasoningEffort: ""` 是非法值**。原 `modelPolicy` 的 standard 与 fast 档都写了空字符串。空串不会被框架清洗，会被当成一个非法强度传下去。→ 改为**省略字段**，`check_team.py` 拦截。

14. **引用校验工具对 CSSCI 结构性失效**（我实测过，不是推测）：
    ```
    api.crossref.org/journals/1002-4921  (中国社会科学)      → 404
    api.crossref.org/journals/1000-3894  (数量经济技术经济研究) → 404
    api.openalex.org/sources/issn:1002-4921                   → 404
    ```
    高星工具 `citegate`(102★) 对合法 CSSCI 条目记 `NOT FOUND (title similarity 0.00)`；`bibtex-verifier`(143★) 还把真实的 LeCun/Bengio/Hinton Nature 2015 误判为作者错误。→ 不引入，改自写 `verify_paper.py`。

15. **statcheck 不可用**。`MicheleNuijten/statcheck`(194★ GPL-3) 实测中文四种常见写法只认 1 种（`t(120)=2.45, p=0.016` ✅；`t=2.45，p<0.01`、全角 `t（120）＝2.45`、`F(2,45)=3.10，p<0.001` 全 ❌），Python 移植版在 pandas 3.0/numpy 2.5 下直接抛 `_UFuncNoLoopError`。→ `verify_paper.py` 自实现 t/F/χ²/Z 分布（Lentz 连分式算正则化不完全 beta/gamma），9/9 自检通过。

### 已存在但一直没人发现的坑

16. **Word 输出链路是断的**。`formatter_agent.md:115` 与 `:539` 用 `pandoc --reference-doc=template.docx`，但仓库里**根本没有 template.docx**。真正的 docx 能力藏在 `skills/corpus-paper-archiving/scripts/docx_build.py`（宋体 12pt / 1.5 行距 / 首行缩进 2 字 / 黑体分级标题 / TOC 域 / 页码域 / md 表格转真表格），从未接入流程。→ 新增 `scripts/docx_build_submission.py`（含 GB/T 7713.2 题名页、中图分类号、三线表）+ `selftest_docx.py` 进 CI。

17. **索引自己过期**。`llms.txt` 原先是手写的，技能改名后仍留旧名（如 `Full-empirical-analysis-skill`），外部智能体照索引找不到文件。→ 改为 `gen_llms.py` 生成物 + `--check`。

18. **手册自己过期**。`docs/论文攻坚组-团队配置手册.docx` 封面写「六成员」、名册写「七名成员」、技能写「68 个」、任务写「11 个」，全部与实际不符——而它长得最像官方文件，比 README 更容易被当真。→ 改为 `gen_manual.py` 从 `team.json` 现算生成。

## 三、第 8 条（CNKI）的真话

调研结论不乐观，但必须说清：

- **知网没有公开 API**，GitHub 上没有任何项目靠第三方付费 API 做 CNKI 检索。MCP 全家桶最高仅 56★。
- 四位数星的两个是**入库通道不是检索器**：`jasminum`(7325★, AGPL-3.0) 用 Zotero 取 cookie 补全中文 PDF 元数据；`translators_CN`(4783★, AGPL) 在结果页一键存条目。
- **已死的不要碰**：`bughandler/cnki-downloader`(1769★) README 首行自认接口失效；`yanzhou/CnkiSpider`(680★) Deprecated，Python 2；`qiuqingyu/CNKICrawler`(159★) 停在 2017。
- `cookjohn/cnki-skills`(1021★) 功能最贴需求（高级检索带 CSSCI/北大核心筛选、导出 GB/T 7714），但**无 LICENSE**，只能借鉴它的设计（10 个 skill 拆分 + 检测到腾讯滑块即暂停等人工过）。
- **万方/维普/NCPSSD 更差**：万方最高 30★ 无许可停在 2017，NCPSSD 最高 1★。

→ 落地写成 `docs/cnki-workflow.md` 的四条路线（合规度降序）：A 人工检索+官方导出（推荐主线）→ B 真浏览器 CDP + 人工过验证码 → C `SepineTam/cnki-mcp`(56★ GPL-3.0，专业检索式最完整) → D 别做：requests+正则爬虫。

### 顺带确认的两个空白

- **中文脚注制 CSL 不存在**。GB/T 7714 是文后参考文献表国标，脚注制是 **CY/T 121-2015**，GitHub 上没有它的高星 CSL，最接近的是一个 20★ 无许可的 2022 年仓库。这块只能自建。
- **中文投稿信（cover letter）生成器在 GitHub 上不存在**。检索 total=4，全是 0★ 或无关。

## 四、技能库：84 个，8 族

| 族 | 数量 | 说明 |
|---|---|---|
| `auto-empirical-research-skills` | 32 | 实证全谱系（Python/R/Stata/StatsPAI + AER 19 连 + p-hacking 11 连 + 去 AIGC） |
| `socialscience-zh` | **16** | **本次原创**，见下 |
| `supervisor-skills` | 12 | 写作、润色、审稿、图表设计、选题评估 |
| `ai-research-skills` | 10 | 头脑风暴、创意方法、论文写作（ML/系统） |
| `academic-research-skills` | 5 | 深度调研、论文流水线、5 席评审、PRISMA 筛选 |
| `deep-research-skills` | 5 | 分阶段深度调研编排 |
| `academic-figure-skills` | 3 | 图分析、图绘制、图转 PPTX |
| `corpus-paper-archiving` | 1 | 逐篇精读建可核对读档 |

### `socialscience-zh`（16 个原创，3722 行）

**统计方法**（7 个）：`reliability-validity`（α/折半/重测、内容与结构效度）、`efa-cfa`（KMO+Bartlett、平行分析、CFA 拟合、AVE/CR）、`anova-family`（单/双/多因素、ANCOVA、MANOVA、**判别分析**、重复测量、事后比较）、`regression-family`（多元/分层/逐步、logistic、Poisson/负二项、**分位数回归**、正则化、交互项中心化）、`mediation-moderation`（简单/并行/链式中介、**PROCESS Model 1–76 全覆盖**、Bootstrap BCa）、`sem-pls`（SEM 路径、多组比较、PLS-SEM）、`nonparametric-tests`（t 检验、Mann-Whitney、Wilcoxon、Kruskal-Wallis、卡方）。

**设计与质量**（3 个）：`sample-size-power`、`common-method-bias`（Harman / 标记变量 / ULMC）、`spss-syntax`（可复算的语法而非点点点）。

**中文社科实务**（6 个，原本全是空白）：`qualitative-analysis`（扎根/案例/访谈/三级编码/Kappa）、`journal-submission`（选刊、cover letter、中图分类号、GB/T 7713.2 摘要要件）、`manuscript-formatting`（GB/T 7714-2015、CY/T 121-2015 脚注制、三线表、交稿 Word）、`response-letter-zh`（中文核心期刊返修答复）、`research-ethics`（知情同意、匿名化、伦理批件）、`bibliometrics-review`（PRISMA 2020、CNKI 专业检索式、CiteSpace/VOSviewer）。

> 原有技能库里 `选刊`/`投稿信`/`扎根`/`案例研究`/`量表开发`/`问卷设计`/`选题`/`返修`/`中图分类号` 的 grep 命中数**全是 0**。`rebuttal` 有 8 处但全是 ICLR/NeurIPS 语境，中文核心期刊的返修信写法一处都没有。

## 五、九个 CI 脚本（全绿）

```
check_skills.py                       OK   技能总数 84 ｜ 被引用 84 ｜ 问题 0
check_team.py                         OK   成员 9 ｜ 任务 13 ｜ 技能 84 ｜ 错误 0 ｜ 警告 0
gen_agents.py --check                 OK   9 份提示词与单一数据源逐字一致
gen_llms.py --check                   OK   索引与 team.json / skills/ 一致
apply_models.py --dry-run --strict    OK   9 个成员模型与 modelPolicy 一致
gen_manual.py --check                 OK   手册可现算（段落 222 / 表格 15）
export_profile.py --check             OK   dsh-profile.yml 与 team.json 同步
verify_paper.py --selftest            OK   9/9 统计分布数值精度
selftest_docx.py                      OK   交稿 Word 链路活着（38322 字节，含表格与题名页）
```

## 六、还剩什么没做

1. **脚注制 CSL 需要自建**（CY/T 121-2015，GitHub 无现成方案）。
2. **中文投稿信模板**只能手写（GitHub 不存在）。
3. **`socialscience-zh` 的统计技能未在真实数据上跑过**——都是方法论 + 代码骨架，第一次真用会暴露缺口。建议拿一份已有问卷数据跑一遍 t4b 全链路。
4. **CI 只在 config 层校验，不跑真稿**——`verify_paper.py` 需要真实 manuscript.md 才有意义，目前只有合成测试稿。
5. **许可风险仍在**：84 个技能中 48 个无任何许可声明，按著作权法默认规则版权归原作者，本仓库不构成再分发授权。若要商用或公开发布，需要逐个确认或替换。

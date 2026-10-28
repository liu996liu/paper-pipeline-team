# 第三方组件与许可声明

本仓库是多个来源的技能库整合发行版，**不适用单一开源许可证**。各目录的许可情况如下，使用或再分发时请遵守对应条款。

## MIT 许可

可自由使用、修改、再分发，需保留原版权声明与许可文本（许可文件已随目录保留）。

| 目录 | 版权方 | 许可文件位置 |
|---|---|---|
| `skills/auto-empirical-research-skills/aer-skills/` | Copyright (c) 2026 Bryce Wang | `LICENSE` |
| `skills/auto-empirical-research-skills/p-hacking-skills/` | Copyright (c) 2026 Bryce Wang | `LICENSE` |
| `skills/auto-empirical-research-skills/aer-skills/examples/replication-package-skeleton/` | MIT（代码部分） | `LICENSE` |
| `skills/supervisor-skills/drawio-reconstruction/` | Copyright (c) 2026 VCG-Bench Authors | `LICENSE` |
| `skills/ai-research-skills/`（10 个 skill） | 见各 `SKILL.md` frontmatter | 声明于 frontmatter |

## CC-BY-4.0（署名）

可再分发与改编，须**署名原作者**。

- `skills/supervisor-skills/benchmark-paper-template/`
- `skills/supervisor-skills/figure-designer/`
- `skills/supervisor-skills/idea-evaluator/`
- `skills/supervisor-skills/pre-submission-reviewer/`
- `skills/supervisor-skills/tech-paper-template/`
- `skills/supervisor-skills/vibe-research-workflow/`

## CC-BY-NC-SA-4.0（署名 + 非商用 + 相同方式共享）

⚠️ **限制最强的一组**：须署名；**不得用于商业目的**；修改后的衍生版本须以相同许可发布。

- `skills/supervisor-skills/intro-drafter/`
- `skills/supervisor-skills/paper-polish/`
- `skills/supervisor-skills/paper-writer/`
- `skills/supervisor-skills/supervisor-deep-research/`

> 由于包含上述组件，**本仓库整体不可用于商业用途**，也不能整体标注为 MIT。

## 本仓库原创：`skills/socialscience-zh/`（16 个技能）

作者原创，随本仓库以 **CC-BY-NC-SA-4.0** 发布（署名 + 非商用 + 相同方式共享）。

**实证统计族（10 个）**

- `reliability-validity` 信度与效度
- `efa-cfa` 探索性与验证性因子分析
- `anova-family` 方差分析全家族
- `regression-family` 回归分析全家族
- `mediation-moderation` 中介与调节效应
- `sem-pls` 结构方程与 PLS-SEM
- `common-method-bias` 共同方法偏差
- `sample-size-power` 样本量与功效分析
- `nonparametric-tests` 非参数与基础差异检验
- `spss-syntax` SPSS 语法与结果导出

**中文投稿实务族（6 个，2026-10-28 补齐）**

- `qualitative-analysis` 质性研究：扎根理论三级编码、案例研究、访谈、编码信度
- `journal-submission` 选刊与投稿：CSSCI/北大核心目录核查、选刊矩阵、GB/T 7713.2 摘要要件、中图分类号、cover letter
- `manuscript-formatting` 交稿排版：GB/T 7714-2015 引注、三线表、脚注制、OMML 公式、套刊模板
- `response-letter-zh` 中文修回说明：接受 / 部分接受 / 礼貌反驳三策略
- `research-ethics` 研究伦理：伦理审查、知情同意、匿名化、AIGC 使用声明
- `bibliometrics-review` 文献计量与系统综述：PRISMA 2020 计数、CNKI 专业检索式、CiteSpace/VOSviewer

这些技能是参考公开的统计学教材、期刊方法与各软件官方文档编写的操作规范，
不含任何第三方受版权保护的文本或代码。

## 未声明许可的目录

以下目录内未发现许可证文件或 `license` 字段。按著作权法默认规则，版权归原作者所有，本仓库仅作技术聚合与迁移示例，不构成授权。

- `skills/academic-research-skills/`
- `skills/academic-figure-skills/`
- `skills/deep-research-skills/`
- `skills/corpus-paper-archiving/`
- `vendor/agent-teams/`
- `skills/supervisor-skills/rebuttal-guidance/`
- `skills/auto-empirical-research-skills/` 下：`de-aigc-skills/`、`full-empirical-python/`、`full-empirical-r/`、`full-empirical-stata/`、`literature-review-tools/`、`statspai/`

如你是上述内容的权利人且不希望被收录，请提交 issue，将立即移除。

## 团队配置部分

`agents/`、`team.json`、`README.md`、`llms.txt`、`CITATION.cff`、`docs/`、`scripts/`、`skills/socialscience-zh/` 为本仓库作者原创整理，采用 **CC-BY-NC-SA-4.0** 许可：

- **署名**：引用、转载或改编时须注明来源（本仓库地址）与作者。
- **非商业**：不得用于商业目的。
- **相同方式共享**：基于本配置的修改版本须以相同许可发布。

如需商业授权，请联系仓库作者。

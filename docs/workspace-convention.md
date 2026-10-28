# 工作区目录约定

所有交付物落在 `paper/<slug>/<NN-stage>/` 下。**未落盘等于未交付，落错目录也等于未交付。**

`<slug>` 用论文的英文短名（小写连字符，如 `sizheng-youth-green-lowcarbon`），整个项目期间不变。

---

## 一、目录结构

```
paper/<slug>/
├── 00-brief/          t1   选题定位、研究问题、目标期刊、实证路径判定
├── 10-literature/     t2   文献读档（每篇一份 md）、综述矩阵、引文库
│   └── imports/       t2   CNKI/万方/NoteExpress 导出的 RIS 原始文件
├── 20-data/           t4/t4b 数据字典、清洗脚本、清洗后数据
├── 30-analysis/       t4/t4b 分析脚本（一键复算）、结果表、稳健性
├── 40-figures/        t5   图表规格、绘图脚本、导出图
├── 50-draft/          t6/t8/t9 稿件，按版本分子目录
│   ├── v1/            t6 初稿
│   ├── v2/            t8 修订稿
│   └── v3/            t9 去 AI 痕迹后
├── 60-review/         t7/t10.5/t11 审查意见、复核记录、验收结论
│   ├── r1/            t7 第 1 轮
│   ├── r2/            t7 第 2 轮
│   ├── t9/            t9 的文体前后对照
│   ├── diff/          t10.5 差异复审台账
│   └── escalation.md  maxRounds 用尽后的升级裁决包
└── 90-submit/         t11 通过的最终交付件（Word/PDF、图和表）
```

> **`10-literature/imports/` 为什么要单独列**：知网/万方/维普没有公开 API，
> 正确做法是人工检索后导出 RIS / NoteExpress 文件，再由脚本解析。
> 把原始导出文件留在 `imports/` 里，是做可复现性审查时唯一能证明
> 「这批文献确实检索到了、不是编的」的东西。规程见 `docs/cnki-workflow.md`。

---

## 二、分阶段落盘规则

| 阶段 | 任务 | 必须落盘的产物 |
|---|---|---|
| 选题 | t1 | `00-brief/brief.md`（研究问题、创新点、目标期刊、体例要求）、`00-brief/empirical-path.md`（走计量/问卷/两者）、`00-brief/target-journals.md` |
| 文献 | t2 | `10-literature/notes/<作者-年份>.md` 每篇一份、`10-literature/review-matrix.md`（按争议点组织的矩阵）、`10-literature/records.json`（引文库）、`10-literature/search-log.md`（可复现的检索式） |
| 实证 | t4 | `20-data/data-dictionary.md`、`30-analysis/run_all.py`、`30-analysis/results/*.csv`、`30-analysis/tables.md`、`30-analysis/robustness.md` |
| 问卷 | t4b | `20-data/data-dictionary.md`、`30-analysis/analysis.py`（或 `analysis.R`）、`30-analysis/results/*.csv`、`30-analysis/reliability-validity.md`、`30-analysis/tables.md` |
| 图表 | t5 | `40-figures/figure-plan.md`、`40-figures/scripts/*`、`40-figures/out/*.{png,svg,pdf}` |
| 写作 | t6 | `50-draft/v1/manuscript.md`、`50-draft/v1/claims-evidence-map.md` |
| 审查 | t7 | `60-review/r<N>/findings.md`（含 verdict 与逐条缺陷） |
| 修订 | t8 | `50-draft/v2/manuscript.md`、`60-review/r<N>/response-to-review.md` |
| 去 AI | t9 | `50-draft/v3/manuscript.md`、`60-review/t9/style-diff.md` |
| 定稿 | t10 | `50-draft/v3/manuscript-final.md`（或 `90-submit/pre-submit.md`） |
| 差异复审 | t10.5 | `60-review/diff/t9-to-t10.md` |
| 验收 | t11 | `60-review/r<N>/gate-report.md`、`90-submit/` 最终件 |

> **交稿件的额外产物**：确定投某刊后，`90-submit/` 下应同时有
> `manuscript.docx`（用 `scripts/docx_build_submission.py` 生成）、`cover-letter.md`、
> `highlights.md`（若该刊要求）、`figures/`（按刊要求的分辨率与格式）。
> 只交 `.md` 视为未完成投稿准备。

---

## 三、三条硬规矩

**1. 数字只有一个来源。** 正文、表格、图注里出现的任何统计量，都必须能在 `30-analysis/results/*.csv` 里找到同值单元格。做不到就说明这个数字是手写的，一律退回。

**2. 版本不覆盖。** t8、t9、t10 各建新目录，保留上一版。审查意见是针对某一版的，覆盖掉就没法回溯"这条意见改在哪一版"。

**3. 脚本要能一键复算。** `run_all.py` / `analysis.R` / `analysis.do` 从原始数据一次跑完全部分析与出表。跑不出来的结果，视为不存在。

---

## 四、命名

- 稿件：`manuscript.md`，放版本目录下，不再加后缀
- 结果表：`results/<分析名>.csv`，小写连字符
- 图：`fig<N>_<短名>.<ext>`，N 与正文出现顺序一致
- 文献读档：`notes/<第一作者姓><年份>.md`，如 `notes/zhang2023.md`
- 审查意见：`findings.md`，轮次目录区分

中文文件名只用于交付给编辑的最终件（`90-submit/`），中间产物一律用英文名，避免跨平台与脚本处理问题。

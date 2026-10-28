---
name: "spss-syntax"
description: "SPSS 语法编写与结果导出：用 .sps 语法文件替代界面点击，实现可复算、可版本控制的统计分析。覆盖数据导入与变量定义、反向计分、缺失值、描述统计、信度、因子分析、ANOVA、回归、中介调节、结果导出（OMS/SAVE TRANSLATE）。含中文变量名与编码问题的处理、语法文件组织规范、以及与 Python/R 结果的交叉验证方法。适用于要求复现包可审计的中文社科投稿。"
metadata:
  version: "1.0.0"
---

# SPSS 语法（可复算的分析流程）

## 为什么必须用语法而不是点界面

中文社科研究里 SPSS 界面点击占绝对主流，但它有四个致命问题：

1. **不可复现**：别人（包括三个月后的你）无法重现你点了哪些菜单、选了哪些选项。
2. **不可审计**：t11 的复现包闸门要求"重跑能得出同样数字"，界面点击无法被重跑。
3. **易出错无痕迹**：误点一个选项，结果就不同，且没有记录。
4. **版本漂移**：SPSS 不同版本的对话框默认值会变（如缺失值处理默认值）。

**语法文件 `.sps` 解决全部四个问题**：它是纯文本，能进 git，能被审阅，
能被原样重跑。审稿人要求提供分析代码时，`analysis.sps` 就是答案。

---

## 一、语法文件组织规范

**一个主控文件 + 分阶段子文件**，主控文件按顺序 `INSERT` 子文件：

```
30-analysis/
├── 00_master.sps          # 主控：按顺序跑完全部分析
├── 01_import.sps          # 导入数据、定义变量、值标签
├── 02_clean.sps           # 反向计分、缺失值、异常值、合成量表分
├── 03_descriptives.sps    # 样本描述、描述统计
├── 04_reliability.sps     # 信度
├── 05_factor.sps          # EFA / CFA（AMOS 另算）
├── 06_anova.sps           # 方差分析
├── 07_regression.sps      # 回归
├── 08_mediation.sps       # 中介调节（PROCESS 或手动）
└── 09_export.sps          # 导出结果表
```

`00_master.sps`：

```spss
* 主控文件：一次运行完成全部分析.
* 数据路径用相对路径，确保换机器可跑.
CD 'D:\paper\project'.

INSERT FILE='01_import.sps'.
INSERT FILE='02_clean.sps'.
INSERT FILE='03_descriptives.sps'.
INSERT FILE='04_reliability.sps'.
INSERT FILE='05_factor.sps'.
INSERT FILE='06_anova.sps'.
INSERT FILE='07_regression.sps'.
INSERT FILE='09_export.sps'.

* 完成.
```

**语法文件头部必须写注释块：**

```spss
* ============================================================.
* 文件名：04_reliability.sps
* 用途：各维度 Cronbach's α
* 输入：data_clean.sav
* 输出：reliability.csv, reliability_view.spv
* 依赖：02_clean.sps 已完成反向计分
* 最后修改：2026-10-28
* ============================================================.
```

---

## 二、数据导入与变量定义

```spss
* 读 Excel.
GET DATA
  /TYPE=XLSX
  /FILE='20-data\raw\questionnaire.xlsx'
  /SHEET=name 'Sheet1'
  /CELLRANGE=FULL
  /READNAMES=ON
  /ASSUMEDSTRWIDTH=32767.
DATASET NAME raw WINDOW=FRONT.

* 读 CSV（注意编码，中文常需 UTF8）.
GET DATA
  /TYPE=TXT
  /FILE='20-data\raw\data.csv'
  /ENCODING='UTF8'
  /DELIMITERS=","
  /QUALIFIER='"'
  /ARRANGEMENT=DELIMITED
  /FIRSTCASE=2
  /VARIABLES=
    id A20
    gender F1.0
    age F3.0
    Q1 TO Q20 F2.0.
DATASET NAME raw WINDOW=FRONT.

* 变量标签与值标签（必做，否则输出全是 Q1 Q2 看不懂）.
VARIABLE LABELS
  gender '性别'
  age    '年龄'
  Q1     '我对自己未来的发展充满信心'
  Q2     '我经常感到压力很大'.

VALUE LABELS gender 1 '男' 2 '女'.
VALUE LABELS Q1 TO Q20
  1 '完全不同意' 2 '不同意' 3 '一般' 4 '同意' 5 '完全同意'.

* 缺失值定义.
MISSING VALUES Q1 TO Q20 (9, 99).
```

**中文变量名的坑：** SPSS 支持中文变量名，但导出 CSV 和与其他软件交互时极易乱码。
**建议变量名用英文/拼音，变量标签用中文**，输出时标签会覆盖显示。

---

## 三、反向计分与量表合成

```spss
* 反向题：Q5 Q9 Q14 为反向题，5 点量表.
COMPUTE Q5_R  = 6 - Q5.
COMPUTE Q9_R  = 6 - Q9.
COMPUTE Q14_R = 6 - Q14.
VARIABLE LABELS Q5_R '压力感受（反向）'.
EXECUTE.

* 或者用 RECODE（更灵活）.
RECODE Q5 (1=5) (2=4) (3=3) (4=2) (5=1) (ELSE=SYSMIS) INTO Q5_R.
EXECUTE.

* 维度分 = 题目均值（推荐均值而非加总，便于跨维度比较与处理缺失）.
COMPUTE dim1 = MEAN(Q1, Q2, Q3, Q4, Q5_R).
COMPUTE dim2 = MEAN(Q6, Q7, Q8).

* 若允许部分缺失（如至少答 80% 才算有效）.
COMPUTE dim1 = MEAN.4(Q1, Q2, Q3, Q4, Q5_R).   /* 至少 4 题有效 */
EXECUTE.

* 可靠性检查：反向计分后应与正向题正相关.
CORRELATIONS /VARIABLES=Q1 Q2 Q5_R /PRINT=TWOTAIL NOSIG.
```

**反向计分的自检：** 反向转换后跑一次 `RELIABILITY ... /SUMMARY=TOTAL`，
看校正的项总计相关性。如果反向题的该项仍为负，说明**要么转换方向错了，
要么原题表述有歧义**，必须人工复核题目原话，不能靠调数字解决。

---

## 四、描述统计与样本描述

```spss
* 人口学分布.
FREQUENCIES VARIABLES=gender age education unit_type
  /FORMAT=AVALUE TABLE
  /STATISTICS=MEAN STDDEV MINIMUM MAXIMUM
  /ORDER=ANALYSIS.

* 连续变量描述.
DESCRIPTIVES VARIABLES=dim1 dim2 dim3
  /STATISTICS=MEAN STDDEV MIN MAX SEMEAN KURTOSIS SKEWNESS.

* 正态性检验.
EXAMINE VARIABLES=dim1 dim2 dim3
  /PLOT BOXPLOT HISTOGRAM NPPLOT
  /STATISTICS DESCRIPTIVES
  /CINTERVAL 95
  /MISSING LISTWISE
  /NOTOTAL.
```

`EXAMINE` 的 `NPPLOT` 出 K-S 与 Shapiro-Wilk；`HISTOGRAM` 出直方图；
`BOXPLOT` 出箱线图找异常值。

---

## 五、信度

```spss
* 逐维度.
RELIABILITY
  /VARIABLES=Q1 Q2 Q3 Q4 Q5_R
  /SCALE('维度一：职业认同') ALL
  /MODEL=ALPHA
  /STATISTICS=DESCRIPTIVE SCALE CORR
  /SUMMARY=TOTAL.

RELIABILITY
  /VARIABLES=Q6 Q7 Q8
  /SCALE('维度二：压力感受') ALL
  /MODEL=ALPHA
  /SUMMARY=TOTAL.

* 折半信度.
RELIABILITY
  /VARIABLES=Q1 TO Q10
  /SCALE('总量表') ALL
  /MODEL=SPLIT
  /SUMMARY=TOTAL.
```

`/SUMMARY=TOTAL` 是关键，输出"校正的项总计相关性"与"删除项后的 α"。

---

## 六、因子分析

```spss
* EFA：主轴因子 + 斜交旋转（社科推荐）.
FACTOR
  /VARIABLES=Q1 Q2 Q3 Q4 Q5_R Q6 Q7 Q8
  /MISSING=LISTWISE
  /PRINT=INITIAL KMO EXTRACTION ROTATION
  /FORMAT=SORT BLANK(.4)
  /PLOT=EIGEN
  /CRITERIA=FACTORS(3) ITERATE(50)
  /EXTRACTION=PAF
  /ROTATION=PROMAX.

* 若用主成分 + 正交旋转（中文期刊常见）.
FACTOR
  /VARIABLES=Q1 TO Q20
  /PRINT=INITIAL KMO EXTRACTION ROTATION
  /PLOT=EIGEN
  /CRITERIA=MINEIGEN(1) ITERATE(25)
  /EXTRACTION=PC
  /ROTATION=VARIMAX.
```

**CFA 在 SPSS 里做不了**（需要 AMOS 或 R 的 lavaan）。AMOS 是独立 GUI，
同样面临不可复现问题——**建议 CFA 用 lavaan 写脚本**，SPSS 只做 EFA 与描述。

---

## 七、方差分析

```spss
* 单因素 ANOVA + 事后比较 + 方差齐性.
ONEWAY dim1 BY group
  /STATISTICS=DESCRIPTIVES HOMOGENEITY WELCH
  /PLOT=MEANS
  /POSTHOC=TUKEY GAMESHOWELL ALPHA(0.05)
  /MISSING=ANALYSIS.

* 双因素（含交互）+ 简单效应.
UNIANOVA dim1 BY gender education
  /METHOD=SSTYPE(3)
  /INTERCEPT=INCLUDE
  /POSTHOC=education(TUKEY)
  /EMMEANS=TABLES(gender) COMPARE ADJ(BONFERRONI)
  /EMMEANS=TABLES(education) COMPARE ADJ(BONFERRONI)
  /EMMEANS=TABLES(gender*education)
  /PRINT=ETASQ HOMOGENEITY DESCRIPTIVE
  /CRITERIA=ALPHA(.05)
  /DESIGN=gender education gender*education.

* 重复测量.
GLM time1 time2 time3
  /WSFACTOR=time 3 Polynomial
  /METHOD=SSTYPE(3)
  /PRINT=ETASQ HOMOGENEITY DESCRIPTIVE
  /CRITERIA=ALPHA(.05)
  /WSDESIGN=time.

* 混合设计.
GLM pre post BY group
  /WSFACTOR=time 2 Polynomial
  /METHOD=SSTYPE(3)
  /PRINT=ETASQ HOMOGENEITY DESCRIPTIVE
  /EMMEANS=TABLES(group) COMPARE ADJ(BONFERRONI)
  /EMMEANS=TABLES(time) COMPARE ADJ(BONFERRONI)
  /EMMEANS=TABLES(group*time)
  /CRITERIA=ALPHA(.05)
  /WSDESIGN=time
  /DESIGN=group.
```

`/PRINT=ETASQ` 出效应量；`/PRINT=HOMOGENEITY` 出 Levene；
`/EMMEANS=...COMPARE ADJ(BONFERRONI)` 出简单效应并做校正。

---

## 八、回归

```spss
* 分层回归.
REGRESSION
  /MISSING=LISTWISE
  /STATISTICS=DEFAULTS CI(95) R ANOVA CHANGE COLLIN TOL
  /CRITERIA=PIN(.05) POUT(.10)
  /NOORIGIN
  /DEPENDENT=dim1
  /METHOD=ENTER gender age education
  /METHOD=ENTER iv1 iv2
  /METHOD=ENTER moderator iv1*moderator.

* 二元 logistic.
LOGISTIC REGRESSION VARIABLES y
  /METHOD=ENTER iv1 iv2 age gender
  /PRINT=CI(95) GOODFIT
  /CRITERIA=PIN(0.05) POUT(0.10) ITERATE(20) CUT(0.5).

* 有序 logistic.
PLUM satisfaction BY gender WITH iv1 iv2
  /CRITERIA=CIN(95) DELTA(0) LCONVERGE(0) MXITER(100) MXSTEP(5) PCONVERGE(1.0E-6) SINGULAR(1.0E-8)
  /LINK=LOGIT
  /PRINT=FIT PARAMETER SUMMARY TPARALLEL.
```

`/PRINT=TPARALLEL` 出**平行线检验**（比例优势假设），有序 logistic 必做。

---

## 九、中介与调节

**SPSS 原生不做中介分析。** 两条路：

### 路线 A：PROCESS 宏（Hayes）

```spss
* 先安装 PROCESS（Utilities > Custom Dialogs > Install Custom Dialog）.
* 安装后可用语法调用（宏名 process）.

process y=dim1
  /x=iv
  /m=mediator
  /cov=age gender
  /model=4
  /boot=5000
  /bc=1
  /seed=20261028
  /save=1.
```

参数含义：`model=4` 简单中介；`boot=5000` Bootstrap 次数；`bc=1` BCa；
`seed` **必须设**，否则每次结果略有不同，不可复现。

### 路线 B：手动语法（透明但繁琐）

```spss
* 第一步：M ~ X.
REGRESSION /DEPENDENT=mediator /METHOD=ENTER iv age gender
  /SAVE=PRED(resid_m).

* 第二步：Y ~ X + M.
REGRESSION /DEPENDENT=dim1 /METHOD=ENTER iv mediator age gender
  /SAVE=PRED(resid_y).

* 间接效应需手算 a*b，CI 需另做 Bootstrap（SPSS 不便）.
```

**结论：中介分析优先用 R（lavaan/mediation），SPSS 只作为与导师/合作者沟通的副本。**
R 能给出完整 CI、能进版本控制、能被复现包闸门验证。

---

## 十、结果导出

```spss
* 导出为 CSV（机器可读，进复现包）.
OMS /SELECT TABLES
  /IF COMMANDS=['Reliability Statistics' 'ANOVA']
  /DESTINATION FORMAT=CSV
  OUTFILE='30-analysis\results\reliability_and_anova.csv'.

* 导出清洗后的数据（供 R/Python 交叉验证）.
SAVE TRANSLATE
  /OUTFILE='20-data\clean\data_clean.csv'
  /TYPE=CSV
  /ENCODING='UTF8'
  /FIELDNAMES
  /REPLACE
  /CELLS=VALUES.

* 导出 .sav 供下游使用.
SAVE OUTFILE='20-data\clean\data_clean.sav'
  /COMPRESSED.
```

`OMS`（Output Management System）能把表格直接导出成 CSV，是自动化的关键。
不导出的话，结果只能靠手工抄进论文，抄错的风险很高。

---

## 十一、与 R / Python 的交叉验证（强烈建议）

**关键数字至少用两个工具算一遍。** SPSS、R、Python 在缺失值处理、
Type III SS、因子提取方法上默认值不同，结果会有差异，这种差异本身就是发现。

```r
# R 读 SPSS 导出的 CSV，重算核心结果
library(haven)
df <- read_sav("20-data/clean/data_clean.sav")
fit <- aov(dim1 ~ group, data = df)
summary(fit)
# 与 SPSS 输出的 F 值对比，差异 >0.001 就要查原因
```

常见差异来源：

| 差异来源 | SPSS 默认 | R 默认 |
|---|---|---|
| 方差分析平方和类型 | Type III | Type I（`aov`） |
| 缺失值 | 成列删除 | 报错或 na.rm |
| EFA 提取方法 | 主成分 | 主轴因子 |
| 因子旋转 | 无 | 无 |
| 相关矩阵 | Pearson | Pearson |

**把交叉验证结果写进 `30-analysis/cross-validation.md`**，这会让 t11 的
复现包闸门非常轻松，也会让审稿人对数据可靠性有信心。

---

## 十二、常见错误清单

- [ ] 用界面点击而留不下语法文件
- [ ] 语法文件用了绝对路径，换机器跑不了
- [ ] 反向题未转换或转错方向
- [ ] 变量标签全是 Q1 Q2，输出看不懂
- [ ] 缺失值未定义，被当作有效值参与计算
- [ ] 未设随机种子（Bootstrap / 多重插补）
- [ ] 只在 SPSS 界面看结果，未导出 CSV
- [ ] 有序 logistic 未做平行线检验
- [ ] 双因素 ANOVA 用了 Type I SS（样本不平衡时会错）
- [ ] 重复测量未校正球形性
- [ ] 中介分析手工算 a×b 但没有 CI
- [ ] 中文变量名导致导出乱码

---

## 十三、交付清单

- [ ] `30-analysis/*.sps`：分阶段语法文件 + 主控文件
- [ ] `00_master.sps` 能从原始数据一路跑到导出结果
- [ ] `30-analysis/results/*.csv`：OMS 导出的机器可读结果
- [ ] `30-analysis/cross-validation.md`：与 R/Python 的交叉验证记录
- [ ] `docs/spss-version.md`：SPSS 版本号（版本差异会导致结果不同）
- [ ] 若用了 PROCESS：宏版本号 + 随机种子 + `.sps` 调用语法
- [ ] 若用了 AMOS：`.amw` 项目文件一并提交

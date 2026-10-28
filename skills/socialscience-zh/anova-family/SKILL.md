---
name: "anova-family"
description: "方差分析全家族：单因素 ANOVA、双因素与多因素 ANOVA（含交互）、ANCOVA 协方差分析、MANOVA 多元方差分析、判别分析（LDA/QDA，含与 logit 的取舍判据）、重复测量 ANOVA、混合设计 ANOVA、事后多重比较（LSD/Tukey/Bonferroni/Scheffé/Games-Howell）、简单效应分析。含前提检验（正态性/方差齐性/球形性）、违反前提时的替代方案、效应量报告（η²/partial η²/Cohen's d）与 SPSS/R/Python 完整代码。适用于实验设计、组间比较、问卷分组差异分析。"
metadata:
  version: "1.0.0"
---

# 方差分析全家族

## 一、开工前必须做的三件前提检验

**跳过前提检验直接跑 ANOVA，是中文社科投稿被拒的高频原因。**
三个前提不满足，F 值和 p 值都不可信。

### 1.1 正态性

- 方法：Shapiro-Wilk（N<50）、Kolmogorov-Smirnov with Lilliefors（N≥50）、偏度峰度
  （|偏度|<3、|峰度|<10 可接受）。
- **ANOVA 对正态性有一定稳健性**，N>30 每组时轻微偏离可接受。
- 严重偏离时：数据变换（对数、平方根、Box-Cox），或改用非参数检验
  （见 `nonparametric-tests` 技能）。

### 1.2 方差齐性

- **Levene 检验**（基于中位数更稳健，SPSS 默认基于均值，建议选基于中位数）。
- p>0.05 视为齐性。
- **不齐时**：①Games-Howell 事后比较；②Welch ANOVA（只做单因素）；
  ③数据变换。**不许装作没看见直接跑标准 ANOVA。**

### 1.3 球形性（仅重复测量 / 被试内设计）

- **Mauchly 球形检验**。
- p<0.05 说明违反球形假设，须用 **Greenhouse-Geisser（ε<0.75）** 或
  **Huynh-Feldt（ε>0.75）** 校正自由度。
- **不校正直接报未校正自由度，是重复测量分析最常见的错误。**

---

## 二、单因素 ANOVA

### 2.1 使用场景
一个自变量（3 组及以上），一个连续因变量。

### 2.2 完整流程

```
1. 前提检验（正态 + Levene）
2. F 检验 → p<0.05 才继续
3. 效应量 η² = SS组间 / SS总
4. 事后比较（因为 3 组以上，必须做）
5. 报告均值 ± 标准差 + 显著性标记
```

**只报 F 和 p，不报效应量和事后比较，等于没做完。** 三组以上知道"有差异"
却不知道"谁和谁有差异"，结论无法落地。

### 2.3 效应量判读

| 指标 | 小 | 中 | 大 |
|---|---|---|---|
| η²（eta squared） | 0.01 | 0.06 | 0.14 |
| partial η² | 0.01 | 0.06 | 0.14 |
| Cohen's f | 0.10 | 0.25 | 0.40 |

### 2.4 代码

**R：**

```r
# 前提检验
shapiro.test(df$score[df$group == "A"])       # 正态
car::leveneTest(score ~ group, data = df)     # 方差齐性

# 单因素 ANOVA
fit <- aov(score ~ group, data = df)
summary(fit)                                   # F, p

# 效应量
library(effectsize)
eta_squared(fit)

# 事后比较（推荐 Tukey HSD 或 Games-Howell）
TukeyHSD(fit)
library(rstatix)
games_howell_test(df, score ~ group)          # 方差不齐时用

# 更完整的一站式
library(rstatix)
df %>% anova_test(score ~ group) %>%
       tukey_hsd(score ~ group)
```

**Python：**

```python
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols

# 前提检验
groups = [g["score"].values for _, g in df.groupby("group")]
stats.shapiro(df["score"])                     # 正态（近似）
stats.levene(*groups, center="median")         # 方差齐性

# ANOVA
model = ols("score ~ C(group)", data=df).fit()
table = sm.stats.anova_lm(model, typ=2)
print(table)

# 效应量 η²
ss_between = table["sum_sq"]["C(group)"]
ss_total = table["sum_sq"].sum()
print(f"η² = {ss_between/ss_total:.3f}")

# 事后比较
from statsmodels.stats.multicomp import pairwise_tukeyhsd
print(pairwise_tukeyhsd(df["score"], df["group"]))
```

**SPSS 语法：**

```spss
ONEWAY score BY group
  /STATISTICS=DESCRIPTIVES HOMOGENEITY WELCH
  /PLOT=MEANS
  /POSTHOC=TUKEY GAMESHOWELL ALPHA(0.05)
  /MISSING=ANALYSIS.
```

### 2.5 结果表模板

**表 4 不同组别在 XXX 上的差异（M±SD）**

| 组别 | N | M | SD | F | p | η² | 事后比较 |
|---|---|---|---|---|---|---|---|
| 低分组 | 112 | 3.42 | 0.71 | 5.83 | 0.003 | 0.028 | 低<高** |
| 中分组 | 158 | 3.61 | 0.68 | | | | |
| 高分组 | 142 | 3.78 | 0.66 | | | | |

注：** p<0.01。事后比较采用 Tukey HSD。

---

## 三、双因素 / 多因素 ANOVA（含交互）

### 3.1 核心：交互效应是重点

两个自变量的 ANOVA 有三个效应：主效应 A、主效应 B、**交互 A×B**。

**交互显著时，主效应的解释要极其小心**——因为 A 的作用依赖于 B 的水平。
这时应该做**简单效应分析**（见第五节），而不是继续解释主效应。

**只看主效应不看交互，是双因素设计最常见的误用。**

### 3.2 代码

**R：**

```r
# 双因素 + 交互
fit2 <- aov(score ~ gender * education, data = df)
summary(fit2)

# Type III SS（不平衡设计必须用，R 默认是 Type I）
library(car)
Anova(fit2, type = "III")

# 效应量
library(effectsize)
eta_squared(fit2, partial = TRUE)

# 可视化交互（必做，审稿人会要看）
library(ggplot2)
ggplot(df, aes(x = education, y = score, color = gender, group = gender)) +
  stat_summary(fun = mean, geom = "point", position = position_dodge(0.3)) +
  stat_summary(fun.data = mean_se, geom = "errorbar",
               position = position_dodge(0.3), width = 0.15) +
  labs(y = "得分", x = "教育程度", color = "性别") +
  theme_bw()
```

**Python：**

```python
import statsmodels.api as sm
from statsmodels.formula.api import ols

model = ols("score ~ C(gender) * C(education)", data=df).fit()
# typ=3 需要先设置对比编码
from statsmodels.stats.anova import anova_lm
print(anova_lm(model, typ=2))
print(anova_lm(model, typ=3))
```

**不平衡设计（各组样本量不等）必须用 Type III SS。** R 的 `aov()` 默认 Type I，
顺序不同结果不同，这是 R 用户最容易踩的坑。

### 3.3 结果表模板

**表 5 双因素方差分析结果**

| 变异来源 | SS | df | MS | F | p | partial η² |
|---|---|---|---|---|---|---|
| 性别 | 2.134 | 1 | 2.134 | 4.512 | 0.034 | 0.011 |
| 教育程度 | 8.762 | 2 | 4.381 | 9.263 | <0.001 | 0.044 |
| 性别×教育程度 | 1.982 | 2 | 0.991 | 2.096 | 0.124 | 0.010 |
| 误差 | 191.234 | 404 | 0.473 | | | |

注：N=410。采用 Type III 平方和（样本量不平衡）。

---

## 四、ANCOVA 协方差分析

### 4.1 什么时候用
有组别比较，但同时存在一个**需要控制的连续变量**（协变量），且该协变量与因变量相关。

典型场景：比较不同教学方法的成绩差异，但学生入学基线成绩不同 → 用基线成绩做协变量。

### 4.2 三条前提（比 ANOVA 更严格）

1. **协变量与因变量线性相关**（散点图检查）；
2. **回归斜率同质性**（组别×协变量交互不显著）—— 这条最常被忽略；
3. 协变量测量无误差（理论上要求，实际操作中说明即可）。

**斜率同质性不满足时不能用 ANCOVA**，否则校正后的均值差没有意义。

### 4.3 代码

```r
# 先检验斜率同质性
fit_slope <- aov(score ~ group * baseline, data = df)
summary(fit_slope)   # group:baseline 的 p 应 >0.05

# 斜率同质才做 ANCOVA
fit_ancova <- aov(score ~ group + baseline, data = df)
summary(fit_ancova)
library(emmeans)
emmeans(fit_ancova, ~ group)      # 校正后的边际均值，这是要报告的数
```

```python
import statsmodels.api as sm
from statsmodels.formula.api import ols

# 斜率同质性
print(sm.stats.anova_lm(ols("score ~ C(group) * baseline", data=df).fit(), typ=3))

# ANCOVA
m = ols("score ~ C(group) + baseline", data=df).fit()
print(sm.stats.anova_lm(m, typ=3))
```

**报告时必须给"校正后边际均值"（estimated marginal means），不是原始均值。**
这是 ANCOVA 的价值所在，只报原始均值等于没做校正。

---

## 五、简单效应分析

### 5.1 什么时候做
**交互效应显著时必做。** 交互不显著时做简单效应属于数据挖掘，不要做。

### 5.2 怎么做

```r
library(emmeans)

# 在 education 的每个水平上看 gender 的简单效应
emm <- emmeans(fit2, ~ gender | education)
pairs(emm, adjust = "bonferroni")     # 必须做多重比较校正

# 或者反过来
emmeans(fit2, ~ education | gender) %>% pairs(adjust = "bonferroni")
```

```python
# Python 用 pingouin 最方便
import pingouin as pg
pg.pairwise_tests(data=df, dv="score", between=["gender", "education"],
                  padjust="bonf")
```

### 5.3 多重比较校正（必须做，不许省）

| 方法 | 适用 | 保守程度 |
|---|---|---|
| **LSD** | 仅探索性、比较次数少 | 最宽松（不校正）**正式结论不要用** |
| **Bonferroni** | 通用，比较次数少时 | 最保守 |
| **Tukey HSD** | 所有两两比较 | 中等，推荐 |
| **Scheffé** | 任意复杂对比 | 很保守 |
| **Games-Howell** | 方差不齐 | 中等，推荐 |
| **Dunnett** | 多个组 vs 一个对照组 | 中等 |

**"做了 6 次比较都用 LSD，然后说 p<0.05 显著"是典型的假阳性。**
比较次数 ≥3 就必须校正，并写明用了哪种。

---

## 六、MANOVA 多元方差分析

### 6.1 什么时候用
有**多个相关的因变量**，想同时检验组别差异。

**注意：** 如果几个因变量彼此不相关，直接做多个 ANOVA 更好。MANOVA 的前提是
因变量之间中等相关（0.3–0.7）。

### 6.2 四个检验统计量（报哪个）

| 统计量 | 何时更优 |
|---|---|
| Pillai's Trace | **各组样本量不等时首选**（最稳健，推荐） |
| Wilks' Lambda | 样本量相等、前提满足时 |
| Hotelling's Trace | 两个组时 |
| Roy's Largest Root | 差异集中在一个维度时（最不稳健） |

**报 Pillai's Trace 最安全**，并说明选择理由。

### 6.3 代码

```r
fit_manova <- manova(cbind(dv1, dv2, dv3) ~ group, data = df)
summary(fit_manova, test = "Pillai")
# MANOVA 显著后，做单变量 ANOVA 追查是哪个因变量
summary.aov(fit_manova)
```

Python（statsmodels）：

```python
from statsmodels.multivariate.manova import MANOVA
mv = MANOVA.from_formula('dv1 + dv2 + dv3 ~ C(group)', data=df)
print(mv.mv_test())
```

---

## 六·补 判别分析（Discriminant Analysis）

**社会科学里用它的场合很少，别把它当常规工具。** 只有下面两种情形值得做：

1. **已知分组，想找一组能区分它们的指标**（如用消费行为区分"高频/低频用户"）
2. **分类预测**：给一个新样本判断它属于哪组

**如果因变量本身就是类别（有序/无序），正确答案是 logit 回归，不是判别分析。**
判别分析是 logit 的"老前辈"，在样本正态、协方差齐性时有微弱效率优势，
但它的前提（多元正态、组内协方差相等）比 logit 严格得多，解释性还更差。
**审稿人看到判别分析会先问"为什么不用 logit"。**

### 分类别数

| 分组数 | 方法 | R 函数 |
|---|---|---|
| 2 组 | 线性判别 LDA（Fisher） | `MASS::lda` |
| 2 组且协方差不等 | 二次判别 QDA | `MASS::qda` |
| ≥3 组 | 多类别 LDA | `MASS::lda`（自动多类） |

### 代码与必报指标

```r
library(MASS)
# 关键：先看协方差齐性（Box's M），不齐就转 QDA
ld <- lda(group ~ x1 + x2 + x3, data = train, CV = TRUE)   # CV=TRUE 做留一交叉验证
table(train$group, ld$class)          # 混淆矩阵
mean(ld$class == train$group)         # 留一命中率（比回代命中率高估少）
```

必报：**混淆矩阵**、**留一法（或 k 折）准确率**、**各组的先验概率**。
只报"回代准确率 92%"是典型高估——样本里每组的比例本身就能猜对不少。

```python
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import cross_val_score
lda = LinearDiscriminantAnalysis()
lda.fit(X, y)
print(cross_val_score(lda, X, y, cv=5))    # 交叉验证准确率
```

### 与 logit 的对照（建议同时报，成本很低）

| 指标 | 判别分析 | 多项 logit |
|---|---|---|
| 前提 | 多元正态 + 协方差齐性 | 无严格分布假设 |
| 输出 | 分类结果 + 判别函数 | 各变量的 OR 与显著性 |
| 可解释性 | 差（判别函数是线性组合，无直接含义） | 好（系数直接解释） |
| 社科主流度 | 低，多见于 1990s 文献 | **高，当前默认** |

**结论：除非导师明确要求或研究问题是纯分类预测，一律用 logit。**
真要做判别分析，必须同时报交叉验证准确率与混淆矩阵，并在方法部分说明
"因研究目的是分类预测，故采用判别分析"，否则审稿人会认为你不熟 logit。

---

## 七、重复测量 ANOVA

### 7.1 关键点：球形性

同一批人测多次（前测/后测/追踪），数据不独立，**必须用重复测量 ANOVA 而不是普通 ANOVA**。

Mauchly 检验 p<0.05 → 用 Greenhouse-Geisser（ε<0.75）或 Huynh-Feldt（ε>0.75）校正。

### 7.2 代码

```r
library(rstatix)
# 长格式数据：id, time, score
df %>% anova_test(dv = score, wid = id, within = time)
# 自动做 Mauchly 检验并给 GG 校正结果

# 事后比较
df %>% pairwise_t_test(score ~ time, paired = TRUE, p.adjust.method = "bonferroni")
```

```python
import pingouin as pg
pg.rm_anova(data=df, dv="score", within="time", subject="id", detailed=True)
pg.pairwise_tests(data=df, dv="score", within="time", subject="id", padjust="bonf")
```

**注意：** 重复测量数据里如果有被试缺失某一次测量，处理方法（删被试 / 用混合模型）
要写明。缺失多的建议直接用线性混合模型（LMM），比 RM-ANOVA 更稳健。

---

## 八、混合设计 ANOVA

### 8.1 场景
一个被试间变量（组别）+ 一个被试内变量（时间）。

### 8.2 代码

```r
df %>% anova_test(dv = score, wid = id, between = group, within = time)
# 输出三个效应：组别、时间、组别×时间
# 交互显著 → 做简单效应：在每组内看时间效应，或每个时间点上看组别效应
```

```python
import pingouin as pg
pg.mixed_anova(data=df, dv="score", within="time", between="group", subject="id")
```

**混合设计最常见的错误：** 交互显著后只解释主效应。正确做法是做简单效应
（如"干预组前后测差异显著，对照组不显著"——这才是交互的实际含义）。

---

## 九、违反前提时的替代方案

| 违反的前提 | 替代方案 | 备注 |
|---|---|---|
| 正态性严重偏离 | Kruskal-Wallis（单因素）/ Friedman（重复测量） | 见 `nonparametric-tests` |
| 方差齐性不满足 | Welch ANOVA + Games-Howell | 只适用单因素 |
| 球形性违反 | GG / HF 校正 | 必做 |
| 样本量极小（每组<10） | 非参数检验或置换检验 | 参数检验不可靠 |
| 因变量是二分/计数 | 不用 ANOVA，用 logistic / Poisson 回归 | 见 `regression-family` |
| 数据有嵌套结构（学生嵌套于班级） | 多层线性模型（HLM） | 普通 ANOVA 会低估标准误 |

**嵌套数据用普通 ANOVA 是严重的统计错误**（会把班级层面的效应算成个体层面的），
遇到这种数据结构必须用 HLM 或至少做聚类稳健标准误。

---

## 十、报告规范速查

**F 值格式：** `F(2, 407) = 5.83, p = 0.003, η² = 0.028`

- 括号里是（组间自由度, 组内自由度）
- p 报精确值，p<0.001 才写 p<0.001
- 效应量必报

**均值格式：** `M = 3.42, SD = 0.71`

**表格：** 三线表，注明 N、事后比较方法、显著性标记含义。

**文字与表格不能矛盾：** 正文说"显著高于"，表里的星号必须对应；反之亦然。
t11 的表文数字一致闸门会查这个。

---

## 十一、交付清单

- [ ] `30-analysis/anova.md`：前提检验结果、ANOVA 表、事后比较、简单效应、效应量
- [ ] `30-analysis/results/anova.csv`：机器可读结果
- [ ] 能一键重跑的脚本
- [ ] 交互效应图（双因素以上必做）
- [ ] 前提违反时的处理说明（用了什么替代方案、为什么）
- [ ] 正文段落：把统计结论写成人话（"高分组显著高于低分组，差距为 0.36 分，
      相当于 0.53 个标准差"，而不是只念数字）

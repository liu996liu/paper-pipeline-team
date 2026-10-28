---
name: "nonparametric-tests"
description: "非参数检验与基础差异检验：t 检验（独立/配对/单样本）、方差分析的非参数替代（Mann-Whitney U、Wilcoxon 符号秩、Kruskal-Wallis、Friedman、Scheirer-Ray-Hare）、卡方检验（拟合优度/独立性/Fisher 精确）、Spearman 与 Kendall 相关、置换检验与 Bootstrap 检验。含效应量（Cohen's d、r、Cramér's V）与 R/Python/SPSS 代码，适用于数据不满足参数假设或变量为等级/分类的情形。"
metadata:
  version: "1.0.0"
---

# 非参数检验与基础差异检验

## 零、先做选择决策树

```
因变量是什么？
├─ 连续 + 满足正态与方差齐性 → 参数检验（t / ANOVA）
├─ 连续 + 不满足 → 非参数检验（本技能）
├─ 有序等级（1-5 李克特、ABCD 评级）→ 非参数检验
├─ 二分类 → 卡方 / Fisher
└─ 计数 → Poisson / 负二项（见 regression-family）
```

**"不满足正态就一律非参数"是过度保守。** 中心极限定理保证了：每组 N>30 时，
t 检验和 ANOVA 对正态性偏离相当稳健。真正该用非参数的是：

- 样本量小（每组 <30）且明显偏斜；
- 存在极端离群值且不能删；
- 因变量本质是有序等级（不是连续）；
- 明显天花板/地板效应。

**"因为是李克特量表所以用非参数"是常见误解。** 多题合成后的量表分通常近似连续，
可以用参数检验；单题 5 点量表争议较大，稳妥做法是两种都跑，结果一致就报参数、
在脚注说明非参数结果相同；不一致则以非参数为准。

---

## 一、t 检验

### 1.1 三种 t 检验

| 类型 | 场景 | 例子 |
|---|---|---|
| 单样本 t | 一组分数与已知标准比较 | 样本均值与全国常模 3.5 比 |
| 独立样本 t | 两组独立被试比较 | 男 vs 女 |
| 配对样本 t | 同一批人两次测量 | 前测 vs 后测 |

### 1.2 前提与效应量

前提：正态性（每组）、方差齐性（独立样本）。

**Levene 检验 p>0.05 → 方差齐，读"假定方差相等"那一行；
p<0.05 → 方差不齐，读"不假定方差相等"（Welch）那一行。**
**读错行是 SPSS 用户最常见的错误。**

效应量 Cohen's d：

```
d = (M1 - M2) / SD_pooled
```

| d | 判定 |
|---|---|
| 0.2 | 小 |
| 0.5 | 中 |
| 0.8 | 大 |

### 1.3 代码

**R：**

```r
# 独立样本
t.test(dv ~ group, data = df, var.equal = FALSE)   # Welch，推荐默认

# 效应量
library(effectsize)
cohens_d(dv ~ group, data = df)

# 配对样本
t.test(df$pre, df$post, paired = TRUE)

# 单样本
t.test(df$dv, mu = 3.5)
```

**Python：**

```python
from scipy import stats
import numpy as np

g1 = df.loc[df.group == "A", "dv"]
g2 = df.loc[df.group == "B", "dv"]

# 独立样本（Welch）
t, p = stats.ttest_ind(g1, g2, equal_var=False)

# 效应量
def cohens_d(a, b):
    n1, n2 = len(a), len(b)
    s = np.sqrt(((n1-1)*a.var(ddof=1) + (n2-1)*b.var(ddof=1)) / (n1+n2-2))
    return (a.mean() - b.mean()) / s

print(f"t={t:.3f}, p={p:.4f}, d={cohens_d(g1,g2):.3f}")

# 配对
stats.ttest_rel(df["pre"], df["post"])
```

**SPSS：**

```spss
T-TEST GROUPS=group(1 2)
  /MISSING=ANALYSIS
  /VARIABLES=dv
  /CRITERIA=CI(.95).

T-TEST PAIRS=pre WITH post (PAIRED)
  /CRITERIA=CI(.9500)
  /MISSING=ANALYSIS.

T-TEST /TESTVAL=3.5 /VARIABLES=dv /MISSING=ANALYSIS.
```

---

## 二、非参数替代（两组比较）

### 2.1 Mann-Whitney U（独立样本，替代独立 t）

**适用**：两组独立、因变量有序或连续但非正态。

**报告要注意**：Mann-Whitney 比的是**秩**不是均值。所以报告应该给**中位数**
（Mdn）与四分位距（IQR），而不是均值±标准差。

```r
wilcox.test(dv ~ group, data = df, exact = FALSE)
library(rstatix)
wilcox_effsize(dv ~ group, data = df)   # 效应量 r
```

```python
from scipy import stats
u, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
# 效应量 r = z / sqrt(N)
```

```spss
NPTESTS
  /INDEPENDENT TEST (dv) GROUP (group)
  /MISSING SCOPE=ANALYSIS USERMISSING=EXCLUDE
  /CRITERIA ALPHA=0.05 CILEVEL=95.
```

### 2.2 Wilcoxon 符号秩（配对样本，替代配对 t）

```r
wilcox.test(df$pre, df$post, paired = TRUE)
```

```python
stats.wilcoxon(df["pre"], df["post"])
```

**注意**：样本量很小（N<10）时用精确检验；SPSS 默认给渐近近似，
小样本要手动勾"精确"。

### 2.3 效应量 r 的判读

| r | 判定 |
|---|---|
| 0.10 | 小 |
| 0.30 | 中 |
| 0.50 | 大 |

---

## 三、Kruskal-Wallis（三组以上，替代单因素 ANOVA）

```r
kruskal.test(dv ~ group, data = df)

# 显著后做事后两两比较（必须校正）
library(rstatix)
df %>% kruskal_test(dv ~ group)
df %>% dunn_test(dv ~ group, p.adjust.method = "bonferroni")
```

```python
stats.kruskal(*[g["dv"].values for _, g in df.groupby("group")])
# 事后用 scikit-posthocs
import scikit_posthocs as sp
sp.posthoc_dunn(df, val_col="dv", group_col="group", p_adjust="bonferroni")
```

**Kruskal-Wallis 显著只说明"至少有两组不同"，必须做事后比较才知道哪两组。**
不做事后比较等于没做完。

**报告**：给各组的中位数与 IQR，不要给均值。

---

## 四、Friedman 检验（重复测量，替代重复测量 ANOVA）

```r
friedman.test(as.matrix(df[, c("t1","t2","t3")]))

# 事后
library(rstatix)
df_long %>% friedman_effsize(score ~ time | id)
df_long %>% pairwise_wilcox_test(score ~ time, paired = TRUE,
                                 p.adjust.method = "bonferroni")
```

```python
stats.friedmanchisquare(df["t1"], df["t2"], df["t3"])
```

---

## 五、Scheirer-Ray-Hare（双因素非参数）

**双因素 ANOVA 的非参数替代。** 当数据严重偏斜或有序，但仍要看两个因素的
主效应与交互时使用。

```r
library(rcompanion)
scheirerRayHare(dv ~ factorA * factorB, data = df)
```

**注意**：它只能给出主效应和交互的 H 统计量，**不能做简单效应分析**。
需要简单效应时，改用对齐秩变换（ART）后跑参数 ANOVA：

```r
library(ARTool)
m <- art(dv ~ factorA * factorB, data = df)
anova(m)
art.con(m, "factorA:factorB", adjust = "holm")
```

ART 是目前双因素非参数分析里最推荐的方案，因为它保留了交互的可解释性。

---

## 六、卡方检验

### 6.1 拟合优度（一个分类变量的分布是否符合预期）

```r
chisq.test(c(120, 180, 100), p = c(1/3, 1/3, 1/3))
```

```python
stats.chisquare([120, 180, 100])
```

### 6.2 独立性（两个分类变量是否相关）

```r
tab <- table(df$gender, df$willingness)
chisq.test(tab)
# 效应量
library(rcompanion)
cramerV(tab)
```

```python
import pandas as pd
from scipy.stats import chi2_contingency
tab = pd.crosstab(df["gender"], df["willingness"])
chi2, p, dof, expected = chi2_contingency(tab)
print(f"χ²={chi2:.3f}, df={dof}, p={p:.4f}")
```

```spss
CROSSTABS
  /TABLES=gender BY willingness
  /FORMAT=AVALUE TABLES
  /STATISTICS=CHISQ PHI
  /CELLS=COUNT EXPECTED ROW COLUMN
  /COUNT ROUND CELL.
```

### 6.3 使用条件（必须检查）

| 条件 | 处理 |
|---|---|
| 所有期望频数 ≥5 | 用 Pearson χ² |
| 有期望频数 <5 但 ≥1 的格子不超过 20% | 用连续性校正（Yates） |
| 有期望频数 <1，或 >20% 的格子 <5 | **改用 Fisher 精确检验** |
| 2×2 表且 N<40 | Fisher 精确检验 |

**`chi2_contingency` 默认不做 Yates 校正（`correction=True` 时对 2×2 才做）。**
R 的 `chisq.test` 对 2×2 默认做 Yates 校正，会与 Python 有细微差异，
报告时要说明用了哪个。

```r
fisher.test(tab)     # 2×2 或小样本
```

### 6.4 效应量 Cramér's V

```
V = sqrt(χ² / (N × (min(r,c) - 1)))
```

| V | 小 | 中 | 大 |
|---|---|---|---|
| df=1 (2×2) | 0.10 | 0.30 | 0.50 |
| df=2 | 0.07 | 0.21 | 0.35 |
| df=3 | 0.06 | 0.17 | 0.29 |

**只报 χ² 和 p 不报 V，在中文期刊里通常会被要求补。**

---

## 七、相关分析

### 7.1 三种相关

| 方法 | 变量要求 | 测的是什么 |
|---|---|---|
| Pearson | 两个都连续、线性、近似正态 | 线性关系 |
| Spearman | 至少一个有序，或非正态 | 单调关系（秩相关） |
| Kendall τ | 有序、小样本、有大量并列值 | 单调关系（更稳健） |

### 7.2 代码

```r
cor(df[, c("v1","v2","v3")], method = "pearson")
cor.test(df$v1, df$v2, method = "spearman")

# 相关矩阵 + 显著性星号（论文用）
library(Hmisc)
rcorr(as.matrix(df[, c("v1","v2","v3")]), type = "pearson")

# 或者 psych
library(psych)
corr.test(df[, c("v1","v2","v3")], use = "complete")
```

```python
from scipy import stats
r, p = stats.pearsonr(df["v1"], df["v2"])
rho, p = stats.spearmanr(df["v1"], df["v2"])

# 相关矩阵 + p 值
import pingouin as pg
pg.pairwise_corr(df, columns=["v1","v2","v3"], method="pearson")
```

### 7.3 相关矩阵表模板（论文必备）

**表 12 各变量均值、标准差与相关系数**

| 变量 | M | SD | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|---|
| 1. 变量A | 3.42 | 0.71 | 1 | | | |
| 2. 变量B | 3.61 | 0.68 | 0.412** | 1 | | |
| 3. 变量C | 3.28 | 0.74 | 0.287** | 0.331** | 1 | |
| 4. 变量D | 3.55 | 0.66 | 0.198* | 0.244** | 0.356** | 1 |

注：N=412。* p<0.05，** p<0.01（双尾）。

**区分效度要求 √AVE > 相关系数**，所以这张表要和信效度表对照看
（见 `reliability-validity`）。

---

## 八、置换检验与 Bootstrap（现代替代方案）

**当参数假设不满足、又不想损失信息时，置换检验往往是最优解。**

### 8.1 置换检验（组间差异）

```r
library(coin)
independence_test(dv ~ group, data = df)     # 精确置换检验
```

```python
import numpy as np
def permutation_test(a, b, n=10000):
    obs = a.mean() - b.mean()
    pooled = np.concatenate([a, b])
    cnt = 0
    for _ in range(n):
        np.random.shuffle(pooled)
        d = pooled[:len(a)].mean() - pooled[len(a):].mean()
        if abs(d) >= abs(obs):
            cnt += 1
    return obs, cnt / n
```

**优势**：不要求任何分布假设，对离群值稳健，结果直观（"随机打乱后出现这么大
差异的概率"）。**中文期刊接受度在上升，可以在稳健性检验里报一组。**

### 8.2 Bootstrap 置信区间（均值、中位数、相关系数的 CI）

```python
from scipy.stats import bootstrap
import numpy as np

res = bootstrap((df["dv"].values,), np.mean, n_resamples=5000,
                confidence_level=0.95, method="BCa", random_state=42)
print(res.confidence_interval)
```

**报告均值时给 Bootstrap CI 而不是只给 t 检验的 CI，对小样本偏斜数据更可靠。**

---

## 九、报告规范速查

| 检验 | 报告格式 |
|---|---|
| 独立 t | `t(410) = 2.34, p = 0.020, d = 0.28` |
| 配对 t | `t(119) = 3.45, p = 0.001, d = 0.42` |
| Mann-Whitney | `U = 8421.5, z = -2.14, p = 0.032, r = 0.11`；配 Mdn 与 IQR |
| Wilcoxon | `Z = -3.21, p = 0.001, r = 0.29` |
| Kruskal-Wallis | `H(2) = 8.42, p = 0.015, η²H = 0.06` |
| Friedman | `χ²(2) = 12.34, p = 0.002, Kendall's W = 0.18` |
| 卡方 | `χ²(2, N=412) = 8.42, p = 0.015, Cramér's V = 0.14` |
| 相关 | `r = 0.412, p < 0.001`；或 `ρ = 0.386, p < 0.001` |

**共通用词对照：**

| ❌ 错误 | ✅ 正确 |
|---|---|
| 差异显著（只说显著不说方向） | A 组显著高于 B 组（M=3.61 vs 3.28） |
| p<0.05 | p = 0.032（精确值） |
| 有显著差异 | 差异具有统计学意义（或直接给方向+数值） |
| 无显著差异 | 差异不显著（不等于"没有差异"，尤其小样本） |

---

## 十、常见错误清单

- [ ] Levene 检验后读错了 t 检验的行（方差不齐时读了"假定方差相等"）
- [ ] 只报 p 值不报效应量
- [ ] Mann-Whitney 报均值±SD（应报中位数与 IQR）
- [ ] Kruskal-Wallis 显著后不做事后比较
- [ ] 卡方检验不检查期望频数直接报结果
- [ ] 2×2 表小样本不用 Fisher 精确检验
- [ ] 卡方不报 Cramér's V
- [ ] 相关分析不区分 Pearson / Spearman
- [ ] 多组比较不做多重比较校正
- [ ] 把"差异不显著"写成"两组相同"
- [ ] 李克特数据默认用非参数而不检查是否真的需要
- [ ] 双向非参数检验（Scheirer-Ray-Hare）后强行解释交互

---

## 十一、交付清单

- [ ] `30-analysis/basic-tests.md`：各检验的方法选择理由、结果、效应量
- [ ] `30-analysis/results/`：相关矩阵、组间比较的 CSV
- [ ] 一键重跑脚本
- [ ] 箱线图 / 带误差棒的均值图（组间比较必备）
- [ ] 相关矩阵表（论文版格式，含 M/SD 与显著性星号）
- [ ] 正文段落：把检验结论写成"谁比谁高多少、差多少个百分点或标准差"

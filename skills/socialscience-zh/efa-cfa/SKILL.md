---
name: "efa-cfa"
description: "探索性与验证性因子分析：KMO 与 Bartlett 球形检验、EFA 的载荷矩阵与因子数判定（特征值/碎石图/平行分析三法）、旋转方式选择、CFA 拟合指标判读与修正、多组测量等价性检验。给出 Python(factor_analyzer/semopy)、R(lavaan/psych)、SPSS/AMOS 完整代码与结果表模板。适用于量表结构验证、维度划分论证，以及审稿人追问因子结构是否成立的时候。"
metadata:
  version: "1.0.0"
---

# EFA 与 CFA

## 顺序不能反

```
样本够 + KMO 达标 → EFA（探索）→ 依据结果定维度 → CFA（验证，最好换一半样本或另采样本）
```

**用同一批数据先 EFA 再 CFA 是可以的，但必须在文中说明**，因为这是"用数据定结构、
再用同一数据验证结构"，存在循环论证风险。更严谨的做法：随机分半，一半做 EFA，
一半做 CFA；或 EFA 用预调研样本，CFA 用正式样本。分半是成本最低的补救，
审稿人看到分半会加分。

**先做 KMO，KMO 不达标不许做 EFA。**

---

## 一、KMO 与 Bartlett

```python
from factor_analyzer.factor_analyzer import calculate_kmo, calculate_bartlett_sphericity
import pandas as pd

kmo_all, kmo_model = calculate_kmo(df)
chi2, p = calculate_bartlett_sphericity(df)
print(f"KMO = {kmo_model:.3f}   Bartlett χ² = {chi2:.2f}, p = {p:.4f}")
```

```r
library(psych)
KMO(df)          # 总体 MSA 与逐题 MSA
cortest.bartlett(cor(df), n = nrow(df))
```

```spss
FACTOR
  /VARIABLES=Q1 TO Q20
  /MISSING=LISTWISE
  /PRINT=INITIAL KMO EXTRACTION ROTATION
  /CRITERIA=MINEIGEN(1) ITERATE(25)
  /EXTRACTION=PC
  /ROTATION=VARIMAX.
```

判定：

| 指标 | 阈值 | 不达标怎么办 |
|---|---|---|
| KMO | ≥0.7 可做；0.6–0.7 勉强；<0.6 不可做 | 加样本、删低 MSA 的题、或换指标 |
| Bartlett p | <0.001 | p 不显著说明变量间无相关，不适合降维 |

逐题 MSA 看对角线：**<0.5 的题单独考虑删除**，删了会改善整体 KMO。

---

## 二、EFA

### 2.1 因子数怎么定（三法一致才稳）

1. **特征值 >1（Kaiser 准则）**：最常用也最容易高估因子数。**单独用它不够。**
2. **碎石图拐点**：看曲线由陡变缓的位置。主观但直观。
3. **平行分析（parallel analysis）**：最可靠。把实际特征值与随机数据特征值比较，
   取实际值大于随机值的个数。

```r
library(psych)
fa.parallel(df, fa = "fa", n.iter = 1000)
# 输出建议的因子数，图表直接可放进附录
```

```python
from factor_analyzer import FactorAnalyzer
import numpy as np

# 平行分析（手写，无需额外依赖）
def parallel_analysis(df, n_iter=1000):
    n, p = df.shape
    eig_real = np.linalg.eigvalsh(np.corrcoef(df.T))[::-1]
    eig_rand = np.zeros((n_iter, p))
    for i in range(n_iter):
        rnd = np.random.normal(size=(n, p))
        eig_rand[i] = np.linalg.eigvalsh(np.corrcoef(rnd.T))[::-1]
    # 95 分位
    thresh = np.percentile(eig_rand, 95, axis=0)
    return eig_real, thresh, int((eig_real > thresh).sum())

real, thresh, nfac = parallel_analysis(df)
print(f"平行分析建议因子数：{nfac}")
```

**三法结果不一致时，以平行分析为准，并在文中说明分歧。**

### 2.2 提取与旋转

| 选择 | 什么时候用 |
|---|---|
| **主成分法（PCA）** | SPSS 默认，但严格说不是因子分析。中文期刊广泛接受，可用 |
| **主轴因子法（PAF）** | 更贴近因子模型，理论更正确 |
| **最大似然（ML）** | 可做 χ² 检验，配合 CFA 使用 |

| 旋转 | 适用 |
|---|---|
| **方差最大正交旋转（Varimax）** | 假设因子间不相关（社科量表里这个假设常常不成立） |
| **斜交旋转（Promax / Oblimin）** | 允许因子相关，**社科研究更推荐**。选它就要报因子间相关矩阵 |

**用斜交旋转时，报"模式矩阵"和"结构矩阵"两个**，只报一个是漏项。

### 2.3 载荷判读

| 载荷 | 判定 |
|---|---|
| ≥0.5 | 良好 |
| 0.4–0.5 | 可接受，需说明 |
| <0.4 | 该题贡献不足，考虑删除 |
| 跨载荷（两个因子都 >0.4） | 结构不清，删题或重新设计 |
| 单因子载荷差 <0.2 | 同上 |

累积解释方差：社科研究 **≥50%** 可接受，≥60% 良好。低于 50% 要说明原因，
不能装作没看见。

### 2.4 EFA 结果表模板

**表 3 探索性因子分析结果（N=412，斜交旋转，Promax）**

| 题项 | 因子1 | 因子2 | 因子3 | 共同度 |
|---|---|---|---|---|
| Q1 | **0.812** | 0.043 | 0.112 | 0.684 |
| Q2 | **0.776** | 0.089 | 0.034 | 0.612 |
| Q6 | 0.051 | **0.834** | 0.077 | 0.712 |

注：KMO=0.876，Bartlett χ²(153)=3421.55，p<0.001。累积解释方差 63.42%。
仅显示载荷 ≥0.4 的项，加粗为该题主载荷。

---

## 三、CFA

### 3.1 拟合指标（每个都要报，缺一个就被追问）

| 指标 | 可接受 | 良好 | 说明 |
|---|---|---|---|
| χ²/df | <5 | <3 | 受样本量影响大，N>500 时几乎必然显著，须说明 |
| RMSEA | <0.08 | <0.05 | 报告 90% CI，上限须 <0.08 |
| CFI | >0.90 | >0.95 | 增量拟合指数 |
| TLI | >0.90 | >0.95 | 惩罚复杂模型 |
| SRMR | <0.08 | <0.05 | 标准化残差均方根，对样本量不敏感 |
| GFI / AGFI | >0.90 / >0.85 | — | 老指标，中文期刊仍常要求 |

**只报 CFI 一个指标是不合格的。** 至少报 χ²/df、RMSEA、CFI、TLI、SRMR 五个。

### 3.2 R lavaan 实现

```r
library(lavaan)

model <- '
  F1 =~ Q1 + Q2 + Q3 + Q4 + Q5
  F2 =~ Q6 + Q7 + Q8 + Q9
  F3 =~ Q10 + Q11 + Q12 + Q13
'

fit <- cfa(model, data = df, estimator = "MLR")   # MLR 稳健估计，推荐
summary(fit, fit.measures = TRUE, standardized = TRUE)

# 标准化载荷、CR、AVE
std <- standardizedSolution(fit)
loadings <- std[std$op == "=~", c("rhs", "est.std")]
# 按因子分组算 CR / AVE...
```

**用 MLR（稳健最大似然）而不是默认 ML**：社科数据普遍非正态（Likert 5 点），
MLR 能纠正。报告时说明用了稳健估计。

### 3.3 Python semopy 实现

```python
import semopy

desc = """
F1 =~ Q1 + Q2 + Q3 + Q4 + Q5
F2 =~ Q6 + Q7 + Q8 + Q9
F3 =~ Q10 + Q11 + Q12 + Q13
"""
model = semopy.Model(desc)
res = model.fit(df)
stats = semopy.calc_stats(model)
print(stats.T)     # CFI / TLI / RMSEA / GFI / AGFI / NFI
print(model.inspect(std_est=True))   # 标准化载荷
```

### 3.4 模型修正（必须极其克制）

当拟合不达标时可以做修正，但**每次修正都要有理论依据，不能纯看修正指数（MI）**：

- **允许残差相关**：只在同一维度内、且理论上可解释（如两道表述近似的题）时做。
  跨维度加残差相关是典型的"为拟合而拟合"，审稿人会抓。
- **删题**：载荷 <0.4 或 MI 极高且理论上站不住时删。删了必须重报全部指标，
  并说明删题理由。
- **不许**：为了 CFI 好看而反复试、试到过 0.9 为止。修正次数要如实报告。

**报告的诚实做法：** 写一行"初始模型 χ²/df=3.8、RMSEA=0.092、CFI=0.881；
依据 MI 与理论允许题 7 与题 9 残差相关后，χ²/df=2.4、RMSEA=0.061、CFI=0.945"。
把修正前后的数字都放出来，比只报修正后的可信一百倍。

### 3.5 多组测量等价性（跨群体比较必做）

如果论文要比较两组（如男女、城乡、不同学历）的均值或路径系数，**必须**先检验
测量等价性，否则"差异"可能只是测量不同：

```
形态等价（configural）→ 载荷等价（metric）→ 截距等价（scalar）→ 误差方差等价
```

判定用 ΔCFI <0.01 与 ΔRMSEA <0.015（Cheung & Rensvold 2002 的常用阈值）。
**至少达到截距等价，才能比较潜均值。**

```r
fit_config <- cfa(model, data = df, group = "gender")
fit_metric <- cfa(model, data = df, group = "gender", group.equal = "loadings")
fit_scalar <- cfa(model, data = df, group = "gender",
                  group.equal = c("loadings", "intercepts"))
anova(fit_config, fit_metric, fit_scalar)
```

---

## 四、EFA / CFA 结果不一致怎么办

这是最常见也最容易被审稿人抓住的问题。

**情形 1：EFA 得到 4 因子，CFA 却拟合很差**
- 先查是不是 EFA 的因子数定多了（平行分析 vs 特征值>1 的分歧）；
- 再查跨载荷题：EFA 里跨载荷的题在 CFA 里会拖累拟合，删掉重跑；
- 报告时如实写"EFA 建议 4 因子，CFA 显示 3 因子结构拟合更优，结合理论取 3 因子"。

**情形 2：CFA 拟合好但某个维度 AVE <0.5**
- 该维度题目异质性高，可考虑拆分或合并维度；
- 若 CR>0.7 仍可保留，在局限里说明。

**情形 3：题目在某样本聚成一维，另一样本聚成多维**
- 检查是不是样本特征差异（如学生 vs 在职）；
- 做多组 CFA 检验；若结构确实不同，这可能本身就是发现，可写成论文的一部分。

---

## 五、交付清单

- [ ] `30-analysis/efa-cfa.md`：KMO/Bartlett、因子数判定三法结果、载荷矩阵、拟合指标表
- [ ] `30-analysis/results/`：`loadings.csv`、`fit_indices.csv`、`correlation.csv`
- [ ] 能重跑出上述结果的脚本
- [ ] 分半说明（用了哪个种子、两半样本量）
- [ ] 模型修正的过程记录：修正前指标 → 做了什么 → 修正后指标 → 理论依据
- [ ] 碎石图 / 平行分析图（进附录或正文）

**不许只报最终模型指标而不报初始模型指标。** 那是选择性报告。

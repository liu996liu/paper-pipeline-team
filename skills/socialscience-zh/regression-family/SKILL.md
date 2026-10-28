---
name: "regression-family"
description: "回归分析全家族：多元线性回归、逐步回归、分层/层级回归（hierarchical）、logistic 回归（二元/多项/有序）、Poisson 与负二项回归、岭回归与 Lasso、分位数回归、中介与调节的回归实现。含共线性/自相关/异方差/残差诊断、虚拟变量编码、交互项中心化、稳健标准误选择、模型比较（ΔR²/ΔF/AIC/BIC）与 R/Python/SPSS 代码。适用于问卷数据与二手数据的假设检验。"
metadata:
  version: "1.0.0"
---

# 回归分析全家族

## 零、先问三个问题再选模型

**选错模型比跑错代码更致命。** 动笔前先回答：

| 问题 | 答案 | 该用的模型 |
|---|---|---|
| 因变量是什么尺度？ | 连续 | 线性回归 / 分位数回归 |
| | 二分类（是/否） | 二元 logistic |
| | 多分类无序 | 多项 logistic |
| | 有序（1-5 李克特） | 有序 logistic **或** 线性回归（附论证） |
| | 计数（次数、人数） | Poisson / 负二项 |
| 核心目的？ | 解释（哪个变量影响大） | 标准回归 + 系数解释 |
| | 预测（谁预测得准） | 交叉验证 + 正则化 |
| | 因果 | 见 `aer-identification`（回归不等于因果） |
| 自变量多且相关？ | 是 | 岭回归 / Lasso / 主成分回归 |

**李克特 5 点量表当连续变量跑线性回归，是中文社科的普遍做法，但要说明理由**
（如"量表题数多、分布近似正态、前人研究惯例"），不能想当然。更严谨的做法是
同时跑有序 logistic 做稳健性检验。

---

## 一、多元线性回归

### 1.1 六条假设（每条都要检验，不能只跑不查）

| 假设 | 检验方法 | 违反后果 |
|---|---|---|
| 线性 | 偏残差图（component+residual plot） | 系数有偏 |
| 独立性 | Durbin-Watson（1.5–2.5 可接受） | 标准误低估 |
| 正态性 | Q-Q 图 + Shapiro-Wilk（残差） | 小样本下 p 值不可信 |
| 同方差性 | 残差-拟合值散点图 / Breusch-Pagan | 标准误有偏 |
| 无多重共线性 | VIF <5（严格 <3）/ 容忍度 >0.2 | 系数不稳定、符号反常 |
| 无强影响点 | Cook's D <1 / 标准化残差 >3 的比例 | 结论被少数点绑架 |

**VIF 是必报的。** 中文期刊审稿人几乎必问共线性。

### 1.2 完整代码

**R：**

```r
model <- lm(dv ~ iv1 + iv2 + iv3 + age + gender, data = df)
summary(model)

# 标准化系数（比较相对重要性必须用标准化）
library(lm.beta)
lm.beta(model)

# 共线性
library(car)
vif(model)                  # >5 需处理，>10 严重
# 自相关
car::durbinWatsonTest(model)
# 异方差
car::ncvTest(model)
# 强影响点
plot(model, which = 4)      # Cook's D 图
# 残差诊断四联图
par(mfrow = c(2, 2)); plot(model)

# 稳健标准误（异方差存在时）
library(sandwich); library(lmtest)
coeftest(model, vcov = vcovHC(model, type = "HC3"))
```

**Python：**

```python
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

model = smf.ols("dv ~ iv1 + iv2 + iv3 + age + C(gender)", data=df).fit()
print(model.summary())

# VIF
X = df[["iv1","iv2","iv3","age"]]
import pandas as pd
vif = pd.DataFrame({
    "var": X.columns,
    "VIF": [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
})
print(vif)

# 稳健标准误（HC3）
model_robust = model.get_robustcov_results(cov_type="HC3")
print(model_robust.summary())

# 标准化系数
from scipy import stats
z = df.copy()
for c in ["dv","iv1","iv2","iv3"]:
    z[c] = stats.zscore(z[c])
print(smf.ols("dv ~ iv1 + iv2 + iv3", data=z).fit().params)
```

**SPSS 语法：**

```spss
REGRESSION
  /MISSING=LISTWISE
  /STATISTICS=DESCRIPTIVES COEFF OUTS CI(95) R ANOVA COLLIN TOL CHANGE
  /CRITERIA=PIN(.05) POUT(.10)
  /NOORIGIN
  /DEPENDENT=dv
  /METHOD=ENTER iv1 iv2 iv3 age gender
  /RESIDUALS=DURBIN HISTOGRAM(ZRESID) NORMPROB(ZRESID)
  /CASEWISE=ALL OUTLIERS
  /SAVE=MAHAL COOK ZRESID.
```

`/STATISTICS=COLLIN TOL` 出 VIF；`/RESIDUALS=DURBIN` 出 DW 值。

### 1.3 结果表模板

**表 6 多元线性回归结果（因变量：XXX）**

| 变量 | 模型1 (β) | 模型2 (β) | 模型3 (β) |
|---|---|---|---|
| 控制变量 | | | |
| 性别（男=1） | 0.082 | 0.071 | 0.065 |
| 年龄 | -0.034 | -0.028 | -0.031 |
| 自变量 | | | |
| 变量A | | 0.342*** | 0.318*** |
| 变量B | | | 0.226*** |
| R² | 0.021 | 0.148 | 0.198 |
| ΔR² | | 0.127*** | 0.050*** |
| F | 2.314 | 18.452*** | 21.337*** |
| VIF 最大值 | 1.12 | 1.34 | 1.52 |

注：N=412。表中为标准化系数。*** p<0.001。

---

## 二、分层回归（hierarchical regression）

### 2.1 什么时候用

**这是中文社科最常见的模型呈现方式**：控制变量 → 主效应 → 交互项，逐层加入，
看 ΔR² 的显著性。

用途：
- 证明主效应在控制变量之后仍有解释力；
- 证明交互项/中介变量带来增量解释。

### 2.2 代码

```r
m1 <- lm(dv ~ gender + age + education, data = df)
m2 <- lm(dv ~ gender + age + education + iv, data = df)
m3 <- lm(dv ~ gender + age + education + iv + moderator + iv:moderator, data = df)
anova(m1, m2, m3)      # 看 ΔR² 与 ΔF
summary(m2)$r.squared - summary(m1)$r.squared
```

```python
m1 = smf.ols("dv ~ C(gender) + age + education", data=df).fit()
m2 = smf.ols("dv ~ C(gender) + age + education + iv", data=df).fit()
sm.stats.anova_lm(m1, m2)     # 模型比较
```

### 2.3 关键报告项

- 每层的 R² 与 ΔR²
- ΔR² 的 F 变化及其显著性（**这是分层回归的核心，不是只看最终模型**）
- 每层的 VIF

**只说"最终模型 R²=0.198"，不说增量从哪来，等于没用分层回归。**

---

## 三、逐步回归（stepwise）

### 3.1 强烈警告

**逐步回归在方法学上已被广泛批评**（Whittington 等，1990s 起）：

- 系数有偏且标准误低估（选择性偏差）；
- p 值不可信（多重比较未校正）；
- 结果不稳定（换样本变量集就变）；
- 无法处理共线性（两个高度相关变量只会留一个，留哪个随机）。

**中文期刊仍在用，但审稿人越来越不认。** 如果必须用：

1. 说明为什么用（如"探索性研究、无先验假设"）；
2. 同时报告全模型，让读者对比；
3. 在局限里承认其方法论局限。

**更好的替代：** 有理论依据就手动指定变量；要筛选就用 Lasso（有正则化、有交叉验证）。

### 3.2 代码（供必要时使用）

```r
# 三种方向：both / backward / forward
step(lm(dv ~ ., data = df[, c("dv","iv1","iv2","iv3","iv4")]),
     direction = "both", trace = 1)
```

```python
# Python 无内置逐步回归，需手写或用 mlxtend
from mlxtend.feature_selection import SequentialFeatureSelector
from sklearn.linear_model import LinearRegression
sfs = SequentialFeatureSelector(LinearRegression(), k_features="best",
                                forward=True, scoring="r2", cv=5)
sfs.fit(X, y)
```

---

## 四、Logistic 回归

### 4.1 二元 logistic

**场景：** 因变量是"是/否"（如"是否愿意生育二孩"）。

```r
model <- glm(y ~ x1 + x2 + age + gender, data = df, family = binomial)
summary(model)

# 优势比 OR 与 95% CI（这是要报告的核心结果）
exp(cbind(OR = coef(model), confint(model)))

# 模型拟合
library(ResourceSelection)
hoslem.test(df$y, fitted(model))        # Hosmer-Lemeshow 检验
# 伪 R²
library(pscl)
pR2(model)                              # McFadden / CoxSnell / Nagelkerke
# 分类准确率
caret::confusionMatrix(factor(as.numeric(fitted(model) > 0.5)), factor(df$y))
```

```python
import statsmodels.api as sm
model = smf.logit("y ~ x1 + x2 + age + C(gender)", data=df).fit()
print(model.summary())
# OR
import numpy as np
print(np.exp(model.params))
print(np.exp(model.conf_int()))
# 伪 R²
print("McFadden:", model.prsquared)
```

**报告要点：**
- 系数 B、标准误、Wald χ²、p、**OR 及其 95% CI**（OR 是核心，不能只报 B）
- 模型整体检验（似然比 χ²）
- 伪 R²（Nagelkerke 最常用，但要说明它不是"解释率"）
- Hosmer-Lemeshow 拟合优度
- 分类准确率与基准率对比（只说"准确率 85%"而不说基准率是欺骗）

### 4.2 多项 logistic（因变量 3 类以上无序）

```r
library(nnet)
model <- multinom(category ~ x1 + x2, data = df)
summary(model)
# 得到 k-1 组系数（相对于参照类）
```

```python
from statsmodels.discrete.discrete_model import MNLogit
model = MNLogit.from_formula("category ~ x1 + x2", data=df).fit()
```

**必须说明参照类是什么。** 不说明参照类，系数无法解释。

### 4.3 有序 logistic（因变量有序，如满意度 1-5）

```r
library(MASS)
model <- polr(factor(satisfaction) ~ x1 + x2, data = df, Hess = TRUE)
summary(model)
# 比例优势假设检验（关键！）
library(brant)
brant(model)
```

**比例优势假设（parallel regression assumption）必须检验。** 违反时：
- 改用偏比例优势模型；
- 或改用多项 logistic（放弃有序信息，但更稳健）。

**不检验比例优势假设直接报有序 logistic，是常见的方法学缺陷。**

```python
from statsmodels.miscmodels.ordinal_model import OrderedModel
model = OrderedModel(df["satisfaction"], df[["x1","x2"]], distr="logit").fit()
```

---

## 五、计数模型（Poisson / 负二项）

### 5.1 场景
因变量是次数（发表论文数、参与活动次数、生育子女数）。

### 5.2 关键：过度离散检验

**Poisson 假设均值=方差。** 社科数据几乎总是方差远大于均值（过度离散），
此时 Poisson 标准误被低估，p 值虚小。

**必须先检验：**

```r
library(AER)
model_p <- glm(count ~ x1 + x2, data = df, family = poisson)
dispersiontest(model_p)          # p<0.05 → 过度离散，改用负二项

library(MASS)
model_nb <- glm.nb(count ~ x1 + x2, data = df)
summary(model_nb)
```

```python
import statsmodels.api as sm
model_p = sm.GLM(df["count"], sm.add_constant(df[["x1","x2"]]),
                 family=sm.families.Poisson()).fit()
# 过度离散参数
pearson_chi2 = model_p.pearson_chi2
df_resid = model_p.df_resid
print("Dispersion:", pearson_chi2 / df_resid)   # >1.5 提示过度离散

model_nb = sm.NegativeBinomial(df["count"], sm.add_constant(df[["x1","x2"]])).fit()
```

**报告要点：**
- 系数（通常取指数后解释为发生率比 IRR）
- 是否用了负二项、为什么
- 零膨胀检验（如果零很多，考虑零膨胀 Poisson/负二项）

---

## 六、正则化回归（岭 / Lasso / 弹性网）

### 6.1 什么时候用
- 自变量很多（几十上百）且高度相关；
- 目的是预测而非解释；
- 需要自动变量筛选但不想用逐步回归。

### 6.2 三者区别

| 方法 | 惩罚项 | 效果 |
|---|---|---|
| 岭回归（Ridge） | L2 | 系数收缩但不为 0，保留所有变量 |
| Lasso | L1 | 系数可收缩为 0，自动筛选变量 |
| 弹性网（Elastic Net） | L1+L2 | 兼顾两者，相关变量组能一起保留 |

### 6.3 代码

```python
from sklearn.linear_model import RidgeCV, LassoCV, ElasticNetCV
from sklearn.preprocessing import StandardScaler
import numpy as np

X = StandardScaler().fit_transform(df[features])   # 必须标准化！否则惩罚不公平
y = df["dv"].values

ridge = RidgeCV(alphas=np.logspace(-3, 3, 50), cv=5).fit(X, y)
lasso = LassoCV(alphas=np.logspace(-3, 3, 50), cv=5).fit(X, y)
print("Ridge alpha:", ridge.alpha_)
print("Lasso alpha:", lasso.alpha_)
print("Lasso 保留的变量:", [f for f, c in zip(features, lasso.coef_) if c != 0])
```

```r
library(glmnet)
X <- as.matrix(df[, features]); y <- df$dv
cv_ridge <- cv.glmnet(X, y, alpha = 0)
cv_lasso <- cv.glmnet(X, y, alpha = 1)
plot(cv_lasso)
coef(cv_lasso, s = "lambda.min")
```

**重要：** 正则化系数**不能直接解释为效应大小**（有偏收缩）。若目的是解释，
用岭回归做变量重要性排序，再用标准回归报最终模型。

---

## 七、分位数回归

### 7.1 什么时候用
- 关注分布的不同位置（如"对高分位人群的影响更大"）；
- 数据有异方差或强影响点，均值回归不稳健；
- 分布严重偏斜（收入、支出）。

### 7.2 代码

```r
library(quantreg)
rq_fit <- rq(dv ~ iv1 + iv2, data = df, tau = c(0.1, 0.25, 0.5, 0.75, 0.9))
summary(rq_fit, se = "boot")      # bootstrap 标准误
```

```python
import statsmodels.formula.api as smf
for tau in [0.1, 0.25, 0.5, 0.75, 0.9]:
    m = smf.quantreg("dv ~ iv1 + iv2", df).fit(q=tau)
    print(f"tau={tau}:", m.params["iv1"])
```

**报告：** 画出系数随分位数变化的图（带 CI），比列表更有说服力。

---

## 八、交互项与中心化

### 8.1 中心化（做交互前必做）

```r
df$iv_c <- scale(df$iv, scale = FALSE)      # 均值中心化
df$mod_c <- scale(df$mod, scale = FALSE)
model <- lm(dv ~ iv_c * mod_c, data = df)
```

**为什么要中心化：** 不中心化时主效应系数是"当调节变量为 0 时的效应"，
而 0 往往在数据范围外（如年龄=0），主效应没有意义。中心化后主效应变成
"在调节变量均值处的效应"，可解释。

**注意：** 中心化不改变交互项系数和显著性，只改变主效应的解释。

### 8.2 简单斜率分析（交互显著后必做）

```r
library(interactions)
interact_plot(model, pred = iv_c, modx = mod_c, interval = TRUE,
              modx.values = "plus-minus")
sim_slopes(model, pred = iv_c, modx = mod_c)
```

```python
# 手算：取调节变量 -1SD / 均值 / +1SD 三个点
for m in [-1, 0, 1]:
    slope = b_iv + b_interaction * m * df["mod"].std()
    # 报告该点的简单斜率及其显著性
```

---

## 九、模型比较与选择

| 指标 | 用途 | 注意 |
|---|---|---|
| R² / 调整 R² | 线性回归解释力 | 嵌套模型比较用 ΔR² |
| ΔR² + ΔF | 分层回归增量 | **核心指标** |
| AIC / BIC | 非嵌套模型比较 | 越小越好；BIC 惩罚更重 |
| 似然比检验 | 嵌套模型 | 需同一批样本 |
| 交叉验证 R²/RMSE | 预测能力 | 解释导向的研究不一定要 |
| Hosmer-Lemeshow | logistic 拟合 | p>0.05 表示拟合可接受 |
| AUC/ROC | 二分类判别力 | 0.7–0.8 可接受，>0.8 良好 |

**不许用 R² 大小来证明"模型对"** ——R² 高不代表模型设定正确，可能只是过拟合。

---

## 十、常见错误清单（逐条自查）

- [ ] 没报 VIF（共线性未检验）
- [ ] 李克特数据当连续变量，未说明理由
- [ ] 有序因变量用了线性回归，未设稳健性检验
- [ ] logistic 只报系数不报 OR 和 CI
- [ ] 计数数据直接跑 OLS（应用 Poisson/负二项）
- [ ] Poisson 未做过度离散检验
- [ ] 有序 logistic 未做比例优势假设检验
- [ ] 交互项未中心化，主效应无法解释
- [ ] 交互显著但未做简单斜率分析
- [ ] 逐步回归未说明方法学局限
- [ ] 只用 p 值不用效应量
- [ ] 样本量与自变量个数比例过低（经验值至少 10:1）
- [ ] 缺失值处理方式未说明
- [ ] 报告 R² 未区分 R² 与调整 R²

---

## 十一、交付清单

- [ ] `30-analysis/regression.md`：模型设定、诊断结果、结果表、解释段落
- [ ] `30-analysis/results/regression.csv`
- [ ] 一键重跑脚本
- [ ] 诊断图（残差图、Q-Q 图、VIF 表）打包进附录
- [ ] 正文段落：**系数要翻译成人话**——"变量 A 每提高 1 个标准差，因变量提高
      0.32 个标准差（β=0.32, p<0.001）"，不能只念 β 值

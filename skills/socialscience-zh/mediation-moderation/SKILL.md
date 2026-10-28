---
name: "mediation-moderation"
description: "中介效应与调节效应分析：简单中介、并行中介、链式（序列）中介、调节效应、有调节的中介（moderated mediation）、PROCESS 模型族（Hayes 76 种）的对应关系、Bootstrap 置信区间（BCa，5000 次以上）、简单斜率与 Johnson-Neyman。含 R(lavaan/mediation/processR)、Python(statsmodels) 完整代码、中介效应量分解表模板，以及逐步回归法为何已被淘汰的说明。适用于问卷研究的机制与边界条件检验。"
metadata:
  version: "1.0.0"
---

# 中介与调节效应分析

## 零、先纠正三个过时做法

**这三个做法在中文期刊里还在大量出现，但方法学上已经被否定十余年。**
审稿人（尤其是懂方法的）看到会直接质疑。

### ❌ 过时做法一：逐步回归法（Baron & Kenny 三步法）

老做法：X→Y 显著、X→M 显著、M→Y（控制 X）显著，就认为有中介。

**为什么被淘汰：**
- 它要求总效应显著，但**中介效应可以在总效应不显著时存在**（遮掩效应 / suppression）；
- 它不能给出中介效应的大小与置信区间；
- 它不能检验多个中介的相对贡献。

**现在的标准做法：** 直接检验间接效应 `a×b` 的 Bootstrap 置信区间。

### ❌ 过时做法二：Sobel 检验

Sobel 检验假设 `a×b` 服从正态分布，但**两个正态变量的乘积不是正态分布**，
所以它的 p 值偏保守、检验力低。已被 Bootstrap 取代。

**Sobel 只可作为补充，不能作为主要判据。**

### ❌ 过时做法三：只看 p 值不看 CI

**中介效应的判据是 Bootstrap 置信区间是否包含 0**，不是 p 值。
报 p 值不报 CI，等于没做现代中介分析。

---

## 一、简单中介（单中介）

### 1.1 模型

```
          M
        ↗   ↘
      a       b
    ↗           ↘
   X  ──c'──→   Y         c = c' + a×b
```

- `a`：X 对 M 的效应
- `b`：控制 X 后 M 对 Y 的效应
- `c'`：控制 M 后 X 对 Y 的直接效应
- `a×b`：间接效应（中介效应）
- `c`：总效应

### 1.2 结果怎么解释

| 情形 | 判定 | 表述 |
|---|---|---|
| 间接效应 CI 不含 0，直接效应 CI 不含 0，且同号 | **部分中介** | "M 在 X 与 Y 之间起部分中介作用" |
| 间接效应 CI 不含 0，直接效应 CI 含 0 | **完全中介** | "M 完全中介了 X 对 Y 的影响" |
| 间接效应 CI 不含 0，直接效应 CI 不含 0，但**异号** | **遮掩效应** | "M 起遮掩效应，间接效应与直接效应方向相反" |
| 间接效应 CI 含 0 | **无中介** | 如实报告，不要硬解释 |

**"完全中介"要慎用**：它意味着 X 对 Y 的全部影响都经由 M，这在社科里很少成立。
更稳妥的表述是"中介效应占总效应的 X%"。

### 1.3 效应量分解（必报）

```
总效应 c = 直接效应 c' + 间接效应 a×b
中介效应占比 = (a×b) / c
```

**占比超过 100% 或为负，说明存在遮掩效应**，不能报"占比 120%"了事。

### 1.4 R 实现（lavaan，推荐）

```r
library(lavaan)

model <- '
  M ~ a * X
  Y ~ b * M + cprime * X
  indirect := a * b
  total    := cprime + (a * b)
  prop     := (a * b) / (cprime + a * b)
'

fit <- sem(model, data = df, se = "bootstrap", bootstrap = 5000)
summary(fit, ci = TRUE, standardized = TRUE, fit.measures = TRUE)
```

**`se="bootstrap"` + `bootstrap=5000` 是底线配置。** 只写 `sem()` 默认不给
Bootstrap CI，报出来的间接效应就没有 CI。

### 1.5 R 实现（mediation 包，BCa 更方便）

```r
library(mediation)

med.fit  <- lm(M ~ X + age + gender, data = df)
out.fit  <- lm(Y ~ X + M + age + gender, data = df)
med.out  <- mediate(med.fit, out.fit, treat = "X", mediator = "M",
                    boot = TRUE, sims = 5000, boot.ci.type = "bca")
summary(med.out)
# 输出 ACME（平均因果中介效应）、ADE（平均直接效应）、Total Effect、Prop. Mediated
```

**`boot.ci.type = "bca"` 是你需要的。** 默认是 percentile，BCa 更准确。

### 1.6 Python 实现

```python
import numpy as np
import statsmodels.api as sm
from statsmodels.formula.api import ols

# 第一步：M ~ X
m_fit = ols("M ~ X + age + C(gender)", data=df).fit()
a = m_fit.params["X"]

# 第二步：Y ~ X + M
y_fit = ols("Y ~ X + M + age + C(gender)", data=df).fit()
b = y_fit.params["M"]
cprime = y_fit.params["X"]

# Bootstrap 间接效应（BCa 版本较复杂，这里给 percentile）
np.random.seed(42)
boot_ab = []
for _ in range(5000):
    idx = np.random.choice(len(df), len(df), replace=True)
    d = df.iloc[idx]
    a_b = ols("M ~ X + age + C(gender)", data=d).fit().params["X"]
    b_b = ols("Y ~ X + M + age + C(gender)", data=d).fit().params["M"]
    boot_ab.append(a_b * b_b)

boot_ab = np.array(boot_ab)
ci_low, ci_high = np.percentile(boot_ab, [2.5, 97.5])
print(f"间接效应 = {a*b:.4f}，95% CI = [{ci_low:.4f}, {ci_high:.4f}]")
# CI 不含 0 → 中介效应显著
```

**注意：** 上面是 percentile CI。要 BCa 需要 `scipy.stats.bootstrap` 或
`pingouin.mediation_analysis`：

```python
import pingouin as pg
pg.mediation_analysis(data=df, x="X", m="M", y="Y", covar=["age","gender"],
                      n_boot=5000, seed=42)
# 输出 ab（间接）、a、b、c'、c 及各自的 CI
```

---

## 二、并行中介（多个中介变量，彼此不因果）

### 2.1 模型
X 同时通过 M1 和 M2 影响 Y，M1 与 M2 之间**不假设因果顺序**。

### 2.2 代码

```r
model <- '
  M1 ~ a1 * X
  M2 ~ a2 * X
  Y  ~ b1 * M1 + b2 * M2 + cprime * X

  ind1 := a1 * b1
  ind2 := a2 * b2
  diff := ind1 - ind2        # 两个中介的相对贡献差异，这是关键！
  total_ind := ind1 + ind2
'

fit <- sem(model, data = df, se = "bootstrap", bootstrap = 5000)
summary(fit, ci = TRUE, standardized = TRUE)
```

**`diff := ind1 - ind2` 是并行中介的核心。** 如果两个中介的 CI 重叠，
不能说"其中 M1 起主要作用"——必须检验差异本身是否显著。

### 2.3 结果表模板

**表 7 并行中介效应分解**

| 路径 | 效应值 | Boot SE | 95% CI | 占总效应比 |
|---|---|---|---|---|
| 直接效应 X→Y | 0.182 | 0.061 | [0.062, 0.302] | 58.3% |
| 间接效应1 X→M1→Y | 0.086 | 0.031 | [0.031, 0.152] | 27.6% |
| 间接效应2 X→M2→Y | 0.044 | 0.022 | [0.008, 0.093] | 14.1% |
| 差异 (ind1-ind2) | 0.042 | 0.038 | [-0.028, 0.119] | — |
| 总效应 | 0.312 | 0.058 | [0.198, 0.426] | 100% |

注：Bootstrap 5000 次，偏差校正的百分位法（BCa）。

**差异的 CI 含 0**，说明不能断言 M1 的中介作用强于 M2——这正是需要报告的。

---

## 三、链式中介（序列中介）

### 3.1 模型
X → M1 → M2 → Y，中介变量之间有因果顺序。

### 3.2 代码

```r
model <- '
  M1 ~ a1 * X
  M2 ~ d * M1 + a2 * X
  Y  ~ b2 * M2 + b1 * M1 + cprime * X

  ind_m1      := a1 * b1
  ind_m2      := a2 * b2
  ind_chain   := a1 * d * b2      # 链式路径，这是重点
  total_ind   := a1*b1 + a2*b2 + a1*d*b2
'
fit <- sem(model, data = df, se = "bootstrap", bootstrap = 5000)
```

**链式路径 `a1*d*b2` 是研究假设的核心**，必须单独检验其 CI，
不能只报总间接效应。

### 3.3 理论依据不可省

**链式顺序必须由理论决定，不能由数据试出来。** 试遍所有顺序挑显著的，
是 p-hacking。如果理论支持两种顺序都成立，那就都报，并说明二者不可区分。

---

## 四、调节效应

### 4.1 模型
X 对 Y 的影响随 W 的水平而变化。

```
Y = b0 + b1·X + b2·W + b3·(X×W) + e
```

`b3` 显著 → 有调节效应。

### 4.2 必做步骤

1. **中心化**：X 与 W 都均值中心化（见 `regression-family` 第八节）；
2. **交互项显著性**；
3. **简单斜率分析**：在 W 的 -1SD / 均值 / +1SD 处分别看 X 的效应；
4. **画交互图**（审稿人必看）。

### 4.3 代码

```r
library(lavaan)
model <- '
  Y ~ b1 * X + b2 * W + b3 * X:W
'
# 或者用 lm 更直接
df$X_c <- scale(df$X, scale = FALSE)
df$W_c <- scale(df$W, scale = FALSE)
fit <- lm(Y ~ X_c * W_c, data = df)
summary(fit)

# 简单斜率
library(interactions)
sim_slopes(fit, pred = X_c, modx = W_c, modx.values = "plus-minus")
interact_plot(fit, pred = X_c, modx = W_c, interval = TRUE, plot.points = TRUE)
```

```python
import statsmodels.formula.api as smf
from scipy import stats

df["X_c"] = stats.zscore(df["X"])
df["W_c"] = stats.zscore(df["W"])
model = smf.ols("Y ~ X_c * W_c + age + C(gender)", data=df).fit()
print(model.summary())     # 看 X_c:W_c 的系数

# 简单斜率：W 在 -1SD / 0 / +1SD
b1, b3 = model.params["X_c"], model.params["X_c:W_c"]
for w in [-1, 0, 1]:
    print(f"W={w:+.0f}SD 时 X 的简单斜率 = {b1 + b3*w:.4f}")
```

### 4.4 Johnson-Neyman 法（比选点更严谨）

选 ±1SD 是惯例，但如果想知道"调节变量在什么区间内 X 的效应显著"，
用 Johnson-Neyman：

```r
library(interactions)
sim_slopes(fit, pred = X_c, modx = W_c, johnson_neyman = TRUE)
# 输出调节变量的显著区间，如 "W < -0.42 或 W > 1.31 时 X 的效应显著"
```

**这比只报三个点信息量大得多。**

---

## 五、有调节的中介（moderated mediation）

### 5.1 模型
中介路径本身被调节。两种常见形态：

**形态 A：前半段被调节**（X→M 的强度随 W 变）
```
W 调节 a 路径：M = a0 + a1·X + a2·W + a3·(X×W)
```

**形态 B：后半段被调节**（M→Y 的强度随 W 变）
```
W 调节 b 路径：Y = b0 + b1·M + b2·W + b3·(M×W) + c'·X
```

### 5.2 判据：条件间接效应

**不能说"间接效应显著"就够了**，必须报**在不同 W 水平下的条件间接效应**：

```r
library(lavaan)
model <- '
  M ~ a1 * X + a3 * X:W
  Y ~ b1 * M + cprime * X

  # 条件间接效应：在 W 取不同值时的 a×b
  ind_w_low  := (a1 + a3 * (-1)) * b1     # W = -1SD
  ind_w_mean := (a1 + a3 * ( 0)) * b1     # W = 均值
  ind_w_high := (a1 + a3 * ( 1)) * b1     # W = +1SD

  # 被调节的中介指数（index of moderated mediation）
  imm := a3 * b1
'
fit <- sem(model, data = df, se = "bootstrap", bootstrap = 5000)
summary(fit, ci = TRUE, standardized = TRUE)
```

**`imm`（被调节的中介指数）是核心指标。** 它的 CI 不含 0，才说明"中介效应确实
随 W 变化"，而不是仅仅某一水平的间接效应显著。

### 5.3 三个条件间接效应要报全

**表 8 有调节的中介：条件间接效应**

| W 水平 | 条件间接效应 | Boot SE | 95% CI |
|---|---|---|---|
| 低 (-1SD) | 0.031 | 0.021 | [-0.010, 0.072] |
| 中 (均值) | 0.078 | 0.028 | [0.025, 0.135] |
| 高 (+1SD) | 0.125 | 0.042 | [0.046, 0.211] |
| 被调节的中介指数 | 0.047 | 0.022 | [0.006, 0.093] |

**只报"高分组显著、低分组不显著"而不报 IMM，是不完整的** ——这可能是抽样波动。

### 5.4 PROCESS 模型号速查（1–76 全谱系）

Hayes 的 PROCESS 宏在中文社科极常用，审稿人看到"中介"就会问"Model 几"。但 **PROCESS 从 2.16 到 5.0 把模型号删改过**，
很多中文论文引用的模型号其实已经不存在了，这是投稿被要求重做的常见原因。

**先记住三条硬事实：**

1. **Model 23–27、30–57 在 PROCESS 3.0（2017-12）被删除**，因为它们是"第三、第四个调节变量"的模型，实际研究里极少用且有统计问题。
2. **Model 74 在 PROCESS 4.0 被删除**。
3. **PROCESS 5 里仍然有效的模型是：1–22、28、29、58–73、75、76。** 引用别的号，说明你抄的是老教材。

#### 一、调节模型（无中介，Models 1–3）

| 模型 | 方程 | 中文常见场景 |
|---|---|---|
| Model 1 | Y = X + M + X×M | 单一调节（**注意：这个模型里调节变量叫 M 而不叫 W**） |
| Model 2 | Y = X + M + W + X×M + X×W | 两个调节变量各自调节 X→Y |
| Model 3 | Y = X + M + W + 全部二阶 + X×M×W | 三重交互 |

#### 二、简单与并行中介（Models 4–6）

| 模型 | 方程 | 说明 |
|---|---|---|
| Model 4 | M ~ X；Y ~ X + M | **最常用**。M 可放多个 → 并行中介 |
| Model 5 | M ~ X；Y ~ X + M + W + X×W | 中介 + 直接路径被调节 |
| Model 6 | M1 ~ X；M2 ~ M1 + X；Y ~ X + M1 + M2 | **链式中介**（序列中介） |

#### 三、被调节的中介（Models 7–22，一个中介）

| 模型 | 哪段被调节 | 中文常见场景 |
|---|---|---|
| **Model 7** | 前半段 a（X→M） | "X 通过 M 影响 Y，且这一中介在 W 高时更强" |
| **Model 14** | 后半段 b（M→Y） | "……且在 W 高时 M 对 Y 的作用更强" |
| Model 8 | 前后两段都被同一个 W 调节 | 全模型中调节 |
| Model 15 | 直接路径 + 后半段被同一个 W 调节 | |
| Model 21 | 前半段 a + 后半段 b 各被一个 W 调节 | 两个不同调节变量分别管一段 |
| Model 58 | a 段被调节，**同时 b 段也被同一 W 调节**（不含 X×W 到 Y） | 5.x 提到的"前后半段都调" |
| Model 59 | 同 58，但 Y 方程含 X×W | |
| Model 76 | 前半段被两个调节变量同时调节 + 后半段被调节 | 最复杂的单中介形态 |

> **Model 7 与 Model 58 的区别，是中文论文最高频的错误。**
> Model 7 只调节 a 段，Y 方程里没有 M×W；Model 58 两段都调节。
> 如果你的理论说"中介效应整体随 W 变"，两段都得调节 → 用 58，用 7 会漏掉后半段。

#### 四、双中介与更复杂（Models 76 之外的组合）

PROCESS 的模型号只覆盖**单个中介**（Model 4/6 的 m 可以塞多个，但那是并行/链式，不叫带调节的双中介）。
**如果你的模型是"两个中介，其中一个的路径还被调节"，PROCESS 没有现成号。**
三条出路：

1. 拆成两个 PROCESS 跑（审稿人可能认为不严谨）
2. **直接用 lavaan 写全模型**（推荐，透明可复现，见本节前面的代码）
3. 用 `pyprocessmacro` 的 `m=[...]` 多中介 + `modval` 组合，但要确认模型号支持

#### 五、用脚本代替 SPSS 宏（推荐主线）

**PROCESS 是 SPSS/SAS 宏，不是必需品。** 它闭源、不能版本控制、结果无法一键复算。
用 Python 库 `pyprocessmacro` 可以拿到**完全一致的结果**且可复现：

```bash
pip install pyprocessmacro      # 要求 Python 3.11+
```

```python
from pyprocessmacro import Process
import pandas as pd

df = pd.read_csv("data.csv")

# Model 7：前半段被 W 调节
p = Process(data=df, model=7,
            x="X", y="Y", m=["M"], w="W",
            controls=["age", "gender"], controls_in="all",
            # 复现 PROCESS 3/4/5 的默认（而非 2.16 的默认），中文期刊引的多是 3 及以上
            percent=True, spotlight="percentiles",
            seed=20261028)          # 固定种子，Bootstrap 结果才能复算
p.summary()
```

**`percent=True` 与 `spotlight="percentiles"` 这两个参数不能省。** 库的默认值跟的是 PROCESS **2.16**
（偏差校正 CI + 均值±1SD），而 PROCESS **3.0 起**改成了百分位 CI + 16/50/84 百分位。
你按 3.x/4.x/5.x 写的方法部分，就必须传这两个参数，否则 CI 类型和取值点都跟正文写的不一致。

**该库相对原版 PROCESS 的差异（写方法部分要提一句，或至少心里有数）：**

| 项 | 说明 |
|---|---|
| 精度 | 模型 1–76 全部对照 PROCESS 2.16 输出做过逐模型比对测试；PROCESS 5 仍定义的 42 个模型另与 R 版 PROCESS 5.0 比对 |
| 支持范围 | 连续结局用 OLS；二分类用 Newton-Raphson logit；计数结局用 `family="negbin"`（**原版 PROCESS 无此功能**） |
| 中介数上限 | 无上限（原版最多 10 个） |
| 正态理论检验 | **不报**（作者认为 Bootstrap 已足够）——审稿人要 Sobel 或正态理论 CI 时需自己补 |
| 已删功能 | 模型 58–73、75、76 不报被调节的中介指数（IMM），因为这些模型里间接效应对调节变量非线性。**若你的模型是 58/59 且必须报 IMM，就得用 lavaan 手算或回 SPSS** |
| 随机数 | Bootstrap 抽样与 SPSS 版不同源，CI 只能在蒙特卡洛误差内一致 |

```python
# 二分类结局
p = Process(data=df, model=4, x="X", y="Y_binary", m=["M"], logit=True)

# 计数结局（这是原版没有的）
p = Process(data=df, model=4, x="X", y="Y_count", m=["M"], family="negbin")

# 自定义调节变量取值点
p = Process(data=df, model=7, x="X", y="Y", m=["M"], w="W",
            modval={"W": [-1, 0, 1]})
```

**结论：主线用 lavaan 或 pyprocessmacro 脚本，PROCESS 只在导师/期刊明确要求时交叉验证一遍。**
三者结果应一致（差异只在 Bootstrap 随机误差内），不一致说明哪里写错了，这正是交叉验证的价值。

---

## 六、样本量与检验力

**中介效应检验对小样本很敏感。** 经验要求：

| 分析 | 最低样本量 | 稳妥样本量 |
|---|---|---|
| 简单中介 | 150 | 200+ |
| 并行/链式中介 | 200 | 300+ |
| 有调节的中介 | 250 | 400+ |
| SEM 全模型 | 200 | 300+ |

样本不够时：
- Bootstrap 次数提高到 10000 次（不能弥补样本不足，但能稳定 CI）；
- 报告功效分析（见 `sample-size-power`）；
- 在局限里明确承认。

---

## 七、常见错误清单

- [ ] 用逐步回归法判中介（应直接检验 a×b 的 Bootstrap CI）
- [ ] 只做 Sobel 检验
- [ ] 报间接效应不报 CI
- [ ] Bootstrap 次数 <5000
- [ ] 用 percentile CI 却说用了 BCa
- [ ] 完全中介随便说（直接效应 CI 其实不含 0）
- [ ] 中介占比超过 100% 不解释（遮掩效应）
- [ ] 并行中介不比两个中介的差异，只说"都有中介作用"
- [ ] 链式中介顺序靠试而非靠理论
- [ ] 调节效应不中心化
- [ ] 调节显著不做简单斜率、不画图
- [ ] 有调节的中介只报条件间接效应，不报 IMM
- [ ] 控制变量一大堆但不能说明为什么要控制（过度控制会引入对撞偏倚）
- [ ] 横断面数据做中介，却在文中写因果语言（"导致""影响"）

**最后一条尤其重要：** 横断面问卷只能证相关结构，不能说因果。正确表述是
"中介作用""中介效应"（statistical mediation），而不是"X 通过 M 导致 Y"。
要做因果中介需要纵向数据或实验操纵，或在文中明确说明这是"统计中介而非因果中介"。

---

## 八、交付清单

- [ ] `30-analysis/mediation-moderation.md`：模型设定、路径图、效应分解表、条件效应表
- [ ] `30-analysis/results/mediation.csv`：a/b/c'/间接/直接/总效应及 CI
- [ ] 一键重跑脚本（Bootstrap 种子固定）
- [ ] 交互效应图 / 简单斜率图
- [ ] 理论论证段落：为什么假设这个中介路径、这个调节方向（不能事后编）
- [ ] 正文段落：把效应量翻译成人话（"间接效应为 0.086，占总效应的 27.6%"）

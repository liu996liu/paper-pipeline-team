---
name: "sem-pls"
description: "结构方程模型与 PLS-SEM：路径分析、潜变量 SEM、多组比较、中介的 SEM 实现、SmartPLS 操作流程、PLS 与 CB-SEM 的选择依据、Reflective 与 Formative 测量模型、f²/ Q²/ VIF 等 PLS 特有指标。含 R(lavaan/seminr)、Python(semopy)、SmartPLS 三条路线。适用于复杂假设模型（多中介、多因变量、多组比较）的检验。"
metadata:
  version: "1.0.0"
---

# 结构方程模型（SEM）与 PLS-SEM

## 一、先选路线：CB-SEM 还是 PLS-SEM

**这个选择必须写进方法部分，不能默默用了一个不说明。**

| 判据 | CB-SEM（lavaan / AMOS） | PLS-SEM（SmartPLS） |
|---|---|---|
| 研究目的 | **理论检验**（验证一个有理论依据的模型） | **预测 / 探索**（模型还在发展中） |
| 样本量 | N≥200，参数:样本 ≥1:5 | N 可小至 100 左右（10 倍规则） |
| 分布假设 | 多元正态 | 不要求分布假设 |
| 模型复杂度 | 中等（参数不能太多） | 可处理复杂模型（多构念多路径） |
| 拟合指标 | χ²/df、RMSEA、CFI、TLI、SRMR | **无全局拟合指标**，只有 Q²、SRMR、NFI |
| 测量模型 | 主要 Reflective（反映型） | Reflective 与 Formative 都支持 |
| 中文期刊接受度 | **主流**（AMOS 普及度高） | 增长中，管理学接受度高，教育学偏保守 |

**底线：投中文核心期刊，CB-SEM 更安全。** 用 PLS 要在文中说明为什么
（如样本小、模型复杂、非正态、formative 构念）。

**绝对不要：** 因为 CB-SEM 拟合不好就改用 PLS，然后把 PLS 结果当主结果。
这是"换方法换到显著"，属于方法学上的 p-hacking。

---

## 二、CB-SEM：lavaan 完整流程

### 2.1 两步法（Anderson & Gerbing）

```
第一步：测量模型（CFA）—— 确认每个潜变量的测量质量
第二步：结构模型 —— 检验潜变量之间的路径
```

**必须分两步做，分别报结果。** 直接跑全模型然后只报路径系数，
无法判断问题出在测量还是结构。

### 2.2 测量模型

```r
library(lavaan)

measurement <- '
  F1 =~ Q1 + Q2 + Q3 + Q4
  F2 =~ Q5 + Q6 + Q7
  F3 =~ Q8 + Q9 + Q10
  F4 =~ Q11 + Q12 + Q13
'
fit_m <- cfa(measurement, data = df, estimator = "MLR")
summary(fit_m, fit.measures = TRUE, standardized = TRUE)
```

报：拟合指标、标准化载荷、CR、AVE、区分效度（见 `reliability-validity`）。

### 2.3 结构模型

```r
structure <- '
  # 测量部分
  F1 =~ Q1 + Q2 + Q3 + Q4
  F2 =~ Q5 + Q6 + Q7
  F3 =~ Q8 + Q9 + Q10
  F4 =~ Q11 + Q12 + Q13

  # 结构部分
  F2 ~ a * F1
  F3 ~ b * F2 + c * F1
  F4 ~ d * F3 + e * F1

  # 间接效应
  ind1 := a * b * d
  ind2 := c * d
  total_ind := ind1 + ind2
  direct := e
'

fit_s <- sem(structure, data = df, se = "bootstrap", bootstrap = 5000)
summary(fit_s, ci = TRUE, standardized = TRUE, fit.measures = TRUE)
```

### 2.4 结果表模板

**表 9 结构模型路径系数**

| 路径 | 非标准化 B | SE | z | p | 标准化 β | 95% CI |
|---|---|---|---|---|---|---|
| F1 → F2 | 0.482 | 0.061 | 7.90 | <0.001 | 0.512 | [0.362, 0.602] |
| F2 → F3 | 0.312 | 0.058 | 5.38 | <0.001 | 0.341 | [0.198, 0.426] |
| F1 → F4（直接） | 0.088 | 0.052 | 1.69 | 0.091 | 0.096 | [-0.014, 0.190] |

注：N=412。采用 MLR 稳健估计，Bootstrap 5000 次。
模型拟合：χ²/df=2.14，RMSEA=0.053，CFI=0.947，TLI=0.938，SRMR=0.046。

### 2.5 R² 与效应量

SEM 里每个内生变量都有 R²：

```r
lavInspect(fit_s, "rsquare")
```

报：每个内生潜变量的 R²。这是"模型解释了多少"的直接证据，不能漏。

---

## 三、多组 SEM（跨群体比较）

### 3.1 三个层次的问题

```
1. 测量等价吗？（见 efa-cfa 的多组测量等价性）
2. 结构路径系数在不同组相同吗？
3. 潜均值在不同组有差异吗？
```

**顺序不能跳。** 测量不等价就比结构，结论无效。

### 3.2 代码

```r
# 基准模型（自由估计）
fit_free <- sem(structure, data = df, group = "group_var")

# 约束路径相等
fit_equal <- sem(structure, data = df, group = "group_var",
                 group.equal = c("loadings", "intercepts", "regressions"))

# 比较
anova(fit_free, fit_equal)
# Δχ² 显著 → 路径在不同组有差异 → 逐条约束找出哪条路径不同
```

### 3.3 逐条找差异

```r
# 只约束载荷和截距（测量等价），路径自由
fit_metric <- sem(structure, data = df, group = "group_var",
                  group.equal = c("loadings", "intercepts"))

# 再逐条加约束
fit_path1 <- sem(structure, data = df, group = "group_var",
                 group.equal = c("loadings", "intercepts", "regressions"),
                 group.partial = c("F2 ~ F1"))   # 放开的路径
anova(fit_metric, fit_path1)
```

**`group.partial` 是逐条检验的关键。** 全约束后 Δχ² 显著，说明"有差异"，
但不知道哪条；用 partial 逐条放开才知道。

---

## 四、PLS-SEM：SmartPLS 操作流程

### 4.1 两阶段评估（Hair et al. 的标准流程）

```
第一阶段：测量模型评估
   Reflective：载荷、内部一致性（ρA/CR）、AVE、区分效度（HTMT）
   Formative：外部权重、载荷、VIF（共线性）、显著性

第二阶段：结构模型评估
   VIF（内部共线性）、路径系数与显著性（Bootstrap）、R²、f²、Q²、SRMR
```

### 4.2 SmartPLS 具体步骤

1. **导入数据**（CSV，第一行为变量名，无缺失或先用均值填补）。
2. **画模型**：拖入构念（圆形），连路径（箭头），给每个构念挂指标（矩形）。
3. **设置**：
   - PLS-SEM 算法：Weighting Scheme = Path，最大迭代 300，停止准则 1.0×10⁻⁷；
   - Bootstrapping：子样本 5000，置信区间 BCa，检验类型双尾，显著性 0.05；
   - Blindfolding：Omission Distance 设为 5–10（要能整除样本量）。
4. **跑 PLS 算法** → 看测量模型（Outer Loadings、Construct Reliability and Validity）。
5. **跑 Bootstrapping** → 看路径显著性（Path Coefficients 的 T 统计量与 P 值）。
6. **跑 Blindfolding** → 得到 Q²。
7. **导出报告**（Quality Criteria 各表）。

### 4.3 PLS 特有指标与阈值

| 指标 | 阈值 | 说明 |
|---|---|---|
| Outer Loading | ≥0.708（0.6–0.7 可接受，<0.4 删除） | 反映型指标 |
| Cronbach's α | ≥0.7 | |
| ρA（可靠度系数） | ≥0.7 | PLS 推荐，介于 α 与 CR 之间 |
| CR（组合信度） | ≥0.7，≤0.95 | >0.95 提示题目冗余 |
| AVE | ≥0.5 | |
| **HTMT** | <0.85（严格）/ <0.90（宽松） | 区分效度，PLS 论文必报 |
| **VIF（内部）** | <5，最好 <3 | 结构模型共线性，**PLS 论文必须报** |
| **f²** | 0.02 小 / 0.15 中 / 0.35 大 | 效应量，**必报** |
| **Q²** | >0 | 预测相关性，**必报** |
| **SRMR** | <0.08 | PLS 唯一近似全局拟合的指标 |

**PLS 论文不报 f² 和 Q²、不报 VIF，基本会被拒。** 这是 PLS 审稿的三件套。

### 4.4 PLS 结果表模板

**表 10 PLS-SEM 结构模型结果**

| 路径 | 路径系数 β | T 值 | P 值 | f² | 95% CI |
|---|---|---|---|---|---|
| F1 → F2 | 0.512 | 8.214 | <0.001 | 0.354（大） | [0.396, 0.618] |
| F2 → F3 | 0.341 | 5.677 | <0.001 | 0.142（中） | [0.223, 0.453] |

| 内生构念 | R² | 调整 R² | Q² |
|---|---|---|---|
| F2 | 0.262 | 0.260 | 0.148 |
| F3 | 0.398 | 0.395 | 0.221 |

注：Bootstrap 5000 次，BCa 置信区间。SRMR=0.061。

### 4.5 R 实现（seminr / cSEM，可脚本化）

```r
library(seminr)

# 测量模型
mm <- constructs(
  reflective("F1", c("Q1","Q2","Q3","Q4")),
  reflective("F2", c("Q5","Q6","Q7")),
  reflective("F3", c("Q8","Q9","Q10"))
)

# 结构模型
sm <- relationships(
  paths(from = "F1", to = "F2"),
  paths(from = c("F1","F2"), to = "F3")
)

model <- estimate_pls(data = df, measurement_model = mm, structural_model = sm)
summary(model)
boot_model <- bootstrap_model(model, nboot = 5000, cores = 4)
summary(boot_model)
```

**用脚本而不是 GUI 的原因：** 可复现、可进版本控制、t11 复现包闸门能验。
SmartPLS 的 GUI 操作无法被脚本复现，必须导出项目文件（.splsm）一并提交。

---

## 五、Formative 与 Reflective 测量模型

### 5.1 怎么判断

| 问题 | Reflective（反映型） | Formative（形成型） |
|---|---|---|
| 指标是构念的表现还是构成？ | 表现（指标反映构念） | 构成（指标组成构念） |
| 指标之间必须高度相关吗？ | 是 | 不必，甚至不应太高 |
| 去掉一个指标会影响构念含义吗？ | 不会（还有其他指标反映） | **会**（构念定义不完整） |
| 例 | 焦虑量表（各题都反映焦虑） | 社会经济地位（收入+教育+职业构成它） |

**社科问卷绝大多数是 Reflective。** 误把 formative 当 reflective 处理，会删掉
"不相关"的指标，从而破坏构念定义。

### 5.2 Formative 的评估方式（不同！）

- **不看**内部一致性（α/CR 对 formative 无意义）；
- **看** 外部权重（outer weights）的显著性；
- **看** 指标间 VIF（<5，共线性太高的指标要合并或删除）；
- **看** 外部载荷（outer loadings）作为补充（<0.5 且权重不显著可考虑删除）。

**报 formative 构念的 Cronbach's α 是方法学错误。**

---

## 六、常见错误清单

- [ ] 未说明为何选 CB-SEM 或 PLS-SEM
- [ ] 不分两步（测量 + 结构）直接跑全模型
- [ ] CB-SEM 报拟合指标不全（缺 SRMR 或 TLI）
- [ ] PLS 报 Cronbach's α 但不报 ρA、CR、HTMT
- [ ] PLS 不报 f² 和 Q²
- [ ] PLS 不报内部 VIF
- [ ] 多组比较未先检验测量等价性
- [ ] 多组比较只报"有显著差异"，未用 group.partial 找出哪条路径
- [ ] Formative 构念按 reflective 评估
- [ ] 用 SEM 做因果推断（SEM 是协方差结构，不是因果识别）
- [ ] 模型修正次数未报告
- [ ] 样本量与参数个数比例不足
- [ ] R² 未报告
- [ ] 模型图缺失或不标准

---

## 七、交付清单

- [ ] `30-analysis/sem.md`：测量模型表、结构模型表、R²、拟合指标、模型图
- [ ] `30-analysis/results/sem_paths.csv`
- [ ] 一键重跑脚本（lavaan 或 seminr）
- [ ] 路径图（可编辑格式，进正文或附录）
- [ ] 模型修正记录（修正前 → 修正理由 → 修正后）
- [ ] 多组比较时的测量等价性报告
- [ ] 正文段落：**把路径系数翻译成人话**，说明每条假设支持与否

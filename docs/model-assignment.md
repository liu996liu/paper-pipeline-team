# 模型分配（角色级）

9 个角色各自拥有独立的 `model` 与 `reasoningEffort` 字段。本文说明当前分配、理由，以及换成你自己模型的方法。

> ⚠️ 当前填写的模型 ID 只使用了仓库内已验证可用的两个（`deepseek-v4.1-flash-sg`、`deepseek-v4.1-flash`）。**若你账号里有更强的模型，按下文「换模型」改一处即可**，不需要动 9 个文件。

---

## 一、三档定义

| 档位 | 模型 | 推理强度 | 适用特征 |
|---|---|---|---|
| `strong` | `deepseek-v4.1-flash-sg` | `max` | 判断型任务：要权衡、要发现别人忽略的问题、要写长文本 |
| `standard` | `deepseek-v4.1-flash-sg` | 默认 | 有脚本、表格或核对清单兜底，模型只做执行与比对 |
| `fast` | `deepseek-v4.1-flash` | 默认 | 模式化、体量大、格式固定 |

> `standard` 档刻意**不写** `reasoningEffort` 字段，而不是写空字符串 `""`。空字符串不是合法的推理强度值，部分客户端会直接报错或静默降级；缺省即代表使用模型默认值。

---

## 二、逐角色分配与理由

| 角色 | 承担任务 | 档位 | 理由 |
|---|---|---|---|
| `research-orchestrator` | t1 选题开题、t10 候选定稿 | **strong** | t1 的目标期刊与框架一旦定错，后面全部返工；t10 需要在冲突意见间做取舍 |
| `deep-researcher` | t3 深度调研 | **strong** | 创新点核查是判断型任务，弱模型倾向「默认通过」 |
| `paper-supervisor` | t6 全文写作、t8 修订、t9 去 AI 痕迹 | **strong** | 直接决定成稿质量，且需要逐条回应审查意见；t9 是全文文体重写，不是模式化替换 |
| `academic-reviewer` | t7 独立审查 | **strong** | 对抗式评审，最忌「礼貌性通过」；这一环用弱模型等于没有审查 |
| `empirical-analyst` | t4 计量实证 | standard | 数字由脚本生成，模型只做识别策略设计与结果解释 |
| `survey-analyst` | t4b 问卷量表分析 | standard | 同上。信效度与中介调节的判定阈值已写死在技能里，不需要强推理 |
| `quality-gatekeeper` | t10.5 差异复审、t11 质量验收 | standard | 按核对表逐条比对，规则明确，不依赖生成能力 |
| `corpus-archivist` | t2 文献精读归档 | fast | 量大、字段固定（读档模板 + 页码定位） |
| `figure-designer` | t5 图表设计 | fast | 输出是图表规格与绘图脚本，不是长文本 |

**成本结构**：strong ×4、standard ×3、fast ×2。

**为什么审查角色值得花 strong 的钱**：这套流水线最容易崩的地方不是没人写，而是写了一篇有问题但看起来没问题的稿子。审查是唯一能拦住它的环节。把 `academic-reviewer` 降到 standard，省下的钱会在返工轮次上加倍花掉。

若要压成本，优先把 `figure-designer` 或 `corpus-archivist` 降档（已经是 fast，可换更便宜的模型），而不是动审查环节。

---

## 三、换模型（唯一入口）

模型配置集中在 `team.json` 的 `modelPolicy`：

```json
"modelPolicy": {
  "tiers": {
    "strong":   { "model": "你的强模型ID", "reasoningEffort": "max" },
    "standard": { "model": "你的标准模型ID" },
    "fast":     { "model": "你的快模型ID" }
  },
  "roles": {
    "research-orchestrator": { "tier": "strong", "why": "…" },
    "corpus-archivist":      { "tier": "fast",   "why": "…" }
  }
}
```

改完 `tiers` 后执行：

```bash
python scripts/apply_models.py --dry-run   # 先看会影响哪些文件
python scripts/apply_models.py             # 写入各成员定义
```

脚本会同步 9 个 `agents/*.md` 的 frontmatter，避免手改漏改。

> ⚠️ `agents/*.md` 由 `scripts/gen_agents.py` 生成。如果你之后又跑了 `gen_agents.py`，它会用脚本内嵌的 `model=` 值覆盖掉 `apply_models.py` 写入的内容。**正确顺序是**：先改 `team.json` 改 `gen_agents.py` 里的 `model`/`effort` 默认值，再 `gen_agents.py` → `apply_models.py`。为了免掉这个坑，`gen_agents.py` 的默认值应与 `modelPolicy.tiers` 保持一致，`apply_models.py` 只作为二次校准。

**只想改某一个角色**：把 `roles.<角色>.tier` 改成另一档，或者直接编辑该角色的 `agents/<角色>.md` 里的 `model:` 行（不推荐，会与 team.json 不一致，且下次重新生成即被覆盖）。

---

## 四、各客户端的兼容性

| 客户端 | 是否尊重 frontmatter 的 model | 说明 |
|---|---|---|
| DeepSeek Harness | ✅ | 原生读取 `team.json` 的 `model` 与 `reasoningEffort` |
| WorkBuddy | ❌ | 不读 agent frontmatter；派子代理时需显式指定模型 |
| Claude Code | ⚠️ | 只接受 `sonnet` / `opus` / `haiku` / `inherit`，需把 ID 换成这几个值 |

因此：**这套分配在 DeepSeek Harness 中直接生效；在其他客户端需要按平台改写模型 ID**，档位划分逻辑仍然适用。

---

## 五、两个已知局限

**1. 按角色分配的粒度无法区分同一角色内部的轻重差异。** 最典型的是 `paper-supervisor`：t6 写全文（最重）与 t9 去 AI 痕迹（相对轻）共用同一模型。若将来觉得不划算，可改为「角色默认 + 任务覆盖」—— 在 `team.json` 的 `tasks` 里给单个任务加 `model` 字段。当前未实现，属于可选扩展。

**2. 三档目前只用到两个真实模型。** `strong` 与 `standard` 的模型 ID 相同，差异只在 `reasoningEffort`。真正的成本分档要等你填入自己的模型 ID 才成立。保持现状的原因是「已验证可用」优先于「看起来分了三档」，填一个不存在或无权访问的模型 ID 会让整条流水线起不来。

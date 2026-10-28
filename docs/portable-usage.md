# 在其他 Agent 客户端中使用本团队

本仓库有三类可移植物，不同客户端支持程度不同：

| 产物 | 格式 | 说明 |
|---|---|---|
| `skills/` | Agent Skills 约定（`<skill>/SKILL.md` + YAML frontmatter） | 通用性最好，多数客户端支持 |
| `agents/*.md` | 子代理定义（frontmatter + 系统提示词） | 各家格式不同，需按客户端调整 |
| `team.json` | 本仓库自有清单（成员、任务、依赖） | 非行业标准，仅供人阅读或自建编排脚本使用 |

> **先注意目录层级**：本仓库技能是 `skills/<技能族>/<技能>/SKILL.md`（部分还嵌到第 4 层），而绝大多数客户端只识别**一层** `<skill>/SKILL.md`。安装前必须扁平化，直接用 `scripts/install.py`。

---

## 一、一条命令扁平化安装

```bash
python scripts/install.py --target <目标skills目录>
python scripts/install.py --target <目标目录> --dry-run   # 先看会复制什么
python scripts/install.py --target <目标目录> --force     # 覆盖已存在的同名技能
```

脚本会递归查找所有含 `SKILL.md` 的目录，按目录名扁平复制到目标，遇到重名会报告并跳过（不静默覆盖）。

---

## 二、各客户端接入方式

### 1. Claude Code

```bash
# 技能（用户级）
python scripts/install.py --target ~/.claude/skills

# 技能（项目级）
python scripts/install.py --target ./.claude/skills

# 子代理
mkdir -p .claude/agents && cp agents/*.md .claude/agents/
```

⚠️ **必须改 frontmatter**：Claude Code 的 `model` 字段只接受 `sonnet` / `opus` / `haiku` / `inherit`，本仓库的 `deepseek-v4.1-flash-sg` 会被判为非法值；`reasoningEffort` 字段它不认识，建议删除。改法：

```yaml
---
name: paper-supervisor
description: 写作与修订：全文写作、引言专项、语言润色；按独立审查意见逐条修订
model: inherit
---
```

### 2. Codex CLI

在项目根目录建 `AGENTS.md`，写清「用哪个 skill 做哪个任务」：

```markdown
# 论文攻坚组

技能库位于 .claude/skills（或已扁平化的 skills/），使用时先读取对应 SKILL.md 再执行。

任务顺序：t1 选题 → t2 文献精读 / t3 深度调研 / t4 计量实证 或 t4b 问卷量表
→ t5 图表 → t6 写作 → t7 独立审查 → t8 修订 → t9 去 AI 痕迹 → t10 候选定稿
→ t10.5 差异复审 → t11 质量验收

硬规则：写作与审查不得同一人；质量验收 pass 才交付；每个成员接单第一步先加载自己绑定的技能。
```

技能仍需扁平化到 Codex 认识的目录。

### 3. Cursor / Cline / Continue

这三类没有原生 skills 运行时，只能把技能当**参考资料**用：

```
.cursor/rules/paper-pipeline.mdc      # 放任务顺序与硬规则
```

在 rule 里写明路径，让模型按需读取：

```markdown
论文写作时，按 skills/<技能名>/SKILL.md 的指令执行。
先读 SKILL.md 的 frontmatter 判断适用场景，再按其流程做。
```

### 4. WorkBuddy / 同类中文客户端

```bash
python scripts/install.py --target ~/.workbuddy/skills
```

这类客户端通常只认一层目录，扁平化后即可在对话中用 Skill 调用。`agents/*.md` 的 persona 可直接粘成系统提示词。

### 5. DeepSeek Harness（原环境）

Harness 的 AgentTeams 插件**不认识 `team.json` 的原生格式**——它的 profile 校验是严格的（源码 `lib/profiles.js` 的 `assertAllowedKeys` 遇到未知键直接抛错），允许的键只有：

| 层级 | 允许的键 |
|---|---|
| profile | `description` `protocol` `executionPrompt` `fallback` `members` `tasks` `taskPlanning` `reviewPolicy` |
| member | `name` `role` `provider` `model` `reasoning_effort` `executionPrompt` `fallback` `tool_policy` |
| task | `id` `subject` `description` `assignee` `dependencies` |

`team.json` 里的 `kind` / `objective` / `acceptance` / `verify` / `degrade` / `dependsOnPolicy` / `flowRules` / `retryPolicy` / `workspace` 全部是平台未知键，原样导入会直接报 `profiles.xxx.tasks[0].kind is unknown`。

正确做法是用编译脚本单向生成：

```bash
python scripts/export_profile.py --out docs/dsh-profile.yml
```

生成的 `docs/dsh-profile.yml` 是一个合法的 profile 片段，做了三件事：

1. 成员 → `members[]`，带上模型与 `reasoning_effort`（注意：`reasoningEffort` 为空字符串时**整段省略**，因为插件不会清洗空串，会当成非法强度传下去）
2. 13 个任务按拓扑序 → `tasks[]`，`id` / `subject` / `assignee` / `dependencies` 直接对应
3. 平台不认识的契约字段（objective / acceptance / deliverables / verify / degrade / 禁止项 / 轮次）**压成每个 task 的 `description` 前缀**，flowRules 与 retryPolicy 压进 profile 的 `protocol`——这样 captain 开设团队时仍看得到它们，而不是悄悄丢掉

装法：把生成文件里的 `profiles:` 段合并进 `~/.dsh/profiles/<你的 profile>/cordis.patch.yml`，然后 `/agent-teams --profile paper-pipeline <研究目标>`。

> **9 人超出默认上限**：插件的 `maxMembers` 默认是 8，本团队 9 人。必须在同一份 `cordis.patch.yml` 的 `agent-teams` 条目里加 `config: { maxMembers: 9 }`，否则 `agent_teams_create({profile})` 会报 `has 9 members but maxMembers is 8`。生成文件顶部已写好这段注释。

> **单向同步**：`docs/dsh-profile.yml` 是生成物，改 `team.json` 后要重跑 `export_profile.py`；CI 的 `--check` 会拦住忘记重跑的情况。反过来不要手改生成文件。


### 6. 只能对话、没有工具的环境（ChatGPT 网页等）

退化为「复制粘贴」用法：

1. 打开 `agents/<角色>.md`，把「系统提示词」一节整段粘进对话
2. 需要具体方法时，再把对应 `skills/<技能>/SKILL.md` 粘进去
3. 产物自己存文件，不存在交接自动化

---

## 三、只想要团队结构、不想要技能库

如果目标客户端已有自己的技能体系，可以只用 `team.json` 与 `agents/`：

- `team.json` 的 `tasks` 给出 13 个任务、负责人与依赖（每个任务还带 objective / acceptance / deliverables / inScope），`flowRules` 给出 13 条硬规则，`workspace` 给出目录约定，`retryPolicy` 给出降级策略
- 照着它在你所用客户端里建 agent，把 `agents/*.md` 的 persona 作为各自系统提示词
- 技能换成该客户端自带的对应能力

---

## 四、网络受限环境下的取用方式

若目标智能体在中国大陆网络，直接抓 `raw.githubusercontent.com` 大概率失败（实测 TLS 握手失败，返回 000）。三条替代通道，按稳定性排序：

| 通道 | 命令 | 说明 |
|---|---|---|
| `git clone` | `git clone --depth 1 https://github.com/<user>/<repo>.git` | HTTPS 与 SSH 通常可用，一次拿全库 |
| GitHub API | `curl https://api.github.com/repos/<user>/<repo>/contents/llms.txt` | 返回 JSON，`content` 字段是 base64，需解码 |
| 网页 | 直接访问仓库页面 | 人工查看可以，自动化不便 |

结论：**让智能体优先用 `git clone`，把 raw 链接当备用**。若智能体具备网络代理，raw 与 CDN 通道可正常使用。

---

## 五、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 装了但客户端不识别 | 目录多了一层（`skills/族/skill/`） | 用 `install.py` 扁平化 |
| 识别了但不触发 | `SKILL.md` 的 `description` 太宽泛 | 在 description 里写清触发场景与关键词 |
| 子代理报 model 非法 | frontmatter 的 model 值不被支持 | 改为该客户端接受的值或删除 |
| 同名技能被覆盖 | 多个族里有同名目录 | `install.py` 会报告冲突，需手动决定保留哪个 |
| 技能里的脚本跑不了 | 缺少 Python 依赖 | 各 SKILL.md 的 `references/` 或 `requirements.txt` 里有说明 |
| `check_skills.py` 报 name 不一致 | 手工改过 frontmatter | 跑 `python scripts/normalize_skills.py` 批量对齐 name 与目录名 |
| 改了 `team.json` 但成员没变 | `agents/*.md` 是生成物 | 依次跑 `gen_agents.py`、`apply_models.py`、`gen_llms.py` |
| 成员不加载技能就开工 | 客户端不主动读仓库 | 每个 `agents/*.md` 开头有「开工前必读」清单，靠提示词强约束；见 flowRule 12 |

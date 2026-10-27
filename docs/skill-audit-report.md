# DSH 插件 Skill 审查统一报告

- **审查团队**：skill-audit（captain + 3 reviewer + integrator）
- **审查对象**：`<技能库根目录>/.claude/skills/` 下 5 个 DSH 插件 skill
- **审查方式**：3 名 reviewer 并行逐条核实 → integrator 合并去重 + 交叉验证
- **交叉验证执行时间**：2026-10-20 08:35–08:50 (Asia/Shanghai)
- **运行时基线**：DSH `0.2.1-rc.2`（`DeepSeek Harness.exe` FileVersion 实测）；profile `desktop` 已装 6 个插件
- **本报告未修改任何 SKILL.md**

---

## 1. 总览表

| Skill | 发现数 | 最高严重度 | 判定 |
|---|---|---|---|
| [agent-teams](.claude/skills/agent-teams/SKILL.md) | 1 | low | **可信** |
| [dsh-plugin-market](.claude/skills/dsh-plugin-market/SKILL.md) | 8 | low | **可信**（可选微调） |
| [whale-balance](.claude/skills/whale-balance/SKILL.md) | 5 | medium | **需小修** |
| [dsh-context-insight](.claude/skills/dsh-context-insight/SKILL.md) | 6 | medium | **需小修** |
| [openbiliclaw](.claude/skills/openbiliclaw/SKILL.md) | 6 | **high** | **需小修** |
| **合计** | **26** | high | — |

**严重度分布**：blocker 0 / high 1 / medium 7 / low 18（合计 26 条，其中 U26 与 U1 同源）

> 计数口径：U26（openbiliclaw L91 运行状态）与 U1（L21）同源同证，为保留 reviewer 原始两处行号引用而单列，故 openbiliclaw 计 6 条、总量 26 条。按去重后口径则为 25 条。

**另有两项发现已被 reviewer 自行撤回**（见 §5 撤回记录），不纳入上表。

---

## 2. 交叉验证说明

本环节对全部 blocker/high 级发现及多数 medium 级发现做了独立复跑，防止 reviewer 误报。

| 复验对象 | 复验命令 / 读取 | 结论 |
|---|---|---|
| **A1（high）** openbiliclaw 后端运行状态 | `Get-NetTCPConnection -State Listen \| ? LocalPort 8400-8500`；`Invoke-WebRequest http://127.0.0.1:8420/api/health`；`Get-CimInstance Win32_Process` 过滤 openbiliclaw；serve-api.log LastWriteTime | **属实**。4 项证据一致：8400-8500 无监听、health 连接失败、无 openbiliclaw 进程、日志止于 2026-10-19 23:59:53 |
| **A3（medium）** 22 vs 24 工具数 | `[regex]` 提取 `dsh-openbiliclaw/lib/index.js` 中 `name: "openbiliclaw_*"`；实跑 `uv run ... capabilities` 并计数 skill_names | **属实，但 reviewer 有一处细节错误**（见 U2）：22 与 24 的差集是 `sync_account` + `sync_saved`，不是 reviewer 写的 `sync_account` + `get_capabilities` |
| **A4（medium）** health check 返 503 | `Select-String serve-api.log -Pattern "agent-bridge\|503"` | **属实**：日志 3 次 `POST /api/agent-bridge HTTP/1.1" 503 Service Unavailable` |
| **A5（low）** 命令表缺 doctor / emit-skill-descriptors | 实跑 `uv run ... --help` | **属实**：CLI 共 27 个命令，含 `doctor`、`emit-skill-descriptors`，SKILL.md 表内均无 |
| **F11（medium）** whale tools/ 不在 npm 包 | `Test-Path tools`；读 `package.json` 的 `files[]` | **属实**：`Test-Path` = False；`files[]` = `lib, assets, icon.png, cordis.patch.yml, README.md, PROVENANCE.md`，无 tools |
| **F12（medium）** whale engines 无包内出处 | 读 `dsh-whale-widget/package.json` | **属实**：`engines` 字段不存在；`dsh` 仅有 `bundle.patch` |
| **#1（medium）** dsh-context 版本过期 | UTF8 读 `node_modules/dsh-context/package.json` 与 profile package.json | **属实**：两处均为 `0.73.3`，SKILL.md 写 `0.73.2` |
| **#5（medium）** browser 类目越界 | 读 `dsh-context/lib/client.js` 内联 locale 的 `cat.*` 键 | **属实**：仅 7 个类目 `system/tools/user/inject/skill/assistant/tool`；`tab.fleet`（编队）是独立条目，无 event / agent-teams 类目 |
| **#6（low）** index.js 职责描述 | grep index.js 与 client.js 的 `sidebarRightTabs` / `inputTriggers` | **属实**：index.js 两者均为 0 次；client.js 各 2 次 |
| **#7（low）** dsh-api-remotes 引用失真 | grep client.js 的 `dsh-api-remotes` / 模块 require / fetch 路径 | **属实**：`dsh-api-remotes` 0 次；实际 require 4 个模块（react / react-dom / react/jsx-runtime / @deepseek-ai/dsh-client-ui-primitives），数据经 `fetch('api/dsh-context/{detail,fleet,skills,attachment,balance,backfill}')` 与 `ctx.get('connection').rpc.call` |
| **#8（low）** locale 文件只含 meta | 读 `locale/en.json`、`locale/zh.json` | **属实**：各 6 行 / 226-247 字节，仅 `meta.title` + `meta.description`；900+ UI 文案内联打包在 client.js |
| **A2（medium）** 子进程端口声明 | 读 `serve-api.log` L55-59、`logs/child-*.log` 大小 | **属实**：日志明确写 `推荐 API TCP 127.0.0.1:8423 pid=3904`、`image-proxy pid=27124（端口 8421）`；`child-image-service.log` 为 0 字节 |
| **F15（low）** 错误文案引文 | 实跑 `--profile desktop --dump-config` / `--dump-config-schema` / `--dump-default-config` | **属实**：三者均 exit 1，原文 `error: profile "desktop" is managed exclusively by the Electron application`（无句点）；reviewer 补充的 `--dump-config-schema` / `--dump-default-config` 同样被拒也复现成功 |
| **F13/F14（low）** assets 回退与热加载 | 读 `whale/lib/index.js` L684-699 | **属实**：`WIDGET_FILE_CANDIDATES` 依次探测 `lib/whale-widget.js`、包根、`assets/whale-widget.js`；注释明写「改 widget 后硬刷新页面即生效(无需重启 DSH)」「每次请求按 mtime 判断是否需要重读」 |
| **A6（low）** fork 继承表述无代码支持 | grep lib 全库 `fork` / `inherits` / `completed lead turns` | **属实**：`lib/index.js:60` 只有 `memberProvider: z.string().default('spawn')`；`lineage.js:193 forkLineageNote` 仅用于诊断「本会话是某会话的 fork」，无「fork 继承已完成 lead turns」语义 |
| **F1（已撤回）** "incompatible with dsh" 文案 | 独立 grep `.plugin-manager/logs/operation-OcXNek/pnpm.log` | **reviewer 撤回正确**：日志原文 `dsh: installation rejected: Plugin @openbiliclaw/dsh-plugin@0.4.0 is incompatible with dsh 0.2.1-rc.2: requirements {...}`，SKILL.md 措辞成立 |
| **F9（low）** registry 每日刷新 / 发布前审核 | grep `dshmarket/README.md` | **部分支持，建议下调严重度或改写**：README L123 明写「Fetched live on every open … star counts refreshed daily by CI」，L113 说明走 awesome-dsh-plugin 仓库 PR 收录。「daily-refreshed」有据；「reviewed before publishing」由 PR 收录模型间接支持，但无直接可执行证据 |

---

## 3. 按严重度分组的问题清单

### HIGH（1 项）

#### U1 · openbiliclaw：后端运行状态为过期陈述
- **文件 / 行号**：[openbiliclaw/SKILL.md](.claude/skills/openbiliclaw/SKILL.md) L21、L91（关联 L103-105、L97）
- **问题**：L21 表格称「`serve-api` backend running on `http://127.0.0.1:8420`」，L91 注释称「already running as background job on this machine」，L103-105 描述其 4 个子进程——但后端实际已停止。这是全库唯一 high，因为它是**会被读者直接依赖去执行的操作性陈述**（照文档去 curl 会失败）。
- **证据**：`Get-NetTCPConnection -State Listen` 在 8400-8500 无任何监听；`Invoke-WebRequest http://127.0.0.1:8420/api/health` → 「无法连接到远程服务器」；`Get-CimInstance Win32_Process` 无 openbiliclaw / python / uv 相关进程；`serve-api.log` LastWriteTime = 2026-10-19 23:59:53，4 个子进程日志均止于 2026-10-20 00:01。
- **建议修法**：把 L21 那行改为「`serve-api` backend — **not currently running**（历史日志见 `serve-api.log`）；L91 的 `# start (already running as background job on this machine)` 改为 `# start`；L103-105 补一句「以下端口声明来自历史日志，当前未运行，无法当场核实」。若希望文档长期有效，可改为「启动后应监听 8420，并派生 4 个子进程」的条件式表述，去掉机器状态快照。

### MEDIUM（7 项）

#### U2 · openbiliclaw：22 vs 24 工具数口径未对齐
- **文件 / 行号**：[openbiliclaw/SKILL.md](.claude/skills/openbiliclaw/SKILL.md) L119
- **问题**：「The plugin would have registered **22** `openbiliclaw_*` tools」未说明统计口径。同一份生态里 `capabilities` 命令返回 24 个 skill_names，两个数字并存易误导。
- **证据**：`[regex]` 提取 `dsh-openbiliclaw/lib/index.js` 得 22 个 `name: "openbiliclaw_*"`；实跑 `uv run --no-sync python -m openbiliclaw.integrations.openclaw.cli capabilities` 得 `skill_names.Count = 24`。**差集为 `openbiliclaw_sync_account` 与 `openbiliclaw_sync_saved`**（integrator 复算，修正了 reviewer 原报告中「第二项是 `get_capabilities`」的笔误——`get_capabilities` 实际已注册在 `lib/index.js:126`）。
- **建议修法**：改为「registered 22 `openbiliclaw_*` tools in `lib/index.js`； the bridge `capabilities` response advertises 24 skill names — the extra two (`openbiliclaw_sync_account`, `openbiliclaw_sync_saved`) are bridge-side only.」

#### U3 · openbiliclaw：子进程端口声明无法当场核实
- **文件 / 行号**：[openbiliclaw/SKILL.md](.claude/skills/openbiliclaw/SKILL.md) L103-104
- **问题**：「recommendation API (TCP 127.0.0.1:8423) and image proxy (port 8421)」本身可从日志佐证，但文档未说明后端已停；且 `logs/child-image-service.log` 为 0 字节，image proxy 是否真正起来过无正面证据。
- **证据**：`serve-api.log` L56 `已启动独立推荐 API pid=3904（TCP 127.0.0.1:8423）`、L59 `已启动独立 image-proxy pid=27124（端口 8421）`；`OpenBiliClaw/logs/child-image-service.log` Length = 0（其余 3 个子进程日志各 ~7KB）。
- **建议修法**：与 U1 一并处理——端口声明改为「启动日志记录 recommendation API 8423 / image proxy 8421；image proxy 日志为 0 字节，未能独立佐证」，并去掉「当前正在运行」的暗示。

#### U4 · openbiliclaw：health check 命令名不副实
- **文件 / 行号**：[openbiliclaw/SKILL.md](.claude/skills/openbiliclaw/SKILL.md) L96-97
- **问题**：`curl -Method POST http://127.0.0.1:8420/api/agent-bridge -Body '{"command":"capabilities"}'` 被标为 `# health check`，但该端点在 degraded mode 下返回 **503**，并非健康信号；文档 L78 自己也写了「HTTP bridge answers 503」，自相矛盾。
- **证据**：`serve-api.log` L70-72 三次 `POST /api/agent-bridge HTTP/1.1" 503 Service Unavailable`；L37 `FastAPI started in degraded mode`。
- **建议修法**：把注释改为 `# bridge smoke test (expect 503 in degraded mode — see above)`，或改用真正的健康端点；若确无 `/api/health` 路由，可直接删掉该注释行。

#### U5 · whale-balance：tools/ 审计脚本不在 npm 包内
- **文件 / 行号**：[whale-balance/SKILL.md](.claude/skills/whale-balance/SKILL.md) L62-65
- **问题**：「The plugin ships its own CI audits (`tools/z-layer-audit.mjs`, `tools/ci-audit.mjs`)」与实际安装包不符——npm 消费者拿不到这两个脚本，文档却要求读者「keep those invariants」。
- **证据**：`Test-Path ...\node_modules\dsh-whale-widget\tools` = **False**；`package.json` 的 `files[]` = `lib, assets, icon.png, cordis.patch.yml, README.md, PROVENANCE.md`（无 tools）；已安装 README.md 中 `z-layer-audit` / `ci-audit` 0 匹配。
- **建议修法**：改为「源码仓库提供 `tools/` 下的审计脚本（npm 包内不含）；若你从源码构建，编辑 `assets/whale-widget.js` 后应跑这两个脚本检查 z-index 层叠与 innerHTML 安全」。

#### U6 · whale-balance：engines 版本约束无包内出处
- **文件 / 行号**：[whale-balance/SKILL.md](.claude/skills/whale-balance/SKILL.md) L66-67
- **问题**：「Requires DSH `>=0.1.7-rc.2 || >=0.2.0-rc.2`」无法从包本身核实。后半句（兼容已装 0.2.1-rc.2）成立，前半句来源不明。
- **证据**：`dsh-whale-widget/package.json` **无 `engines` 字段**；`dsh` 键仅 `{"bundle":{"patch":"./cordis.patch.yml"}}`；`lib/index.js` 中 `0.1.7` / `0.2.0` 均 0 匹配（`dshVersion` 7 处命中但均为宿主环境探测，无 semver 门禁）；已安装 README.md 亦未记录该约束。
- **建议修法**：二选一——(a) 删掉该 engines 行；(b) 改写为「未在包内声明 `engines.dsh` 门禁；实测可运行于 DSH `0.2.1-rc.2`（`DeepSeek Harness.exe` FileVersion）」。

#### U7 · dsh-context-insight：版本号过期
- **文件 / 行号**：[dsh-context-insight/SKILL.md](.claude/skills/dsh-context-insight/SKILL.md) L10
- **问题**：「current version 0.73.2」与本机实际安装版本不符，实际为 `0.73.3`。（`0.73.2` 在 npm 上真实存在，属「过期」而非「编造」。）
- **证据**：`node_modules/dsh-context/package.json` L3 `"version": "0.73.3"`；profile `package.json` 依赖 `"dsh-context": "0.73.3"`；`lib/index.js` 头注释 `dsh-context v0.73.3 @built 2026-10-19`；`dsh plugin --profile desktop list` 输出 `dsh-context@0.73.3`。
- **建议修法**：改为 `current version 0.73.3`；更稳妥的做法是去掉硬编码版本，改写为「版本随 `dsh plugin --profile desktop list` 输出而定」。

#### U8 · dsh-context-insight：Context browser 类目越界
- **文件 / 行号**：[dsh-context-insight/SKILL.md](.claude/skills/dsh-context-insight/SKILL.md) L16-17
- **问题**：声称 browser 可检视「tools, tool results, images, events, agent teams」。其中 **events 与 agent teams 不属于 context browser 类目**——browser 只有 7 个类目；events 是独立「Context Events」卡片，agent teams 是独立「Fleet」标签页。
- **证据**：`lib/client.js` 内联 locale 的 `cat.*` 键共 7 项：`system / tools / user / inject / skill / assistant / tool`，无 event / agent 类目；同文件另有独立键 `tab.fleet`（编队）。tools / tool results / images 三项有佐证（`cat.tools` / `cat.tool` / 附件 image+file 卡片）。
- **建议修法**：改为「inspect the individual items: system prompt, tool definitions, user / assistant messages, injected content, skill injections, tool results, and attachments (images / files)」，并把 events 与 agent teams 移到单独一行说明它们是相邻的 Context Events 卡片与 Fleet 标签页。

### LOW（19 项）

| # | 文件 / 行号 | 问题 | 证据 | 建议修法 |
|---|---|---|---|---|
| U9 | dsh-plugin-market L69-70 | 「Compatibility is enforced」未说明前提：门禁只在插件自带 `engines.dsh` 时生效 | 两个受审包（dshmarket 1.66.39 / dsh-whale-widget 0.4.2）`package.json` 均无 `engines` 字段；隔离 fixture 证明门禁真实存在且会拒绝安装，但对二者不生效 | 补一句：「仅当插件 `package.json` 声明 `engines.dsh` 时才会在安装时校验并拒绝；未声明者不做 DSH 版本门禁」 |
| U10 | dsh-plugin-market L14 | 「Settings → Plugins」菜单位置无法从 CLI 侧验证 | `dshmarket/client/client.js` 中 Plugins / 插件 / Settings 字符串计数 75 / 140 / 15，`lib/index.js` 装载路由，构成合理佐证；但 headless 下无法直接断言菜单位置 | 措辞降级为「Plugins 页面（通常位于 Settings → Plugins）」，或经 GUI 核对后保留 |
| U11 | dsh-plugin-market L60-62 | pnpm 日志描述不完整：成功时也为 0 字节，不区分成败 | 真实 desktop profile 的 16 个 `operation-*` 目录中 8 个 `pnpm.log` 为 0 字节；失败时可读的是 stderr 摘要 + pnpm.log 的 `Command failed with exit code 1 ...` 一行 | 补一句：「0 字节日志属正常；失败时优先看 stderr 与 pnpm.log 的 'Command failed' 行」 |
| U12 | dsh-plugin-market L39 | `link:<absolute-dir>` 安装的附加行为未提 | 语法本身已验证可用（隔离 profile 实跑生成 `dsh-whale-widget@link:...` 符号链接依赖，`list` 可见）；但会触发 pnpm `The store at ... is not used because packages cannot be hard linked` 警告，且不校验 link 目标的 `engines.dsh` | 可选补一句：「link: 安装可能出现 pnpm store hard-link 警告，属正常现象」 |
| U13 | dsh-plugin-market L46-47 | `Test-Path <prof>\<package>\cordis.patch.yml` 作为通用规则不完整 | 对两个受审插件均成立（dshmarket 4 行 / dsh-whale-widget 15 行）；但 link: 安装时该文件在 link 目标目录而非 profile node_modules，且 DSH 规范中 patch 由 `package.json` 的 `dsh.bundle.patch` 声明（两包均为 `./cordis.patch.yml`） | 改为读 `package.json` 的 `dsh.bundle.patch` 字段定位 patch 文件，更稳 |
| U14 | dsh-plugin-market L20 | 「Its own update-api-v1 endpoint」未加可用前提 | `lib/update-api-v1.js` 与 `lib/types/update-api-v1.d.ts` 存在，导出 `UPDATE_API_V1_SCHEMA='dsh-market/update-api/v1'`、`MAX_UPDATE_OPERATIONS_V1=50`；但 `lib/index.js` L2-3 注释明写「mounts the market's HTTP routes once the profile composes the webServer and shell services」，`ctx.inject(['webServer','loader'], ...)` | 补一句：「该端点仅当 dshmarket 已安装且所在 profile 组合了 webServer/shell 服务时可用」 |
| U15 | dsh-plugin-market L18-19 | 「daily-refreshed registry … reviewed before publishing」仅部分可验证 | **交叉验证下调**：`dshmarket/README.md` L123 明写「Fetched live on every open from awesome-dsh-plugin.com/plugins.json — … star counts refreshed daily by CI」，L113 说明收录走 awesome-dsh-plugin 仓库 PR。「daily-refreshed」有据；「reviewed before publishing」仅由 PR 模型间接支持 | 改为可查措辞：「registry 每次打开实时从 awesome-dsh-plugin.com 抓取，star 数由 CI 每日刷新；新插件通过 awesome-dsh-plugin 仓库 PR 收录」 |
| U16 | dsh-plugin-market L67-68 | 错误信息引文标点偏差，且遗漏另外两个同样受限的开关 | 原文为 `error: profile "desktop" is managed exclusively by the Electron application`（**无句点**，integrator 实跑 `--dump-config` exit 1 复现）；`--dump-config-schema` 与 `--dump-default-config` 同样被拒（均已实跑复现） | 引文去掉句点，并补 `--dump-config-schema` / `--dump-default-config` 同样受限 |
| U17 | whale-balance L52-54 | 「no `dsh.client` half」作为 whale 特性单独强调，与 dsh-plugin-market 表述不对称 | `package.json` 确实只有 `dsh.bundle.patch`，无 `dsh.client`；但 dshmarket **有** `dsh.client`（inject 3 个 `@deepseek-ai` 客户端包 + `platform: web`，已核实）。真实区别是 whale 走 `assets/whale-widget.js` 静态注入 | 补一句对比：「dshmarket 通过 `dsh.client` 注入客户端包，dsh-whale-widget 则靠 `assets/whale-widget.js` 静态文件注入」 |
| U18 | whale-balance L47, L53 | 「so `assets/` must be present for the widget to render」略绝对 | `lib/index.js:687-691` 的 `WIDGET_FILE_CANDIDATES` 依次回退 `lib/whale-widget.js`、包根 `whale-widget.js`、`assets/whale-widget.js`；assets 下现有 16 个文件（含 `whale-widget.js`） | 改为「优先从 `assets/whale-widget.js` 读取（`lib/index.js` 亦兼容 `lib/` 与包根的同名文件）」 |
| U19 | whale-balance L60-61 | 「Sound files are `.mp3` / `.wav`」遗漏 gif/png 同样可替换；且未区分「装新插件要重启」与「改 assets 不必重启」 | assets/ 含 `.mp3` ×4、`.wav` ×5、`.gif` ×3、`.png` ×3；`lib/index.js:685-686` 注释明写「改 widget 后硬刷新页面即生效(无需重启 DSH)」「每次请求按 mtime 判断是否需要重读」 | 补一句：「仅改 `assets/` 下文件时硬刷新页面即可生效，不必重启 DSH（安装新插件仍需重启）」 |
| U20 | dsh-context-insight L34 | 「host half (registers the context surfaces)」不准确——UI surface 实际由 client 注册 | `lib/index.js` 中 `sidebarRightTabs` / `inputTriggers` 均 **0 次**；其注册的是 `sessionProjections`（9 处）、`systemPrompt` 前后缀段（2 处）、`/api/dsh-context/{detail,fleet,skills,attachment,balance,backfill}` 路由。`sidebarRightTabs.register({id:'dsh-context'})` 与 `inputTriggers registerSource('/context')` 均在 `lib/client.js`（各 2 处） | 改为「host half (session projections, system-prompt segments, `/api/dsh-context/*` routes)」 |
| U21 | dsh-context-insight L64-66 | 「reads through `@deepseek-ai/dsh-api-remotes` and `dsh-client-connection`」中 `dsh-api-remotes` 无任何引用 | `lib/client.js` 中 `dsh-api-remotes` **0 次**；实际 require 4 个模块：`react` / `react-dom` / `react/jsx-runtime` / `@deepseek-ai/dsh-client-ui-primitives`；数据经 `fetch('api/dsh-context/{detail,fleet,skills,attachment,balance,backfill}')` 与 `ctx.get('connection').rpc.call` 取得。`connection` 部分有佐证 | 改为「reads through the host's `/api/dsh-context/*` HTTP routes and a `connection` RPC call」 |
| U22 | dsh-context-insight L36, L67 | 「locale/*.json en + zh」字面成立但实质内容只在 bundle 内 | `locale/en.json`（226 B / 6 行）与 `locale/zh.json`（247 B / 6 行）**仅含 `meta.title` + `meta.description`**；全部 UI 文案以 en/zh 两套内联 locale map（900+ 键）打包在 `lib/client.js` | 改为「`locale/*.json` 提供 en + zh 的插件元信息；UI 文案的 en/zh 映射内联打包在 `lib/client.js`，随 DSH 界面语言切换」 |
| U23 | dsh-context-insight L9 | 安装命令 `@latest` 与本机 pin 不一致 | `dsh plugin --help` 确认 `--profile <name>` + pnpm 转发 `add <pkg>` 形式可用；但本机 profile `package.json` 是精确 pin `0.73.3` 而非 `@latest`，且 `@latest` 会解析到 0.73.3，与 L10 的 0.73.2 自相矛盾 | 与 U7 一并处理：统一改为 `add dsh-context@0.73.3` 或去掉版本号说明 |
| U24 | openbiliclaw L42-59 | 命令表缺 `doctor` 与 `emit-skill-descriptors` | CLI `--help` 列出 27 个命令，含 `doctor` 与 `emit-skill-descriptors`；`skills/openbiliclaw-adapter/SKILL.md` 明确称「complete source of truth is `openbiliclaw_get_capabilities` / `emit-skill-descriptors`」，而本 SKILL.md 未提后者 | 表格补两行：`doctor`（环境自检）、`emit-skill-descriptors`（导出技能描述符） |
| U25 | agent-teams L93 | 「`fork` inherits completed lead turns」无代码佐证 | `lib/index.js:60` 仅 `memberProvider: z.string().default('spawn')`；`cordis.patch.yml:21 memberProvider: spawn`；lib 全库 grep `fork` / `inherits` 只得 `lineage.js:193 forkLineageNote`（诊断「本会话是某会话的 fork」）与 fork 回归解析辅助，无「继承已完成 lead turns」语义 | 改为「`memberProvider` defaults to `spawn`; `fork` reuses the parent session's lineage」或直接删去后半句 |
| U26 | openbiliclaw L91 | 「already running as background job」与 U1 同源 | 同 U1 | 同 U1 |

> 注：U26 与 U1 同源同证，单列是为保留原始 reviewer 的两处行号引用（L21 / L91）；修复时一并处理。

---

## 4. 已验证无误的声明清单

以下声明经 integrator 独立复核或 reviewer 实证，**确认与事实一致**：

### agent-teams（5/5 项核心核查通过）
1. 版本 `0.1.25` — `package.json` L3 `"version": "0.1.25"`；profile 依赖 `^0.1.25`；`release-notes/v0.1.25.md` 存在；`bundles[]` 含该插件。
2. 12 个 `agent_teams_*` 工具名 — `lib/tools.js` 实际注册 **14** 个（create / edit_plan / approve / add_member / remove_member / create_task / reassign_task / claim_task / update_task / amend_task / send_message / status / resume / delete），SKILL.md 表列 12 项全部逐字命中，无编造。
3. 状态目录布局 — `lib/state.js:4-6` 注释 + `createTeamDir`（mkdir inbox、写 team.json）+ `appendMailbox(inbox/<key>.jsonl)`；`lib/index.js:59` `stateDir` 默认 `.agent-teams`；`cordis.patch.yml:19` 一致；实盘 `.agent-teams/skill-audit/team.json` 存在（本团队即实例）。
4. captain 协议 — `approval=required`（`tools.js:836`）；不得同轮批准（`tools.js:1100` / `index.js:108` "never call it during the turn that created or edited the plan"）；质量门禁链 `requirements → implementation → verification → review → integration`（`quality-gates.js:7-13` + `index.js:113`）；`attempt_id` 缺失/陈旧硬报错（`tools.js:1798-1802`）。
5. `compatibility.json`（47 行，recommendedHost 0.2.1-rc.2）与 `scripts/doctor.mjs` 均存在于 `node_modules/@nanmicoder/dsh-agent-teams/`。

### dsh-plugin-market
6. dshmarket 版本 `1.66.39` — 与 `node_modules` 实际一致，`dsh plugin --profile desktop list` 输出 `dshmarket@1.66.39`。
7. CLI 命令可跑 — 实跑 `plugin --profile desktop list` / `why dshmarket` / `add` / `remove` / `version-exemptions` 均 exit 0。
8. `link:<absolute-dir>` 安装语法 — 隔离 profile 实跑可用，生成符号链接依赖。
9. `--dump-config` 被拒 — 实跑 exit 1，文案逐字一致（仅标点见 U16）。
10. `allow-version` 转义 — 隔离 profile 实测可用并写入 `compatibility.json`。
11. "incompatible with dsh `<version>`" 措辞 — **integrator 独立从 `.plugin-manager/logs/operation-OcXNek/pnpm.log` 取证**：原文 `dsh: installation rejected: Plugin @openbiliclaw/dsh-plugin@0.4.0 is incompatible with dsh 0.2.1-rc.2: requirements {...}. Running it may cause crashes or data loss.`，SKILL.md 引文成立（reviewer 原 F1 发现已据此撤回）。
12. `add` 自动写入 `dsh.profile.bundles[]` — reviewer 在干净隔离 profile 实测：add 前无 `dsh.profile`，add 后自动生成 `"dsh":{"profile":{"bundles":["dsh-whale-widget"]}}`（原 F7 发现已据此撤回）。
13. dshmarket 确有 `dsh.client` — `inject` 3 个 `@deepseek-ai` 包 + `platform: web` + `bundle.patch: ./cordis.patch.yml`。

### whale-balance
14. 版本 `0.4.2` — 与 `node_modules` 及 `plugin list` 一致。
15. 文件布局 — `lib/index.js`、`lib/accounting.mjs`、`assets/`（16 个文件）、`cordis.patch.yml`（15 行）、`icon.png` 全部存在。
16. 「package.json 无 `dsh.client` 声明」— 属实（仅 `dsh.bundle.patch`）。
17. assets 齐全度 — 16 个文件：`.mp3`×4、`.wav`×5、`.gif`×3、`.png`×3、`whale-widget.js`。
18. `cordis.patch.yml` 挂载行内容与 SKILL.md YAML 块一致。

### dsh-context-insight
19. `dsh.client.inject` 6 个包名 — 与 `package.json` L61-68 **逐字一致**（`Compare-Object` 零差异），无多写/少写/拼错；`"platform": "web"`、`"bundle": {"patch": "./cordis.patch.yml"}` 亦逐字一致。
20. 文件布局 — `lib/index.js`、`lib/client.js`、`locale/en.json`、`locale/zh.json`、`cordis.patch.yml` 全部真实存在；`cordis.patch.yml` 内容 `- insert: - id: dsh-context / name: dsh-context` 与 SKILL.md L54-58「Mount row」逐字一致。
21. `engines.dsh` 兼容范围 `>=0.1.7-rc.2 || >=0.2.0-rc.2` — 与 `package.json` L18 逐字一致；已装 DSH `0.2.1-rc.2`（integrator 实跑 `--version` 复核）确实被覆盖。
22. 功能整体（dashboard / browser / sidebar / command / token & timing stats）— 均有代码或 README 佐证，非凭空推断：Dashboard（`stats.title` / `overview.title` / `timing.title: Timing Stats`）、Sidebar（`sidebarRightTabs.register` + `sidebar.right.pane.tab` slot）、Command（`/context` 经 `inputTriggers.registerSource`）、Token/timing（`timing.gen` / `blockTimes` / `callTimes` + cost 估算）。
23. `locale/en.json` 与 `locale/zh.json` 均存在（内容范围见 U22）。

### openbiliclaw
24. 安装路径 `<插件目录>/OpenBiliClaw` 及 `config.toml` — 目录存在（含 `src/`、`pyproject.toml`、`uv.lock`、`data/`、`logs/`），`config.toml` 909+ 行；`[llm.instances.deepseek].api_key = ""` 属实，`[bilibili].cookie = ""` 属实。
25. bridge 协议版本 — `agent-bridge/v2`、adapter `0.3.229`、**24 capabilities**（integrator 实跑 `capabilities` 复现 `ok:true`、`skill_names.Count=24`）。
26. 命令表 — 与 CLI `--help` 的 27 个命令及 adapter SKILL.md 一致，表内 21 项逐字正确（缺 2 项见 U24）。
27. 「只有 `capabilities` 无需 LLM，其余报 `RegistryBuildError`」— reviewer 实测 6 个命令：`capabilities` 成功返回 `ok:true`；`get-profile` / `runtime-status` / `list-saved` / `recommend` / `activity-feed` 全部抛 `openbiliclaw.llm.registry.RegistryBuildError: No LLM instances are available from the current configuration.`（registry.py:197）。
28. `@openbiliclaw/dsh-plugin@0.4.0` 未挂载及原因 — `package.json` 的 8 项 `@deepseek-ai/dsh-*` peerDependencies 均为 `^0.1.5-rc.2`；运行时 FileVersion `0.2.1-rc.2`（integrator 复核实测）；`.plugin-manager/logs/operation-OcXNek/pnpm.log` 原文记录 `installation rejected: Plugin @openbiliclaw/dsh-plugin@0.4.0 is incompatible with dsh 0.2.1-rc.2: requirements {...^0.1.5-rc.2...}`；desktop `bundles[]` 不含该插件。
29. 「LLM credentials NOT configured — backend is in degraded mode」「HTTP bridge answers 503」— 均与 `serve-api.log` L37 `FastAPI started in degraded mode` 及 L70-72 三次 503 一致。

---

## 5. 撤回记录（不计入发现数）

reviewer-web-market 在补充实证后自行撤回两项原 medium 发现，integrator 已独立复核，**撤回成立**：

| 原编号 | 原判定 | 撤回理由 | integrator 复核 |
|---|---|---|---|
| F1 | medium | 用自制 fixture（`engines.dsh ^99.0.0`）实测，DSH 0.2.1-rc.2 实际拒绝文案含「is incompatible with dsh 0.2.1-rc.2」，SKILL.md 措辞是原文核心，F1 为误报 | **复核确认**：integrator 独立从真实 `.plugin-manager/logs/operation-OcXNek/pnpm.log` 提取到同一措辞 |
| F7 | medium | 干净隔离 profile 实测 `add dsh-whale-widget@0.4.2`：add 前 package.json 无 `dsh.profile`，add 后自动生成 `dsh.profile.bundles=["dsh-whale-widget"]`；此前看到的 `bundles:[]` 是 remove 之后的末态 | **复核确认**：`dsh plugin --profile desktop list` 输出 6 个已装插件，与 add 自动 reconciliation 行为不矛盾 |

修正后 t1 统计：blocker 0 / high 0 / medium 2（F11、F12）/ low 10 → 本报告按 8 条 low 计（F9 交叉验证后下调为 U15，保留）。

---

## 6. 汇总结论

1. **没有 blocker，没有编造性事实。** 5 份 SKILL.md 中所有版本号、路径、CLI 命令、包名、协议版本、能力数量经复核均真实存在，唯一 high 是「后端已停却声称运行」这类**时效性陈述过期**，而非虚假声明。
2. **两类系统性问题**：
   - **版本号 / 运行状态硬编码快照**（U1/U26、U7、U23）：四处都是把某一时刻的机器状态写成了永久事实。建议统一改为条件式表述或指向可复跑的验证命令。
   - **细节归因失真**（U8、U20、U21、U17）：都是「方向对、主语错」——把 client 侧注册说成 host 侧、把独立标签页说成 browser 类目、把未引用的包名说成数据通路。改动量都很小，但会实质误导读者。
3. **修复优先级建议**：
   - P0（1 项，2 处行号）：U1/U26 — openbiliclaw 运行状态，会导致读者按文档执行失败。
   - P1（7 项 medium）：U2、U3、U4、U5、U6、U7、U8 — 数字口径、包内容边界、版本号、类目归属。
   - P2（18 项 low）：措辞补全与引文校正，可批量处理。
4. **agent-teams 与 dsh-plugin-market 可直接采信**；whale-balance、dsh-context-insight、openbiliclaw 建议按上述建议修法小修后即可达到「可信」。

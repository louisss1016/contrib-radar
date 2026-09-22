---
name: contrib-radar
description: 开源贡献侦察兵。核心定位：Find the right open-source contribution before you write code — 在写代码之前，用可解释的打分和碰撞检测帮你锁定真正值得投入的贡献机会。自动发现适合贡献的开源项目（按技术栈、活跃度、友好度筛选），深入分析项目中可提交 PR 的具体切入点（Issue 筛选 + 启发式打分 + Collision Risk 分级 + Why this issue 决策理由 + 架构缺陷分析 + Top 3 贡献建议），并支持持续监控与自动贡献模式。当用户想找开源项目做贡献、挖掘 PR/Issue 机会、分析某个 GitHub 仓库的贡献切入点、寻找 good first issue、准备开源贡献面试素材、或要求每天自动扫描贡献机会时使用。触发词：找开源项目、开源贡献、PR 切入点、Issue 挖掘、good first issue、给 XX 项目提 PR、开源项目分析、contribute to open source。若用户提供具体仓库地址，跳过项目发现，直接定位该项目的 PR 与 Issue 机会。
agent_created: true
---

# Contrib Radar — 开源贡献雷达

## Overview

**核心定位：Find the right open-source contribution before you write code.**

帮助用户在写代码之前，用可解释的打分和碰撞检测锁定真正值得投入的贡献机会：**找到合适的项目 → 找到合适的切入点（PR/Issue 方向）→ 决策支持 → 实现 → 提交 → 维护**。
内容源自《AI Agent 开源项目贡献完整流程手册》，并融合了 GitHub 官方指南与社区最佳实践（项目健康度打分、聚合站点、维护者沟通规范）。

核心原则：**先沟通再动手、小步快跑、一切结论定位到具体文件与函数，禁止泛泛而谈、禁止编造数据。**

v3 更新：脚本层基于共享封装 `scripts/github_api.py`（统一限速/降级）；`find_issues.py` 新增启发式打分与撞车检测（剔除已被 open PR 引用的 Issue）；`repo_health.py` 新增 AI 生成代码政策检查；`discover_repos.py` 新增新手甜蜜区模式（--beginner）与 --json 导出。
v3.1 更新：新增 Route C 持续监控（每日定时任务）与 Route C+（自动实现 + 人工确认提交）。
v3.2 更新：基于实战反馈的全链路增强——`find_issues.py` 标签零命中自动 fallback 全量 issue + milestone 打分维度；`repo_health.py` AI 政策去误报；`contribution-workflow.md` 补认领检测/baseline/rebase/可复现测试报告/Windows 坑；SKILL.md 降级链加 MCP/OAuth；Route C+ 扩展为完整自动贡献流程（状态持久化 + 质量门控 + PR 生命周期跟踪）。
v3.3 更新：决策可解释性升级——`find_issues.py` 新增 Collision Risk 分级（LOW/MEDIUM/HIGH + 原因 + 建议）与 Why this issue? 决策理由清单（✓/⚠）；README 新增 Case Study 漏斗图（From 1,000 Issues → 3 Contributions）与 Core vs Agent Workflow 能力边界表；项目定位收紧为"Find the right open-source contribution before you write code"。
v3.4 更新：打分模型升级——Contribution Score 拆分为 Issue Quality（清晰度30+标签15+新鲜度25+milestone20+讨论10）和 Contribution Feasibility（撞车30+修改范围25+新手友好25+技术栈匹配20）双维度，最终分 = Quality×0.5 + Feasibility×0.5；新增 `--stack` 技术栈匹配度（Stack Match % + 逐项 ✓/—），匹配仓库主语言和 issue 正文关键词。
v3.5 更新：新增 `references/api-pr-submission.md`——git clone/push 被代理或防火墙阻断时，改用纯 GitHub REST API（fork → Git Data API → PR）完成提交；Route C+ 提交步骤挂接该降级通道。
v3.6 更新：Route C+ 全面自动化——取消默认流程中的两个人工确认点，扫描、筛选、实现、提交、维护全程无人干预；6 项质量门控 + 冷却期 + 黑名单成为唯一安全防线（不过不提交）；人工确认降级为可选保守模式（用户在 Query 中显式开启才生效）。
v3.7 更新：执行可视化——新增 `scripts/progress.py` 共享进度事件模块，五个入口脚本按阶段向 stderr 发射 `[CR-PROGRESS]` 单行 JSON 事件（管道模式，agent/CI 消费）或刷新 ASCII 进度条（TTY 模式，人类观看），stdout 数据契约不受影响；SKILL.md 新增「执行可视化规范」（双层更新机制 / 进度卡片四区域 / Route 阶段序列表 / 异常状态处理 / 核心功能不受影响硬约束）。
v3.6.1 更新：Windows 兼容性修复——`github_api.py` 新增 `ensure_utf8_stdio()`（交互终端切代码页 65001 + stdio reconfigure UTF-8），五个入口脚本启动时调用；修复 Windows GBK(cp936) 控制台/管道下输出 ⭐🟢✓• 等字符时 `print` 抛 `UnicodeEncodeError` 直接崩溃的问题（JSON 输出为 `ensure_ascii=False`，必崩）；新增 4 个回归测试。

## 触发条件

- 用户想找开源项目做贡献但不知道选哪个（"帮我找个适合贡献的开源项目"）
- 用户给了具体仓库地址，想知道能提什么 PR / Issue（"分析这个项目有什么贡献机会"）
- 用户想挖 good first issue、评估某项目是否值得投入
- 用户想把开源贡献作为面试素材来规划
- 用户要求"每天/定期盯一下有哪些可认领的 Issue"（Route C，可由定时任务触发）
- 用户要求"发现值得做的 Issue 就自动实现并提交 PR"（Route C+ 自动贡献模式）

## 输入

| 输入 | 必填 | 说明 |
|------|------|------|
| 项目地址 | 否 | GitHub 仓库 URL。**提供则跳过项目发现，直接进入 Route B 分析** |
| 技术栈 | 否 | 如 "Python、LangChain、MCP"。Route A 必需，缺失时先问一次 |
| 兴趣方向 | 否 | 如 "AI Agent / 后端框架 / DevOps"，默认 AI Agent |
| 时间预算 | 否 | 默认 "2 周内可完成的 PR" |

## 路由逻辑

```
用户提供仓库 URL？
├── 是 → Route B：直接分析该项目的 PR/Issue 切入点
├── 否 + 用户要求每日/定期监控或自动贡献 → Route C / C+
└── 否 → Route A：发现候选项目 → 用户选定一个 → 进入 Route B
```

## 工具降级链

所有 GitHub 数据获取按以下顺序降级，任一级失败自动降下一级：

1. **已绑定的 GitHub MCP / OAuth 连接**（如 `github-remote` skill 的 MCP 工具）：最可靠，走 OAuth 认证，不受未认证限流影响，支持读写操作
2. `gh` CLI（已安装且已登录时）：`gh search repos` / `gh search issues` / `gh pr create`
3. skill 自带脚本直连 API（共享封装 `scripts/github_api.py`，零依赖，支持 GITHUB_TOKEN）：
   `scripts/discover_repos.py` / `scripts/find_issues.py` / `scripts/repo_health.py`
4. WebFetch 直接抓 GitHub 页面或 API
5. WebSearch（最后手段，数据可靠性最低，需标注"未实时核验"）

> **限流提示**：未认证时 Search API 约 10 次/分、core API 约 60 次/时；脚本已内置自适应限速
> （只对 search 端点打点，403 时按 X-RateLimit-Reset 等待重试）。多仓库批量筛查强烈建议设置
> `GITHUB_TOKEN`（core 5000/时、Search 30/分）或使用已绑定的 MCP/OAuth 连接，避免等待或降级。
> **注意**：未认证 API 限流耗尽后，MCP/OAuth 连接不受影响，应优先切换到 MCP 通道。

## 执行可视化规范（v3.7）

执行期间必须让用户清晰看到运行进度。核心原则：**真进度可以慢，假进度不许有**。

### 更新机制（双层）

| 层 | 载体 | 消费者 | 形式 |
|---|---|---|---|
| 脚本层 | 五个入口脚本 + `scripts/progress.py` | agent / CI | 管道模式：stderr 逐行 `[CR-PROGRESS] {json}` 事件（纯 ASCII，GBK 安全）；TTY 模式：ASCII 进度条原地刷新 |
| Agent 层 | 对话内进度卡片 | 用户 | 阶段边界刷新，聚合脚本事件 + agent 自身执行状态 |

- 脚本事件字段：`phase / status(start|running|ok|warn|error|skip|done) / current / total / item / detail`。
- 批量命令（体检多仓库、扫描多 issue）执行期间无法增量刷新卡片：条目级进度以 stderr 事件为准，命令返回后在下一次卡片刷新时汇总。
- 纯 LLM 阅读阶段（读 CONTRIBUTING、逐条读 issue 正文）没有脚本事件，卡片显示"进行中"，**不得编造百分比**。
- 双通道互斥且自动选择：stderr 是管道（agent 消费）出 JSON 事件；stderr 是 TTY（人类观看）出 ASCII 进度条。`CR_PROGRESS_BAR=1` 可强制进度条，`CR_QUIET=1` 或 `--quiet` 全部关闭。

### 展示形式（进度卡片）

预计 ≥2 个阶段或 ≥3 次工具调用的执行，渲染一张进度卡片，包含四个区域：

1. **阶段步骤条**：当前 Route 的阶段序列（见下表），已完成 ✓ / 进行中 ▶ / 未开始 ○ / 失败 ✗；
2. **当前状态行**：正在执行的动作 + 计数器（如"体检 3/10"）+ 当前条目名；
3. **阶段性成果**：已完成阶段的关键数字（候选 N 个 / 高分 issue M 条 / 待跟踪 PR K 个）；
4. **异常区**（有异常才出现）：红色状态 + 失败项 + 已采取的降级动作。

Route 阶段序列（卡片步骤条的数据源，脚本 phase 名与之对齐）：

| Route | 阶段序列 | 脚本 phase 名 |
|---|---|---|
| A | 画像收集 → 项目发现 → 健康度体检 → 候选清单 | `repo-discover` / `health-check` |
| B | 项目理解 → Issue 筛选 → 撞车检测 → 架构分析 → Top 3 建议 | `issue-fetch`(+`issue-fallback`) / `collision-detect` / `issue-score` |
| B（认领） | bot 检测 → 冲突检查 → 建议生成 | `claim-bot-detect` / `conflict-check` |
| C | 跨仓扫描 → 撞车复核 → 日报 diff → 输出 | 复用上述 phase |
| C+ | 状态读取 → 打分筛选 → 自动实现 → 质量门控 → 提交 → PR 跟踪 | `pr-track` 等 |

### 异常状态处理

- **单条目失败**（API 错误 / 超时 / 解析失败）：该条目标 ✗ 并继续，批次结束时汇总失败清单与原因（脚本已发 `error` / `skip` 事件，卡片必须呈现）；
- **整阶段失败**（限流 / 认证失效）：显示降级链当前所在层级（MCP/OAuth → gh CLI → 脚本 → WebFetch → WebSearch），按既有降级链执行并如实标注；
- **质量门控未过**（Route C+）：明确显示"未提交" + 未过项，禁止静默跳过；
- **通用红线**：任何异常不得渲染为成功；事件中的 `warn` / `error` / `skip` 必须原样呈现。

### 不干扰核心功能（硬约束）

- 进度输出只走 stderr；`--json` 的 stdout 契约不变（纯 JSON，无进度行混入）；
- 进度代码零第三方依赖；`--quiet` / `CR_QUIET=1` 可完全关闭；
- 进度字符串纯 ASCII（GBK 控制台安全，与 v3.6.1 同一原则）；
- 进度事件不得改变任何打分、筛选、门控逻辑。

## Route A：项目发现（无 URL 时）

1. **收集画像**：确认技术栈、方向、时间预算。只问缺失的关键项，一次问完。
   **技术栈优先确认 Python / TypeScript**——当前前沿 Agent 框架生态以 TypeScript 为主
   （Vercel AI SDK、OpenAI Agents SDK、Mastra、LangGraph.js、Eliza 等），Python 侧以
   LangChain / PydanticAI / OpenAI SDK 为主；用户未指定时先问一句是否考虑 TS 项目，
   不要默认只搜 Python。
2. **生成候选**：运行 `scripts/discover_repos.py --topic <方向> --language <python|typescript> --stars 1000`
   获取候选清单（脚本的 stars/pushed 默认值已对齐手册标准；新手可加 `--beginner` 进入 100~1000 star
   甜蜜区模式）。结果不足时按降级链补充，或引导用户放宽条件。聚合站点等补充渠道见 `references/project-discovery.md`。
3. **健康度筛查**：对候选批量运行 `scripts/repo_health.py <repo1> <repo2> ...`，按手册标准打红绿灯；
   同时查看输出的 **AI 政策** 提示（是否有 AI 生成代码限制声明）。
4. **输出候选清单**（表格），并给出推荐：

| 项目 | Stars | 技术栈 | 最近提交 | Issue 关闭率 | PR 响应 | 健康度 | AI政策 | 推荐理由 |
|------|-------|--------|---------|-------------|---------|--------|--------|---------|

5. **让用户选定 1 个项目**后进入 Route B。禁止替用户擅自决定。

## Route B：贡献切入点分析（有 URL 或 Route A 选定后）

详细维度、筛选条件与输出模板见 `references/opportunity-analysis.md`，严格执行：

1. **项目理解**：读 README.md / CONTRIBUTING.md / CHANGELOG.md / 主入口文件（不存在则跳过）。克隆或在线阅读均可。输出：目录结构（depth=3）+ 核心模块标注 + 2~3 句话概括项目核心机制。
2. **Issue 列表筛选**：先运行 `scripts/find_issues.py <owner/repo> [--stack python,langchain]` 拿到机筛候选
   （默认新手友好标签 / open / 近 60 天活跃 / 无 assignee / **双维度打分**：Issue Quality + Contribution Feasibility → Contribution Score / **Collision Risk 分级**（LOW/MEDIUM/HIGH，HIGH 默认隐藏，加 `--show-collision` 查看）/ **Stack Match**（`--stack` 参数，匹配仓库主语言和 issue 正文）/ **Why this issue? 决策理由清单**（✓/⚠）；
   **标签零命中时自动 fallback 到全量 open issue 列表**，避免漏检不打标签的 roadmap issue）。
   再逐条阅读正文与评论做语义判断（评论中是否有人声称认领、描述是否清晰、改动是否 1~3 个文件可控）。
   按模板表格输出。需要更大候选面时加 `--include-bugs`。
3. **AI 政策前置检查**：读取 CONTRIBUTING.md / 仓库政策，扫描 AI 生成代码限制关键词
   （v3.2 已去误报："llm" 单独命中不触发，必须与禁止性动词组合才算限制声明）。命中"明确禁止"时，标注高风险并建议用户改用
   "理解需求后自行实现、明确标注无 AI 辅助"的方式；命中"相关表述"时提示人工确认口径。
4. **架构层缺陷分析**：AI Agent 类项目按 7 个维度逐一检查（任务规划 / 多 Agent 协作 / 上下文管理 / Human-in-the-loop / 评估框架 / Tool 检索路由 / Streaming 可见性）；非 Agent 项目改用通用维度（见 references 附录）。**每个维度必须定位到具体文件路径 + 函数名**，按"现状/缺陷/影响程度/改进方向/改动范围/面试叙事角度"六段输出。
5. **Top 3 贡献建议**：综合两个维度，按模板输出排序建议（含入口文件、适配度、工作量、面试价值、风险点）。输出前对照 `references/example-analysis.md` 的格式自检清单校准颗粒度。

## 报告落盘约定

Route B 分析完成后，将完整报告写入 `oss-analysis-<owner>-<repo>-<YYYY-MM-DD>.md`（当前工作目录），并向用户展示。后续方案设计阶段直接读取该文件注入上下文，不依赖对话复制粘贴。Route A 的候选清单可追加写入同一文件头部，形成完整决策链。

## Route C：持续监控（每日定时任务）

当用户要求"每天/定期盯一下有哪些可认领的 Issue"、或任务由定时任务（如豆包 cron）触发时启用：

1. **每日例行**（触发后依次执行）：
   - 跨仓库扫描：按 `references/project-discovery.md` 的搜索语法或脚本，扫描
     `label:"good first issue"` / `label:"help wanted"` + `no:assignee` + 用户技术栈语言
     （Python / TypeScript）+ 近 24~48 小时有更新，捕获新增的可认领 Issue；
   - 可选：`discover_repos.py` 发现新候选项目，对高价值新仓库跑 `repo_health.py` 体检（含 AI 政策）；
   - 撞车复核：`find_issues.py` 已内置 open PR 引用剔除，跨仓库扫描时对 top 候选手动复核认领评论。
2. **与上次结果对比**：读取上次日报 `daily-issue-scan-<YYYY-MM-DD>.md`，只输出差异（新增 / 状态变化 / 已认领）。
3. **输出日报**：写入 `daily-issue-scan-<YYYY-MM-DD>.md`，包含：
   - 今日新增可认领 Issue（表格：# / 仓库 / 标题 / 打分 / 链接）
   - 状态变化（新增 N 条 / 被认领 M 条 / 已关闭 K 条）
   - 推荐动作（1~2 条：最值得现在动手的 Issue + 理由）
4. **限速注意**：未认证 Search API 10/min——跨仓库扫描控制搜索次数（每语言 1 次 + 撞车 1 次）；
   设置 `GITHUB_TOKEN`（search 30/min）可放开。脚本见 `scripts/`。

### Route C+：全自动贡献模式（发现 → 实现 → 提交 → 维护）

当用户要求"发现值得做的 Issue 就自动实现并提交 PR"、或定时任务配置为自动贡献模式时启用。

**核心设计：状态持久化 + 质量门控 + 全自动执行（全程无人干预，人工确认为可选保守模式）。**

#### 0. 状态持久化（必须）

定时任务是无状态的，但贡献流程是有状态的。每次运行前读取 `contrib-radar-state.json`（当前工作目录），运行后更新：

```json
{
  "scanned_issues": {
    "owner/repo#25": {"first_seen": "2026-09-11", "status": "pr_submitted", "pr_url": "https://github.com/.../pull/72"}
  },
  "active_prs": [
    {"repo": "helsome/folio", "pr_number": 72, "status": "awaiting_review", "last_check": "2026-09-12T08:00:00Z"}
  ],
  "blacklisted_repos": [],
  "cooldown": {"owner/repo": "2026-09-20"},
  "daily_stats": {"2026-09-11": {"scanned": 27, "candidates": 3, "implemented": 1, "pr_submitted": 1}}
}
```

状态字段说明：
- `scanned_issues`：防止重复扫描/实现同一个 issue
- `active_prs`：跟踪已提交 PR 的生命周期
- `blacklisted_repos`：AI 政策 blocked 或维护者明确拒绝的仓库
- `cooldown`：PR 被关闭后该仓库进入冷却期（默认 7 天），避免反复提交被拒
- `daily_stats`：每日统计，用于复盘

#### 1. 打分筛选（自动）

对候选按可上手度打分（描述清晰度 / 标签 / milestone / 评论甜蜜区 / 新鲜度），满足以下**全部**条件才进入自动实现：
- 预估改动 1~3 个文件
- 工作量可控（预计 < 300 行）
- 仓库 AI 政策非 blocked
- 该 issue 未在 `scanned_issues` 中（未处理过）
- 该仓库不在 `blacklisted_repos` 和 `cooldown` 中
- 该仓库当前没有用户的活跃 PR（同一仓库同时最多 1 个活跃 PR）

#### 2. 选点（自动，可审计）

自动选定打分最高、预估改动最小、Collision Risk 最低的 1 个 issue，把选型依据写入每日日报供事后审计：
- 选定的 issue（标题、链接、打分、预估工作量）
- 简要实现方案（2~3 句话）
- 风险点

**默认直接开始实现，不停下等待确认。** 唯一例外：用户在 Query 中显式开启人工确认（保守模式）时，先展示上述信息、等用户确认后再实现；用户拒绝则标记该 issue 为 `skipped_by_user`，继续下一个候选。

#### 3. 自动实现（按 `references/contribution-workflow.md`）

执行完整流程：
- Baseline 采集（改代码前先跑全量测试记录预先存在的失败）
- 认领方式检测（bot /claim 或评论认领）
- 方案设计 → 接口定义 → 核心逻辑 → 集成 → 测试
- 每步可验证，项目始终可运行

#### 4. 质量门控（硬门槛，不通过不提交）

实现完成后必须通过以下**全部**检查才允许进入提交阶段：
- [ ] 项目原有测试全部通过（或新增失败为 0，与 baseline 对比）
- [ ] typecheck / lint 通过
- [ ] 新增代码有测试覆盖（至少 2~3 个核心用例）
- [ ] 改动行数在阈值内（默认 300 行，超出则建议拆分或标记需人工确认）
- [ ] AI 政策非 blocked
- [ ] 无撞车（提交前最后复核该 issue 无新 open PR 引用）

任何一项不通过 → 记录失败原因到状态文件 → **不提交** → 下次运行时重试（最多 3 次）或跳过。

#### 5. 提交（自动，材料可审计）

质量门控全部通过后**直接执行提交**，完整的「待提交材料」写入每日日报供事后审计：
- 改动文件清单 + diff 摘要
- 可复现测试报告（环境/命令/pass-fail 数量/baseline 对比）
- PR 描述草稿（Problem/Solution/Changes/Testing/Notes）
- Commit 拆分方案

提交步骤：
1. fork 目标仓库（如未 fork）
2. 创建分支（`feat/<issue-number>-<short-desc>`）
3. Conventional Commits 拆分 2~4 个 commit
4. push 到 fork
5. 创建 Pull Request（标题/描述用准备好的材料，关联 `Closes #N`）

> **可选保守模式**：用户在 Query 中显式开启人工确认时，提交前先向用户展示上述材料，确认后才执行。

> **git 不可用时的降级通道**：当 `git clone` / `git push` 被代理、防火墙或大仓库传输阻断（`RPC failed` / `IncompleteRead`），但 REST API 小响应仍可用时，跳过本地 git，改用 **Git Data API** 直接构造 commit 并开 PR（fork → blob → tree → commit → branch ref → PR）。完整流程与脚本见 `references/api-pr-submission.md`。

#### 6. PR 生命周期跟踪（每日自动）

提交后不是结束，每次定时任务运行时检查所有 `active_prs`：
- **CI 状态**：查 check runs，失败则自动尝试修复（如果是简单的 lint/type 错误）或通知用户
- **Review 意见**：有新 review 评论则通知用户，简单的修改（拼写、格式）可自动处理
- **上游更新**：上游 main 有新 commit 且与 PR 文件有交集 → 自动 rebase + 重跑测试 + force push（rebase 冲突复杂时通知用户）
- **无回应跟进**：超过 7 天无 review 回应 → 自动发礼貌跟进评论（"Gentle ping: this PR is ready for review when you have time."）
- **被合并** → 更新状态为 `merged`，记录成果，从 active_prs 移除
- **被关闭** → 更新状态为 `closed`，记录原因，该仓库进入 cooldown

#### 7. 并发与速率控制

- 每天最多实现 N 个 issue（默认 1，可配置），避免贪多嚼不烂
- 同一仓库同时最多 1 个活跃 PR
- GitHub API 调用全局限速（脚本已处理；跨天运行时状态文件中记录剩余配额）
- 优先使用 MCP/OAuth 连接，避免未认证限流

#### 8. 认证要求

提交步骤依赖 GitHub 认证（MCP/OAuth 连接、`gh` CLI 已登录、或 `GITHUB_TOKEN`）；
认证不可用时，自动实现和材料准备不受影响，提交步骤提示用户完成认证后手动执行或下次运行时重试。

#### 9. 红线

- 仓库 AI 政策明确禁止 AI 生成代码（blocked）时不得生成提交材料
- 提交前必须复核无撞车（该 issue 无新 open PR 引用、无新 assignee）
- 质量门控不通过不得提交——全自动模式下这是唯一安全防线，任何一项不过就跳过该 issue，不带病上线
- 默认（全自动）模式下，6 项质量门控全部通过即允许执行 GitHub 写操作（fork / push / create PR / 评论）；保守模式下，写操作前还必须获得用户确认

## 后续阶段（可选，用户确认后执行）

用户选定切入点并想继续推进时，按 `references/contribution-workflow.md` 执行：

- **方案设计**：问题边界定义 → 2~3 个技术方案 + 对比矩阵 → 文件级实现规划 → 起草发给维护者的英文评论（≤150 词，先沟通再写代码）
- **代码实现**：Baseline 采集 → 接口先行 → 逐步实现每步可运行 → 最小侵入 → 风格一致 → 验证（demo + 单测）
- **PR 提交**：Conventional Commits 拆分 2~4 个 commit → PR 描述模板（含可复现测试报告）→ 提交后礼貌跟进
- **PR 维护**：rebase 最新 main → 解决冲突 → 重跑测试更新报告 → force push
- **面试叙事**：按 STAR 六要素整理（背景/贡献/过程/成果/困难/反思），可再压缩为 60 秒面试话术

## 硬性规则

- **禁止编造**：Stars、日期、Issue 编号等数据必须来自实时查询（MCP / WebFetch / gh CLI / 自带脚本），查不到就明说。
- **先认领再动手**：动手前先在 Issue 下认领（bot `/claim` 或评论），避免与他人的工作冲突。发完 `/claim` 不要编辑评论。
- **Baseline 先行**：改代码前先跑全量测试记录预先存在的失败，改完后对比，只有新增失败才是自己的问题。
- **可复现测试报告**：PR 描述的 Testing 字段必须包含环境（runtime/OS/arch）、精确命令、pass/fail/skip 数量、预先存在的失败列表。
- **遵守仓库规范**：任何产出建议必须以 CONTRIBUTING.md 为准；没有贡献指南的项目要标注风险。
- **AI 政策红线**：仓库明确禁止 AI 生成代码贡献时，不得建议"直接让 AI 写代码提交"；应提示理解后自行实现，或换项目。
- **撞车意识**：AI 时代 issue 被认领/被提交 PR 的速度明显加快，动手前必须复核该 Issue 是否已有人在做（含 open PR 引用）。
- **范围控制**：单个 PR 建议改动控制在 300 行以内，超出则建议拆分。
- **PR 维护**：上游 main 更新后及时 rebase，冲突解决后必须重跑测试，force push 用 `--force-with-lease`。
- **非 GitHub 平台**（GitLab/Gitee）：流程通用，但自带脚本仅支持 GitHub，需改用 WebFetch 人工核查活跃度。

## Resources

- `references/project-discovery.md` — 项目筛选标准、活跃度指标、GitHub 搜索语法（日期动态化示例）、聚合站点、健康度打分模型
- `references/opportunity-analysis.md` — 贡献类型、Issue 筛选模板、AI 政策前置检查、7 维架构分析清单、Top 3 输出模板
- `references/contribution-workflow.md` — Baseline 采集 / 认领检测 / 方案设计 / 代码实现 / PR 提交（含可复现测试报告模板）/ PR 维护（rebase/冲突）/ 面试叙事（STAR + 60 秒话术）/ 跨平台注意事项
- `references/example-analysis.md` — 端到端分析示例与格式自检清单（输出颗粒度校准用）
- `references/communication-templates.md` — 英文沟通模板：Issue 认领、方向提案、PR 描述、回应 review、礼貌跟进
- `references/api-pr-submission.md` — git 不可用时的纯 REST API 提 PR 流程（fork → Git Data API → PR），含脚本骨架与坑
- `scripts/github_api.py` — 共享 GitHub API 封装（统一请求/限速/降级/仓库解析），三个脚本共用
- `scripts/progress.py` — 共享执行进度事件（v3.7）：管道模式发 `[CR-PROGRESS]` JSON 事件，TTY 模式刷 ASCII 进度条，全部走 stderr；`--quiet` / `CR_QUIET=1` 关闭
- `scripts/discover_repos.py` — 候选项目发现：`python scripts/discover_repos.py --topic ai-agent --language typescript [--beginner] [--json]`
- `scripts/repo_health.py` — 仓库健康度体检（支持批量 + AI 政策检查，v3.2 去误报）：`python scripts/repo_health.py owner/repo [owner/repo2 ...] [--json]`
- `scripts/find_issues.py` — 可认领 Issue 机筛与打分（含撞车检测 + 标签零命中 fallback + milestone 维度）：`python scripts/find_issues.py owner/repo [--include-bugs] [--json] [--no-fallback]`

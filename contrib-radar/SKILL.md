---
name: contrib-radar
description: 开源贡献侦察兵。自动发现适合贡献的开源项目（按技术栈、活跃度、友好度筛选），并深入分析项目中可提交 PR 或 Issue 的具体切入点（Issue 筛选 + 架构缺陷分析 + Top 3 贡献建议）。当用户想找开源项目做贡献、挖掘 PR/Issue 机会、分析某个 GitHub 仓库的贡献切入点、寻找 good first issue、准备开源贡献面试素材时使用。触发词：找开源项目、开源贡献、PR 切入点、Issue 挖掘、good first issue、给 XX 项目提 PR、开源项目分析、contribute to open source。若用户提供具体仓库地址，跳过项目发现，直接定位该项目的 PR 与 Issue 机会。
agent_created: true
---

# Contrib Radar — 开源贡献雷达

## Overview

帮助用户完成开源贡献的前半段链路：**找到合适的项目 → 找到合适的切入点（PR/Issue 方向）**。
内容源自《AI Agent 开源项目贡献完整流程手册》，并融合了 GitHub 官方指南与社区最佳实践（项目健康度打分、聚合站点、维护者沟通规范）。

核心原则：**先沟通再动手、小步快跑、一切结论定位到具体文件与函数，禁止泛泛而谈、禁止编造数据。**

v3 更新：脚本层基于共享封装 `scripts/github_api.py`（统一限速/降级）；`find_issues.py` 新增启发式打分与撞车检测（剔除已被 open PR 引用的 Issue）；`repo_health.py` 新增 AI 生成代码政策检查；`discover_repos.py` 新增新手甜蜜区模式（--beginner）与 --json 导出。
v3.1 更新：新增 Route C 持续监控（每日定时任务）——每天扫描新出现的可认领 Issue，输出差异日报。

## 触发条件

- 用户想找开源项目做贡献但不知道选哪个（"帮我找个适合贡献的开源项目"）
- 用户给了具体仓库地址，想知道能提什么 PR / Issue（"分析这个项目有什么贡献机会"）
- 用户想挖 good first issue、评估某项目是否值得投入
- 用户想把开源贡献作为面试素材来规划
- 用户要求"每天/定期盯一下有哪些可认领的 Issue"（Route C，可由定时任务触发）

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
├── 否 + 用户要求每日/定期监控 → Route C：持续监控（每日定时任务）
└── 否 → Route A：发现候选项目 → 用户选定一个 → 进入 Route B
```

## 工具降级链

所有 GitHub 数据获取按以下顺序降级，任一级失败自动降下一级：

1. `gh` CLI（已安装且已登录时）：`gh search repos` / `gh search issues`
2. skill 自带脚本直连 API（共享封装 `scripts/github_api.py`，零依赖，支持 GITHUB_TOKEN）：
   `scripts/discover_repos.py` / `scripts/find_issues.py` / `scripts/repo_health.py`
3. WebFetch 直接抓 GitHub 页面或 API
4. WebSearch（最后手段，数据可靠性最低，需标注"未实时核验"）

> **限流提示**：未认证时 Search API 约 10 次/分、core API 约 60 次/时；脚本已内置自适应限速
> （只对 search 端点打点，403 时按 X-RateLimit-Reset 等待重试）。多仓库批量筛查强烈建议设置
> `GITHUB_TOKEN`（core 5000/时、Search 30/分），避免等待或降级。

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
2. **Issue 列表筛选**：先运行 `scripts/find_issues.py <owner/repo>` 拿到机筛候选
   （默认新手友好标签 / open / 近 60 天活跃 / 无 assignee / 已剔除被 open PR 引用的撞车条目，并附 0~100 启发式打分）。
   再逐条阅读正文与评论做语义判断（评论中是否有人声称认领、描述是否清晰、改动是否 1~3 个文件可控）。
   按模板表格输出。需要更大候选面时加 `--include-bugs`。
3. **AI 政策前置检查**：读取 CONTRIBUTING.md / 仓库政策，扫描 AI 生成代码限制关键词
   （ai-generated / copilot / llm / no ai 等）。命中"明确禁止"时，标注高风险并建议用户改用
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

## 后续阶段（可选，用户确认后执行）

用户选定切入点并想继续推进时，按 `references/contribution-workflow.md` 执行：

- **方案设计**：问题边界定义 → 2~3 个技术方案 + 对比矩阵 → 文件级实现规划 → 起草发给维护者的英文评论（≤150 词，先沟通再写代码）
- **代码实现**：接口先行 → 逐步实现每步可运行 → 最小侵入 → 风格一致 → 验证（demo + 单测）
- **PR 提交**：Conventional Commits 拆分 2~4 个 commit → PR 描述模板（Problem/Solution/Changes/Testing/Notes for Reviewer）→ 提交后礼貌跟进
- **面试叙事**：按 STAR 六要素整理（背景/贡献/过程/成果/困难/反思），可再压缩为 60 秒面试话术

## 硬性规则

- **禁止编造**：Stars、日期、Issue 编号等数据必须来自实时查询（WebFetch / gh CLI / 自带脚本），查不到就明说。
- **先认领再动手**：建议用户动手前先在 Issue 下评论认领，避免与他人的工作冲突。
- **遵守仓库规范**：任何产出建议必须以 CONTRIBUTING.md 为准；没有贡献指南的项目要标注风险。
- **AI 政策红线**：仓库明确禁止 AI 生成代码贡献时，不得建议"直接让 AI 写代码提交"；应提示理解后自行实现，或换项目。
- **撞车意识**：AI 时代 issue 被认领/被提交 PR 的速度明显加快，动手前必须复核该 Issue 是否已有人在做（含 open PR 引用）。
- **范围控制**：单个 PR 建议改动控制在 300 行以内，超出则建议拆分。
- **非 GitHub 平台**（GitLab/Gitee）：流程通用，但自带脚本仅支持 GitHub，需改用 WebFetch 人工核查活跃度。

## Resources

- `references/project-discovery.md` — 项目筛选标准、活跃度指标、GitHub 搜索语法（日期动态化示例）、聚合站点、健康度打分模型
- `references/opportunity-analysis.md` — 贡献类型、Issue 筛选模板、AI 政策前置检查、7 维架构分析清单、Top 3 输出模板
- `references/contribution-workflow.md` — 方案设计 / 代码实现 / PR 提交 / 面试叙事（STAR + 60 秒话术）全流程模板
- `references/example-analysis.md` — 端到端分析示例与格式自检清单（输出颗粒度校准用）
- `references/communication-templates.md` — 英文沟通模板：Issue 认领、方向提案、PR 描述、回应 review、礼貌跟进
- `scripts/github_api.py` — 共享 GitHub API 封装（统一请求/限速/降级/仓库解析），三个脚本共用
- `scripts/discover_repos.py` — 候选项目发现：`python scripts/discover_repos.py --topic ai-agent --language typescript [--beginner] [--json]`
- `scripts/repo_health.py` — 仓库健康度体检（支持批量 + AI 政策检查）：`python scripts/repo_health.py owner/repo [owner/repo2 ...] [--json]`
- `scripts/find_issues.py` — 可认领 Issue 机筛与打分（含撞车检测）：`python scripts/find_issues.py owner/repo [--include-bugs] [--json]`

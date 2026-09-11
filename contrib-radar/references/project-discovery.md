# 项目发现与筛选参考（Route A）

## 一、项目筛选标准（手册标准）

合适的项目需同时满足：

1. **方向强相关**：与用户目标领域相关（默认 AI Agent）
2. **Star 数量够多**：有一定社区认可度（参考阈值 ≥1000；新手也可考虑 100~1000 的"甜蜜区"，竞争小、维护者回复快）
3. **仍然活跃**，健康信号如下：

| 指标 | 健康的信号 |
|------|-----------|
| Last commit | 近 1 个月内有提交 |
| Issues 关闭率 | closed/open 比例 > 1 |
| PR 合并速度 | 一般 < 2 周有回应 |
| Release 频率 | 每月或每季度有版本 |

补充绿灯信号（社区最佳实践）：
- 有 CONTRIBUTING.md 且步骤清晰
- good first issue 有详细说明
- 维护者在 Issue 下 2~3 天内有回复
- 有 LICENSE 文件

红灯信号（直接淘汰）：
- 最后提交在 6 个月前
- 大量 open PR 长期无人 review
- 无贡献指南、无 Issue 模板
- 维护者在讨论中态度敌对

## 二、GitHub 高级搜索语法

> 以下示例中的日期均为占位符，使用时替换为"当前日期-1 个月"。推荐直接使用脚本
> （`discover_repos.py` 会自动生成），此处语法供 gh CLI / 网页搜索手动使用。

### 发现仓库（AI Agent 方向示例）

```
topic:ai-agent stars:>1000 pushed:>{当前日期-1月}
topic:ai-agent language:typescript stars:>500 pushed:>{当前日期-1月}
```

可替换的 topic：`mcp`、`llm`、`langchain`、`ai-agents`、`rag`、`agent-framework`；
TS 生态专属 topic：`vercel-ai-sdk`、`ai-sdk`、`mastra`、`agents-sdk`、`langgraphjs`、`eliza`、`ai-agents-ts`。
按用户技术栈加 `language:typescript` / `language:python`。

> **生态现状提示（2026）**：当前前沿 Agent 框架项目大多基于 TypeScript——
> Vercel AI SDK、OpenAI Agents SDK (JS)、Mastra、LangGraph.js、Eliza、Copilot Kit 等；
> Python 侧以 LangChain、PydanticAI、OpenAI SDK 为主，偏研究向。Route A 收集画像时
> 先确认用户技术栈（Python / TypeScript），不要默认只搜一种语言。

### 发现 Issue（跨仓库找切入点）

```
is:issue is:open label:"good first issue" language:python stars:>500
is:issue is:open label:"help wanted" no:assignee topic:ai-agent
```

常用 label 过滤：

```
label:"good first issue"
label:"help wanted"
label:"bug"
label:"documentation"
label:"first-timers-only"
```

### gh CLI 用法（若可用，优先使用）

> 注意：以下示例中的日期为占位符，**使用时替换为"当前日期-1 个月"**（如今天是 2026-09-11，
> 则 pushed 时间过滤用 `>2026-08-11`）。不要直接复制过期日期。推荐直接用脚本
> `discover_repos.py` / `find_issues.py`，它们会自动生成当前日期。

```bash
gh search repos "topic:ai-agent stars:>1000 pushed:>{当前日期-1月}" --sort=updated --limit=20
gh search issues "label:\"good first issue\" language:python state:open" --sort=created --limit=30
gh api repos/{owner}/{repo} --jq '{stars: .stargazers_count, pushed: .pushed_at, open_issues: .open_issues_count, license: .license.spdx_id}'
gh api "search/issues?q=repo:{owner}/{repo}+type:pr+is:merged+merged:>{当前日期-1月}" --jq '.total_count'
```

## 三、聚合站点（补充渠道）

- goodfirstissue.dev — 实时聚合新手友好 Issue（DeepSource 维护，活跃）
- goodfirstissues.com — 聚合最新 good first issue 标签 Issue
- up-for-grabs.net — 按语言筛选 help wanted 项目（活跃）
- firsttimersonly.com — 专为首次贡献者准备的项目（2026-08 复核仍活跃）
- github.com/MunGell/awesome-for-beginners — 按语言整理的新手友好清单
- github.com/topics/<topic> — 按主题浏览
- github.com/trending — 当日热门
- CodeTriage — 订阅关注项目的每日一个 open issue
- Libraries.io — 2800 万+ 开源仓库与 250 万+ 包目录（按依赖/生态筛选）
- OpenSauced — 基于贡献历史的个性化发现与仓库健康洞察（OSCR 贡献者评分）
- OSS Insight / star-history — 仓库趋势、star 增长与社区热度可视化
- First Contributions — 手把手走通第一次贡献流程（适合新手教程）
- 24 Pull Requests — 年末贡献挑战活动
- SourceSort — 按兴趣推荐可贡献项目的服务

策略性选项目技巧：
- 优先选用户日常在用的工具/库（理解问题域，切入快）
- 看项目依赖树里的库（改动可本地验证）
- 开发者工具/CLI 类项目范围小、反馈快

## 四、项目健康度打分模型（1~5 分制）

对每个候选项目按四个维度各打 1~5 分：

1. **目标相关性**：技术栈是否匹配？这段贡献对求职/学习目标是否有加分？
2. **项目健康度**：Issue 是否数日内有回应？近 30 天是否有 PR 被合并？活跃维护者是否多于 1 人？有无贡献指南？
3. **可上手性**：有无 good first issue / help wanted？代码库一个周末能否读懂？文档能否支撑本地跑起来？
4. **社区氛围**：维护者在评论中是否友善？有无 Code of Conduct？贡献者是否被致谢？

| 总分 | 结论 |
|------|------|
| 16~20 | 理想首选，直接投入 |
| 11~15 | 值得尝试，前提是与目标匹配 |
| 6~10 | 摩擦较大，考虑替代品 |
| 1~5 | 放弃 |

## 五、输出模板：候选项目清单

| 项目 | Stars | 技术栈 | 最近提交 | Issue 关闭率 | PR 响应 | 健康度(🚦) | 打分 | 推荐理由 |
|------|-------|--------|---------|-------------|---------|-----------|------|---------|
| owner/repo | | | | | | 🟢/🟡/🔴 | /20 | |

表格后附 1~2 句总结：**推荐哪个、为什么、主要风险是什么**。然后请用户选定一个进入切入点分析。

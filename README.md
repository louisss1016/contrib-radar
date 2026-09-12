<div align="center">

<img src="./assets/logo.png" alt="Contrib Radar" width="140">

# Contrib Radar

**开源贡献自动化侦察 — 从一堆项目里锁定真正能上手的 issue，一路跟踪到 PR 合并。**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-lightgrey.svg)](./contrib-radar/scripts)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-purple.svg)](https://agentskills.io)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

**[快速开始](#-快速开始) · [特性](#-特性) · [真实效果](#-真实效果) · [命令参考](#-命令参考) · [工作流程](#-工作流程) · [定时任务自动化](#-定时任务自动化) · [FAQ](#-faq)**

</div>

---

## 🚀 快速开始

### 1. 安装

把 `contrib-radar/` 文件夹放入 Agent Skills 目录即可，无需 `pip install`：

```bash
git clone https://github.com/louisss1016/contrib-radar.git
```

| 平台 | 目录 |
|------|------|
| Claude Code | `~/.claude/skills/contrib-radar/` |
| Cursor / Copilot | `.cursor/skills/` 或 `.github/skills/`（项目级） |
| 豆包 Doubao | `~/.doubao/agent_mode/workspace/.skills/contrib-radar/` |
| 其他平台 | 按平台约定放入 skills 目录 |

### 2. 使用

在对话里直接说：

> 帮我找一个 TypeScript 写的 AI Agent 方向、star 100~1000 的开源项目，看看有哪些适合新手的 Issue。

或当纯命令行工具用：

```bash
cd contrib-radar/scripts

python discover_repos.py --topic ai-agent --language typescript --beginner   # 发现候选项目
python repo_health.py <owner/repo>                                           # 健康体检 + AI 政策
python find_issues.py <owner/repo> --min-score 40                            # 筛选可认领 Issue
python claim_issue.py <owner/repo> <issue_number>                            # 检测认领方式 + 冲突检查
python pr_tracker.py <owner/repo> <pr_number>                                # PR 生命周期跟踪
```

> 💡 建议设置 `GITHUB_TOKEN`（Search 30/min、core 5000/hr），或使用已绑定 GitHub MCP/OAuth 的 Agent 平台，不受未认证限流影响。

---

## ✨ 特性

| 能力 | 说明 |
|------|------|
| 候选项目发现 | topic / 语言 / star 区间筛选，自动排除 fork 与归档仓库 |
| 新手甜蜜区模式 | `--beginner`：100~1000 star，竞争小、维护者回复快 |
| 12 项健康体检 | 提交活跃度、Issue 关闭率、PR 合并速度、Release 频率、贡献指南、License 等 |
| AI 政策扫描（去误报） | 读取 `CONTRIBUTING.md` 判定 `blocked / mention / ok / unknown`；"llm" 单独命中不触发，必须与禁止性动词组合才算限制声明 |
| Issue 启发式打分 | 0~100 可解释分：清晰度 30 + 标签 15 + 评论 15 + 新鲜度 20 + milestone 20 |
| 标签零命中 fallback | 标签搜索无结果时自动拉取全量 open issue，避免漏检不打标签的 roadmap/feature issue |
| 撞车检测 | 自动拉取全部 open PR，剔除已被 `fixes #N` 引用的 Issue |
| 认领方式检测 | `claim_issue.py` 自动检测 claim bot（`/claim`）或评论认领，检查 assignee/认领评论/PR 引用冲突 |
| PR 生命周期跟踪 | `pr_tracker.py` 检查 CI/Review/可合并性/上游更新，自动判断下一步动作（修复 CI/回应 review/rebase/礼貌跟进） |
| 批量体检 | `repo_health.py repo1 repo2 ...`，单项失败自动降级不中断 |
| `--json` 输出 | 全部脚本均支持，方便接入其他工具链和定时任务 |
| 零依赖 | 纯 Python 标准库，无需 `pip install` |
| TS 生态优先 | 内置前沿 Agent 项目 topic（Vercel AI SDK / Mastra / LangGraph.js / Eliza 等） |
| 每日监控（Route C） | 配合定时任务每天扫描新出现的可认领 Issue，输出差异日报 |
| 自动贡献模式（Route C+） | 状态持久化 + 6 项质量门控 + 两个人工确认点 + PR 生命周期跟踪，高分 Issue 自动实现并提交 PR |

---

## 📊 真实效果

<details>
<summary><b>发现候选项目</b>（TS 生态 · 新手甜蜜区）</summary>

```text
$ python discover_repos.py --topic vercel-ai-sdk --language typescript --beginner --limit 3
命中 10 个仓库，按最近更新取前 3 个:

1. zoonk/zoonk  ⭐150  [TypeScript]  0天前推送
   Turn any topic into clear, structured lessons
2. vargHQ/sdk  ⭐337  [TypeScript]  1天前推送
   AI video generation SDK — One API for Kling, Flux, ElevenLabs, Veed
3. jagreehal/ai-sdk-ollama  ⭐132  [TypeScript]  1天前推送
   A Vercel AI SDK provider for Ollama
```
</details>

<details>
<summary><b>Issue 筛选 + 打分 + 撞车检测</b>（标签零命中自动 fallback）</summary>

```text
$ python find_issues.py helsome/folio --limit 3
[信息] 标签搜索零命中，自动 fallback 到全量 open issue 列表...
撞车检测: 已剔除 2 个被 open PR 引用的 Issue

[ 82/100] #25  [Finance Data] Add provider routing, rate-limit handling, cache, and failover
   标签: - | 2天前活跃 | 评论 0 | milestone: Finance Data v0.5
   打分: 清晰度28/30, 标签0/15, 评论6/15, 新鲜度20/20, milestone15/20
```
</details>

<details>
<summary><b>认领方式检测 + 冲突检查</b></summary>

```text
$ python claim_issue.py helsome/folio 25
=== Claim Bot 检测 ===
  ✅ 检测到 claim bot: issue-claim.yml
=== 认领冲突检查 ===
  ✅ 无认领冲突，可以认领
=== 认领建议 ===
  🤖 通过 bot 认领: 命令 /claim
     发完后不要编辑评论（bot 只在评论 created 时触发）
```
</details>

<details>
<summary><b>PR 生命周期跟踪</b>（CI / Review / Rebase / 下一步动作）</summary>

```text
$ python pr_tracker.py helsome/folio 72
=== 基本状态 ===
  状态: 🟢 open | 可合并: True (state: clean)
=== CI 状态 ===
  总计: 3 | ✅ 3 | ❌ 0 | ⏳ 0  →  success
=== Review 状态 ===
  Reviews: 1 (✅ approved: 1)
=== Rebase 检测 ===
  ✅ 无需 rebase
=== 下一步动作 ===
  🟢 wait: PR 状态正常，等待维护者合并
```
</details>

---

## 📖 命令参考

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `discover_repos.py` | 按方向/语言/规模发现候选项目 | `--topic` `--language` `--beginner` `--stars` `--json` |
| `repo_health.py` | 12 项健康度体检 + AI 政策扫描 | 多仓库批量、`--json` |
| `find_issues.py` | Issue 筛选、打分、撞车检测、fallback | `--include-bugs` `--min-score` `--no-fallback` `--json` |
| `claim_issue.py` | 认领方式检测 + 冲突检查 | `owner/repo N` 或 issue URL、`--json` |
| `pr_tracker.py` | PR 生命周期跟踪 + 下一步动作 | `owner/repo N` 或 PR URL、`--json` |

> 全部脚本支持 `--help`。

---

## 🧭 工作流程

```
用户提供仓库 URL？
├── 是 → Route B：直接分析该项目的 PR/Issue 切入点
├── 否 + 要求每日监控或自动贡献 → Route C / C+
└── 否 → Route A：发现候选项目 → 用户选定 → Route B
```

- **Route A · 从零开始**：收集技术栈画像 → 发现候选 → 批量健康体检 → 输出候选表 → 用户选定
- **Route B · 已有目标仓库**：项目理解 → 机筛 Issue + 人工复核 → AI 政策检查 → 架构缺陷分析 → Top 3 建议
- **Route C · 持续监控**：每日扫描新 Issue → 撞车复核 → 与上次日报对比 → 输出差异日报
- **Route C+ · 自动贡献**：状态持久化 → 打分筛选 → **人工确认 1** → Baseline 采集 → 认领 → 自动实现 → 6 项质量门控 → **人工确认 2** → 提交 PR → 生命周期跟踪

---

## ⏰ 定时任务自动化

> 与上方手动对话触发不同，以下 Query 模板专为**定时任务自动触发**设计，包含完整的状态持久化、质量门控和人工确认点。

### 快速配置

1. 创建每天执行的定时任务（建议 `0 8 * * *`）
2. 复制下方 Query 模板到任务的 query 字段
3. 修改 `【用户画像】` 部分为你的技术栈
4. 确保 GitHub MCP/OAuth 已绑定

### Query 模板

```text
本次请求是由「每日开源贡献自动扫描」定时任务到时触发的。

请执行 contrib-radar skill 的 Route C+ 自动贡献模式。

【Skill 位置】
<contrib-radar 目录的绝对路径>
先读取该目录下的 SKILL.md，严格按其 Route C+ 规范执行。

【用户画像】
- 技术栈：Python（LangChain / PydanticAI / OpenAI SDK）、TypeScript（React / Node / Electron / Bun）
- 兴趣方向：AI Agent、AI 应用开发、LLMOps、开发者工具
- 时间预算：单个 PR 控制在 300 行以内，1~2 天可完成
- GitHub 账号：<你的用户名>
- 偏好：commit message 用中文，PR 标题用英文

【每日执行流程】
1. 读取 contrib-radar-state.json，恢复上次进度
2. 项目发现：discover_repos.py 分别跑 typescript 和 python 的 --beginner，各取 top 5
3. 健康度筛查：repo_health.py 批量体检，过滤 AI 政策 blocked 和健康度 < 50%
4. Issue 筛选：find_issues.py --min-score 50，取打分最高的 3 个
5. 认领冲突检查：claim_issue.py 排除有冲突的
6. PR 跟踪：pr_tracker.py 检查所有 active_prs，按 next_actions 自动处理

【自动实现（每天最多 1 个新 PR）】
- 选打分最高、预估改动最小的 1 个 issue
- 【人工确认点 1】展示 issue 标题/链接/打分/预估工作量/实现方案，等用户回复"确认"
- clone → baseline 采集 → 认领 → 逐步实现 → 补测试
- 质量门控：① 测试零新增失败 ② typecheck 通过 ③ 有测试覆盖 ④ <300 行 ⑤ AI 政策非 blocked ⑥ 无撞车
- 【人工确认点 2】展示改动清单 + 测试报告 + PR 描述草稿，等用户回复"确认提交"
- fork → 分支 → commit → push → 创建 PR（Closes #N）
- 更新状态文件

【输出要求】
- 日报写入 daily-issue-scan-<YYYY-MM-DD>.md
- 到达人工确认点时明确提示，不要自行跳过
- 状态持久化到 contrib-radar-state.json
```

### 状态文件

定时任务维护 `contrib-radar-state.json`，防止重复扫描和重复提交：

```json
{
  "scanned_issues": {"owner/repo#25": {"status": "pr_submitted"}},
  "active_prs": [{"repo": "helsome/folio", "pr_number": 72, "status": "awaiting_review"}],
  "blacklisted_repos": [],
  "cooldown": {"owner/repo": "2026-09-20"}
}
```

---

## 📁 项目结构

```
contrib-radar/
├── SKILL.md                       # Skill 主文件：Route A/B/C/C+ 全流程
├── references/                    # 方法论参考（5 个）
│   ├── project-discovery.md       #   项目发现与避坑
│   ├── opportunity-analysis.md    #   切入点分析与架构缺陷
│   ├── contribution-workflow.md   #   贡献全流程：Baseline → 认领 → PR → 面试
│   ├── communication-templates.md #   英文沟通模板
│   └── example-analysis.md        #   完整案例分析
└── scripts/                       # 零依赖 Python 工具（6 个）
    ├── github_api.py              #   共享模块：请求/限速/重试
    ├── discover_repos.py          #   候选项目发现
    ├── find_issues.py             #   Issue 筛选 + 打分 + 撞车检测
    ├── repo_health.py             #   健康度体检 + AI 政策检查
    ├── claim_issue.py             #   认领方式检测 + 冲突检查
    └── pr_tracker.py              #   PR 生命周期跟踪
```

---

## 🗺️ 路线图

- **v3.2（当前）**：标签零命中 fallback、milestone 打分、AI 政策去误报、`claim_issue.py`、`pr_tracker.py`、Route C+ 完整自动贡献流程
- **候选方向**：MCP server 化、个性化推荐、周报导出、GitLab/Gitee 支持

---

## ❓ FAQ

**需要 GitHub token 吗？**
不需要，脚本开箱即用。但建议设置 `GITHUB_TOKEN` 或使用已绑定 MCP/OAuth 的 Agent 平台以提升速率限额。

**打分是 LLM 做的吗？**
不是。打分是确定性启发式（权重公开可审计），LLM 语义判断由 Agent 在读正文时补充。

**会撞车吗？**
脚本会剔除被 open PR 引用的 Issue，`claim_issue.py` 进一步检查 assignee 和认领评论。动手前仍建议留言认领。

**自动提交安全吗？**
Route C+ 设了两个人工确认点（选定 issue 后、提交 PR 前），6 项质量门控不通过不得提交。其余步骤可全自动。

**标签搜索零命中怎么办？**
`find_issues.py` 会自动 fallback 到全量 open issue（最多 300 条），再用打分模型过滤。可用 `--no-fallback` 关闭。

---

## 🤝 贡献

欢迎 [Issue](https://github.com/louisss1016/contrib-radar/issues) 和 PR。保持零依赖、兼容 Agent Skills 标准。

## 📄 License

[MIT](./LICENSE) © 2026 Louisss

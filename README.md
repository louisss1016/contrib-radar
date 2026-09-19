<div align="center">

<img src="./assets/logo.png" alt="Contrib Radar" width="140">

# Contrib Radar

**Find the right open-source contribution before you write code.**

开源贡献侦察雷达：在写代码之前，用可解释的打分和碰撞检测，从一堆项目里锁定真正值得投入的 Issue，一路跟踪到 PR 合并。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-lightgrey.svg)](./contrib-radar/scripts)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-purple.svg)](https://agentskills.io)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/louisss1016/contrib-radar/issues)

**[快速开始](#-快速开始) · [它解决什么问题](#-它解决什么问题) · [命令参考](#-命令参考) · [工作流程](#-工作流程) · [能力边界](#-能力边界) · [定时任务自动化](#-定时任务自动化) · [FAQ](#-faq)**

</div>

---

## 🎯 它解决什么问题

开源贡献最常见的四个卡点，Contrib Radar 逐一拆掉：

| 卡点 | 表现 | 解决方式 |
|------|------|---------|
| **不知道选哪个项目** | 热门仓库门槛高，冷门仓库怕没响应 | `discover_repos.py` 按方向/语言/规模筛选，`--beginner` 进入 100~1000 star 甜蜜区 |
| **不知道从哪个 Issue 入手** | 海量 Issue 里找不到「低门槛 + 有人理」的；roadmap issue 不打标签容易漏 | `find_issues.py` 双维度启发式打分，标签零命中自动 fallback 全量 |
| **怕白干** | 提交前才发现已有人认领，或项目禁止 AI 代码 | 撞车检测剔除被 open PR 引用的 Issue + `claim_issue.py` 冲突检查 + AI 政策扫描（去误报） |
| **PR 石沉大海** | 提交后没人跟进、CI 挂了、上游更新没 rebase | `pr_tracker.py` 跟踪 CI / Review / Rebase，自动判断下一步动作 |

**适合**：想开始做开源贡献的开发者、把开源贡献当面试素材的求职者、想系统化「找项目 → 找切入点 → 实现 → 提交 → 维护」全流程的人。

**不适合**（边界声明）：想要「完全无人值守自动提 PR」的场景（本工具设了两个人工确认点）；只想在某一个固定仓库长期深耕（直接用 `find_issues.py` + `claim_issue.py` 即可）；需要商业级 SLA 的团队场景（本项目是零依赖的个人开源工具）。

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
| Codex（OpenAI） | `~/.codex/skills/contrib-radar/` |
| Cursor | `.cursor/skills/contrib-radar/`（项目级） |
| GitHub Copilot | `.github/skills/contrib-radar/`（项目级） |
| 豆包 Doubao | `~/.doubao/agent_mode/workspace/.skills/contrib-radar/` |
| WorkBuddy 等本地 Agent | `~/.workbuddy/skills/contrib-radar/`（用户级，通用） |
| 其他 Agent Skills 平台 | 按平台约定放入 skills 目录即可 |

### 2. 使用

**对话式**（推荐）：在支持 Agent Skills 的对话里直接说——

> 帮我找一个 TypeScript 写的 AI Agent 方向、star 100~1000 的开源项目，顺便看看有哪些适合新手的 Issue。

**命令行**：也可以把它当纯 CLI 工具用（见下方「命令参考」）。

> 💡 **建议设置 `GITHUB_TOKEN`**：Search 限额从 10/min 提到 30/min、core 从 60/hr 提到 5000/hr，并取消节流等待。使用已绑定 GitHub MCP/OAuth 的 Agent 平台则不受未认证限流影响。

---

## 📖 命令参考

```bash
cd contrib-radar/scripts

python discover_repos.py --topic ai-agent --language typescript --beginner   # ① 发现候选项目
python repo_health.py <owner/repo>                                           # ② 健康体检 + AI 政策
python find_issues.py <owner/repo> --min-score 40                            # ③ 筛选可认领 Issue
python claim_issue.py <owner/repo> <issue_number>                            # ④ 认领方式检测 + 冲突检查
python pr_tracker.py <owner/repo> <pr_number>                                # ⑤ PR 生命周期跟踪
```

| 脚本 | 作用 | 关键参数 |
| --- | --- | --- |
| `discover_repos.py` | 按方向/语言/规模发现候选项目 | `--topic` `--language` `--beginner` `--stars` `--max-stars` `--pushed-days` `--limit` `--json` |
| `repo_health.py` | 12 项健康体检 + AI 政策扫描 | 多仓库批量、`--json`（单项缺失自动降级不中断） |
| `find_issues.py` | Issue 筛选 + 双维度打分 + Collision Risk + Stack Match + Why this issue? | `--min-score` `--stack` `--include-bugs` `--beginner-only` `--labels` `--days` `--no-fallback` `--show-collision` `--json` |
| `claim_issue.py` | 认领方式检测 + 冲突检查 | `owner/repo N` 或 issue URL、`--json` |
| `pr_tracker.py` | PR 生命周期跟踪 + 下一步动作 | `owner/repo N` 或 PR URL、`--json` |

全部脚本支持 `--help`，纯 Python 标准库实现，零第三方依赖。

---

## 🧭 工作流程

```
用户提供仓库 URL？
├── 是 → Route B：直接分析该项目的 PR/Issue 切入点
├── 否 + 用户要求每日/定期监控或自动贡献 → Route C / C+
└── 否 → Route A：发现候选项目 → 用户选定一个 → 进入 Route B
```

- **Route A · 从零开始**：收集画像（技术栈先确认 Python / TypeScript）→ 发现候选 → 批量健康体检 → 输出候选表 → 用户选定
- **Route B · 已有目标仓库**：项目理解 → 机筛 Issue + 人工复核 → AI 政策前置检查 → 架构缺陷分析（定位到文件/函数）→ Top 3 贡献建议
- **Route C · 持续监控**：配合定时任务每日扫描新出现的可认领 Issue，输出差异日报
- **Route C+ · 自动贡献模式**：状态持久化 → 打分筛选 → 人工确认点 1 → 自动实现 → 6 项质量门控 → 人工确认点 2 → 提交 PR → 生命周期跟踪

选定切入点后，可继续走 `references/contribution-workflow.md` 全流程，最终沉淀为 STAR + 60 秒面试话术。

---

## 🏗️ 能力边界

Contrib Radar 明确区分**脚本能力**（确定性、可复现、零依赖）和 **Agent 依赖能力**（需 LLM 推理或人工确认），避免对自动化产生过高期待：

| 层 | 职责 | 状态 |
|----|------|------|
| **Core Scripts** | 项目发现、健康体检、Issue 打分、撞车检测、认领检测、PR 跟踪、`--json` 输出 | ✅ 已实现，开箱即用 |
| **Agent Workflow** | 项目理解/架构分析、方案设计、代码实现、测试编写 | 🤖 依赖 Agent 能力，方法论在 `references/` |
| **人工确认点** | 选定 issue 后、提交 PR 前 | 🔒 两个安全闸门，不关闭 |

> 核心原则：脚本做「筛选和决策支持」，Agent 做「理解和实现」，人工确认做「安全闸门」。

---

## ⏰ 定时任务自动化（Route C+）

在支持 cron 的 Agent 平台（如豆包）创建每日定时任务，自动执行「扫描 → 筛选 → 认领 → 实现 → 质量门控 → 人工确认 → 提交 → 跟踪」全流程。

<details>
<summary><b>Query 模板（可直接复制，点击展开）</b></summary>

```text
本次请求是由「每日开源贡献自动扫描」定时任务到时触发的。
请执行 contrib-radar skill 的 Route C+ 自动贡献模式。

【Skill 位置】
<把 contrib-radar 目录的绝对路径填在这里，如 ~/.doubao/agent_mode/workspace/.skills/contrib-radar/>
先读取该目录下的 SKILL.md，严格按其 Route C+ 规范执行。

【用户画像】
- 技术栈：Python（LangChain / PydanticAI / OpenAI SDK）、TypeScript（React / Node / Electron / Bun）
- 兴趣方向：AI Agent、AI 应用开发、LLMOps、开发者工具
- 时间预算：单个 PR 控制在 300 行以内，1~2 天可完成
- GitHub 账号：<你的 GitHub 用户名>
- 偏好：commit message 用中文，PR 标题用英文

【每日执行流程】
1. 读取当前工作目录的 contrib-radar-state.json，恢复上次进度（已扫描 issue、活跃 PR、黑名单、冷却期）
2. 项目发现：scripts/discover_repos.py 分别用 --language typescript --beginner 和 --language python --beginner，各取 top 5
3. 健康度筛查：scripts/repo_health.py 批量体检，过滤 AI 政策 blocked 和健康度 < 50% 的
4. Issue 筛选：scripts/find_issues.py --min-score 50，取打分最高的 3 个
5. 认领冲突检查：scripts/claim_issue.py 排除 assignee/认领评论/PR 引用冲突
6. PR 跟踪：scripts/pr_tracker.py 处理所有 active_prs（CI 失败则修复、上游更新则 rebase、超 7 天无回应则跟进）

【自动实现（每天最多 1 个新 PR）】
- 从候选选打分最高、预估改动最小的 1 个 issue（排除已在状态文件中的）
- 【人工确认点 1】展示 issue 标题/链接/打分/预估工作量/实现方案，等用户回复「确认」后才开始写代码
- 实现：clone → baseline 采集 → 认领（bot /claim 发完不要编辑）→ 按 references/contribution-workflow.md 实现 → 补测试
- 质量门控（全过才提交）：① 测试零新增失败 ② typecheck/lint 通过 ③ 有测试覆盖 ④ 改动 < 300 行 ⑤ AI 政策非 blocked ⑥ 提交前无撞车
- 【人工确认点 2】展示改动清单 + 可复现测试报告 + PR 描述草稿，等用户回复「确认提交」后才执行 GitHub 写操作
- 提交：fork → 分支 → Conventional Commits → push → 创建 PR（标题英文、Closes #N）
- 更新状态文件：标记 pr_submitted，PR 加入 active_prs

【输出要求】
- 每日日报写入 daily-issue-scan-<YYYY-MM-DD>.md
- 到达人工确认点时明确提示「需要你确认后才能继续」，不自行跳过
- 无合适候选时说明原因并列出被排除的仓库及理由
- 状态持久化到 contrib-radar-state.json
```

</details>

**核心机制**：定时任务无状态，但贡献流程有状态——`contrib-radar-state.json` 持久化已扫描 Issue、活跃 PR、黑名单、冷却期和每日统计，避免重复扫描/重复实现/重复提交。

> ⚠️ **安全设计**：两个人工确认点故意保留，定时任务触发后会停下等你回复，不会全自动提交。提交步骤依赖 GitHub MCP/OAuth 或 `gh` CLI 认证。

---

## 📁 目录结构

```
contrib-radar/
├── SKILL.md                       # Skill 主文件：定位、触发词、Route A/B/C/C+ 全流程
├── references/                    # 方法论参考（6 个）
│   ├── project-discovery.md       #   项目发现：搜索语法 + 聚合站点 + 避坑
│   ├── opportunity-analysis.md    #   切入点分析：架构缺陷、依赖、路线图、文档
│   ├── contribution-workflow.md   #   贡献全流程：Baseline → 认领 → 实现 → PR → 维护 → 面试
│   ├── communication-templates.md #   交流模板：Issue/PR 提问、跟帖话术
│   ├── example-analysis.md        #   完整案例分析（输出颗粒度校准）
│   └── api-pr-submission.md       #   git 不可用时的纯 REST API 提 PR 流程
└── scripts/                       # 零依赖 Python 工具（6 个）
    ├── github_api.py              #   共享模块：请求/限速/重试/仓库解析
    ├── discover_repos.py          #   候选项目发现
    ├── find_issues.py             #   Issue 筛选 + 打分 + 撞车检测 + fallback
    ├── repo_health.py             #   健康体检 + AI 政策检查（去误报）
    ├── claim_issue.py             #   认领方式检测 + 冲突检查
    └── pr_tracker.py              #   PR 生命周期跟踪 + 下一步动作
```

---

## 🧪 测试

零依赖测试套件（仅 Python 标准库 `unittest`），覆盖打分模型、碰撞检测、技术栈匹配、AI 政策去误报、API 工具函数：

```bash
python run_tests.py          # 运行全部测试
python run_tests.py -v       # 详细输出
```

| 测试文件 | 覆盖范围 |
|----------|---------|
| `test_scoring.py` | Issue Quality / Feasibility 打分、Stack Match、Score Regression |
| `test_collision.py` | Collision Risk 分级（HIGH/MEDIUM/LOW） |
| `test_ai_policy.py` | AI 政策去误报（"llm" 单独不触发、禁止性短语、中文） |
| `test_github_api.py` | parse_repo / days_ago 纯函数 |

---

## 🏛️ 设计原则

1. **零依赖、可审计**：6 个脚本纯标准库实现，无供应链风险
2. **对 GitHub API 友好**：未认证时只对 search 端点限速打点，403 按 `X-RateLimit-Reset` 自适应等待
3. **AI 时代意识**：AI 贡献政策扫描 + 撞车检测 + 认领冲突检查，是当下开源贡献绕不开的三个新变量
4. **可解释的确定性输出**：双维度打分权重透明，可审计、可复现
5. **状态驱动的自动化**：Route C+ 通过状态文件持久化，配合质量门控和人工确认点，在自动化与安全之间取平衡
6. **遵守 Agent Skills 标准**：`SKILL.md` 自包含、name 用 kebab-case、description 写明「做什么 + 何时用」

---

## 🗺️ 路线图

**已交付**：共享 API 封装 · 撞车检测 · 启发式打分 · AI 政策扫描 · `--beginner` 甜蜜区 · `--json` 导出 · TS 生态 · Route C 每日监控 · Route C+ 自动贡献（状态持久化 + 质量门控 + 人工确认点 + PR 跟踪）· Collision Risk 三级分级 · Why this issue? 决策理由 · 双维度打分（Quality × 0.5 + Feasibility × 0.5）· `--stack` 技术栈匹配 · 纯 REST API 提 PR 降级通道。

**候选方向**（欢迎 Issue 讨论，暂未排期）：MCP server 化、个性化推荐、周报导出、多平台支持（GitLab / Gitee）。

---

## ❓ FAQ

**需要 GitHub token 吗？**
不需要，脚本开箱即用。但建议设置 `GITHUB_TOKEN` 提升限额并取消节流；绑定 GitHub MCP/OAuth 的 Agent 平台直接走 OAuth 通道，不受未认证限流影响。

**打分是 LLM 做的吗？**
不是。打分是确定性启发式（权重公开可审计），零成本、可复现；LLM 语义判断（如评论里是否有人认领）由 Agent 读正文时补充。

**会撞车吗？**
脚本会剔除被 open PR 引用（`fixes #N` 等）的 Issue，`claim_issue.py` 进一步检查 assignee 和认领评论；动手前仍建议在 Issue 下留言认领。

**自动提交安全吗？**
Route C+ 设了两个人工确认点（选定 issue 后、提交 PR 前），6 项质量门控不通过不得提交，认证不可用时会生成待提交材料供你手动提交。

**支持 GitLab / Gitee 吗？**
流程方法论通用，但自带脚本仅支持 GitHub；其他平台需用 WebFetch 人工核查活跃度。

---

## 🤝 贡献

欢迎 Issue 和 PR：

- **报 Bug / 提需求**：开 [Issue](https://github.com/louisss1016/contrib-radar/issues)，说明复现方式
- **改代码**：先开 Issue 讨论，再提 PR；保持零依赖、兼容 Agent Skills 标准

## 📄 License

[MIT](./LICENSE) © 2026 Louisss

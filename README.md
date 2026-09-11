<div align="center">

# 📡 Contrib Radar · 开源贡献雷达

**帮你找到值得贡献的开源项目，锁定不撞车的好上手 Issue，输出一份可执行的贡献方案。**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies: zero](https://img.shields.io/badge/Dependencies-zero-lightgrey.svg)](./contrib-radar/scripts)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-purple.svg)](https://agentskills.io)

**[快速上手](#-快速上手) · [真实效果](#-真实效果) · [特性](#-特性) · [命令参考](#-命令参考) · [工作流程](#-工作流程) · [设计原则](#-设计原则) · [路线图](#-路线图) · [FAQ](#-faq)**

</div>

---

## 🚀 快速上手

**第 1 步 · 获取**：克隆本仓库，或直接下载 zip：

```bash
git clone https://github.com/louisss1016/contrib-radar.git
```

**第 2 步 · 安装**：把 `contrib-radar/` 文件夹放入你所用平台的 Agent Skills 目录（支持 [Agent Skills](https://agentskills.io) 标准的 Claude Code / Codex / 豆包等均可）。

**第 3 步 · 使用**：在对话里直接说：

> 帮我找一个 TypeScript 写的 AI Agent 方向、star 100~1000 的开源项目，顺便看看有哪些适合新手的 Issue。

也可以把它当纯命令行工具用（无需任何 `pip install`）：

```bash
cd contrib-radar/scripts

python discover_repos.py --topic ai-agent --language typescript --beginner   # ① 发现候选
python repo_health.py <owner/repo>                                           # ② 健康体检 + AI 政策
python find_issues.py <owner/repo> --min-score 40                            # ③ 筛选可认领 Issue
```

> 💡 建议设置环境变量 `GITHUB_TOKEN`：Search 限额从 10/min 提升至 30/min、core 从 60/hr 提升至 5000/hr，并取消节流等待。

---

## 📊 真实效果

以下为实测输出（数据随查询时间变化，仅示意效果）：

<details>
<summary><b>① 发现候选项目</b>（TS 生态 · 新手甜蜜区）</summary>

```text
$ python discover_repos.py --topic vercel-ai-sdk --language typescript --beginner --limit 3
查询: topic:vercel-ai-sdk stars:100..1000 pushed:>=2026-06-13 archived:false fork:false language:typescript
命中 10 个仓库，按最近更新取前 3 个:

1. zoonk/zoonk  ⭐150  [TypeScript]  0天前推送
   Turn any topic into clear, structured lessons
   https://github.com/zoonk/zoonk

2. vargHQ/sdk  ⭐337  [TypeScript]  1天前推送
   AI video generation SDK — JSX for videos. One API for Kling, Flux, ElevenLabs, Veed.
   https://github.com/vargHQ/sdk

3. jagreehal/ai-sdk-ollama  ⭐132  [TypeScript]  1天前推送
   A Vercel AI SDK provider for Ollama built on the official ollama package.
   https://github.com/jagreehal/ai-sdk-ollama
```
</details>

<details>
<summary><b>② 健康体检 + AI 政策检查</b>（12 项指标红绿灯）</summary>

```text
$ python repo_health.py pydantic/pydantic --json
仓库: pydantic/pydantic  ⭐ 28756  🍴 2937
主语言: Python  |  https://github.com/pydantic/pydantic
  🟢 最近提交: 0 天前
  🟢 Issue 关闭率 (closed/open): 5195/540 = 9.62
  🟢 近 30 天合并 PR 数: 67
  🟢 最近 Release: 13 天前
  🟢 贡献指南: 有
  🟢 开源 License: MIT
健康度: 12/12  →  🟢 健康，适合投入
AI 政策: mention — 命中 CONTRIBUTING.md: ['ai generated']（有 AI 相关表述，需人工确认口径）
```
</details>

<details>
<summary><b>③ Issue 筛选 + 打分 + 撞车检测</b>（已剔除被 open PR 认领的条目）</summary>

```text
$ python find_issues.py langchain-ai/langchain --include-bugs --limit 3 --min-score 30
仓库: langchain-ai/langchain  条件: open / 无assignee / 近60天活跃 / 标签 ['good first issue', 'help wanted', 'bug', 'enhancement']
撞车检测: 已剔除 1 个被 open PR 引用的 Issue

[ 90/100] #40354  langchain: MCP adapter test asserts a POSIX-only error message ...
   标签: bug,langchain,external | 0天前活跃 | 评论 1 | https://github.com/langchain-ai/langchain/issues/40354
   打分: 清晰度35/35, 标签10/20, 评论20/20, 新鲜度25/25

[ 86/100] #40298  text-splitters: `MarkdownHeaderTextSplitter` keeps the closing ...
   标签: bug,text-splitters,external | 0天前活跃 | 评论 4 | https://github.com/langchain-ai/langchain/issues/40298
   打分: 清晰度35/35, 标签10/20, 评论16/20, 新鲜度25/25
```
</details>

---

## 🎯 它是做什么的

开源贡献最常见的三个卡点，Contrib Radar 逐一拆掉：

| 卡点 | 表现 | 解决方式 |
|------|------|---------|
| **不知道选哪个项目** | 热门仓库门槛高，冷门仓库怕没响应 | `discover_repos.py` 按方向/语言/规模筛选，`--beginner` 进入 100~1000 star 甜蜜区 |
| **不知道从哪个 Issue 入手** | 海量 Issue 里找不到"低门槛 + 有人理"的 | `find_issues.py` 启发式打分（0~100），按可上手度排序 |
| **怕白干** | 提交前才发现已有人认领，或项目禁止 AI 代码 | 撞车检测剔除被 open PR 引用的 Issue + AI 政策扫描（`blocked / mention / ok / unknown`） |

它适合：想开始做开源贡献的开发者、把开源贡献当面试素材的求职者、以及任何想系统化"找项目 → 找切入点"流程的人。

---

## ✨ 特性

| 能力 | 说明 |
|------|------|
| 候选项目发现 | topic / 语言 / star 区间筛选，自动排除 fork 与归档仓库 |
| 新手甜蜜区模式 | `--beginner`：100~1000 star，竞争小、维护者回复快 |
| 12 项健康体检 | 提交活跃度、Issue 关闭率、PR 合并速度、Release 频率、贡献指南、License 等 |
| AI 政策扫描 | 读取 `CONTRIBUTING.md` 判定 `blocked / mention / ok / unknown`，避免触碰 AI 贡献红线 |
| Issue 启发式打分 | 0~100 可解释分：清晰度 35 + 标签 20 + 评论甜蜜区 20 + 新鲜度 25 |
| 撞车检测 | 自动拉取全部 open PR，剔除已被 `fixes #N` 引用的 Issue |
| 批量体检 | `repo_health.py repo1 repo2 ...`，单项失败自动降级不中断 |
| `--json` 输出 | 三个脚本均支持，方便接入其他工具链 |
| 零依赖 | 纯 Python 标准库，无需 `pip install` |
| TS 生态优先 | 内置前沿 Agent 项目 topic（Vercel AI SDK / Mastra / LangGraph.js / Eliza 等） |

---

## 📖 命令参考

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `discover_repos.py` | 按方向/语言/规模发现候选项目 | `--topic` `--language` `--beginner` `--stars` `--max-stars` `--pushed-days` `--json` |
| `repo_health.py` | 12 项健康度体检 + AI 政策扫描 | 多仓库批量、`--json`（单项缺失自动降级，不中断） |
| `find_issues.py` | Issue 筛选、打分、撞车检测 | `--include-bugs` `--beginner-only` `--labels` `--min-score` `--days` `--json` |

---

## 🧭 工作流程（Agent 视角）

```
用户提供仓库 URL？
├── 是 → Route B：直接分析该项目的 PR/Issue 切入点
└── 否 → Route A：发现候选项目 → 用户选定一个 → 进入 Route B
```

- **Route A · 从零开始**：收集画像（技术栈先确认 **Python / TypeScript**）→ 发现候选 → 批量健康体检 → 输出候选表 → 用户选定
- **Route B · 已有目标仓库**：项目理解（README/CONTRIBUTING/主入口）→ 机筛 Issue + 人工复核 → AI 政策前置检查 → 7 维架构缺陷分析（定位到具体文件/函数）→ Top 3 贡献建议

选定切入点后，可继续走 `references/contribution-workflow.md` 全流程：方案设计 → 代码实现 → PR 提交 → 面试叙事（STAR + 60 秒话术）。

---

## 📁 目录结构

```
contrib-radar/
├── SKILL.md                       # Skill 主文件：定位、触发词、Route A/B 全流程
├── references/                    # 方法论参考（5 个）
│   ├── project-discovery.md       #   项目发现：搜索式 + 聚合站点 + 避坑
│   ├── opportunity-analysis.md    #   切入点分析：架构缺陷、依赖、路线图、文档
│   ├── contribution-workflow.md   #   贡献全流程：认领 → 测试 → PR → 合并
│   ├── communication-templates.md #   交流模板：Issue/PR 提问、跟帖话术
│   └── example-analysis.md        #   完整案例分析（输出颗粒度校准）
└── scripts/                       # 零依赖 Python 工具（4 个）
    ├── github_api.py              #   共享模块：请求/限速/重试/仓库解析
    ├── discover_repos.py          #   候选项目发现
    ├── find_issues.py             #   Issue 筛选 + 打分 + 撞车检测
    └── repo_health.py             #   健康度体检 + AI 政策检查
```

---

## 🏗️ 设计原则

为什么这个项目值得信任：

1. **零依赖、可审计**：4 个脚本纯标准库实现，代码可直接读、可直接跑，不引入供应链风险
2. **对 GitHub API 友好**：未认证时只对 search 端点限速打点（6.2s），403 时按 `X-RateLimit-Reset` 自适应等待；配置 token 后自动取消节流
3. **AI 时代意识**：AI 贡献政策扫描 + 撞车检测，是 2026 年开源贡献绕不开的两个新变量
4. **可解释的确定性输出**：打分权重透明（清晰度 35 / 标签 20 / 评论 20 / 新鲜度 25），可审计、可复现
5. **遵守 Agent Skills 标准**：`SKILL.md` 自包含、name 用 kebab-case、description 写明"做什么 + 何时用"，可被主流 Agent 平台自动发现

---

## 🗺️ 路线图

**v3（当前）已交付**：共享 API 封装、撞车检测、启发式打分、AI 政策扫描、`--beginner` 甜蜜区、`--json` 导出、TS 生态支持。

**候选方向**（欢迎 Issue 讨论，暂未排期）：

- 订阅与守护：定期 watch 目标仓库的新 good first issue 并推送
- MCP server 化：把三个脚本封装为 MCP 工具，供更多 Agent 平台直接调用
- 个性化推荐：结合用户技术栈历史做加权排序
- 周报导出：将一周的贡献跟踪结果汇总为 Markdown/HTML 报告

---

## ❓ FAQ

**需要 GitHub token 吗？**
不需要，脚本开箱即用。但建议设置 `GITHUB_TOKEN` 以大幅提升速率限额并取消节流等待。

**打分是 LLM 做的吗？会不会不准？**
打分是确定性启发式（权重公开可审计），零成本、可复现；LLM 语义判断（如评论中是否有人认领）由 Agent 在读正文时补充，脚本不替代。

**会撞车吗？**
脚本会剔除所有被 open PR 引用（`fixes #N` 等）的 Issue，并提示人工复核评论中的认领短语；动手前仍建议在 Issue 下留言认领。

**支持 GitLab / Gitee 吗？**
流程方法论通用，但自带脚本仅支持 GitHub；其他平台需用 WebFetch 人工核查活跃度。

---

## 🤝 贡献

欢迎 Issue 和 PR：

- **报 Bug / 提需求**：开 [Issue](https://github.com/louisss1016/contrib-radar/issues)，说明复现方式
- **改代码**：先开 Issue 讨论，再提 PR；保持零依赖、兼容 Agent Skills 标准
- **AI 生成代码**：请在本仓库明确声明后提交

## 📄 License

[MIT](./LICENSE) © 2026 Louisss

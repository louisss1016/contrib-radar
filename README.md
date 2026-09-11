# Contrib Radar · 开源贡献雷达

> 帮你在 GitHub 上找到值得贡献的开源项目，并锁定好上手、不撞车的 PR / Issue 切入点。

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Dependencies: zero](https://img.shields.io/badge/Dependencies-zero-lightgrey.svg)

Contrib Radar 是一个 **Agent Skill**（遵循 [Agent Skills](https://agentskills.io) 开放标准），把「开源贡献」这个重复流程工具化：**发现候选项目 → 健康体检 → 筛选 Issue 打分 → 撞车检测 → AI 政策核查**，最终交付一份可执行的贡献方案，而不是让 AI 每次从零临场发挥。

## 为什么做这个

开源贡献最常见的三个卡点：

1. **不知道选哪个项目** —— 热门仓库门槛高，冷门仓库又怕没维护者响应；
2. **不知道从哪个 Issue 入手** —— 海量 Issue 里找不到"低门槛 + 有人理"的切入点；
3. **怕白干** —— 提交前没发现已经有 PR 在认领，或者项目明确不欢迎 AI 生成代码。

Contrib Radar 用三个零依赖脚本 + 一套方法论把这三个卡点逐一拆掉。

## 特性

- **候选项目发现**：按 topic / 语言 / star 区间筛选，`--beginner` 进入新手甜蜜区（100~1000 star）
- **健康体检（12 项）**：提交活跃度、Issue 关闭率、PR 响应速度、Release 频率、贡献指南、开源 License 等
- **AI 生成代码政策扫描**：自动读取 `CONTRIBUTING.md`，判定项目对 AI 贡献是 `blocked / mention / ok / unknown`
- **Issue 启发式打分（0-100）**：清晰度 35 + 标签 20 + 评论甜蜜区 20 + 新鲜度 25
- **撞车检测**：自动拉取全部 open PR，剔除已被认领（`fixes #N`）的 Issue
- **零依赖**：纯 Python 标准库，无需 `pip install`
- **`--json` 输出**：方便接入其他工具链
- **TypeScript 生态优先**：内置前沿 Agent 项目（Vercel AI SDK / Mastra / LangGraph.js / Eliza 等）topic 清单

## 快速开始

### 作为 Agent Skill 使用

将 `contrib-radar/` 整个目录放入你的 Agent Skills 目录（如 Claude Code / Codex / 豆包等支持 Agent Skills 标准的平台），然后在对话中直接提出需求，例如：

> 帮我找一个 TypeScript 写的 AI Agent 方向、star 100~1000 的开源项目，顺便看看有哪些适合新手的 Issue。

### 作为命令行工具使用

```bash
cd contrib-radar/scripts

# 1. 发现候选项目（新手甜蜜区 + TypeScript 生态）
python discover_repos.py --topic ai-agent --language typescript --beginner

# 2. 对候选做健康体检（含 AI 政策检查）
python repo_health.py <owner/repo>

# 3. 筛选可上手的 Issue（打分 + 撞车检测）
python find_issues.py <owner/repo> --min-score 40
```

所有脚本走 GitHub 公共 API，未配置 token 时自动限速（search 10/min），配置 `GITHUB_TOKEN` 后限额提升至 30/min 并取消节流。

## 命令一览

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `discover_repos.py` | 按方向/语言/规模发现候选项目 | `--topic` `--language` `--beginner` `--json` |
| `repo_health.py` | 12 项健康度体检 + AI 政策扫描 | `--json`（单项缺失自动降级，不中断） |
| `find_issues.py` | Issue 筛选、打分、撞车检测 | `--include-bugs` `--beginner-only` `--min-score` `--json` |

## 目录结构

```
contrib-radar/
├── SKILL.md                       # Skill 主文件：定位、触发词、Route A/B 全流程
├── references/                    # 方法论参考（5 个）
│   ├── project-discovery.md       #   项目发现：搜索式 + 聚合站点 + 避坑
│   ├── opportunity-analysis.md    #   切入点分析：架构缺陷、依赖、路线图、文档
│   ├── contribution-workflow.md   #   贡献全流程：认领 → 测试 → PR → 合并
│   ├── communication-templates.md #   交流模板：Issue/PR 提问、跟帖话术
│   └── example-analysis.md        #   完整案例分析：Redis 风格复盘示例
└── scripts/                       # 零依赖 Python 工具（4 个）
    ├── github_api.py              #   共享模块：请求/限速/重试/仓库解析
    ├── discover_repos.py          #   候选项目发现
    ├── find_issues.py             #   Issue 筛选 + 打分 + 撞车检测
    └── repo_health.py             #   健康度体检 + AI 政策检查
```

## 工作流程（Agent 视角）

- **Route A — 从零开始**：收集画像（技术栈先确认 Python / TypeScript）→ 发现候选 → 健康体检 → 筛选 Issue → 输出候选表
- **Route B — 已有目标仓库**：直接体检 + 筛 Issue → 架构缺陷分析 → 产出贡献方案

## 给本项目贡献

欢迎 Issue 和 PR：

- **报 Bug / 提需求**：开 Issue，说明复现方式
- **改代码**：先开 Issue 讨论，再提 PR；保持零依赖、兼容 Agent Skills 标准
- **AI 生成代码**：请在本仓库 `CONTRIBUTING.md` 明示后再提交

## License

[MIT](./LICENSE) © 2026 Louisss

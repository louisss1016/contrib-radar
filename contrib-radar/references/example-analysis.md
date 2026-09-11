# 端到端分析示例（输出校准用）

> 这是一个压缩版的完整 Route B 输出样例，用于校准格式与颗粒度。
> 关键标准：每个结论都定位到具体文件/函数；不确定的地方明说"未确认"，禁止编造。

## 目标项目

`example-org/agentkit`（Python，单 Agent 工具调用框架，⭐3.2k）

用户画像：Python / FastAPI / LangChain，目标 2 周内完成 1 个可讲述的 PR。

## 0. 项目理解

```
agentkit/
├── agent/          # 核心：Agent 循环与执行器
│   ├── executor.py     # AgentExecutor.run() 主循环
│   └── planner.py      # 简单的一步提示规划
├── tools/          # 工具注册与调用
│   ├── base.py         # Tool 基类与 schema 生成
│   └── registry.py     # 全量工具注册表
├── memory/         # 对话历史管理
└── server/         # FastAPI 服务层
```

核心机制：`AgentExecutor.run()` 是经典的 ReAct 单 Agent 循环——把全部 tool schema 注入 system prompt，LLM 逐步决策调用工具，无显式规划层、无状态持久化。

## 1. Issue 筛选结果

| Issue # | 标题 | 类型 | 所需技能 | 预估工作量 | 推荐理由 |
|---------|------|------|---------|-----------|---------|
| #412 | Tool schema 超过 token 上限时直接报错 | bug | Python、prompt 工程 | 小 | 入口清晰，改动应在 tools/registry.py 一处 |
| #387 | 希望支持 MCP server 作为工具来源 | enhancement | Python、MCP 协议 | 中 | help wanted 标签，维护者明确表示欢迎 |

（已排除 #399：评论中有人 3 天前说 "I'll take this"。）

## 2. 架构维度分析（节选 2 个维度作示例）

### 维度 6：Tool 检索与路由

- **现状描述：** `tools/registry.py` 的 `ToolRegistry.get_prompt_schemas()` 把所有注册工具的 JSON schema 全量拼接进 system prompt，无任何筛选。
- **缺陷 / 缺失：** 工具数超过 ~15 个时 prompt 膨胀，token 浪费且 LLM 选错工具概率上升（#412 即由此引发）。
- **影响程度：** high
- **改进方向：** 引入基于任务描述的向量化工具检索，每轮只注入 top-k（如 k=8）相关工具 schema；保留全量注入作为 fallback 配置。
- **改动范围：** 新增 `tools/retrieval.py`（约 120 行），修改 `registry.py` 与 `executor.py` 各 1 处（<30 行）。
- **面试叙事角度：** 体现对 Agent 系统"上下文经济学"的理解和 RAG 思想在工具层的落地。

### 维度 4：Human-in-the-loop 机制

- **现状描述：** `agent/executor.py` 的 `_execute_tool()` 直接调用工具，无风险分级、无确认钩子。
- **缺陷 / 缺失：** 写文件、发请求等高风险工具与只读工具无差别执行。
- **影响程度：** medium
- **改进方向：** 在 `Tool` 基类增加 `risk_level` 字段，executor 遇到 high 风险工具时回调可插拔的确认函数。
- **改动范围：** `tools/base.py` + `executor.py`，约 80 行。
- **面试叙事角度：** 体现对 Agent 安全边界与可控性的工程化思考。

## 3. Top 3 贡献建议

**第 1 名：工具按需检索（解决 #412 的根治方案）**
- 一句话描述：为 ToolRegistry 增加向量检索层，按任务动态选取工具子集注入 prompt
- 来源维度：Issue #412 + 代码分析-维度 6
- 入口文件：`tools/registry.py`、`agent/executor.py`
- 为什么适合我：Python 为主，正好覆盖 LangChain/RAG 经验
- 预计工作量：中
- 面试中能讲什么：上下文管理策略、检索增强在工具层的应用、向后兼容设计（保留全量注入开关）
- 风险点：引入向量检索可能需要新依赖（需先与维护者确认，或用 numpy 手写余弦相似度避免依赖）

**第 2名：接入 MCP 工具来源（#387）**
- 一句话描述：支持把 MCP server 暴露的工具注册进 ToolRegistry
- 来源维度：Issue #387
- 入口文件：`tools/registry.py`，新增 `tools/mcp_adapter.py`
- 为什么适合我：有 MCP 集成经验
- 预计工作量：中
- 面试中能讲什么：协议适配层设计、生态兼容性思考
- 风险点：依赖维护者对 MCP 依赖的态度；改动面比第 1 名大

**第 3 名：高风险工具人工确认钩子**
- 一句话描述：为工具执行增加 risk_level 分级与可插拔确认回调
- 来源维度：代码分析-维度 4
- 入口文件：`tools/base.py`、`agent/executor.py`
- 为什么适合我：改动小、概念清晰，适合作为该项目的第一个 PR 建立信任
- 预计工作量：小
- 面试中能讲什么：HITL 机制设计、最小侵入改造
- 风险点：无对应 open Issue，需先开 Issue 讨论（先沟通再动手）

---

**格式自检清单**（输出前逐项确认）：
- [ ] 每个维度都写了具体文件路径 + 函数名
- [ ] Issue 表排除了已认领条目，并注明排除原因
- [ ] Top 3 每条都含入口文件、风险点、面试价值
- [ ] 工作量评估与时间预算匹配
- [ ] 不确定的信息标注"未确认"，没有编造

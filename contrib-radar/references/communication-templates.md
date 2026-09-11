# 英文沟通模板（即取即用）

> 所有模板保持简洁专业。根据实际项目替换 `{}` 占位内容，不要逐字照抄。
> 原则：先沟通再动手；不催促；把维护者的时间当作稀缺资源。

## 1. Issue 认领留言

```
Hi! I'd like to work on this issue. My plan is to {一句话方案，如
"add a retrieval layer in tools/registry.py that selects the top-k
relevant tools per task"}. Please let me know if that direction makes
sense, or if anyone is already working on it.
```

## 2. 新贡献方向提案（无现成 Issue 时，开 Issue 或在 Discussion 发起）

```
Hi! While reading the codebase, I noticed that {客观描述现象，如
"ToolRegistry.get_prompt_schemas() injects all tool schemas into the
system prompt, which breaks once the tool count grows past ~15"}.

I'd like to propose {解决方向，只说方向不展开细节，如 "adding a
retrieval step that dynamically selects a relevant tool subset per
task"}.

Would you be open to a PR in this direction, or is this already on
the roadmap? Happy to adjust the approach to fit the project's design.
```

## 3. PR 描述模板

```markdown
## Problem
{客观陈述当前问题，不带情绪。引用相关 Issue：Fixes #123}

## Solution
{本 PR 的解决思路，以及为什么选这个方案（1~3 句）}

## Changes
- {新增/修改了什么，按文件列出}

## Testing
- {如何验证：demo 步骤 / 新增测试覆盖了哪些场景}

## Notes for Reviewer
- {需要重点关注的地方，或有意为之的设计决策}
```

## 4. 回应 Review 意见

```
Thanks for the review! I've pushed changes to address your comments:
- {意见 1}: {如何修改的}
- {意见 2}: {如何修改的}
Let me know if anything else needs adjustment.
```

若有不同意见（保持讨论而非争论）：

```
Good point. My concern with {维护者建议的方案} is {客观理由}. An
alternative could be {折中方案}. What do you think?
```

## 5. 礼貌跟进（超过 1~2 周无回应）

```
Hi, just a friendly ping on this PR. Happy to make any changes if
needed — no rush, and thanks for maintaining the project!
```

## 6. 无法继续时的交接留言

```
Thanks for the opportunity! I won't be able to continue on this due to
time constraints. Unassigning myself so others can pick it up — my
current progress is in {分支链接} if useful.
```

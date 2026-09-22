#!/usr/bin/env python3
"""Issue 认领方式检测与冲突检查（v1.0，零第三方依赖，基于共享 github_api 模块）。

在动手实现前，自动检测目标仓库的认领机制，并检查认领冲突：
1. 检测 .github/workflows/ 中是否有 claim bot（issue-claim.yml 等）
2. 检查 issue 是否已被认领（assignee / 评论中的认领声明）
3. 检查是否已有 open PR 引用该 issue（撞车检测）
4. 输出认领建议（bot 命令或评论模板）

注意：本脚本只做检测和准备，不实际发送评论。发送评论需要通过
已认证的 MCP/OAuth 连接、gh CLI 或 GITHUB_TOKEN。

用法:
    python claim_issue.py owner/repo 25
    python claim_issue.py owner/repo 25 --json
    python claim_issue.py https://github.com/owner/repo/issues/25
    python claim_issue.py owner/repo 25 --quiet

进度（v3.7）：bot 检测 / 冲突检查 / 建议生成三阶段向 stderr 发射
[CR-PROGRESS] JSON 事件（管道模式）；--json 的 stdout 契约不受影响。

可选: 设置环境变量 GITHUB_TOKEN 以提高 API 速率限制。
"""

import argparse
import json
import re
import sys

import github_api as gh
import progress as pg

# 认领 bot 的 workflow 文件名关键词
CLAIM_BOT_PATTERNS = [
    r"claim", r"issue-claim", r"assign", r"take",
]

# 认领声明短语（评论中出现这些短语说明有人声称在做）
CLAIM_PHRASES = [
    "i'll take this", "i will take this", "i'm working on this",
    "i am working on this", "on it", "assign me", "claim",
    "我来做", "我认领", "交给我",
]

# PR 引用 issue 的模式
PR_REF_PATTERNS = [
    r"(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s*[#:]?\s*(\d+)",
    r"#(\d+)",
]


def detect_claim_bot(owner, repo):
    """检测仓库是否有 claim bot。返回 (has_bot, bot_name, workflow_path)。"""
    # 列出 .github/workflows/ 目录
    contents = gh.get(f"/repos/{owner}/{repo}/contents/.github/workflows")
    if "_error" in contents or not isinstance(contents, list):
        return False, None, None

    for item in contents:
        name = item.get("name", "").lower()
        for pattern in CLAIM_BOT_PATTERNS:
            if re.search(pattern, name):
                return True, item["name"], item.get("path")
    return False, None, None


def check_claim_conflict(owner, repo, issue_number):
    """检查 issue 的认领冲突。返回冲突详情字典。"""
    result = {
        "has_assignee": False,
        "assignees": [],
        "claim_comments": [],
        "referenced_by_prs": [],
        "conflict": False,
        "conflict_reasons": [],
    }

    # 1. 检查 issue 详情（assignee）
    issue = gh.get(f"/repos/{owner}/{repo}/issues/{issue_number}")
    if "_error" in issue:
        result["error"] = issue["_error"]
        return result

    assignees = issue.get("assignees", [])
    if assignees:
        result["has_assignee"] = True
        result["assignees"] = [a["login"] for a in assignees]
        result["conflict"] = True
        result["conflict_reasons"].append(f"已被指派给 {', '.join(result['assignees'])}")

    # 2. 检查评论中的认领声明
    comments = gh.get(f"/repos/{owner}/{repo}/issues/{issue_number}/comments?per_page=100")
    if "_error" not in comments and isinstance(comments, list):
        for comment in comments:
            body = (comment.get("body") or "").lower()
            for phrase in CLAIM_PHRASES:
                if phrase in body:
                    result["claim_comments"].append({
                        "user": comment["user"]["login"],
                        "created_at": comment["created_at"],
                        "phrase": phrase,
                        "url": comment["html_url"],
                    })
                    break
        if result["claim_comments"]:
            result["conflict"] = True
            users = [c["user"] for c in result["claim_comments"]]
            result["conflict_reasons"].append(f"评论中有人声称认领: {', '.join(set(users))}")

    # 3. 检查是否有 open PR 引用该 issue
    pr_data = gh.get(
        f"/search/issues?q=repo:{owner}/{repo}+type:pr+state:open&per_page=100",
        search=True
    )
    if "_error" not in pr_data:
        for pr in pr_data.get("items", []):
            text = f"{pr.get('title') or ''} {pr.get('body') or ''}"
            for pattern in PR_REF_PATTERNS:
                for m in re.finditer(pattern, text, re.I):
                    if int(m.group(1)) == issue_number:
                        result["referenced_by_prs"].append({
                            "number": pr["number"],
                            "title": pr["title"],
                            "url": pr["html_url"],
                            "user": pr["user"]["login"],
                        })
                        break
        if result["referenced_by_prs"]:
            result["conflict"] = True
            pr_nums = [f"#{p['number']}" for p in result["referenced_by_prs"]]
            result["conflict_reasons"].append(f"已被 open PR 引用: {', '.join(pr_nums)}")

    return result


def generate_claim_suggestion(has_bot, bot_name, conflict_info):
    """根据检测结果生成认领建议。"""
    if conflict_info["conflict"]:
        return {
            "action": "skip",
            "reason": "存在认领冲突，建议换一个 issue",
            "details": conflict_info["conflict_reasons"],
        }

    if has_bot:
        return {
            "action": "claim_via_bot",
            "command": "/claim",
            "bot": bot_name,
            "instructions": [
                "在 issue 下发表评论，内容仅为 /claim",
                "发完后不要编辑评论（bot 只在评论 created 时触发，编辑不触发）",
                "等待 bot 回复确认（通常会评论 'Assigned!' 或类似）",
                "如果 bot 无响应，检查 workflow 是否启用、是否有权限限制",
            ],
        }

    return {
        "action": "claim_via_comment",
        "comment_template": (
            "I'd like to work on this issue. Could you assign it to me?\n\n"
            "My plan:\n"
            "- {简要描述你的实现方向，1-2 句话}\n\n"
            "I'll submit a PR within {预计时间，如 1-2 天}."
        ),
        "instructions": [
            "在 issue 下发表认领评论",
            "等待维护者回复或手动 assign",
            "如果 3-5 天无回应，可礼貌跟进一次",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="Issue 认领方式检测与冲突检查")
    ap.add_argument("repo", help="owner/repo 或 GitHub issue URL")
    ap.add_argument("issue_number", nargs="?", type=int, help="Issue 编号（如果 repo 参数不是 URL）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiet", action="store_true", help="关闭 stderr 进度输出")
    args = ap.parse_args()
    if args.quiet:
        pg.set_quiet(True)  # --quiet 覆盖 CR_QUIET 默认值

    # 解析参数：支持直接传 issue URL
    if args.repo.startswith("http"):
        m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)", args.repo)
        if not m:
            sys.exit("无法解析 issue URL")
        owner, repo, issue_number = m.group(1), m.group(2), int(m.group(3))
    else:
        owner, repo = gh.parse_repo(args.repo)
        if not owner or not args.issue_number:
            sys.exit("需要提供 owner/repo 和 issue_number，或直接传 issue URL")
        issue_number = args.issue_number

    pg.phase("claim-check", total=3, detail=f"{owner}/{repo}#{issue_number}")

    # 1. 检测 claim bot
    pg.phase("claim-bot-detect")
    has_bot, bot_name, bot_path = detect_claim_bot(owner, repo)
    pg.phase("claim-bot-detect", "done" if has_bot else "warn",
             detail=bot_name if has_bot else "no claim bot, comment claim required")

    # 2. 检查认领冲突
    pg.phase("conflict-check")
    conflict_info = check_claim_conflict(owner, repo, issue_number)
    if conflict_info.get("error"):
        pg.phase("conflict-check", "error", detail=str(conflict_info["error"]))
    elif conflict_info["conflict"]:
        pg.phase("conflict-check", "warn",
                 detail=f"conflict: {len(conflict_info['conflict_reasons'])} reasons")
    else:
        pg.phase("conflict-check", "done", detail="no conflict")

    # 3. 生成认领建议
    suggestion = generate_claim_suggestion(has_bot, bot_name, conflict_info)
    pg.phase("claim-check", "done", detail=f"suggestion: {suggestion['action']}")

    result = {
        "repo": f"{owner}/{repo}",
        "issue_number": issue_number,
        "issue_url": f"https://github.com/{owner}/{repo}/issues/{issue_number}",
        "claim_bot": {
            "detected": has_bot,
            "workflow": bot_name,
            "path": bot_path,
        },
        "conflict_check": conflict_info,
        "suggestion": suggestion,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    print(f"仓库: {owner}/{repo}  Issue: #{issue_number}")
    print(f"链接: {result['issue_url']}\n")

    print("=== Claim Bot 检测 ===")
    if has_bot:
        print(f"  ✅ 检测到 claim bot: {bot_name} ({bot_path})")
    else:
        print("  ❌ 未检测到 claim bot，需用评论认领")

    print("\n=== 认领冲突检查 ===")
    if conflict_info.get("error"):
        print(f"  ⚠️  检查出错: {conflict_info['error']}")
    elif conflict_info["conflict"]:
        print("  ⛔ 存在认领冲突:")
        for reason in conflict_info["conflict_reasons"]:
            print(f"     - {reason}")
        if conflict_info["claim_comments"]:
            print("  认领评论详情:")
            for c in conflict_info["claim_comments"]:
                print(f"     - @{c['user']} ({c['created_at']}): '{c['phrase']}' → {c['url']}")
        if conflict_info["referenced_by_prs"]:
            print("  引用 PR:")
            for p in conflict_info["referenced_by_prs"]:
                print(f"     - #{p['number']} by @{p['user']}: {p['title'][:50]} → {p['url']}")
    else:
        print("  ✅ 无认领冲突，可以认领")

    print("\n=== 认领建议 ===")
    if suggestion["action"] == "skip":
        print(f"  ⛔ {suggestion['reason']}")
        for d in suggestion["details"]:
            print(f"     - {d}")
    elif suggestion["action"] == "claim_via_bot":
        print(f"  🤖 通过 bot 认领:")
        print(f"     命令: {suggestion['command']}")
        for inst in suggestion["instructions"]:
            print(f"     - {inst}")
    else:
        print("  💬 通过评论认领:")
        print(f"     模板:\n{suggestion['comment_template']}")
        for inst in suggestion["instructions"]:
            print(f"     - {inst}")

    print("\n注意: 本脚本只做检测和建议，不实际发送评论。")
    print("发送评论请通过已认证的 MCP/OAuth 连接、gh CLI 或 GITHUB_TOKEN。")


if __name__ == "__main__":
    gh.ensure_utf8_stdio()
    main()

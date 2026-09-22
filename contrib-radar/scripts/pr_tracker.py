#!/usr/bin/env python3
"""PR 生命周期跟踪（v1.0，零第三方依赖，基于共享 github_api 模块）。

跟踪已提交 PR 的状态，用于 Route C+ 自动贡献模式的日常检查：
1. CI 状态（check runs：成功/失败/进行中）
2. Review 状态（是否有新 review 评论、是否被 request changes）
3. 可合并性（mergeable / mergeable_state）
4. 上游更新检测（base 分支是否有新 commit，是否需要 rebase）
5. 合并/关闭状态

输出结构化状态报告，供定时任务判断下一步动作（修复 CI / 回应 review / rebase / 跟进 / 记录成果）。

用法:
    python pr_tracker.py owner/repo 72
    python pr_tracker.py owner/repo 72 --json
    python pr_tracker.py https://github.com/owner/repo/pull/72
    python pr_tracker.py owner/repo 72 --quiet

进度（v3.7）：合并性 / CI / Review / Rebase 四项检查按阶段向 stderr
发射 [CR-PROGRESS] JSON 事件（管道模式）；--json 的 stdout 契约不受影响。

可选: 设置环境变量 GITHUB_TOKEN 以提高 API 速率限制。
"""

import argparse
import json
import re
import sys

import github_api as gh
import progress as pg


def check_ci_status(owner, repo, pr_number, head_sha):
    """检查 PR 的 CI check runs 状态。"""
    result = {
        "total": 0,
        "success": 0,
        "failure": 0,
        "pending": 0,
        "skipped": 0,
        "failed_checks": [],
        "status": "unknown",  # success / failure / pending / unknown
    }

    if not head_sha:
        return result

    data = gh.get(f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs?per_page=100")
    if "_error" in data:
        result["error"] = data["_error"]
        return result

    for run in data.get("check_runs", []):
        result["total"] += 1
        status = run.get("status")  # queued / in_progress / completed
        conclusion = run.get("conclusion")  # success / failure / neutral / cancelled / skipped / timed_out / action_required

        if status != "completed":
            result["pending"] += 1
        elif conclusion == "success":
            result["success"] += 1
        elif conclusion in ("failure", "timed_out", "action_required"):
            result["failure"] += 1
            result["failed_checks"].append({
                "name": run.get("name"),
                "conclusion": conclusion,
                "url": run.get("html_url"),
                "output": (run.get("output") or {}).get("summary", "")[:200],
            })
        elif conclusion == "skipped":
            result["skipped"] += 1
        # neutral / cancelled 不计入失败

    if result["pending"] > 0:
        result["status"] = "pending"
    elif result["failure"] > 0:
        result["status"] = "failure"
    elif result["success"] > 0:
        result["status"] = "success"

    return result


def check_reviews(owner, repo, pr_number):
    """检查 PR 的 review 状态。"""
    result = {
        "total_reviews": 0,
        "approved": 0,
        "changes_requested": 0,
        "commented": 0,
        "dismissed": 0,
        "latest_review": None,
        "has_unaddressed_comments": False,
        "review_comments_count": 0,
    }

    # 列出 reviews
    reviews = gh.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews?per_page=100")
    if "_error" not in reviews and isinstance(reviews, list):
        for review in reviews:
            state = review.get("state", "").lower()
            result["total_reviews"] += 1
            if state == "approved":
                result["approved"] += 1
            elif state == "changes_requested":
                result["changes_requested"] += 1
            elif state == "commented":
                result["commented"] += 1
            elif state == "dismissed":
                result["dismissed"] += 1

            # 记录最新的非 dismissed review
            if state != "dismissed":
                result["latest_review"] = {
                    "user": review["user"]["login"],
                    "state": state,
                    "submitted_at": review.get("submitted_at"),
                    "body": (review.get("body") or "")[:300],
                    "url": review.get("html_url"),
                }

    # 列出 review comments（行内评论）
    comments = gh.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/comments?per_page=100")
    if "_error" not in comments and isinstance(comments, list):
        result["review_comments_count"] = len(comments)
        # 简单判断：有未解决的评论（GitHub API 没有直接的 resolved 字段，
        # 这里只统计数量，具体是否已解决需要人工或更复杂的判断）
        if comments:
            result["has_unaddressed_comments"] = True

    return result


def check_mergeability(owner, repo, pr_number):
    """检查 PR 的可合并性。"""
    pr = gh.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
    if "_error" in pr:
        return {"error": pr["_error"]}

    return {
        "mergeable": pr.get("mergeable"),  # True / False / None（正在计算）
        "mergeable_state": pr.get("mergeable_state"),  # clean / dirty / blocked / unstable / behind
        "merged": pr.get("merged", False),
        "merged_at": pr.get("merged_at"),
        "state": pr.get("state"),  # open / closed
        "draft": pr.get("draft", False),
        "head_sha": pr.get("head", {}).get("sha"),
        "base_sha": pr.get("base", {}).get("sha"),
        "base_branch": pr.get("base", {}).get("ref"),
        "title": pr.get("title"),
        "user": pr["user"]["login"],
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
    }


def check_needs_rebase(owner, repo, pr_number, base_branch, base_sha):
    """检查 PR 是否需要 rebase（base 分支是否有新 commit）。"""
    if not base_branch or not base_sha:
        return {"needs_rebase": False, "reason": "missing base info"}

    # 获取 base 分支最新 commit
    branch = gh.get(f"/repos/{owner}/{repo}/branches/{base_branch}")
    if "_error" in branch:
        return {"needs_rebase": False, "error": branch["_error"]}

    latest_sha = branch.get("commit", {}).get("sha")
    if not latest_sha:
        return {"needs_rebase": False, "reason": "cannot get latest base sha"}

    # 比较：如果 PR 的 base_sha 不等于分支最新 sha，说明上游有更新
    if latest_sha != base_sha:
        # 进一步检查：比较两个 commit，看是否有文件交集
        comparison = gh.get(
            f"/repos/{owner}/{repo}/compare/{base_sha}...{latest_sha}"
        )
        files_changed = []
        if "_error" not in comparison:
            files_changed = [f.get("filename") for f in comparison.get("files", [])]

        return {
            "needs_rebase": True,
            "base_latest_sha": latest_sha,
            "pr_base_sha": base_sha,
            "ahead_by": comparison.get("total_commits", 0) if "_error" not in comparison else "unknown",
            "files_changed_upstream": files_changed,
            "reason": f"base 分支有 {comparison.get('total_commits', '?')} 个新 commit",
        }

    return {"needs_rebase": False, "base_latest_sha": latest_sha}


def determine_next_action(merge_info, ci_info, review_info, rebase_info):
    """根据所有检查结果，判断下一步动作。"""
    actions = []

    if merge_info.get("merged"):
        actions.append({
            "action": "record_merged",
            "priority": "done",
            "reason": f"PR 已合并于 {merge_info.get('merged_at')}",
        })
        return actions

    if merge_info.get("state") == "closed":
        actions.append({
            "action": "record_closed",
            "priority": "done",
            "reason": "PR 已关闭",
        })
        return actions

    if merge_info.get("draft"):
        actions.append({
            "action": "wait",
            "priority": "low",
            "reason": "PR 仍为 draft 状态",
        })

    # CI 失败
    if ci_info.get("status") == "failure":
        failed_names = [c["name"] for c in ci_info.get("failed_checks", [])]
        actions.append({
            "action": "fix_ci",
            "priority": "high",
            "reason": f"CI 失败: {', '.join(failed_names)}",
            "details": ci_info["failed_checks"],
        })

    # CI 进行中
    if ci_info.get("status") == "pending":
        actions.append({
            "action": "wait_for_ci",
            "priority": "medium",
            "reason": f"CI 进行中 ({ci_info.get('pending')} 个 check 未完成)",
        })

    # Review 要求修改
    if review_info.get("changes_requested", 0) > 0:
        latest = review_info.get("latest_review")
        actions.append({
            "action": "address_review",
            "priority": "high",
            "reason": f"有 {review_info['changes_requested']} 个 review 要求修改",
            "details": latest,
        })

    # 有 review 评论
    if review_info.get("has_unaddressed_comments"):
        actions.append({
            "action": "check_comments",
            "priority": "medium",
            "reason": f"有 {review_info['review_comments_count']} 条 review 评论待处理",
        })

    # 需要 rebase
    if rebase_info.get("needs_rebase"):
        actions.append({
            "action": "rebase",
            "priority": "medium",
            "reason": rebase_info.get("reason", "base 分支有更新"),
            "details": {
                "files_changed": rebase_info.get("files_changed_upstream", []),
                "ahead_by": rebase_info.get("ahead_by"),
            },
        })

    # mergeable_state 检查
    ms = merge_info.get("mergeable_state")
    if ms == "blocked":
        actions.append({
            "action": "investigate_block",
            "priority": "high",
            "reason": "PR 被阻止合并（可能需要 review 批准或 CI 通过）",
        })
    elif ms == "unstable":
        actions.append({
            "action": "wait",
            "priority": "low",
            "reason": "PR 可合并但 CI 不稳定",
        })

    # 无回应跟进（超过 7 天无更新且无 action）
    if not actions and merge_info.get("updated_at"):
        try:
            from datetime import datetime, timezone, timedelta
            updated = datetime.fromisoformat(merge_info["updated_at"].replace("Z", "+00:00"))
            days_since_update = (datetime.now(timezone.utc) - updated).days
            if days_since_update >= 7:
                actions.append({
                    "action": "gentle_ping",
                    "priority": "low",
                    "reason": f"已 {days_since_update} 天无更新，可礼貌跟进",
                })
        except Exception:
            pass

    if not actions:
        actions.append({
            "action": "wait",
            "priority": "low",
            "reason": "PR 状态正常，等待维护者 review",
        })

    return actions


def main():
    ap = argparse.ArgumentParser(description="PR 生命周期跟踪")
    ap.add_argument("repo", help="owner/repo 或 GitHub PR URL")
    ap.add_argument("pr_number", nargs="?", type=int, help="PR 编号（如果 repo 参数不是 URL）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiet", action="store_true", help="关闭 stderr 进度输出")
    args = ap.parse_args()
    pg.set_quiet(args.quiet)

    # 解析参数
    if args.repo.startswith("http"):
        m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)", args.repo)
        if not m:
            sys.exit("无法解析 PR URL")
        owner, repo, pr_number = m.group(1), m.group(2), int(m.group(3))
    else:
        owner, repo = gh.parse_repo(args.repo)
        if not owner or not args.pr_number:
            sys.exit("需要提供 owner/repo 和 pr_number，或直接传 PR URL")
        pr_number = args.pr_number

    pg.phase("pr-track", total=4, detail=f"{owner}/{repo}#{pr_number}")

    # 1. 基本信息 + 可合并性
    pg.phase("mergeability")
    merge_info = check_mergeability(owner, repo, pr_number)
    if "error" in merge_info:
        pg.phase("mergeability", "error", detail=str(merge_info["error"]))
        sys.exit(f"获取 PR 信息失败: {merge_info['error']}")
    pg.phase("mergeability", "done",
             detail=f"state={merge_info.get('state')}, mergeable={merge_info.get('mergeable')}")

    # 2. CI 状态
    pg.phase("ci-check")
    ci_info = check_ci_status(owner, repo, pr_number, merge_info.get("head_sha"))
    if "error" in ci_info:
        pg.phase("ci-check", "error", detail=str(ci_info["error"]))
    else:
        pg.phase("ci-check", "done",
                 detail=f"{ci_info.get('success')}/{ci_info.get('total')} passing, status={ci_info.get('status')}")

    # 3. Review 状态
    pg.phase("review-check")
    review_info = check_reviews(owner, repo, pr_number)
    if "error" in review_info:
        pg.phase("review-check", "error", detail=str(review_info["error"]))
    else:
        pg.phase("review-check", "done",
                 detail=f"{review_info.get('approved')} approved, {review_info.get('changes_requested')} changes requested")

    # 4. Rebase 检测
    pg.phase("rebase-check")
    rebase_info = check_needs_rebase(
        owner, repo, pr_number,
        merge_info.get("base_branch"),
        merge_info.get("base_sha")
    )
    if "error" in rebase_info:
        pg.phase("rebase-check", "error", detail=str(rebase_info["error"]))
    else:
        pg.phase("rebase-check", "done",
                 detail="needs rebase" if rebase_info.get("needs_rebase") else "up to date")

    # 5. 下一步动作
    next_actions = determine_next_action(merge_info, ci_info, review_info, rebase_info)
    pg.phase("pr-track", "done", detail=f"{len(next_actions)} next actions")

    result = {
        "repo": f"{owner}/{repo}",
        "pr_number": pr_number,
        "pr_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
        "title": merge_info.get("title"),
        "state": merge_info.get("state"),
        "merged": merge_info.get("merged"),
        "draft": merge_info.get("draft"),
        "mergeable": merge_info.get("mergeable"),
        "mergeable_state": merge_info.get("mergeable_state"),
        "ci": ci_info,
        "reviews": review_info,
        "rebase": rebase_info,
        "next_actions": next_actions,
        "updated_at": merge_info.get("updated_at"),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    print(f"仓库: {owner}/{repo}  PR: #{pr_number}")
    print(f"标题: {merge_info.get('title')}")
    print(f"链接: {result['pr_url']}\n")

    print("=== 基本状态 ===")
    state_icon = "✅" if merge_info.get("merged") else ("🟢" if merge_info.get("state") == "open" else "🔴")
    print(f"  状态: {state_icon} {merge_info.get('state')}" +
          (f" (已合并于 {merge_info.get('merged_at')})" if merge_info.get("merged") else ""))
    print(f"  Draft: {'是' if merge_info.get('draft') else '否'}")
    print(f"  可合并: {merge_info.get('mergeable')} (state: {merge_info.get('mergeable_state')})")
    print(f"  最后更新: {merge_info.get('updated_at')}")

    print("\n=== CI 状态 ===")
    if "error" in ci_info:
        print(f"  ⚠️  获取失败: {ci_info['error']}")
    else:
        print(f"  总计: {ci_info['total']} | ✅ {ci_info['success']} | ❌ {ci_info['failure']} | ⏳ {ci_info['pending']} | ⏭️ {ci_info['skipped']}")
        print(f"  状态: {ci_info['status']}")
        if ci_info["failed_checks"]:
            print("  失败的 check:")
            for c in ci_info["failed_checks"]:
                print(f"    - {c['name']}: {c['conclusion']} → {c['url']}")

    print("\n=== Review 状态 ===")
    print(f"  Reviews: {review_info['total_reviews']} (✅ approved: {review_info['approved']}, "
          f"❌ changes: {review_info['changes_requested']}, 💬 commented: {review_info['commented']})")
    print(f"  Review 评论: {review_info['review_comments_count']} 条")
    if review_info.get("latest_review"):
        lr = review_info["latest_review"]
        print(f"  最新 review: @{lr['user']} ({lr['state']}) at {lr['submitted_at']}")
        if lr.get("body"):
            print(f"    {lr['body'][:100]}...")

    print("\n=== Rebase 检测 ===")
    if rebase_info.get("needs_rebase"):
        print(f"  ⚠️  需要 rebase: {rebase_info.get('reason')}")
        if rebase_info.get("files_changed_upstream"):
            print(f"  上游改动文件: {', '.join(rebase_info['files_changed_upstream'][:5])}")
    else:
        print("  ✅ 无需 rebase（base 分支无新 commit）")

    print("\n=== 下一步动作 ===")
    for action in next_actions:
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "done": "✅"}.get(action["priority"], "⚪")
        print(f"  {priority_icon} [{action['priority']}] {action['action']}: {action['reason']}")

    print("\n注意: 本脚本只做状态检测，不执行任何写操作。")
    print("实际动作（修复 CI / rebase / 发评论）需由 agent 根据 next_actions 执行。")


if __name__ == "__main__":
    gh.ensure_utf8_stdio()
    main()

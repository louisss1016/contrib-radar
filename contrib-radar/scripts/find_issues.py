#!/usr/bin/env python3
"""GitHub 可认领 Issue 筛选与打分（v3，零第三方依赖，基于共享 github_api 模块）。

按《开源手册》Route B 的筛选条件自动过滤，并做启发式打分排序：
- 标签：默认仅 good first issue / help wanted（新手友好，避免 bug/enhancement 洪泛）
- 状态 open、近 N 天内有活动、无 assignee
- 撞车检测：自动拉取该仓库全部 open PR，剔除已被 PR 引用（fixes #123 等）的 issue
- 启发式打分（0~100）：清晰度（描述长度/代码块/复现步骤）+ 标签权重 + 评论甜蜜区 + 新鲜度
- 评论中是否有人声称认领（"I'll take this"）仍需模型读正文做语义判断，本脚本不替代

用法:
    python find_issues.py owner/repo
    python find_issues.py owner/repo --days 60 --limit 15
    python find_issues.py owner/repo --include-bugs          # 显式纳入 bug/enhancement
    python find_issues.py owner/repo --json                  # JSON 输出
    python find_issues.py owner/repo --min-score 60          # 只保留打分 >=60 的

可选: 设置环境变量 GITHUB_TOKEN 以提高 API 速率限制（强烈建议）。
"""

import argparse
import json
import re
import sys

import github_api as gh

DEFAULT_LABELS = ["good first issue", "help wanted"]
BEGINNER_ONLY_LABELS = ["good first issue", "help wanted", "first-timers-only", "beginner friendly"]
FULL_LABELS = ["good first issue", "help wanted", "bug", "enhancement"]

# 认领声明短语（供模型复核时参考；脚本不做网络评论抓取以避免 core 限流）
CLAIM_PHRASES = ["i'll take this", "i will take this", "i'm working on this",
                 "i am working on this", "on it", "assign me", "claim"]


def score_issue(it, days_active):
    """启发式打分 0~100（可解释、权重透明）。"""
    body = it.get("body") or ""
    labels = {l["name"].lower() for l in it.get("labels", [])}
    comments = it.get("comments", 0)

    s = 0.0
    parts = []

    # 1. 清晰度（35 分）：描述长度 + 代码块 + 复现/验收关键词
    clarity = 0.0
    clarity += min(len(body.strip()) / 200.0, 1.0) * 15.0          # 描述 >=200 字符满分
    if "```" in body:
        clarity += 8.0
    if re.search(r"(reproduc|steps to|expected behavior|acceptance criteri|example)", body, re.I):
        clarity += 12.0
    clarity = min(clarity, 35.0)
    s += clarity
    parts.append(f"清晰度{clarity:.0f}/35")

    # 2. 标签权重（20 分）
    label_score = 0.0
    if "good first issue" in labels:
        label_score = 20.0
    elif "first-timers-only" in labels or "beginner friendly" in labels:
        label_score = 18.0
    elif "help wanted" in labels:
        label_score = 14.0
    elif "documentation" in labels:
        label_score = 16.0
    elif "bug" in labels:
        label_score = 10.0
    elif "enhancement" in labels:
        label_score = 8.0
    s += label_score
    parts.append(f"标签{label_score:.0f}/20")

    # 3. 评论甜蜜区（20 分）：1~5 条最佳，过多说明争议大/复杂度高
    if comments <= 0:
        c_score = 8.0
    elif comments <= 5:
        c_score = 20.0 - (comments - 1) * 1.5
    else:
        c_score = max(6.0, 14.0 - (comments - 5) * 1.0)
    s += c_score
    parts.append(f"评论{c_score:.0f}/20")

    # 4. 新鲜度（25 分）：1~30 天甜蜜区，越老越低
    if days_active is None:
        f_score = 10.0
    elif days_active <= 30:
        f_score = 25.0 - (days_active - 1) * 0.3
    else:
        f_score = max(5.0, 16.0 - (days_active - 30) * 0.15)
    s += f_score
    parts.append(f"新鲜度{f_score:.0f}/25")

    return round(min(s, 100.0)), parts


def main():
    ap = argparse.ArgumentParser(description="筛选并打分可认领的 Issue（v3）")
    ap.add_argument("repo", help="owner/repo 或 GitHub URL")
    ap.add_argument("--days", type=int, default=60, help="近 N 天内有活动，默认 60")
    ap.add_argument("--labels", default="", help="自定义标签列表（逗号分隔，覆盖默认）")
    ap.add_argument("--include-bugs", action="store_true", help="纳入 bug/enhancement 标签（默认只找新手友好标签）")
    ap.add_argument("--beginner-only", action="store_true", help="只保留新手专属标签（含 first-timers-only / beginner friendly）")
    ap.add_argument("--limit", type=int, default=15, help="最多返回条数，默认 15")
    ap.add_argument("--min-score", type=int, default=0, help="只保留打分 >= 该值的 Issue，默认 0")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    owner, repo = gh.parse_repo(args.repo)
    if not owner:
        sys.exit(f"无法解析仓库: {args.repo}")

    if args.labels:
        labels = [x.strip() for x in args.labels.split(",") if x.strip()]
    elif args.beginner_only:
        labels = BEGINNER_ONLY_LABELS
    elif args.include_bugs:
        labels = FULL_LABELS
    else:
        labels = DEFAULT_LABELS

    since = gh_days_ago(args.days)

    # 1) 按标签逐标签搜索（GitHub 搜索不支持 label OR 语义），按 issue 号去重
    seen = {}
    for label in labels:
        q = f"repo:{owner}/{repo} type:issue state:open no:assignee updated:>={since} label:" + json.dumps(label)
        data = gh.get("/search/issues?q=" + quote(q) + "&sort=updated&order=desc&per_page=30", search=True)
        if "_error" in data:
            print(f"[警告] 标签 '{label}' 搜索失败: {data['_error']}，跳过该标签")
            continue
        for it in data.get("items", []):
            seen[it["number"]] = it

    if not seen:
        sys.exit("没有符合条件的 Issue。可尝试 --days 放宽时间，或 --include-bugs / 自定义 --labels。")

    # 2) 撞车检测：一次拉取仓库全部 open PR，提取 PR 文本中引用的 issue 号
    pr_refs = set()
    pr_data = gh.get(f"/search/issues?q=repo:{owner}/{repo}+type:pr+state:open&per_page=100", search=True)
    if "_error" not in pr_data:
        for pr in pr_data.get("items", []):
            text = f"{pr.get('title') or ''} {pr.get('body') or ''}"
            for m in re.finditer(r"(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s*[#:]?\s*(\d+)", text, re.I):
                pr_refs.add(int(m.group(1)))
            for m in re.finditer(r"#(\d+)", text):
                pr_refs.add(int(m.group(1)))

    rows = []
    for num, it in sorted(seen.items(), key=lambda x: -_updated_ts(x[1])):
        if num in pr_refs:
            continue  # 已有人提交 PR 引用该 issue，剔除
        days = gh.days_ago(it.get("updated_at"))
        score, parts = score_issue(it, days)
        if score < args.min_score:
            continue
        rows.append((score, parts, it, days))
        if len(rows) >= args.limit:
            break

    if not rows:
        sys.exit("筛选后没有符合条件的 Issue（可能全部被 open PR 占用，或低于 --min-score）。")

    rows.sort(key=lambda x: -x[0])

    if args.json:
        out = [{
            "number": it["number"], "title": it["title"], "score": score,
            "score_breakdown": parts, "labels": [l["name"] for l in it.get("labels", [])],
            "comments": it.get("comments", 0), "active_days_ago": days,
            "url": it["html_url"], "body": (it.get("body") or "")[:500],
        } for score, parts, it, days in rows]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"仓库: {owner}/{repo}  条件: open / 无assignee / 近{args.days}天活跃 / 标签 {labels}")
    print(f"撞车检测: 已剔除 {len([1 for n in seen if n in pr_refs])} 个被 open PR 引用的 Issue\n")
    for score, parts, it, days in rows:
        lbs = ",".join(l["name"] for l in it.get("labels", []))
        act = f"{days}天前" if days is not None else "未知"
        print(f"[{score:>3}/100] #{it['number']}  {it['title'][:64]}")
        print(f"   标签: {lbs or '-'} | {act}活跃 | 评论 {it.get('comments', 0)} | {it['html_url']}")
        print(f"   打分: {', '.join(parts)}\n")

    print("下一步: 逐条阅读正文与评论，排除评论中声称认领的条目（认领短语如："
          + " / ".join(CLAIM_PHRASES) + "），")
    print("再补充 所需技能 / 预估工作量 / 推荐理由 三列，输出候选表格。")


def gh_days_ago(days):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def quote(s):
    import urllib.parse
    return urllib.parse.quote(s)


def _updated_ts(it):
    try:
        from datetime import datetime
        return datetime.fromisoformat(it["updated_at"].replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa: BLE001
        return 0


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""GitHub 可认领 Issue 筛选与打分（v3.3，零第三方依赖，基于共享 github_api 模块）。

按《开源手册》Route B 的筛选条件自动过滤，并做启发式打分排序：
- 标签：默认仅 good first issue / help wanted（新手友好，避免 bug/enhancement 洪泛）
- 状态 open、近 N 天内有活动、无 assignee
- 标签零命中时自动 fallback 到全量 open issue 列表（很多 roadmap/feature issue 不打标签）
- 撞车检测：自动拉取该仓库全部 open PR，对每个 issue 计算 Collision Risk（LOW/MEDIUM/HIGH）
- 启发式打分（0~100）：清晰度 + 标签权重 + 评论甜蜜区 + 新鲜度 + milestone/roadmap 加成
- Why this issue?：每个 Top Issue 输出可解释的决策理由清单（✓/⚠）

用法:
    python find_issues.py owner/repo
    python find_issues.py owner/repo --days 60 --limit 15
    python find_issues.py owner/repo --include-bugs          # 显式纳入 bug/enhancement
    python find_issues.py owner/repo --json                  # JSON 输出
    python find_issues.py owner/repo --min-score 60          # 只保留打分 >=60 的
    python find_issues.py owner/repo --no-fallback           # 禁用全量 fallback（严格标签模式）
    python find_issues.py owner/repo --show-collision        # 显示被隐藏的高碰撞风险 issue

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

# 认领声明短语（供 deep collision 检查时参考）
CLAIM_PHRASES = ["i'll take this", "i will take this", "i'm working on this",
                 "i am working on this", "on it", "assign me", "claim"]


def score_issue(it, days_active):
    """启发式打分 0~100（可解释、权重透明）。返回 (score, parts_dict)。"""
    body = it.get("body") or ""
    labels = {l["name"].lower() for l in it.get("labels", [])}
    comments = it.get("comments", 0)

    s = 0.0
    parts = {}

    # 1. 清晰度（30 分）：描述长度 + 代码块 + 复现/验收关键词
    clarity = 0.0
    clarity += min(len(body.strip()) / 200.0, 1.0) * 12.0
    has_code_block = "```" in body
    if has_code_block:
        clarity += 8.0
    has_repro = bool(re.search(r"(reproduc|steps to|expected behavior|acceptance criteri|example)", body, re.I))
    if has_repro:
        clarity += 10.0
    clarity = min(clarity, 30.0)
    s += clarity
    parts["clarity"] = {"score": round(clarity), "max": 30, "has_code": has_code_block, "has_repro": has_repro}

    # 2. 标签权重（15 分）
    label_score = 0.0
    label_kind = "none"
    if "good first issue" in labels:
        label_score = 15.0
        label_kind = "good first issue"
    elif "first-timers-only" in labels or "beginner friendly" in labels:
        label_score = 13.0
        label_kind = "beginner friendly"
    elif "help wanted" in labels:
        label_score = 10.0
        label_kind = "help wanted"
    elif "documentation" in labels:
        label_score = 12.0
        label_kind = "documentation"
    elif "bug" in labels:
        label_score = 7.0
        label_kind = "bug"
    elif "enhancement" in labels:
        label_score = 5.0
        label_kind = "enhancement"
    s += label_score
    parts["label"] = {"score": round(label_score), "max": 15, "kind": label_kind}

    # 3. 评论甜蜜区（15 分）：1~5 条最佳，过多说明争议大/复杂度高
    if comments <= 0:
        c_score = 6.0
    elif comments <= 5:
        c_score = 15.0 - (comments - 1) * 1.2
    else:
        c_score = max(4.0, 10.0 - (comments - 5) * 0.8)
    s += c_score
    parts["comments"] = {"score": round(c_score), "max": 15, "count": comments}

    # 4. 新鲜度（20 分）：1~30 天甜蜜区，越老越低
    if days_active is None:
        f_score = 8.0
    elif days_active <= 30:
        f_score = 20.0 - (days_active - 1) * 0.25
    else:
        f_score = max(4.0, 13.0 - (days_active - 30) * 0.12)
    s += f_score
    parts["freshness"] = {"score": round(f_score), "max": 20, "days": days_active}

    # 5. Milestone / roadmap 加成（20 分）
    milestone = it.get("milestone")
    milestone_title = None
    if milestone:
        milestone_title = milestone.get("title")
        m_score = 15.0
        due = milestone.get("due_on")
        if due:
            try:
                from datetime import datetime, timezone
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                days_until = (due_dt - datetime.now(timezone.utc)).days
                if 0 <= days_until <= 30:
                    m_score = 20.0
                elif days_until < 0:
                    m_score = 12.0
            except Exception:
                pass
        s += m_score
        parts["milestone"] = {"score": round(m_score), "max": 20, "title": milestone_title}
    else:
        parts["milestone"] = {"score": 0, "max": 20, "title": None}

    return round(min(s, 100.0)), parts


def compute_collision_risk(it, pr_refs_map):
    """计算 issue 的碰撞风险等级。返回 (risk, reasons, recommendation)。

    risk: HIGH / MEDIUM / LOW
    - HIGH: 被 open PR 引用，或有 assignee
    - MEDIUM: 评论数较多（>=8），可能有人在讨论或认领
    - LOW: 无明显冲突信号
    """
    reasons = []
    num = it["number"]

    # 被 open PR 引用
    referencing_prs = pr_refs_map.get(num, [])
    if referencing_prs:
        for pr in referencing_prs:
            reasons.append(f"Open PR #{pr['number']} references this issue ({pr['user']})")
        return "HIGH", reasons, "DO NOT CLAIM — someone is already working on it"

    # 有 assignee
    if it.get("assignee"):
        assignee = it["assignee"]["login"]
        reasons.append(f"Already assigned to @{assignee}")
        return "HIGH", reasons, "DO NOT CLAIM — already assigned"

    # 评论数较多
    comments = it.get("comments", 0)
    if comments >= 8:
        reasons.append(f"High comment activity ({comments} comments) — possible ongoing discussion or claim")
        return "MEDIUM", reasons, "Check comments before claiming"

    if comments >= 3:
        reasons.append(f"Moderate discussion ({comments} comments)")
        return "LOW", reasons, "Safe to claim after reading comments"

    return "LOW", ["No open PR, no assignee, low comment activity"], "Safe to claim"


def generate_why(it, parts, collision_risk, days_active):
    """生成 Why this issue? 决策理由清单。返回 (checks, warnings)。"""
    checks = []
    warnings = []

    # 清晰度
    clarity = parts["clarity"]
    if clarity["score"] >= 20:
        if clarity["has_repro"] and clarity["has_code"]:
            checks.append("Clear description with reproduction steps and code example")
        elif clarity["has_repro"]:
            checks.append("Clear description with reproduction steps")
        else:
            checks.append("Detailed description")
    else:
        warnings.append("Description may be sparse — read issue body before starting")

    # 标签
    label = parts["label"]
    if label["kind"] == "good first issue":
        checks.append("Tagged 'good first issue' — maintainer signals beginner-friendly")
    elif label["kind"] == "beginner friendly":
        checks.append("Tagged beginner-friendly")
    elif label["kind"] == "help wanted":
        checks.append("Tagged 'help wanted' — maintainer explicitly asking for help")
    elif label["kind"] == "none":
        warnings.append("No beginner-friendly label (may be a roadmap issue requiring more context)")

    # Milestone
    milestone = parts["milestone"]
    if milestone["title"]:
        checks.append(f"On project roadmap (milestone: {milestone['title']})")

    # 新鲜度
    freshness = parts["freshness"]
    if days_active is not None and days_active <= 7:
        checks.append(f"Recently active ({days_active} day{'s' if days_active != 1 else ''} ago) — maintainer is engaged")
    elif days_active is not None and days_active <= 30:
        checks.append(f"Active within last {days_active} days")

    # 碰撞风险
    if collision_risk == "LOW":
        checks.append("No active collision — no open PR, no assignee")
    elif collision_risk == "MEDIUM":
        warnings.append("Medium collision risk — check comments before claiming")

    # 评论
    comments = parts["comments"]["count"]
    if 1 <= comments <= 5:
        checks.append(f"Healthy discussion ({comments} comments) — maintainer responsive")
    elif comments == 0:
        warnings.append("No comments yet — be the first to engage")

    return checks, warnings


def main():
    ap = argparse.ArgumentParser(description="筛选并打分可认领的 Issue（v3.3）")
    ap.add_argument("repo", help="owner/repo 或 GitHub URL")
    ap.add_argument("--days", type=int, default=60, help="近 N 天内有活动，默认 60")
    ap.add_argument("--labels", default="", help="自定义标签列表（逗号分隔，覆盖默认）")
    ap.add_argument("--include-bugs", action="store_true", help="纳入 bug/enhancement 标签")
    ap.add_argument("--beginner-only", action="store_true", help="只保留新手专属标签")
    ap.add_argument("--limit", type=int, default=15, help="最多返回条数，默认 15")
    ap.add_argument("--min-score", type=int, default=0, help="只保留打分 >= 该值的 Issue")
    ap.add_argument("--no-fallback", action="store_true", help="禁用全量 open issue fallback")
    ap.add_argument("--show-collision", action="store_true", help="显示被隐藏的高碰撞风险 issue")
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

    # 1) 按标签逐标签搜索
    seen = {}
    for label in labels:
        q = f"repo:{owner}/{repo} type:issue state:open no:assignee updated:>={since} label:" + json.dumps(label)
        data = gh.get("/search/issues?q=" + quote(q) + "&sort=updated&order=desc&per_page=30", search=True)
        if "_error" in data:
            print(f"[警告] 标签 '{label}' 搜索失败: {data['_error']}，跳过该标签")
            continue
        for it in data.get("items", []):
            seen[it["number"]] = it

    # 1b) Fallback：标签零命中时自动拉全量
    if not seen and not args.no_fallback:
        print(f"[信息] 标签搜索零命中，自动 fallback 到全量 open issue 列表...")
        page = 1
        while page <= 3:
            all_data = gh.get(f"/repos/{owner}/{repo}/issues?state=open&per_page=100&page={page}")
            if "_error" in all_data:
                print(f"[警告] 全量 issue 拉取失败: {all_data['_error']}")
                break
            if not isinstance(all_data, list) or not all_data:
                break
            for it in all_data:
                if "pull_request" in it:
                    continue
                if it.get("assignee"):
                    continue
                seen[it["number"]] = it
            if len(all_data) < 100:
                break
            page += 1

    if not seen:
        sys.exit("没有符合条件的 Issue。可尝试 --days 放宽时间，或 --include-bugs / 自定义 --labels。")

    # 2) 撞车检测：拉取全部 open PR，构建 issue -> [PRs] 映射
    pr_refs_map = {}
    pr_data = gh.get(f"/search/issues?q=repo:{owner}/{repo}+type:pr+state:open&per_page=100", search=True)
    if "_error" not in pr_data:
        for pr in pr_data.get("items", []):
            text = f"{pr.get('title') or ''} {pr.get('body') or ''}"
            pr_info = {"number": pr["number"], "user": pr["user"]["login"], "title": pr.get("title", "")}
            refs = set()
            for m in re.finditer(r"(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s*[#:]?\s*(\d+)", text, re.I):
                refs.add(int(m.group(1)))
            for m in re.finditer(r"#(\d+)", text):
                refs.add(int(m.group(1)))
            for ref_num in refs:
                if ref_num not in pr_refs_map:
                    pr_refs_map[ref_num] = []
                pr_refs_map[ref_num].append(pr_info)

    # 3) 打分 + 碰撞风险 + 分类
    safe_rows = []      # LOW/MEDIUM 风险，正常展示
    hidden_rows = []    # HIGH 风险，默认隐藏

    for num, it in sorted(seen.items(), key=lambda x: -_updated_ts(x[1])):
        days = gh.days_ago(it.get("updated_at"))
        score, parts = score_issue(it, days)
        if score < args.min_score:
            continue
        risk, reasons, recommendation = compute_collision_risk(it, pr_refs_map)
        checks, warnings = generate_why(it, parts, risk, days)

        row = {
            "score": score, "parts": parts, "it": it, "days": days,
            "collision_risk": risk, "collision_reasons": reasons,
            "collision_recommendation": recommendation,
            "why_checks": checks, "why_warnings": warnings,
        }

        if risk == "HIGH":
            hidden_rows.append(row)
        else:
            safe_rows.append(row)

    safe_rows.sort(key=lambda x: -x["score"])
    safe_rows = safe_rows[:args.limit]

    if not safe_rows and not hidden_rows:
        sys.exit("筛选后没有符合条件的 Issue。")

    # 4) 输出
    if args.json:
        out = []
        for r in safe_rows:
            it = r["it"]
            out.append({
                "number": it["number"], "title": it["title"], "score": r["score"],
                "score_breakdown": {k: v["score"] for k, v in r["parts"].items()},
                "labels": [l["name"] for l in it.get("labels", [])],
                "comments": it.get("comments", 0), "active_days_ago": r["days"],
                "milestone": r["parts"]["milestone"]["title"],
                "collision_risk": r["collision_risk"],
                "collision_reasons": r["collision_reasons"],
                "why_checks": r["why_checks"], "why_warnings": r["why_warnings"],
                "url": it["html_url"],
            })
        if args.show_collision:
            for r in hidden_rows:
                it = r["it"]
                out.append({
                    "number": it["number"], "title": it["title"], "score": r["score"],
                    "collision_risk": r["collision_risk"],
                    "collision_reasons": r["collision_reasons"],
                    "recommendation": r["collision_recommendation"],
                    "url": it["html_url"], "hidden": True,
                })
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    print(f"仓库: {owner}/{repo}  条件: open / 无assignee / 近{args.days}天活跃 / 标签 {labels}")
    print(f"碰撞检测: 扫描 {len(pr_refs_map)} 个 open PR 引用，隐藏 {len(hidden_rows)} 个高碰撞风险 Issue\n")

    risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}

    for r in safe_rows:
        it = r["it"]
        lbs = ",".join(l["name"] for l in it.get("labels", []))
        act = f"{r['days']}天前" if r["days"] is not None else "未知"
        ms = r["parts"]["milestone"]["title"] or "-"
        print(f"[{r['score']:>3}/100] #{it['number']}  {it['title'][:64]}")
        print(f"   标签: {lbs or '-'} | {act}活跃 | 评论 {it.get('comments', 0)} | milestone: {ms} | {it['html_url']}")
        breakdown = ", ".join(f"{k}{v['score']}/{v['max']}" for k, v in r["parts"].items())
        print(f"   打分: {breakdown}")
        print(f"   Collision Risk: {risk_icon[r['collision_risk']]} {r['collision_risk']} — {r['collision_reasons'][0]}")
        print(f"   🎯 Why this issue?")
        for c in r["why_checks"]:
            print(f"     ✓ {c}")
        for w in r["why_warnings"]:
            print(f"     ⚠ {w}")
        print()

    if args.show_collision and hidden_rows:
        print(f"{'='*60}")
        print(f"⚠ 被隐藏的高碰撞风险 Issue（{len(hidden_rows)} 个）")
        print(f"{'='*60}\n")
        for r in hidden_rows:
            it = r["it"]
            print(f"🔴 [HIDDEN] #{it['number']}  {it['title'][:60]}")
            print(f"   Score: {r['score']}/100 | {it['html_url']}")
            print(f"   Collision Risk: HIGH")
            print(f"   Reason:")
            for reason in r["collision_reasons"]:
                print(f"   • {reason}")
            print(f"   Recommendation: {r['collision_recommendation']}")
            print()

    if not args.show_collision and hidden_rows:
        print(f"💡 {len(hidden_rows)} 个高碰撞风险 Issue 已隐藏，加 --show-collision 查看详情")

    print("\n下一步: 对 Top Issue 阅读正文与评论，确认无认领后动手实现。")


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

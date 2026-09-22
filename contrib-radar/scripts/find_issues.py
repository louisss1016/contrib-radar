#!/usr/bin/env python3
"""GitHub 可认领 Issue 筛选与打分（v3.4，零第三方依赖，基于共享 github_api 模块）。

v3.4: Contribution Score 拆分为 Issue Quality + Contribution Feasibility 双维度；
      新增 --stack 技术栈匹配度（Stack Match % + 逐项 ✓/—）。

按《开源手册》Route B 的筛选条件自动过滤，并做启发式打分排序：
- 标签：默认仅 good first issue / help wanted（新手友好，避免 bug/enhancement 洪泛）
- 状态 open、近 N 天内有活动、无 assignee
- 标签零命中时自动 fallback 到全量 open issue 列表（很多 roadmap/feature issue 不打标签）
- 撞车检测：自动拉取该仓库全部 open PR，对每个 issue 计算 Collision Risk（LOW/MEDIUM/HIGH）
- 双维度打分：
    Issue Quality（0~100）：清晰度 + 标签 + 新鲜度 + milestone + 讨论健康度
    Contribution Feasibility（0~100）：撞车风险 + 修改范围 + 新手友好 + 技术栈匹配
    Contribution Score = Quality * 0.5 + Feasibility * 0.5
- Why this issue?：每个 Top Issue 输出可解释的决策理由清单（✓/⚠）

用法:
    python find_issues.py owner/repo
    python find_issues.py owner/repo --days 60 --limit 15
    python find_issues.py owner/repo --include-bugs
    python find_issues.py owner/repo --stack python,langchain,fastapi
    python find_issues.py owner/repo --json
    python find_issues.py owner/repo --min-score 60
    python find_issues.py owner/repo --no-fallback
    python find_issues.py owner/repo --show-collision

进度（v3.7）：抓取 / 撞车检测 / 打分三阶段向 stderr 发射 [CR-PROGRESS]
JSON 事件（管道模式）或 ASCII 进度条（TTY 模式）；--json 的 stdout 契约
不受影响。

可选: 设置环境变量 GITHUB_TOKEN 以提高 API 速率限制（强烈建议）。
"""

import argparse
import json
import re
import sys

import github_api as gh
import progress as pg

DEFAULT_LABELS = ["good first issue", "help wanted"]
BEGINNER_ONLY_LABELS = ["good first issue", "help wanted", "first-timers-only", "beginner friendly"]
FULL_LABELS = ["good first issue", "help wanted", "bug", "enhancement"]

CLAIM_PHRASES = ["i'll take this", "i will take this", "i'm working on this",
                 "i am working on this", "on it", "assign me", "claim"]


# ─── Issue Quality ───────────────────────────────────────────────

def score_issue_quality(it, days_active):
    """Issue Quality 0~100：问题本身的质量、价值和维护者关注度。"""
    body = it.get("body") or ""
    labels = {l["name"].lower() for l in it.get("labels", [])}
    comments = it.get("comments", 0)

    parts = {}

    # 1. 清晰度（30 分）
    clarity = 0.0
    clarity += min(len(body.strip()) / 200.0, 1.0) * 12.0
    has_code = "```" in body
    if has_code:
        clarity += 8.0
    has_repro = bool(re.search(r"(reproduc|steps to|expected behavior|acceptance criteri|example)", body, re.I))
    if has_repro:
        clarity += 10.0
    clarity = min(clarity, 30.0)
    parts["clarity"] = {"score": round(clarity), "max": 30, "has_code": has_code, "has_repro": has_repro}

    # 2. 标签（15 分）
    label_score = 0.0
    label_kind = "none"
    if "good first issue" in labels:
        label_score = 15.0; label_kind = "good first issue"
    elif "first-timers-only" in labels or "beginner friendly" in labels:
        label_score = 13.0; label_kind = "beginner friendly"
    elif "help wanted" in labels:
        label_score = 10.0; label_kind = "help wanted"
    elif "documentation" in labels:
        label_score = 12.0; label_kind = "documentation"
    elif "bug" in labels:
        label_score = 7.0; label_kind = "bug"
    elif "enhancement" in labels:
        label_score = 5.0; label_kind = "enhancement"
    parts["label"] = {"score": round(label_score), "max": 15, "kind": label_kind}

    # 3. 新鲜度（25 分）
    if days_active is None:
        f_score = 10.0
    elif days_active <= 30:
        f_score = 25.0 - (days_active - 1) * 0.3
    else:
        f_score = max(5.0, 16.0 - (days_active - 30) * 0.15)
    parts["freshness"] = {"score": round(f_score), "max": 25, "days": days_active}

    # 4. Milestone（20 分）
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
        parts["milestone"] = {"score": round(m_score), "max": 20, "title": milestone_title}
    else:
        parts["milestone"] = {"score": 0, "max": 20, "title": None}

    # 5. 讨论健康度（10 分）
    if comments == 0:
        d_score = 5.0
    elif comments <= 5:
        d_score = 10.0 - (comments - 1) * 0.8
    else:
        d_score = max(3.0, 6.0 - (comments - 5) * 0.5)
    parts["discussion"] = {"score": round(d_score), "max": 10, "count": comments}

    total = sum(p["score"] for p in parts.values())
    return round(min(total, 100)), parts


# ─── Contribution Feasibility ────────────────────────────────────

def score_feasibility(it, collision_risk, stack_score, stack_details):
    """Contribution Feasibility 0~100：实现这个贡献的容易程度和风险。"""
    parts = {}
    labels = {l["name"].lower() for l in it.get("labels", [])}
    body = ((it.get("body") or "") + " " + (it.get("title") or "")).lower()

    # 1. 撞车风险（30 分）
    collision_score = {"LOW": 30, "MEDIUM": 15, "HIGH": 0}[collision_risk]
    parts["collision"] = {"score": collision_score, "max": 30, "risk": collision_risk}

    # 2. 修改范围预估（25 分）
    scope_score = 15.0
    scope_reason = "medium — general issue"
    if "documentation" in labels or "docs" in it.get("title", "").lower():
        scope_score = 25.0; scope_reason = "documentation — small change surface"
    elif "bug" in labels or re.search(r"\b(fix|bug|typo)\b", body):
        scope_score = 20.0; scope_reason = "bug fix — likely localized"
    elif re.search(r"(refactor|rewrite|major|breaking|migrat|redesign)", body):
        scope_score = 8.0; scope_reason = "large refactor/rewrite — high complexity"
    elif "enhancement" in labels or re.search(r"\b(feature|add|implement)\b", body):
        scope_score = 15.0; scope_reason = "feature — medium scope"
    parts["scope"] = {"score": round(scope_score), "max": 25, "reason": scope_reason}

    # 3. 新手友好度（25 分）
    beginner_score = 10.0
    beginner_reason = "no beginner signal"
    if "good first issue" in labels:
        beginner_score = 25.0; beginner_reason = "good first issue label"
    elif "first-timers-only" in labels or "beginner friendly" in labels:
        beginner_score = 23.0; beginner_reason = "beginner friendly label"
    elif "help wanted" in labels:
        beginner_score = 18.0; beginner_reason = "help wanted label"
    elif "bug" in labels:
        beginner_score = 12.0; beginner_reason = "bug — may need debugging"
    parts["beginner"] = {"score": round(beginner_score), "max": 25, "reason": beginner_reason}

    # 4. 技术栈匹配（20 分）
    parts["stack"] = {"score": stack_score, "max": 20, "details": stack_details}

    total = sum(p["score"] for p in parts.values())
    return round(min(total, 100)), parts


# ─── Stack Match ─────────────────────────────────────────────────

def compute_stack_match(it, repo_language, user_stack):
    """计算技术栈匹配度。返回 (score 0~20, match_pct, details)。

    details: [{"tech": str, "match": "repo_language"|"issue_mentions"|"no_match"}]
    """
    if not user_stack:
        return 10, 50, [{"tech": "(no --stack provided)", "match": "neutral"}]

    text = ((it.get("title") or "") + " " + (it.get("body") or "")).lower()
    repo_lang = (repo_language or "").lower()

    details = []
    matched = 0
    total_techs = 0
    for tech in user_stack:
        tech_lower = tech.strip().lower()
        if not tech_lower:
            continue
        total_techs += 1
        if tech_lower == repo_lang or (repo_lang and tech_lower in repo_lang):
            details.append({"tech": tech, "match": "repo_language"})
            matched += 1
        elif tech_lower in text:
            details.append({"tech": tech, "match": "issue_mentions"})
            matched += 1
        else:
            details.append({"tech": tech, "match": "no_match"})

    if total_techs == 0:
        return 10, 50, details

    match_pct = round(matched / total_techs * 100)
    score = round(match_pct / 100 * 20)
    return score, match_pct, details


# ─── Collision Risk ──────────────────────────────────────────────

def compute_collision_risk(it, pr_refs_map):
    """计算碰撞风险等级。返回 (risk, reasons, recommendation)。"""
    reasons = []
    num = it["number"]

    referencing_prs = pr_refs_map.get(num, [])
    if referencing_prs:
        for pr in referencing_prs:
            reasons.append(f"Open PR #{pr['number']} references this issue ({pr['user']})")
        return "HIGH", reasons, "DO NOT CLAIM — someone is already working on it"

    if it.get("assignee"):
        assignee = it["assignee"]["login"]
        reasons.append(f"Already assigned to @{assignee}")
        return "HIGH", reasons, "DO NOT CLAIM — already assigned"

    comments = it.get("comments", 0)
    if comments >= 8:
        reasons.append(f"High comment activity ({comments} comments) — possible ongoing discussion or claim")
        return "MEDIUM", reasons, "Check comments before claiming"

    if comments >= 3:
        reasons.append(f"Moderate discussion ({comments} comments)")
        return "LOW", reasons, "Safe to claim after reading comments"

    return "LOW", ["No open PR, no assignee, low comment activity"], "Safe to claim"


# ─── Why this issue? ─────────────────────────────────────────────

def generate_why(quality_parts, feasibility_parts, collision_risk, days_active, stack_pct, stack_details):
    """生成决策理由清单。返回 (checks, warnings)。"""
    checks = []
    warnings = []

    # 清晰度
    clarity = quality_parts["clarity"]
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
    label = quality_parts["label"]
    if label["kind"] == "good first issue":
        checks.append("Tagged 'good first issue' — maintainer signals beginner-friendly")
    elif label["kind"] == "beginner friendly":
        checks.append("Tagged beginner-friendly")
    elif label["kind"] == "help wanted":
        checks.append("Tagged 'help wanted' — maintainer explicitly asking for help")
    elif label["kind"] == "none":
        warnings.append("No beginner-friendly label (may be a roadmap issue requiring more context)")

    # Milestone
    milestone = quality_parts["milestone"]
    if milestone["title"]:
        checks.append(f"On project roadmap (milestone: {milestone['title']})")

    # 新鲜度
    if days_active is not None and days_active <= 7:
        checks.append(f"Recently active ({days_active} day{'s' if days_active != 1 else ''} ago) — maintainer is engaged")
    elif days_active is not None and days_active <= 30:
        checks.append(f"Active within last {days_active} days")

    # 碰撞风险
    if collision_risk == "LOW":
        checks.append("No active collision — no open PR, no assignee")
    elif collision_risk == "MEDIUM":
        warnings.append("Medium collision risk — check comments before claiming")

    # 修改范围
    scope = feasibility_parts["scope"]
    if scope["score"] >= 20:
        checks.append(f"Small change surface — {scope['reason']}")
    elif scope["score"] <= 10:
        warnings.append(f"Large change surface — {scope['reason']}")

    # 新手友好
    beginner = feasibility_parts["beginner"]
    if beginner["score"] >= 18:
        checks.append(f"Beginner-friendly — {beginner['reason']}")

    # 技术栈匹配
    if stack_pct >= 75:
        matched_techs = [d["tech"] for d in stack_details if d["match"] != "no_match"]
        checks.append(f"Strong stack match ({stack_pct}%): {', '.join(matched_techs)}")
    elif stack_pct < 50 and stack_details and stack_details[0]["match"] != "neutral":
        unmatched = [d["tech"] for d in stack_details if d["match"] == "no_match"]
        if unmatched:
            warnings.append(f"Stack mismatch — not found: {', '.join(unmatched)}")

    # 讨论
    discussion = quality_parts["discussion"]
    if 1 <= discussion["count"] <= 5:
        checks.append(f"Healthy discussion ({discussion['count']} comments) — maintainer responsive")
    elif discussion["count"] == 0:
        warnings.append("No comments yet — be the first to engage")

    return checks, warnings


# ─── Main ────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="筛选并打分可认领的 Issue（v3.4，双维度打分 + 技术栈匹配）")
    ap.add_argument("repo", help="owner/repo 或 GitHub URL")
    ap.add_argument("--days", type=int, default=60, help="近 N 天内有活动，默认 60")
    ap.add_argument("--labels", default="", help="自定义标签列表（逗号分隔，覆盖默认）")
    ap.add_argument("--include-bugs", action="store_true", help="纳入 bug/enhancement 标签")
    ap.add_argument("--beginner-only", action="store_true", help="只保留新手专属标签")
    ap.add_argument("--limit", type=int, default=15, help="最多返回条数，默认 15")
    ap.add_argument("--min-score", type=int, default=0, help="只保留 Contribution Score >= 该值的 Issue")
    ap.add_argument("--no-fallback", action="store_true", help="禁用全量 open issue fallback")
    ap.add_argument("--show-collision", action="store_true", help="显示被隐藏的高碰撞风险 issue")
    ap.add_argument("--stack", default="", help="你的技术栈（逗号分隔），如 python,langchain,fastapi")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiet", action="store_true", help="关闭 stderr 进度输出")
    args = ap.parse_args()
    if args.quiet:
        pg.set_quiet(True)  # --quiet 覆盖 CR_QUIET 默认值

    owner, repo = gh.parse_repo(args.repo)
    if not owner:
        sys.exit(f"无法解析仓库: {args.repo}")

    user_stack = [s.strip() for s in args.stack.split(",") if s.strip()] if args.stack else []

    if args.labels:
        labels = [x.strip() for x in args.labels.split(",") if x.strip()]
    elif args.beginner_only:
        labels = BEGINNER_ONLY_LABELS
    elif args.include_bugs:
        labels = FULL_LABELS
    else:
        labels = DEFAULT_LABELS

    since = gh_days_ago(args.days)

    # 获取仓库主语言（用于技术栈匹配，1 次 core API 调用）
    repo_language = None
    repo_info = gh.get(f"/repos/{owner}/{repo}")
    if "_error" not in repo_info:
        repo_language = repo_info.get("language")

    # 1) 按标签逐标签搜索
    seen = {}
    pg.phase("issue-fetch", total=len(labels))
    for li, label in enumerate(labels, 1):
        pg.item(li, len(labels), label, "running", phase_name="issue-fetch")
        q = f"repo:{owner}/{repo} type:issue state:open no:assignee updated:>={since} label:" + json.dumps(label)
        data = gh.get("/search/issues?q=" + quote(q) + "&sort=updated&order=desc&per_page=30", search=True)
        if "_error" in data:
            pg.item(li, len(labels), label, "error", detail=str(data["_error"]), phase_name="issue-fetch")
            print(f"[警告] 标签 '{label}' 搜索失败: {data['_error']}，跳过该标签")
            continue
        for it in data.get("items", []):
            seen[it["number"]] = it
        pg.item(li, len(labels), label, "ok", detail=f"{len(data.get('items', []))} hits", phase_name="issue-fetch")
    pg.item_end()

    # 1b) Fallback
    if not seen and not args.no_fallback:
        print(f"[信息] 标签搜索零命中，自动 fallback 到全量 open issue 列表...")
        pg.phase("issue-fallback", total=3)
        page = 1
        while page <= 3:
            pg.item(page, 3, f"page {page}", "running", phase_name="issue-fallback")
            all_data = gh.get(f"/repos/{owner}/{repo}/issues?state=open&per_page=100&page={page}")
            if "_error" in all_data:
                pg.item(page, 3, f"page {page}", "error", detail=str(all_data["_error"]), phase_name="issue-fallback")
                print(f"[警告] 全量 issue 拉取失败: {all_data['_error']}")
                break
            if not isinstance(all_data, list) or not all_data:
                pg.item(page, 3, f"page {page}", "ok", detail="empty", phase_name="issue-fallback")
                break
            for it in all_data:
                if "pull_request" in it:
                    continue
                if it.get("assignee"):
                    continue
                seen[it["number"]] = it
            pg.item(page, 3, f"page {page}", "ok", detail=f"{len(seen)} candidates", phase_name="issue-fallback")
            if len(all_data) < 100:
                break
            page += 1
        pg.item_end()
        pg.phase("issue-fallback", "done", detail=f"{len(seen)} issues after fallback")

    if not seen:
        sys.exit("没有符合条件的 Issue。可尝试 --days 放宽时间，或 --include-bugs / 自定义 --labels。")

    # 2) 撞车检测
    pg.phase("collision-detect")
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
    else:
        pg.phase("collision-detect", "error", detail=str(pr_data["_error"]))
    pg.phase("collision-detect", "done", detail=f"{len(pr_refs_map)} PR refs scanned")

    # 3) 双维度打分
    safe_rows = []
    hidden_rows = []

    total_issues = len(seen)
    pg.phase("issue-score", total=total_issues)
    for si, (num, it) in enumerate(sorted(seen.items(), key=lambda x: -_updated_ts(x[1])), 1):
        pg.item(si, total_issues, f"#{num}", "running", phase_name="issue-score")
        days = gh.days_ago(it.get("updated_at"))
        quality, quality_parts = score_issue_quality(it, days)
        risk, reasons, recommendation = compute_collision_risk(it, pr_refs_map)
        stack_score, stack_pct, stack_details = compute_stack_match(it, repo_language, user_stack)
        feasibility, feasibility_parts = score_feasibility(it, risk, stack_score, stack_details)
        contribution_score = round(quality * 0.5 + feasibility * 0.5)

        if contribution_score < args.min_score:
            pg.item(si, total_issues, f"#{num}", "skip", detail=f"score {contribution_score} < min", phase_name="issue-score")
            continue

        checks, warnings = generate_why(quality_parts, feasibility_parts, risk, days, stack_pct, stack_details)

        row = {
            "score": contribution_score, "quality": quality, "feasibility": feasibility,
            "quality_parts": quality_parts, "feasibility_parts": feasibility_parts,
            "it": it, "days": days,
            "collision_risk": risk, "collision_reasons": reasons,
            "collision_recommendation": recommendation,
            "stack_pct": stack_pct, "stack_details": stack_details,
            "why_checks": checks, "why_warnings": warnings,
        }

        if risk == "HIGH":
            hidden_rows.append(row)
            pg.item(si, total_issues, f"#{num}", "warn", detail=f"score {contribution_score}, collision HIGH (hidden)", phase_name="issue-score")
        else:
            safe_rows.append(row)
            pg.item(si, total_issues, f"#{num}", "ok", detail=f"score {contribution_score}, collision {risk}", phase_name="issue-score")

    pg.item_end()
    pg.phase("issue-score", "done",
             detail=f"{len(safe_rows)} safe, {len(hidden_rows)} hidden (HIGH collision)")

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
                "number": it["number"], "title": it["title"],
                "contribution_score": r["score"],
                "issue_quality": r["quality"], "contribution_feasibility": r["feasibility"],
                "quality_breakdown": {k: v["score"] for k, v in r["quality_parts"].items()},
                "feasibility_breakdown": {k: v["score"] for k, v in r["feasibility_parts"].items()},
                "labels": [l["name"] for l in it.get("labels", [])],
                "comments": it.get("comments", 0), "active_days_ago": r["days"],
                "milestone": r["quality_parts"]["milestone"]["title"],
                "collision_risk": r["collision_risk"],
                "stack_match_pct": r["stack_pct"],
                "stack_details": r["stack_details"],
                "why_checks": r["why_checks"], "why_warnings": r["why_warnings"],
                "url": it["html_url"],
            })
        if args.show_collision:
            for r in hidden_rows:
                it = r["it"]
                out.append({
                    "number": it["number"], "title": it["title"],
                    "contribution_score": r["score"],
                    "collision_risk": r["collision_risk"],
                    "collision_reasons": r["collision_reasons"],
                    "recommendation": r["collision_recommendation"],
                    "url": it["html_url"], "hidden": True,
                })
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    stack_info = f" | 技术栈: {args.stack}" if user_stack else ""
    print(f"仓库: {owner}/{repo}  条件: open / 无assignee / 近{args.days}天活跃 / 标签 {labels}{stack_info}")
    print(f"碰撞检测: 扫描 {len(pr_refs_map)} 个 open PR 引用，隐藏 {len(hidden_rows)} 个高碰撞风险 Issue\n")

    risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}

    for r in safe_rows:
        it = r["it"]
        lbs = ",".join(l["name"] for l in it.get("labels", []))
        act = f"{r['days']}天前" if r["days"] is not None else "未知"
        ms = r["quality_parts"]["milestone"]["title"] or "-"

        print(f"[{r['score']:>3}/100] #{it['number']}  {it['title'][:64]}")
        print(f"   标签: {lbs or '-'} | {act}活跃 | 评论 {it.get('comments', 0)} | milestone: {ms} | {it['html_url']}")

        # 双维度打分
        qb = ", ".join(f"{k}{v['score']}/{v['max']}" for k, v in r["quality_parts"].items())
        fb = ", ".join(f"{k}{v['score']}/{v['max']}" for k, v in r["feasibility_parts"].items())
        print(f"   Issue Quality:        {r['quality']:>3}/100  ({qb})")
        print(f"   Feasibility:          {r['feasibility']:>3}/100  ({fb})")

        # 技术栈匹配
        if user_stack:
            bar_len = 20
            filled = round(r["stack_pct"] / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            stack_str = " | ".join(
                f"{d['tech']} {'✓' if d['match'] != 'no_match' else '—'}"
                for d in r["stack_details"]
            )
            print(f"   Stack Match:          {bar}  {r['stack_pct']}%  ({stack_str})")

        # 碰撞风险
        print(f"   Collision Risk:       {risk_icon[r['collision_risk']]} {r['collision_risk']} — {r['collision_reasons'][0]}")

        # Why this issue?
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
    gh.ensure_utf8_stdio()
    main()

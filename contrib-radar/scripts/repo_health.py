#!/usr/bin/env python3
"""GitHub 仓库健康度体检（v3.1，零第三方依赖，基于共享 github_api 模块）。

用法:
    python repo_health.py owner/repo
    python repo_health.py https://github.com/owner/repo
    python repo_health.py owner/repo1 owner/repo2 ...   # 批量体检候选项目
    python repo_health.py owner/repo --json             # JSON 输出（供自动化复用）
    python repo_health.py owner/repo1 owner/repo2 --quiet  # 关闭 stderr 进度事件

进度（v3.7）：批量体检期间向 stderr 发射 [CR-PROGRESS] JSON 事件
（管道模式）或 ASCII 进度条（TTY 模式）；--json 的 stdout 契约不受影响。

可选: 设置环境变量 GITHUB_TOKEN 以提高 API 速率限制
（未认证时 Search 限 10 次/分，本脚本由共享模块自动打点；core 端点不打点）。

输出: 各指标红绿灯（对照《开源手册》健康标准）+ 汇总评分。
单项指标查询失败时降级为 ⚪ 未知，不影响其余指标输出。

v3.1 相对 v3 的变化:
1. AI 政策检查去误报："llm" 单独命中不再触发（AI 项目的 CONTRIBUTING 里自然会写 LLM），
   必须与禁止性动词组合才视为限制声明。
"""

import argparse
import json
import sys

import github_api as gh
import progress as pg

# AI 生成代码政策检查——禁止性短语（必须包含动词+对象，避免误报 AI 项目的正常提及）
AI_POLICY_BLOCKED_PHRASES = [
    "do not use ai", "no ai generated", "no ai-assisted", "prohibit ai",
    "ai-generated contributions are not", "not accept ai generated",
    "ban ai generated", "forbid ai", "ai generated code is not allowed",
    "do not use copilot", "no copilot", "禁止使用 ai", "不接受 ai 生成",
]
# 提及性关键词（仅触发 mention，需人工确认口径）
AI_POLICY_MENTION_KEYWORDS = [
    "ai-generated", "ai generated code", "ai-assisted", "copilot",
    "chatgpt", "do not use ai", "no ai", "prohibit ai",
]

# 常见 CONTRIBUTING 路径（按出现顺序探测）
CONTRIBUTING_PATHS = [
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "CONTRIBUTING",
    "docs/CONTRIBUTING.md",
]


def light(ok, warn):
    return "🟢" if ok else ("🟡" if warn else "🔴")


def ai_policy_check(owner, repo):
    """检查仓库是否声明了 AI 生成代码限制。

    返回 (状态, 说明)：状态为 'blocked'（明确禁止）/ 'mention'（有相关表述）/
    'ok'（无相关表述）/ 'unknown'（无法读取贡献指南）。

    v3.1 改进：避免把 AI 项目的正常 LLM 提及误判为限制声明。
    只有命中禁止性短语才标 blocked；普通提及（如"我们使用 AI 辅助测试"）标 mention。
    """
    for path in CONTRIBUTING_PATHS:
        content = gh.fetch_file_content(owner, repo, path)
        if content is None:
            continue
        content_lower = content.lower()

        # 先检查明确禁止性短语
        blocked_hits = [kw for kw in AI_POLICY_BLOCKED_PHRASES if kw in content_lower]
        if blocked_hits:
            return "blocked", f"命中 {path}: {blocked_hits[:3]}（明确禁止 AI 生成代码）"

        # 再检查提及性关键词（需人工确认口径）
        mention_hits = [kw for kw in AI_POLICY_MENTION_KEYWORDS if kw in content_lower]
        if mention_hits:
            return "mention", f"命中 {path}: {mention_hits[:3]}（有 AI 相关表述，需人工确认口径）"

        return "ok", f"{path} 无 AI 限制表述"
    return "unknown", "未找到贡献指南，无法判断"


def check_repo(owner, repo):
    """体检单个仓库，返回 (输出行列表, score, total, extra)。任何单项失败不中断。"""
    out, score, total = [], 0, 12

    info = gh.get(f"/repos/{owner}/{repo}")
    if "_error" in info:
        return [f"仓库查询失败: {info['_error']}"], 0, total, {}

    # 搜索类指标：逐项拉取，逐项降级
    since = gh_days_ago_since(30)
    closed = gh.get(f"/search/issues?q=repo:{owner}/{repo}+type:issue+state:closed&per_page=1", search=True)
    open_i = gh.get(f"/search/issues?q=repo:{owner}/{repo}+type:issue+state:open&per_page=1", search=True)
    merged = gh.get(f"/search/issues?q=repo:{owner}/{repo}+type:pr+is:merged+merged:>={since}&per_page=1", search=True)
    rel = gh.get(f"/repos/{owner}/{repo}/releases/latest")

    # 贡献指南存在性（沿用 v2 语义：可降级，不扣分）
    has_contrib = False
    for path in CONTRIBUTING_PATHS:
        if "_error" not in gh.get(f"/repos/{owner}/{repo}/contents/{path}"):
            has_contrib = True
            break

    # AI 政策检查（独立于健康度计分，仅提示）
    ai_state, ai_note = ai_policy_check(owner, repo)

    push_d = gh.days_ago(info.get("pushed_at"))
    rel_d = None if "_error" in rel else gh.days_ago(rel.get("published_at"))

    checks = []
    checks.append(("最近提交", f"{push_d} 天前" if push_d is not None else "未知",
                   light(push_d is not None and push_d <= 30, push_d is not None and push_d <= 90)))

    # 逐项降级：closed / open / merged 各自独立
    if "_error" not in closed and "_error" not in open_i:
        closed_n, open_n = closed.get("total_count", 0), open_i.get("total_count", 0)
        ratio = closed_n / open_n if open_n else float("inf")
        checks.append(("Issue 关闭率 (closed/open)", f"{closed_n}/{open_n} = {ratio:.2f}" if open_n else f"{closed_n}/0",
                       light(ratio > 1, ratio >= 0.5)))
    else:
        total -= 2
        checks.append(("Issue 关闭率", "查询失败（可设 GITHUB_TOKEN 重试）", "⚪"))

    if "_error" not in merged:
        merged_30d = merged.get("total_count", 0)
        checks.append(("近 30 天合并 PR 数", str(merged_30d), light(merged_30d >= 5, merged_30d >= 1)))
    else:
        total -= 2
        checks.append(("近 30 天合并 PR 数", "查询失败", "⚪"))

    checks.append(("最近 Release", f"{rel_d} 天前" if rel_d is not None else "无 Release",
                   light(rel_d is not None and rel_d <= 90, rel_d is not None and rel_d <= 365)))
    checks.append(("贡献指南", "有" if has_contrib else "无",
                   "🟢" if has_contrib else "🟡"))
    checks.append(("开源 License", (info.get("license") or {}).get("spdx_id") or "无",
                   "🟢" if info.get("license") else "🔴"))

    out.append(f"仓库: {owner}/{repo}  ⭐ {info.get('stargazers_count')}  🍴 {info.get('forks_count')}")
    out.append(f"主语言: {info.get('language')}  |  {info.get('html_url')}")
    for name, val, lamp in checks:
        out.append(f"  {lamp} {name}: {val}")
        score += 2 if lamp == "🟢" else (1 if lamp == "🟡" else 0)

    pct = score / total if total else 0
    verdict = "🟢 健康，适合投入" if pct >= 0.83 else ("🟡 有摩擦，谨慎投入" if pct >= 0.5 else "🔴 建议放弃")
    out.append(f"健康度: {score}/{total}  →  {verdict}")
    out.append(f"AI 政策: {ai_state} — {ai_note}")

    return out, score, total, {"ai_policy": ai_state, "ai_note": ai_note, "checks": checks}


def gh_days_ago_since(days):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser(description="GitHub 仓库健康度体检（v3.1）")
    ap.add_argument("repos", nargs="+", help="owner/repo 或 GitHub URL，可多个")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供自动化复用）")
    ap.add_argument("--quiet", action="store_true", help="关闭 stderr 进度输出")
    args = ap.parse_args()
    if args.quiet:
        pg.set_quiet(True)  # --quiet 覆盖 CR_QUIET 默认值

    results = []
    failed = 0
    total = len(args.repos)
    pg.phase("health-check", total=total)
    for idx, arg in enumerate(args.repos, 1):
        owner, repo = gh.parse_repo(arg)
        if not owner:
            pg.item(idx, total, arg, "skip", detail="unparseable", phase_name="health-check")
            print(f"跳过无法解析的参数: {arg}")
            continue
        name = f"{owner}/{repo}"
        pg.item(idx, total, name, "running", phase_name="health-check")
        lines, score, max_score, extra = check_repo(owner, repo)
        if lines and lines[0].startswith("仓库查询失败"):
            pg.item(idx, total, name, "error", detail=lines[0], phase_name="health-check")
            failed += 1
        else:
            pg.item(idx, total, name, "ok", detail=f"{score}/{max_score}", phase_name="health-check")
        print("\n" + "\n".join(lines))
        results.append({"repo": name, "score": score, "max": max_score,
                        "ai_policy": extra["ai_policy"], "ai_note": extra["ai_note"]})
    pg.item_end()
    pg.phase("health-check", "done",
             detail=f"{len(results)} repos checked, {failed} failed")

    if len(results) > 1:
        print("\n===== 批量汇总（按健康度排序）=====")
        for r in sorted(results, key=lambda x: -(x["score"] / x["max"] if x["max"] else 0)):
            print(f"  {r['score']}/{r['max']}  {r['repo']}  [AI政策:{r['ai_policy']}]")

    if args.json:
        print("\n" + json.dumps(results, ensure_ascii=False, indent=2))

    print("\n标准: 近1月有提交 | closed/open>1 | PR 2周内有回应 | 每季有 Release（《开源手册》）")


if __name__ == "__main__":
    gh.ensure_utf8_stdio()
    main()

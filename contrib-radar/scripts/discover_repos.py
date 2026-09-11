#!/usr/bin/env python3
"""GitHub 候选项目发现（v3，零第三方依赖，基于共享 github_api 模块）。

把 Route A 的"找项目"变成确定性输出，替代不稳定的搜索引擎关键词检索。

用法:
    python discover_repos.py                                  # 默认: AI Agent 方向
    python discover_repos.py --topic ai-agent --language typescript   # TS 生态（前沿 Agent 项目多为 TS）
    python discover_repos.py --topic mcp --language python
    python discover_repos.py --topic ai-agent --stars 500 --pushed-days 60 --limit 10
    python discover_repos.py --query "agent framework" --language typescript
    python discover_repos.py --beginner --language typescript  # 新手甜蜜区（100~1000 star）+ TS
    python discover_repos.py --beginner python                # 新手甜蜜区（100~1000 star）
    python discover_repos.py --topic mcp --json               # JSON 输出

可选: 设置环境变量 GITHUB_TOKEN 以提高 API 速率限制。

v3 相对 v2 的变化:
1. 基于共享 github_api.py（统一限速/降级）。
2. 查询串增加 fork:false（排除镜像/复制仓库）。
3. 新增 --beginner 新手甜蜜区模式（star 100~1000，竞争小、维护者回复快）。
4. 新增 --json 输出。
"""

import argparse
import json
import sys
import urllib.parse

import github_api as gh


def build_query(args):
    since = gh_days_ago(args.pushed_days)
    if args.beginner:
        stars_q = "stars:100..1000"  # 新手甜蜜区
    elif args.max_stars:
        stars_q = f"stars:{args.stars}..{args.max_stars}"
    else:
        stars_q = f"stars:>={args.stars}"
    q = args.query if args.query else f"topic:{args.topic}"
    q = f"{q} {stars_q} pushed:>={since} archived:false fork:false"
    if args.language:
        q += f" language:{args.language}"
    return q


def main():
    ap = argparse.ArgumentParser(description="GitHub 候选贡献项目发现（v3）")
    ap.add_argument("--topic", default="ai-agent", help="GitHub topic，默认 ai-agent")
    ap.add_argument("--query", default="", help="自定义关键词（设置后忽略 --topic）")
    ap.add_argument("--language", default="", help="主语言过滤，如 python / typescript / go / java")
    ap.add_argument("--stars", type=int, default=1000, help="最低 star 数，默认 1000")
    ap.add_argument("--max-stars", type=int, default=0, help="最高 star 数（0=不限；想避开顶流项目可设 20000）")
    ap.add_argument("--pushed-days", type=int, default=90, help="最近 N 天内有提交，默认 90")
    ap.add_argument("--beginner", action="store_true",
                    help="新手甜蜜区模式：star 100~1000，竞争小、维护者回复快（覆盖 --stars/--max-stars）")
    ap.add_argument("--limit", type=int, default=10, help="返回数量，默认 10，最大 30")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    q = build_query(args)
    per_page = min(args.limit, 30)
    data = gh.get("/search/repositories?q=" + urllib.parse.quote(q)
                  + f"&sort=updated&order=desc&per_page={per_page}", search=True)
    if "_error" in data:
        sys.exit(f"搜索失败: {data['_error']}")

    items = data.get("items", [])
    if not items:
        sys.exit("没有符合条件的仓库。可尝试放宽 --stars 或 --pushed-days，或 --beginner 甜蜜区。")

    rows = []
    for r in items[: args.limit]:
        pushed_d = gh.days_ago(r.get("pushed_at"))
        rows.append({
            "full_name": r["full_name"], "stars": r["stargazers_count"],
            "language": r.get("language"), "pushed_days_ago": pushed_d,
            "description": (r.get("description") or "").replace("\n", " ")[:100],
            "url": r["html_url"],
        })

    if args.json:
        print(json.dumps({"query": q, "total": data.get("total_count"), "repos": rows},
                         ensure_ascii=False, indent=2))
        return

    print(f"查询: {q}")
    print(f"命中 {data.get('total_count')} 个仓库，按最近更新取前 {len(rows)} 个:\n")
    for i, r in enumerate(rows, 1):
        print(f"{i}. {r['full_name']}  ⭐{r['stars']}  [{r['language'] or '-'}]  {r['pushed_days_ago']}天前推送")
        print(f"   {r['description']}")
        print(f"   {r['url']}\n")

    print("下一步: 对候选逐个运行  python repo_health.py <owner/repo>  做健康度体检（含 AI 政策检查）。")


def gh_days_ago(days):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


if __name__ == "__main__":
    main()

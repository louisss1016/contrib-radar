#!/usr/bin/env python3
"""GitHub 授权预检（v3.8，零第三方依赖）——使用本 skill 的第一道门控。

本 skill 的写操作（认领评论 / fork / push / create PR）以 token 所属的
GitHub 账号身份执行：授权决定"你将以哪个账号提 PR"。因此第一次使用前
必须先过本预检——未授权时输出授权步骤，完成授权后才允许继续。

token 解析优先级（github_api.resolve_token，先命中先返回）：
    环境变量 GITHUB_TOKEN > gh CLI > git credential helper > ~/.contrib-radar/token

用法:
    python auth_check.py           # 人类可读：认证状态；未认证时给完整授权步骤
    python auth_check.py --json    # JSON：{authenticated, source, login, scopes, error[, guidance]}
    python auth_check.py --quiet   # 关闭 stderr 进度输出

退出码: 0=已认证  1=未认证或 token 失效  2=瞬时错误（网络/限流，可重试）

进度（v3.7）：auth-check（含 auth-resolve / auth-verify 两子阶段）向 stderr
发射 [CR-PROGRESS] JSON 事件（管道模式）；--json 的 stdout 契约不受影响。
"""

import argparse
import json
import sys

import github_api as gh
import progress as pg


def main():
    ap = argparse.ArgumentParser(description="GitHub 授权预检（写操作前置门控）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiet", action="store_true", help="关闭 stderr 进度输出")
    args = ap.parse_args()
    if args.quiet:
        pg.set_quiet(True)  # --quiet 覆盖 CR_QUIET 默认值

    pg.phase("auth-check", total=2, detail="github authorization preflight")

    # 1. 解析 token 来源（不发请求）
    pg.phase("auth-resolve")
    token, source = gh.resolve_token()
    if token:
        pg.phase("auth-resolve", "ok", detail=f"token source: {source}")
    else:
        pg.phase("auth-resolve", "warn", detail="no token from any source")

    # 2. 验证 token 有效性（GET /user，确认提 PR 的身份账号）
    pg.phase("auth-verify")
    info = gh.check_auth() if token else {
        "authenticated": False, "source": None, "login": None,
        "scopes": [], "error": "no_token"}

    transient = str(info["error"]).startswith("network:") or info["error"] in (
        "http_403", "http_429", "http_5xx")
    if info["authenticated"]:
        pg.phase("auth-verify", "ok", detail=f"user: {info['login']}")
        pg.phase("auth-check", "done",
                 detail=f"authenticated as {info['login']} ({info['source']})")
    elif transient:
        pg.phase("auth-verify", "error", detail=str(info["error"]))
        pg.phase("auth-check", "error", detail="transient failure, retry later")
    else:
        pg.phase("auth-verify", "warn", detail=str(info["error"]))
        pg.phase("auth-check", "warn", detail="not authenticated")

    result = {
        "authenticated": info["authenticated"],
        "source": info["source"],
        "login": info["login"],
        "scopes": info["scopes"],
        "error": info["error"],
    }
    if not result["authenticated"]:
        result["guidance"] = gh.auth_guidance()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["authenticated"]:
        scopes = ", ".join(result["scopes"]) or "(fine-grained token, scopes not exposed)"
        print("✅ 已通过 GitHub 授权")
        print(f"  账号: {result['login']}  （认领 / 提 PR / commit 将以此账号身份执行）")
        print(f"  token 来源: {result['source']}")
        print(f"  scopes: {scopes}")
    else:
        g = gh.auth_guidance()
        reason = {
            "no_token": "未检测到任何可用 token",
            "http_401": "token 无效或已过期",
            "http_403": "被限流或 token 权限不足",
        }.get(result["error"], result["error"])
        print(f"⛔ 未通过 GitHub 授权：{reason}")
        print(f"\n{g['summary']}\n")
        for opt in g["options"]:
            print(f"【{opt['title']}】")
            for i, step in enumerate(opt["steps"], 1):
                print(f"  {i}. {step}")
            print()
        print(g["note"])
        print("完成授权后重新运行: python scripts/auth_check.py")

    if result["authenticated"]:
        sys.exit(0)
    sys.exit(2 if transient else 1)


if __name__ == "__main__":
    gh.ensure_utf8_stdio()
    main()

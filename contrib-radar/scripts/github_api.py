#!/usr/bin/env python3
"""GitHub API 共享封装（零第三方依赖）。

三个脚本（discover_repos.py / find_issues.py / repo_health.py）统一使用本模块，
避免重复实现请求、限速、错误降级与仓库解析。

设计要点：
- 未认证限额（GitHub 官方）：core REST 60 次/小时；Search 10 次/分钟。
  认证后：core 5000/小时；Search 30/分钟（建议设置 GITHUB_TOKEN）。
- 限速策略：
  * 无 token 时只对 /search/ 端点主动打点（每 6.2s 一次），core 端点不打点
    （单次 Route A 扫描的 core 调用量远低于 60/hr，靠 403 兜底）。
  * 命中 403 时读取 X-RateLimit-Reset，按剩余秒数等待后重试一次。
  * 有 token 时不打点。
- 错误语义：所有失败返回 {"_error": <原因>} 字典，调用方自行降级，不抛异常。

用法:
    import github_api as gh
    data = gh.get("/repos/owner/repo")                 # core 端点
    data = gh.get("/search/issues?q=...", search=True) # search 端点
    owner, repo = gh.parse_repo("owner/repo")          # 解析仓库参数
    token, source = gh.resolve_token()                 # 四源解析 token（v3.8）
    info = gh.check_auth()                             # 验证认证状态（v3.8）
    gh.require_auth("create PR")                       # 写操作门控（v3.8，未认证 exit 2）
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# 限速状态
_last_search_ts = 0.0   # 上一次 search 请求时间戳（无 token 打点用）
_core_calls = 0
_headers = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "contrib-radar",
}
if TOKEN:
    _headers["Authorization"] = f"Bearer {TOKEN}"


def _pace(search):
    """无 token 时的主动限速：只对 search 端点打点。"""
    global _last_search_ts
    if TOKEN:
        return
    if not search:
        return
    gap = _last_search_ts + 6.2 - time.time()
    if gap > 0:
        time.sleep(gap)
    _last_search_ts = time.time()


def get(path, search=False):
    """GET GitHub API。search=True 表示该请求属于 Search 端点（限速口径不同）。

    返回解析后的 JSON；失败返回 {"_error": <原因>}，不抛异常。
    """
    global _core_calls
    if search:
        _pace(search=True)
    else:
        _core_calls += 1

    req = urllib.request.Request(API + path, headers=_headers)
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset = e.headers.get("X-RateLimit-Reset")
                if reset and attempt == 1:
                    # 自适应等待：距离 reset 还有多久就等多久（上限 60s）
                    wait = min(int(reset) - int(time.time()), 60)
                    if wait > 0:
                        time.sleep(wait + 1)
                    continue
                return {"_error": "rate_limited",
                        "hint": "设置 GITHUB_TOKEN 可大幅提高限额（core 5000/hr, search 30/min）"}
            if e.code == 404:
                return {"_error": "not_found"}
            if e.code == 422:
                return {"_error": "invalid_query"}
            return {"_error": f"http_{e.code}"}
        except Exception as e:  # noqa: BLE001
            if attempt == 1:
                time.sleep(2)  # 瞬时错误短退避
                continue
            return {"_error": str(e)}
    return {"_error": "unknown"}


# ---------------------------------------------------------------------------
# GitHub 认证层（v3.8）
#
# 写操作（认领评论 / fork / push / create PR）以哪个账号身份执行，完全取决于
# 这里的 token 解析结果——授权是使用本 skill 的前置门控，不是可选项。
# 解析优先级（先命中先返回）：
#   1. 环境变量 GITHUB_TOKEN
#   2. gh CLI（gh auth token，已安装且已登录时）
#   3. git credential helper（GCM 等已存凭据，不落盘不回显）
#   4. ~/.contrib-radar/token 文件（本 skill 自有存储，单行 token）
# 只读场景（项目发现 / issue 扫描 / 体检）无 token 仍可用（限流降级）；
# 写场景必须 resolve_token() 命中 + GET /user 验证通过。
# ---------------------------------------------------------------------------

TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".contrib-radar", "token")


def _read_token_file():
    """读取 ~/.contrib-radar/token（单行 token）；不存在返回空串。"""
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _token_from_gh_cli():
    """gh auth token：gh 已安装且已登录时返回 token，否则空串。"""
    try:
        import subprocess
        r = subprocess.run(["gh", "auth", "token"],
                           capture_output=True, timeout=10)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001
        pass
    return ""


def _token_from_credential_helper():
    """git credential fill：从系统凭据助手取 github.com 密码（不落盘不回显）。"""
    try:
        import subprocess
        r = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, timeout=10)
        if r.returncode == 0:
            for line in r.stdout.decode("utf-8", errors="replace").splitlines():
                if line.startswith("password="):
                    return line[len("password="):].strip()
    except Exception:  # noqa: BLE001
        pass
    return ""


def resolve_token():
    """按优先级解析 GitHub token。

    返回 (token, source)；source ∈ env | gh | credential | file；
    四源全空返回 ("", None)。
    """
    env = os.environ.get("GITHUB_TOKEN", "").strip()
    if env:
        return env, "env"
    for source, getter in (("gh", _token_from_gh_cli),
                           ("credential", _token_from_credential_helper),
                           ("file", _read_token_file)):
        token = getter()
        if token:
            return token, source
    return "", None


def check_auth(timeout=20):
    """验证 GitHub 认证状态（GET /user）。

    返回 dict：
        authenticated  bool —— token 有效且能读到当前用户
        source         env | gh | credential | file | None
        login          认证用户的 GitHub login（提 PR 的身份）
        scopes         token 的 OAuth scopes（X-OAuth-Scopes，fine-grained 为 []）
        error          None | no_token | http_401 | http_403 | network:<原因> | http_<码>
    任何失败都不抛异常——调用方按 error 分支处理。
    """
    token, source = resolve_token()
    if not token:
        return {"authenticated": False, "source": None, "login": None,
                "scopes": [], "error": "no_token"}
    headers = dict(_headers)
    headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + "/user", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
            scopes = [s.strip() for s in
                      (resp.headers.get("X-OAuth-Scopes") or "").split(",") if s.strip()]
            return {"authenticated": True, "source": source,
                    "login": data.get("login"), "scopes": scopes, "error": None}
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"authenticated": False, "source": source, "login": None,
                    "scopes": [], "error": "http_401"}
        if e.code == 403:
            return {"authenticated": False, "source": source, "login": None,
                    "scopes": [], "error": "http_403"}
        return {"authenticated": False, "source": source, "login": None,
                "scopes": [], "error": f"http_{e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"authenticated": False, "source": source, "login": None,
                "scopes": [], "error": f"network:{e}"}


def auth_guidance():
    """未认证时的授权指引（结构化数据；渲染由 auth_check.py / require_auth 负责）。"""
    return {
        "summary": ("未检测到可用的 GitHub 认证。认领评论 / fork / push / create PR "
                    "等写操作以 token 所属账号身份执行，动手前必须先完成授权，"
                    "确认自己将以哪个账号提 PR。"),
        "options": [
            {
                "id": "pat",
                "title": "方式一：Personal Access Token（最通用，推荐）",
                "steps": [
                    "打开 https://github.com/settings/tokens （Fine-grained）或 https://github.com/settings/tokens/new （Classic）",
                    "Fine-grained：Resource owner 选自己；Repository access 选目标仓库或 All repositories；Permissions -> Repository permissions 给 Contents / Pull requests / Issues 的 Read and write",
                    "Classic：勾选 repo scope 即可（含自己 fork 的推送权限）",
                    "生成后立即复制（gho_ / github_pat_ 开头，只显示一次）",
                    "保存任选其一：a) 环境变量 GITHUB_TOKEN=<token>（PowerShell: $env:GITHUB_TOKEN=\"<token>\"）；b) 写入 ~/.contrib-radar/token 文件（仅一行 token，勿提交到仓库）",
                    "重新运行 python scripts/auth_check.py 验证",
                ],
            },
            {
                "id": "gh",
                "title": "方式二：gh CLI（本机已装 GitHub CLI 时最省事）",
                "steps": [
                    "安装：https://cli.github.com （Windows: winget install GitHub.cli）",
                    "运行 gh auth login -> 选 GitHub.com -> HTTPS -> 浏览器授权或粘贴 token",
                    "重新运行 python scripts/auth_check.py 验证",
                ],
            },
            {
                "id": "mcp",
                "title": "方式三：绑定 GitHub 连接器 / MCP（WorkBuddy 等带连接器的环境）",
                "steps": [
                    "在连接器管理中搜索 GitHub 并完成 OAuth 绑定",
                    "绑定后确认连接器状态为已连接",
                    "重新运行 python scripts/auth_check.py 验证（该通道优先用于读写）",
                ],
            },
        ],
        "note": ("只读操作（项目发现 / issue 扫描 / 体检）可免认证先行；"
                 "一旦进入认领、提 PR、commit 等写操作必须认证。"),
    }


def require_auth(operation="GitHub 写操作"):
    """写操作前置门控。

    认证成功：返回 check_auth() 结果 dict。
    未认证 / token 失效 / 瞬时网络失败：向 stderr 输出授权指引，sys.exit(2)。
    设计取舍：瞬时失败也按未认证拦住——宁可让用户重试，也不带病提交。
    """
    info = check_auth()
    if info["authenticated"]:
        return info
    g = auth_guidance()
    sys.stderr.write(f"\n[授权门控] {operation} 需要 GitHub 认证：{g['summary']}\n")
    for opt in g["options"]:
        sys.stderr.write(f"\n{opt['title']}\n")
        for i, step in enumerate(opt["steps"], 1):
            sys.stderr.write(f"  {i}. {step}\n")
    sys.stderr.write(f"\n{g['note']}\n")
    sys.stderr.write("验证命令: python scripts/auth_check.py --json\n\n")
    sys.exit(2)


def parse_repo(arg):
    """把 'owner/repo' 或 GitHub URL 解析为 (owner, repo)；失败返回 (None, None)。"""
    m = re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", arg)
    if m:
        return m.group(1), m.group(2)
    parts = arg.strip("/").split("/")
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def days_ago(iso):
    """ISO 时间字符串距今多少天；无法解析返回 None。"""
    if not iso:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:  # noqa: BLE001
        return None


def ensure_utf8_stdio():
    """把 stdio 切到 UTF-8，修 Windows 下 print emoji/符号直接崩溃的问题。

    Windows 控制台与重定向默认 GBK(cp936)，脚本输出含 ⭐🟢✓• 等字符、
    且 JSON 用 ensure_ascii=False 时，print 会抛 UnicodeEncodeError。
    交互式终端额外把代码页切到 65001 保证正确渲染；管道/重定向场景
    只 reconfigure，让下游按 UTF-8 解码。幂等；无 reconfigure 的
    老版本 Python 或非常规流（已被替换/捕获）时静默跳过。
    """
    if sys.platform == "win32":
        try:
            if sys.stdout is not None and sys.stdout.isatty():
                import ctypes
                ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except (AttributeError, OSError):
            pass
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def fetch_file_content(owner, repo, path):
    """读取仓库内文本文件内容（如 CONTRIBUTING.md）。

    通过 Contents API 获取；若返回的是大文件外链（git blob）则返回 None。
    失败返回 None。
    """
    data = get(f"/repos/{owner}/{repo}/contents/{path}")
    if "_error" in data or not data.get("content"):
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


def fatal(msg):
    """打印错误并以非零码退出（用于脚本主流程的硬失败场景）。"""
    sys.exit(msg)


if __name__ == "__main__":
    ensure_utf8_stdio()
    # 自检：python github_api.py owner/repo 打印仓库基本元数据
    if len(sys.argv) != 2:
        sys.exit("自检用法: python github_api.py owner/repo")
    owner, repo = parse_repo(sys.argv[1])
    if not owner:
        sys.exit("无法解析仓库参数")
    info = get(f"/repos/{owner}/{repo}")
    if "_error" in info:
        sys.exit(f"查询失败: {info['_error']}")
    print(f"{owner}/{repo}  ⭐{info.get('stargazers_count')}  {info.get('language')}  pushed {days_ago(info.get('pushed_at'))}天前")

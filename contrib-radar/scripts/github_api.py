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

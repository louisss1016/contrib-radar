# 纯 GitHub REST API 提 PR（git 不可用时的降级通道）

当 `git clone` / `git push` 被代理、防火墙或大仓库传输阻断（典型症状：`RPC failed; curl 56 ... unexpected eof while reading`、`IncompleteRead(...)`），但 GitHub REST API 的**小响应**仍可用时，可以完全跳过本地 git，用 **Git Data API** 直接构造 commit 并开 PR。本文件记录完整流程与可直接复用的脚本骨架。

## 适用场景

- 本地代理对大文件传输不稳定，但 API 单请求（几十 KB 内）稳定。
- 只想改少量文件（文档、单点 bug 修复），不值得完整 clone 大仓库。
- `gh` CLI 未安装 / 未登录，但系统里有 GitHub 凭据（如 Git Credential Manager）。

## 认证

优先从已存的凭据助手取 token（不落盘、不回显）：

```bash
TOKEN=$(printf "protocol=https\nhost=github.com\n" | git credential fill | grep '^password=' | cut -d= -f2-)
```

或用环境变量 `GITHUB_TOKEN`（`gho_` / `github_pat_` 均可）。之后所有请求带 `Authorization: Bearer <token>` 头。

## 流程（8 步）

| 步骤 | 端点 | 说明 |
|------|------|------|
| 1. fork | `POST /repos/{upstream}/forks` | 返回 `202`（异步），轮询 `GET /repos/{fork}` 直到 `200` |
| 2. 取 base 分支 | `GET /repos/{fork}/git/ref/heads/{base}` | 拿到 head commit SHA（**PR base 必须选 `develop`**，见 CONTRIBUTING） |
| 3. 取 tree | `GET /repos/{fork}/git/commits/{head}` | 拿到该 commit 的 `tree.sha` 作为 `base_tree` |
| 4. 建 blob | `POST /repos/{fork}/git/blobs` | 对每个改动文件：`{"content": <utf8>, "encoding": "utf-8"}` → 拿 blob SHA |
| 5. 建 tree | `POST /repos/{fork}/git/trees` | `{"base_tree": <step3>, "tree": [{"path","mode":"100644","type":"blob","sha"}]}` → 替换指定路径 |
| 6. 建 commit | `POST /repos/{fork}/git/commits` | `{"message","tree":<step5>,"parents":[<head>]}` |
| 7. 建分支 | `POST /repos/{fork}/git/refs` | `{"ref":"refs/heads/{branch}","sha":<step6>}` |
| 8. 开 PR | `POST /repos/{upstream}/pulls` | `{"title","head":"{user}:{branch}","base":"develop","body"}` |

关键点：用 `base_tree` 增量替换，只改动目标文件，其余路径保持不变；commit 的 `parents` 直接指向 base 分支 head，历史干净。

## 复用脚本骨架

```python
import json, os, time, base64, urllib.request, urllib.error

TOKEN = os.environ["GITHUB_TOKEN"]
H = {"Accept": "application/vnd.github+json", "User-Agent": "contrib-radar",
     "Authorization": "Bearer " + TOKEN}
UPSTREAM, FORK, BRANCH = "TencentCloud/Octop", "louisss1016/Octop", "fix/xxx"

def req(url, method="GET", data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=H, method=method)
    for _ in range(6):
        try:
            resp = urllib.request.urlopen(r, timeout=45)
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            return e.code, (json.loads(e.read()) if e.read() else {})
        except Exception:
            time.sleep(3)
    return None, {"err": "timeout"}

# 1. fork（如未 fork）
s, _ = req(f"https://api.github.com/repos/{UPSTREAM}/forks", "POST", {})  # 202
for _ in range(30):
    time.sleep(4)
    s, mine = req(f"https://api.github.com/repos/{FORK}")
    if s == 200:
        break

# 2-3. base 分支 head + tree
_, ref = req(f"https://api.github.com/repos/{FORK}/git/ref/heads/develop")
head = ref["object"]["sha"]
_, commit = req(f"https://api.github.com/repos/{FORK}/git/commits/{head}")
base_tree = commit["tree"]["sha"]

# 4-5. blob + tree
entries = []
for path, text in {  # {仓库路径: 新内容}
    "src/octop/foo.py": "...",
}.items():
    _, blob = req(f"https://api.github.com/repos/{FORK}/git/blobs",
                  "POST", {"content": text, "encoding": "utf-8"})
    entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
_, tree = req(f"https://api.github.com/repos/{FORK}/git/trees",
              "POST", {"base_tree": base_tree, "tree": entries})

# 6-7. commit + branch
_, nc = req(f"https://api.github.com/repos/{FORK}/git/commits",
            "POST", {"message": "fix: ...", "tree": tree["sha"], "parents": [head]})
req(f"https://api.github.com/repos/{FORK}/git/refs",
    "POST", {"ref": f"refs/heads/{BRANCH}", "sha": nc["sha"]})

# 8. PR
_, pr = req(f"https://api.github.com/repos/{UPSTREAM}/pulls",
            "POST", {"title": "...", "head": f"louisss1016:{BRANCH}",
                     "base": "develop", "body": "..."})
print(pr.get("html_url"))
```

## 坑与对策

- **大响应被代理截断**（`IncompleteRead`）：避免一次拉超大列表（如 `forks?per_page=100`、全量 issue）；改用分页 `per_page=30`、单条精确查询，或对每个请求加重试。
- **PR base 选错**：多数仓库约定 feature PR 打向 `develop`（不是 `main`）。提交前读 `CONTRIBUTING.md` 确认。
- **改动文件必须拿到当前 blob 再改**：直接用 `GET /contents/{path}` 取原文（base64），改完再走 blob→tree 流程；不要凭记忆重写整文件。
- **提交后复核**：`GET /repos/{upstream}/pulls/{n}` 看 `mergeable`；`GET .../pulls/{n}/files` 看 diff 是否符合预期。
- **只读文件 vs 二进制**：Git Data API 的 blob 只适合文本；二进制（图片）不要用此通道。
- **一个 commit 改多个文件**：一次 tree 提交全部 entries，得到**单个 commit**（比 Contents API 逐文件 PUT 更干净）。

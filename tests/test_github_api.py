"""github_api 共享模块测试：parse_repo / days_ago / ensure_utf8_stdio / 认证层（v3.8）。"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

import github_api as gh


class TestParseRepo(unittest.TestCase):

    def test_owner_repo_format(self):
        owner, repo = gh.parse_repo("octocat/hello-world")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "hello-world")

    def test_https_url(self):
        owner, repo = gh.parse_repo("https://github.com/octocat/hello-world")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "hello-world")

    def test_url_with_trailing_slash(self):
        owner, repo = gh.parse_repo("https://github.com/octocat/hello-world/")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "hello-world")

    def test_url_with_dot_git(self):
        owner, repo = gh.parse_repo("https://github.com/octocat/hello-world.git")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "hello-world")

    def test_ssh_url(self):
        owner, repo = gh.parse_repo("git@github.com:octocat/hello-world.git")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "hello-world")

    def test_repo_with_dots(self):
        owner, repo = gh.parse_repo("octocat/hello.world.py")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "hello.world.py")

    def test_invalid_input(self):
        owner, repo = gh.parse_repo("not-a-repo")
        self.assertIsNone(owner)
        self.assertIsNone(repo)

    def test_empty_input(self):
        owner, repo = gh.parse_repo("")
        self.assertIsNone(owner)
        self.assertIsNone(repo)


class TestDaysAgo(unittest.TestCase):

    def test_recent(self):
        iso = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(gh.days_ago(iso), 3)

    def test_today(self):
        iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(gh.days_ago(iso), 0)

    def test_none_input(self):
        self.assertIsNone(gh.days_ago(None))

    def test_empty_input(self):
        self.assertIsNone(gh.days_ago(""))

    def test_invalid_input(self):
        self.assertIsNone(gh.days_ago("not-a-date"))


class TestEnsureUtf8Stdio(unittest.TestCase):
    """Windows GBK(cp936) 控制台/管道下 print emoji 崩溃的修复验证。"""

    def setUp(self):
        self._old_out, self._old_err = sys.stdout, sys.stderr

    def tearDown(self):
        sys.stdout, sys.stderr = self._old_out, self._old_err

    def test_reconfigures_streams_to_utf8(self):
        calls = []

        class Spy:
            def reconfigure(self, **kwargs):
                calls.append(kwargs)

        sys.stdout = sys.stderr = Spy()
        gh.ensure_utf8_stdio()
        self.assertEqual(calls, [{"encoding": "utf-8"}, {"encoding": "utf-8"}])

    def test_stream_without_reconfigure_is_safe(self):
        sys.stdout = sys.stderr = io.StringIO()
        gh.ensure_utf8_stdio()  # 不抛异常即通过

    def test_none_stream_is_safe(self):
        sys.stdout = sys.stderr = None
        gh.ensure_utf8_stdio()  # 不抛异常即通过

    def test_emoji_survives_ascii_stream(self):
        # 复现崩溃场景：流编码为 ascii（类比 GBK 无 emoji 字形），
        # 修复后 print ⭐🟢✓ 不再抛 UnicodeEncodeError，且按 UTF-8 落字节
        buf = io.BytesIO()
        wrapper = io.TextIOWrapper(buf, encoding="ascii")
        sys.stdout = wrapper
        try:
            gh.ensure_utf8_stdio()
            print("⭐🟢✓")
            wrapper.flush()
        finally:
            sys.stdout = self._old_out
        self.assertEqual(buf.getvalue().decode("utf-8").strip(), "⭐🟢✓")


class _FakeResponse:
    """mock urllib.response 上下文管理器：read() 返回 JSON 字节。"""

    def __init__(self, payload=None, headers=None):
        self._payload = payload or {}
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class TestTokenSourceHelpers(unittest.TestCase):
    """四源解析的底层取 token 助手。"""

    def test_gh_cli_success(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=b"gho_x\n", stderr=b"")
            self.assertEqual(gh._token_from_gh_cli(), "gho_x")

    def test_gh_cli_not_logged_in_returns_empty(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 1, stdout=b"", stderr=b"not logged in")
            self.assertEqual(gh._token_from_gh_cli(), "")

    def test_gh_cli_missing_binary_is_safe(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(gh._token_from_gh_cli(), "")

    def test_credential_helper_parses_password(self):
        out = b"protocol=https\nhost=github.com\nusername=u\npassword=gho_c\n"
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=out, stderr=b"")
            self.assertEqual(gh._token_from_credential_helper(), "gho_c")

    def test_credential_helper_without_password_line(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=b"protocol=https\n", stderr=b"")
            self.assertEqual(gh._token_from_credential_helper(), "")

    def test_token_file_missing_returns_empty(self):
        with mock.patch.object(gh, "TOKEN_FILE", os.path.join(tempfile.gettempdir(), "no-such-token")):
            self.assertEqual(gh._read_token_file(), "")

    def test_token_file_reads_single_line(self):
        fd, path = tempfile.mkstemp(suffix=".token")
        self.addCleanup(os.unlink, path)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("file_tok_123\n")
        with mock.patch.object(gh, "TOKEN_FILE", path):
            self.assertEqual(gh._read_token_file(), "file_tok_123")


class TestResolveToken(unittest.TestCase):
    """resolve_token 优先级：env > gh > credential > file > 无。"""

    def setUp(self):
        self._saved_env = os.environ.pop("GITHUB_TOKEN", None)
        patcher = mock.patch.multiple(
            gh,
            _token_from_gh_cli=mock.DEFAULT,
            _token_from_credential_helper=mock.DEFAULT,
            _read_token_file=mock.DEFAULT,
        )
        self.mocks = patcher.start()
        self.addCleanup(patcher.stop)
        for m in self.mocks.values():
            m.return_value = ""

    def tearDown(self):
        if self._saved_env is not None:
            os.environ["GITHUB_TOKEN"] = self._saved_env

    def test_env_wins_over_all(self):
        os.environ["GITHUB_TOKEN"] = "env_tok"
        self.mocks["_token_from_gh_cli"].return_value = "gh_tok"
        self.mocks["_read_token_file"].return_value = "file_tok"
        self.assertEqual(gh.resolve_token(), ("env_tok", "env"))

    def test_gh_cli_second(self):
        self.mocks["_token_from_gh_cli"].return_value = "gh_tok"
        self.mocks["_read_token_file"].return_value = "file_tok"
        self.assertEqual(gh.resolve_token(), ("gh_tok", "gh"))

    def test_credential_helper_third(self):
        self.mocks["_token_from_credential_helper"].return_value = "cred_tok"
        self.mocks["_read_token_file"].return_value = "file_tok"
        self.assertEqual(gh.resolve_token(), ("cred_tok", "credential"))

    def test_token_file_last(self):
        self.mocks["_read_token_file"].return_value = "file_tok"
        self.assertEqual(gh.resolve_token(), ("file_tok", "file"))

    def test_none_available(self):
        self.assertEqual(gh.resolve_token(), ("", None))


class TestCheckAuth(unittest.TestCase):
    """check_auth：GET /user 验证，覆盖 200 / 401 / 403 / 网络错误 / 无 token。"""

    def test_authenticated_returns_login_and_scopes(self):
        with mock.patch.object(gh, "resolve_token", return_value=("tok", "env")), \
             mock.patch("urllib.request.urlopen",
                        return_value=_FakeResponse({"login": "octocat"},
                                                   {"X-OAuth-Scopes": "repo, read:user"})):
            info = gh.check_auth()
        self.assertTrue(info["authenticated"])
        self.assertEqual(info["source"], "env")
        self.assertEqual(info["login"], "octocat")
        self.assertEqual(info["scopes"], ["repo", "read:user"])
        self.assertIsNone(info["error"])

    def test_no_token_short_circuits_without_request(self):
        with mock.patch.object(gh, "resolve_token", return_value=("", None)), \
             mock.patch("urllib.request.urlopen",
                        side_effect=AssertionError("无 token 不应发请求")):
            info = gh.check_auth()
        self.assertFalse(info["authenticated"])
        self.assertEqual(info["error"], "no_token")
        self.assertIsNone(info["login"])

    def test_401_marks_invalid_token(self):
        err = urllib.error.HTTPError(
            "https://api.github.com/user", 401, "Unauthorized", {}, None)
        with mock.patch.object(gh, "resolve_token", return_value=("tok", "env")), \
             mock.patch("urllib.request.urlopen", side_effect=err):
            info = gh.check_auth()
        self.assertFalse(info["authenticated"])
        self.assertEqual(info["error"], "http_401")

    def test_403_marks_rate_limited(self):
        err = urllib.error.HTTPError(
            "https://api.github.com/user", 403, "Forbidden", {}, None)
        with mock.patch.object(gh, "resolve_token", return_value=("tok", "env")), \
             mock.patch("urllib.request.urlopen", side_effect=err):
            info = gh.check_auth()
        self.assertFalse(info["authenticated"])
        self.assertEqual(info["error"], "http_403")

    def test_network_error_is_captured(self):
        with mock.patch.object(gh, "resolve_token", return_value=("tok", "env")), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("connection reset")):
            info = gh.check_auth()
        self.assertFalse(info["authenticated"])
        self.assertTrue(info["error"].startswith("network:"))


class TestAuthGuidance(unittest.TestCase):
    """auth_guidance：三条授权路径结构完整、内容非空。"""

    def test_structure(self):
        g = gh.auth_guidance()
        self.assertTrue(g["summary"])
        self.assertTrue(g["note"])
        self.assertEqual([o["id"] for o in g["options"]], ["pat", "gh", "mcp"])
        for opt in g["options"]:
            self.assertTrue(opt["title"])
            self.assertGreaterEqual(len(opt["steps"]), 3)
            for step in opt["steps"]:
                self.assertTrue(step.strip())

    def test_pat_steps_mention_token_url_and_storage(self):
        joined = " ".join(gh.auth_guidance()["options"][0]["steps"])
        self.assertIn("github.com/settings/tokens", joined)
        self.assertIn("GITHUB_TOKEN", joined)
        self.assertIn("auth_check.py", joined)

    def test_mcp_option_covers_connector_env(self):
        joined = " ".join(gh.auth_guidance()["options"][2]["steps"])
        self.assertIn("OAuth", joined)


class TestRequireAuth(unittest.TestCase):
    """require_auth：写操作前置门控。"""

    def test_returns_info_when_authenticated(self):
        info = {"authenticated": True, "source": "env", "login": "octocat",
                "scopes": [], "error": None}
        with mock.patch.object(gh, "check_auth", return_value=info):
            self.assertIs(gh.require_auth(), info)

    def test_exits_with_guidance_when_not_authenticated(self):
        info = {"authenticated": False, "source": None, "login": None,
                "scopes": [], "error": "no_token"}
        err = io.StringIO()
        with mock.patch.object(gh, "check_auth", return_value=info), \
             mock.patch.object(sys, "stderr", err):
            with self.assertRaises(SystemExit) as cm:
                gh.require_auth("create PR")
        self.assertEqual(cm.exception.code, 2)
        text = err.getvalue()
        self.assertIn("create PR", text)
        self.assertIn("github.com/settings/tokens", text)


if __name__ == "__main__":
    unittest.main()

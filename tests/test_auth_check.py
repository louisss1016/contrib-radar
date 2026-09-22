"""auth_check 入口脚本测试：JSON 契约 / 退出码 / 授权指引渲染 / 进度不污染 stdout。"""
import io
import json
import sys
import unittest
from unittest import mock

import auth_check

AUTHED = {"authenticated": True, "source": "env", "login": "octocat",
          "scopes": ["repo"], "error": None}
NO_AUTH = {"authenticated": False, "source": None, "login": None,
           "scopes": [], "error": "no_token"}
INVALID = {"authenticated": False, "source": "env", "login": None,
           "scopes": [], "error": "http_401"}
TRANSIENT = {"authenticated": False, "source": "env", "login": None,
             "scopes": [], "error": "network:connection reset"}


def run_main(argv, auth_info):
    """以 mock 的认证结果跑 main()，返回 (退出码, stdout, stderr)。

    main() 先调 resolve_token() 再调 check_auth()，两者都 mock：
    source 非空 → 视为取到了 token（走 check_auth 分支）；
    source 为 None → 四源全空（走 no_token 短路分支）。
    """
    resolved = (("tok", auth_info["source"]) if auth_info.get("source")
                else ("", None))
    out, err = io.StringIO(), io.StringIO()
    code = None
    with mock.patch.object(sys, "argv", ["auth_check.py"] + argv), \
         mock.patch.object(sys, "stdout", out), \
         mock.patch.object(sys, "stderr", err), \
         mock.patch.object(auth_check.gh, "resolve_token", return_value=resolved), \
         mock.patch.object(auth_check.gh, "check_auth", return_value=auth_info):
        try:
            auth_check.main()
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class TestAuthCheckCli(unittest.TestCase):

    def test_json_authenticated_exit0_no_guidance(self):
        code, out, _ = run_main(["--json"], AUTHED)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["login"], "octocat")
        self.assertEqual(data["source"], "env")
        self.assertNotIn("guidance", data)

    def test_json_not_authenticated_exit1_with_guidance(self):
        code, out, _ = run_main(["--json"], NO_AUTH)
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertFalse(data["authenticated"])
        self.assertEqual(data["error"], "no_token")
        self.assertEqual([o["id"] for o in data["guidance"]["options"]],
                         ["pat", "gh", "mcp"])

    def test_invalid_token_exit1(self):
        code, out, _ = run_main(["--json"], INVALID)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["error"], "http_401")

    def test_transient_failure_exit2(self):
        code, _, _ = run_main(["--json"], TRANSIENT)
        self.assertEqual(code, 2)

    def test_human_output_unauthenticated_lists_all_paths(self):
        code, out, _ = run_main([], NO_AUTH)
        self.assertEqual(code, 1)
        self.assertIn("github.com/settings/tokens", out)
        self.assertIn("gh auth login", out)
        self.assertIn("连接器", out)
        self.assertIn("auth_check.py", out)

    def test_human_output_authenticated_shows_login(self):
        code, out, _ = run_main([], AUTHED)
        self.assertEqual(code, 0)
        self.assertIn("octocat", out)
        self.assertIn("env", out)

    def test_json_stdout_not_polluted_by_progress_events(self):
        # 进度走 stderr：--json 的 stdout 必须是可解析的纯 JSON
        code, out, err = run_main(["--json"], AUTHED)
        self.assertEqual(code, 0)
        json.loads(out)  # 不抛异常即通过
        self.assertIn("[CR-PROGRESS]", err)


if __name__ == "__main__":
    unittest.main()

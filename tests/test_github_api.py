"""github_api 共享模块测试：parse_repo / days_ago / ensure_utf8_stdio。"""
import io
import sys
import unittest
from datetime import datetime, timedelta, timezone

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


if __name__ == "__main__":
    unittest.main()

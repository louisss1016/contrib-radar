"""github_api 共享模块测试：parse_repo / days_ago 等纯函数。"""
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


if __name__ == "__main__":
    unittest.main()

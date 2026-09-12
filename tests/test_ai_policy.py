"""AI 政策检查测试：重点验证 v3.1 的去误报逻辑。"""
import unittest
from unittest.mock import patch

import repo_health


class TestAIPolicy(unittest.TestCase):

    def _mock_fetch(self, content_map):
        """构造 mock 的 fetch_file_content，按路径返回内容。"""
        def mock_fetch(owner, repo, path):
            return content_map.get(path)
        return mock_fetch

    def test_llm_alone_not_blocked(self):
        """关键去误报：CONTRIBUTING 里只有 'llm' 字样 → 不应触发 blocked。"""
        content = ("We use LLM-powered tools in our CI pipeline.\n"
                   "The project is built with Python and TypeScript.")
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({"CONTRIBUTING.md": content})):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "ok")

    def test_ai_generated_code_alone_is_mention_not_blocked(self):
        """'ai generated code' 单独出现 → mention（需人工确认），不是 blocked。"""
        content = "We welcome ai generated code contributions, but please disclose."
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({"CONTRIBUTING.md": content})):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "mention")

    def test_explicit_ban_is_blocked(self):
        """明确禁止短语 → blocked。"""
        content = "We do not use ai generated code. All contributions must be human-written."
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({"CONTRIBUTING.md": content})):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "blocked")
            self.assertIn("do not use ai", note.lower())

    def test_no_copilot_is_blocked(self):
        """'no copilot' → blocked。"""
        content = "no copilot usage allowed in this repository."
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({"CONTRIBUTING.md": content})):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "blocked")

    def test_chinese_ban_is_blocked(self):
        """中文禁止 → blocked。"""
        content = "本仓库禁止使用 ai 生成代码，所有贡献必须人工编写。"
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({"CONTRIBUTING.md": content})):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "blocked")

    def test_no_contributing_file(self):
        """找不到贡献指南 → unknown。"""
        with patch.object(repo_health.gh, "fetch_file_content", return_value=None):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "unknown")

    def test_fallback_to_github_contributing(self):
        """CONTRIBUTING.md 不存在时，回退到 .github/CONTRIBUTING.md。"""
        content = "no ai generated code allowed."
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({
                              "CONTRIBUTING.md": None,
                              ".github/CONTRIBUTING.md": content,
                          })):
            state, note = repo_health.ai_policy_check("owner", "repo")
            self.assertEqual(state, "blocked")

    def test_ai_project_normal_mention(self):
        """AI 项目的正常 LLM 讨论 + copilot 提及 → mention（不是 blocked）。"""
        content = ("This project is an AI agent framework.\n"
                   "We use LLM APIs extensively.\n"
                   "Feel free to use copilot for coding assistance.")
        with patch.object(repo_health.gh, "fetch_file_content",
                          side_effect=self._mock_fetch({"CONTRIBUTING.md": content})):
            state, note = repo_health.ai_policy_check("owner", "repo")
            # "copilot" 命中 mention 关键词，但不命中 blocked 短语
            self.assertEqual(state, "mention")


if __name__ == "__main__":
    unittest.main()

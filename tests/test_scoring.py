"""打分回归测试：Issue Quality + Contribution Feasibility。

这些测试用固定输入验证打分结果不变，防止算法调整后意外改变排序。
如果算法有意调整，需要同步更新这里的期望值。
"""
import unittest
from datetime import datetime, timedelta, timezone

from find_issues import (
    score_issue_quality,
    score_feasibility,
    compute_stack_match,
)


def _make_issue(title="Test issue", body="", labels=None, comments=0,
                updated_at=None, milestone=None, assignee=None, number=1):
    """构造一个最小化的 issue 字典，模拟 GitHub API 返回。"""
    if updated_at is None:
        updated_at = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    issue = {
        "number": number,
        "title": title,
        "body": body,
        "labels": [{"name": l} for l in (labels or [])],
        "comments": comments,
        "updated_at": updated_at,
        "milestone": milestone,
        "assignee": assignee,
        "html_url": f"https://github.com/owner/repo/issues/{number}",
    }
    return issue


class TestIssueQuality(unittest.TestCase):
    """Issue Quality 维度测试。"""

    def test_clarity_long_body_with_code_and_repro(self):
        """长描述 + 代码块 + 复现步骤 → 清晰度满分。"""
        body = "x" * 300 + "\n```python\nprint('test')\n```\nSteps to reproduce: 1. do this"
        it = _make_issue(body=body)
        score, parts = score_issue_quality(it, days_active=2)
        self.assertEqual(parts["clarity"]["score"], 30)
        self.assertTrue(parts["clarity"]["has_code"])
        self.assertTrue(parts["clarity"]["has_repro"])

    def test_clarity_short_body(self):
        """短描述 → 清晰度低分。"""
        it = _make_issue(body="fix bug")
        score, parts = score_issue_quality(it, days_active=2)
        self.assertLess(parts["clarity"]["score"], 15)

    def test_label_good_first_issue(self):
        """good first issue 标签 → 标签满分。"""
        it = _make_issue(labels=["good first issue"])
        score, parts = score_issue_quality(it, days_active=2)
        self.assertEqual(parts["label"]["score"], 15)
        self.assertEqual(parts["label"]["kind"], "good first issue")

    def test_label_none(self):
        """无标签 → 标签 0 分。"""
        it = _make_issue(labels=[])
        score, parts = score_issue_quality(it, days_active=2)
        self.assertEqual(parts["label"]["score"], 0)
        self.assertEqual(parts["label"]["kind"], "none")

    def test_freshness_recent(self):
        """最近活跃 → 新鲜度高分。"""
        it = _make_issue()
        score, parts = score_issue_quality(it, days_active=1)
        self.assertGreaterEqual(parts["freshness"]["score"], 20)

    def test_freshness_old(self):
        """很久没活跃 → 新鲜度低分。"""
        it = _make_issue()
        score, parts = score_issue_quality(it, days_active=120)
        self.assertLessEqual(parts["freshness"]["score"], 10)

    def test_milestone_present(self):
        """有 milestone → 加分。"""
        it = _make_issue(milestone={"title": "v1.0", "due_on": None})
        score, parts = score_issue_quality(it, days_active=2)
        self.assertEqual(parts["milestone"]["score"], 15)
        self.assertEqual(parts["milestone"]["title"], "v1.0")

    def test_milestone_due_soon(self):
        """milestone 本月内到期 → 最高分。"""
        due = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        it = _make_issue(milestone={"title": "v1.0", "due_on": due})
        score, parts = score_issue_quality(it, days_active=2)
        self.assertEqual(parts["milestone"]["score"], 20)

    def test_milestone_absent(self):
        """无 milestone → 0 分。"""
        it = _make_issue(milestone=None)
        score, parts = score_issue_quality(it, days_active=2)
        self.assertEqual(parts["milestone"]["score"], 0)

    def test_discussion_healthy(self):
        """1-5 条评论 → 讨论健康度高分。"""
        it = _make_issue(comments=2)
        score, parts = score_issue_quality(it, days_active=2)
        self.assertGreaterEqual(parts["discussion"]["score"], 8)

    def test_discussion_too_many(self):
        """评论过多 → 讨论健康度低分（可能争议大）。"""
        it = _make_issue(comments=20)
        score, parts = score_issue_quality(it, days_active=2)
        self.assertLessEqual(parts["discussion"]["score"], 5)

    def test_total_within_0_100(self):
        """总分必须在 0~100 范围内。"""
        for comments in [0, 3, 10, 50]:
            for days in [1, 10, 60, 200]:
                it = _make_issue(comments=comments)
                score, _ = score_issue_quality(it, days_active=days)
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 100)


class TestContributionFeasibility(unittest.TestCase):
    """Contribution Feasibility 维度测试。"""

    def test_collision_low(self):
        """LOW 碰撞风险 → 撞车项满分。"""
        it = _make_issue()
        score, parts = score_feasibility(it, "LOW", 10, [])
        self.assertEqual(parts["collision"]["score"], 30)

    def test_collision_high(self):
        """HIGH 碰撞风险 → 撞车项 0 分。"""
        it = _make_issue()
        score, parts = score_feasibility(it, "HIGH", 10, [])
        self.assertEqual(parts["collision"]["score"], 0)

    def test_scope_documentation(self):
        """documentation 标签 → 修改范围小，高分。"""
        it = _make_issue(labels=["documentation"])
        score, parts = score_feasibility(it, "LOW", 10, [])
        self.assertEqual(parts["scope"]["score"], 25)

    def test_scope_bug_fix(self):
        """bug 标签 → 修改范围较小。"""
        it = _make_issue(labels=["bug"])
        score, parts = score_feasibility(it, "LOW", 10, [])
        self.assertEqual(parts["scope"]["score"], 20)

    def test_scope_large_refactor(self):
        """描述含 refactor/rewrite → 修改范围大，低分。"""
        it = _make_issue(body="We need to refactor the entire architecture and rewrite the core")
        score, parts = score_feasibility(it, "LOW", 10, [])
        self.assertLessEqual(parts["scope"]["score"], 10)

    def test_beginner_good_first_issue(self):
        """good first issue → 新手友好满分。"""
        it = _make_issue(labels=["good first issue"])
        score, parts = score_feasibility(it, "LOW", 10, [])
        self.assertEqual(parts["beginner"]["score"], 25)

    def test_beginner_no_signal(self):
        """无新手信号 → 新手友好低分。"""
        it = _make_issue(labels=[])
        score, parts = score_feasibility(it, "LOW", 10, [])
        self.assertEqual(parts["beginner"]["score"], 10)

    def test_stack_match_full(self):
        """技术栈全匹配 → stack 满分。"""
        details = [{"tech": "python", "match": "repo_language"}]
        it = _make_issue()
        score, parts = score_feasibility(it, "LOW", 20, details)
        self.assertEqual(parts["stack"]["score"], 20)

    def test_total_within_0_100(self):
        """Feasibility 总分必须在 0~100 范围内。"""
        for risk in ["LOW", "MEDIUM", "HIGH"]:
            it = _make_issue()
            score, _ = score_feasibility(it, risk, 10, [])
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)


class TestScoreRegression(unittest.TestCase):
    """打分回归测试：固定输入，验证总分不变。

    这些是"黄金样本"，如果算法有意调整，需要同步更新期望值。
    调整前请确认：排序是否仍然合理？是否有 issue 的相对顺序被意外改变？
    """

    def _golden_issue_a(self):
        """高价值 issue：清晰描述 + good first issue + 近期活跃 + milestone。"""
        body = ("This is a detailed bug report.\n\n"
                "Steps to reproduce:\n"
                "1. Open the app\n"
                "2. Click the button\n"
                "3. See error\n\n"
                "```python\n"
                "def test():\n"
                "    pass\n"
                "```\n\n"
                "Expected behavior: no error.")
        return _make_issue(
            title="Fix crash when clicking submit button",
            body=body,
            labels=["good first issue", "bug"],
            comments=2,
            milestone={"title": "v1.0", "due_on": None},
        )

    def _golden_issue_b(self):
        """中等价值 issue：普通 feature 请求，无标签，无 milestone。"""
        return _make_issue(
            title="Add dark mode support",
            body="It would be nice to have dark mode.",
            labels=[],
            comments=5,
            milestone=None,
        )

    def _golden_issue_c(self):
        """低价值 issue：描述极短，很久没活跃，评论很多（可能争议大）。"""
        return _make_issue(
            title="broken",
            body="fix",
            labels=[],
            comments=15,
            milestone=None,
        )

    def test_regression_issue_a_quality(self):
        it = self._golden_issue_a()
        score, parts = score_issue_quality(it, days_active=3)
        # 清晰度: 长描述+代码+复现 = 30; 标签: good first issue = 15;
        # 新鲜度: 3天 ≈ 24; milestone: 15; 讨论: 2评论 ≈ 7
        self.assertEqual(score, 91)
        self.assertEqual(parts["clarity"]["score"], 28)
        self.assertEqual(parts["label"]["score"], 15)

    def test_regression_issue_b_quality(self):
        it = self._golden_issue_b()
        score, parts = score_issue_quality(it, days_active=10)
        # 清晰度: 短描述 ≈ 3; 标签: 0; 新鲜度: 10天 ≈ 23; milestone: 0; 讨论: 5评论 ≈ 5
        self.assertEqual(score, 31)

    def test_regression_issue_c_quality(self):
        it = self._golden_issue_c()
        score, parts = score_issue_quality(it, days_active=90)
        # 清晰度: 极短 ≈ 1; 标签: 0; 新鲜度: 90天 ≈ 7; milestone: 0; 讨论: 15评论 ≈ 2
        self.assertEqual(score, 10)

    def test_regression_feasibility_low_collision(self):
        it = self._golden_issue_a()
        score, parts = score_feasibility(it, "LOW", 15, [])
        # 撞车: 30; 范围: bug=20; 新手: good first issue=25; stack: 15
        self.assertEqual(score, 90)

    def test_regression_contribution_score(self):
        """最终 Contribution Score = Quality * 0.5 + Feasibility * 0.5。"""
        it = self._golden_issue_a()
        quality, _ = score_issue_quality(it, days_active=3)
        feasibility, _ = score_feasibility(it, "LOW", 15, [])
        contribution = round(quality * 0.5 + feasibility * 0.5)
        self.assertEqual(contribution, 90)  # (91 + 90) / 2 = 90.5 → 90


class TestStackMatch(unittest.TestCase):
    """技术栈匹配测试。"""

    def test_repo_language_match(self):
        """仓库主语言匹配 → repo_language。"""
        it = _make_issue(title="Test", body="")
        score, pct, details = compute_stack_match(it, "Python", ["python"])
        self.assertEqual(pct, 100)
        self.assertEqual(score, 20)
        self.assertEqual(details[0]["match"], "repo_language")

    def test_issue_mentions_match(self):
        """issue 正文提及技术栈 → issue_mentions。"""
        it = _make_issue(title="Test", body="This uses langchain for RAG pipelines")
        score, pct, details = compute_stack_match(it, "JavaScript", ["langchain"])
        self.assertEqual(pct, 100)
        self.assertEqual(details[0]["match"], "issue_mentions")

    def test_no_match(self):
        """技术栈不匹配 → no_match。"""
        it = _make_issue(title="Test", body="A simple Rust project")
        score, pct, details = compute_stack_match(it, "Rust", ["python", "django"])
        self.assertEqual(pct, 0)
        self.assertEqual(score, 0)

    def test_partial_match(self):
        """部分匹配 → 按比例计算。"""
        it = _make_issue(title="Test", body="Uses python and fastapi")
        score, pct, details = compute_stack_match(it, "Python", ["python", "fastapi", "django"])
        self.assertEqual(pct, 67)  # 2/3
        self.assertEqual(score, 13)  # 67% * 20 = 13.4 → 13

    def test_no_stack_provided(self):
        """未提供 --stack → 中性分 10/50%。"""
        it = _make_issue()
        score, pct, details = compute_stack_match(it, "Python", [])
        self.assertEqual(score, 10)
        self.assertEqual(pct, 50)

    def test_case_insensitive(self):
        """匹配不区分大小写。"""
        it = _make_issue(title="Test", body="Uses PYTHON and LANGCHAIN")
        score, pct, details = compute_stack_match(it, "python", ["Python", "LangChain"])
        self.assertEqual(pct, 100)


if __name__ == "__main__":
    unittest.main()

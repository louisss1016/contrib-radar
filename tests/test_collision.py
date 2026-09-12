"""Collision Risk 分级测试。"""
import unittest

from find_issues import compute_collision_risk


def _make_issue(number=1, comments=0, assignee=None):
    return {
        "number": number,
        "title": "Test issue",
        "body": "test",
        "comments": comments,
        "assignee": assignee,
        "html_url": f"https://github.com/owner/repo/issues/{number}",
    }


class TestCollisionRisk(unittest.TestCase):

    def test_high_open_pr_references(self):
        """被 open PR 引用 → HIGH。"""
        it = _make_issue(number=42)
        pr_refs = {42: [{"number": 100, "user": "alice", "title": "Fix #42"}]}
        risk, reasons, rec = compute_collision_risk(it, pr_refs)
        self.assertEqual(risk, "HIGH")
        self.assertIn("Open PR #100", reasons[0])
        self.assertIn("DO NOT CLAIM", rec)

    def test_high_multiple_prs(self):
        """被多个 PR 引用 → HIGH，列出所有。"""
        it = _make_issue(number=42)
        pr_refs = {
            42: [
                {"number": 100, "user": "alice", "title": "Fix #42"},
                {"number": 101, "user": "bob", "title": "closes #42"},
            ]
        }
        risk, reasons, rec = compute_collision_risk(it, pr_refs)
        self.assertEqual(risk, "HIGH")
        self.assertEqual(len(reasons), 2)

    def test_high_assigned(self):
        """有 assignee → HIGH。"""
        it = _make_issue(number=1, assignee={"login": "alice"})
        risk, reasons, rec = compute_collision_risk(it, {})
        self.assertEqual(risk, "HIGH")
        self.assertIn("@alice", reasons[0])

    def test_medium_high_comments(self):
        """评论 >= 8 → MEDIUM（可能有人在讨论或认领）。"""
        it = _make_issue(number=1, comments=10)
        risk, reasons, rec = compute_collision_risk(it, {})
        self.assertEqual(risk, "MEDIUM")
        self.assertIn("10 comments", reasons[0])
        self.assertIn("Check comments", rec)

    def test_low_moderate_comments(self):
        """评论 3-7 → LOW（正常讨论）。"""
        it = _make_issue(number=1, comments=5)
        risk, reasons, rec = compute_collision_risk(it, {})
        self.assertEqual(risk, "LOW")
        self.assertIn("5 comments", reasons[0])

    def test_low_no_signal(self):
        """无冲突信号 → LOW。"""
        it = _make_issue(number=1, comments=0)
        risk, reasons, rec = compute_collision_risk(it, {})
        self.assertEqual(risk, "LOW")
        self.assertIn("No open PR", reasons[0])
        self.assertEqual(rec, "Safe to claim")

    def test_pr_ref_takes_priority_over_comments(self):
        """即使评论少，被 PR 引用也 → HIGH。"""
        it = _make_issue(number=42, comments=0)
        pr_refs = {42: [{"number": 100, "user": "alice", "title": "fix #42"}]}
        risk, _, _ = compute_collision_risk(it, pr_refs)
        self.assertEqual(risk, "HIGH")


if __name__ == "__main__":
    unittest.main()

"""Milestone regressions for collection growth and weighted exposure."""
import unittest
from songranker.reports.stats_activity import coverage_milestone


class CoverageMilestoneTests(unittest.TestCase):
    def test_next_unfinished_target_and_growth(self):
        """Completed milestones advance; newly added records return to one."""
        self.assertEqual(coverage_milestone([2, 3, 1000]),
                         dict(target=3, reached=2, total=3, share=66.7))
        self.assertEqual(coverage_milestone([2, 3, 1000, 0]),
                         dict(target=1, reached=3, total=4, share=75.0))

    def test_empty_and_fractional_evidence(self):
        """Empty pools are unavailable and fractional appearances never round up."""
        self.assertEqual(coverage_milestone([])['share'], None)
        self.assertEqual(coverage_milestone([.999, 2])['target'], 1)
        self.assertEqual(coverage_milestone([.999, 2])['reached'], 1)
        self.assertEqual(coverage_milestone([1000000, 1000000])['target'], 1000001)

"""Coverage analysis — the "where are the blind spots?" step.

This is half of what makes the corpus engine a differentiator: instead of
synthesizing to pad numbers, we measure coverage *first*, find the gaps, and
only then synthesize — so every synthetic sample has a reason to exist.

The metric is deliberately simple and explainable: per-category sample counts
plus a normalized Shannon entropy as a diversity index. The FDE can defend
every number in the report to a customer.
"""

from __future__ import annotations

import math
from collections import Counter

from .types import CorpusItem, CoverageReport


class CoverageAnalyzer:
    """Compute per-category coverage and flag gaps below a target threshold."""

    def __init__(self, min_samples_per_category: int = 100) -> None:
        self.min_samples = min_samples_per_category

    def analyze(self, items: list[CorpusItem]) -> CoverageReport:
        counts: Counter[str] = Counter(i.category for i in items)
        category_counts = dict(counts)

        diversity = self._diversity_index(list(counts.values()))

        report = CoverageReport(
            category_counts=category_counts,
            target_per_category=self.min_samples,
            diversity_index=diversity,
        )
        report.identify_gaps()
        return report

    @staticmethod
    def _diversity_index(counts: list[int]) -> float:
        """Normalized Shannon entropy over the category distribution.

        Returns 0.0 for a single-category corpus (no diversity) and 1.0 for a
        perfectly uniform distribution across N categories.
        """
        total = sum(counts)
        if total == 0 or len(counts) <= 1:
            return 0.0
        entropy = -sum((c / total) * math.log2(c / total) for c in counts if c > 0)
        return entropy / math.log2(len(counts))

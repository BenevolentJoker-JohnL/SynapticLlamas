"""
Result Aggregation for Distributed Execution

Provides strategies for merging results from parallel task execution.
Supports common patterns like collection, voting, consensus, and best-result selection.
"""
import logging
from collections import Counter
from typing import List, Any, Optional
from .tasks import TaskResult

logger = logging.getLogger(__name__)


class ResultAggregator:
    """
    Aggregates results from distributed task execution.

    Provides multiple strategies for combining results from parallel execution:
    - collect: Return all results as a list
    - vote: Return most common result (majority voting)
    - merge: Concatenate all results
    - best: Return fastest/best result
    - consensus: Return result only if consensus threshold met
    """

    def merge(self, results: List[TaskResult], strategy: str) -> Any:
        """
        Merge results using specified strategy.

        Args:
            results: List of TaskResult objects
            strategy: Merge strategy name

        Returns:
            Merged result based on strategy

        Raises:
            ValueError: If strategy is unknown
        """
        strategies = {
            "collect": self._collect,
            "vote": self._vote,
            "merge": self._merge,
            "best": self._best,
            "consensus": self._consensus
        }

        if strategy not in strategies:
            raise ValueError(
                f"Unknown merge strategy '{strategy}'. "
                f"Available: {', '.join(strategies.keys())}"
            )

        return strategies[strategy](results)

    def _collect(self, results: List[TaskResult]) -> List[Any]:
        """
        Return all successful results as a list.

        Args:
            results: Task results

        Returns:
            List of all successful results
        """
        successful = [r for r in results if r.success]
        return [r.result for r in successful]

    def _vote(self, results: List[TaskResult]) -> Any:
        """
        Return most common result (majority voting).

        Useful for consensus when multiple agents process the same task.

        Args:
            results: Task results

        Returns:
            Most common result, or first result if tie
        """
        successful = [r for r in results if r.success]

        if not successful:
            return None

        # Convert results to strings for comparison
        result_strings = [str(r.result) for r in successful]
        most_common_str = Counter(result_strings).most_common(1)[0][0]

        # Find the actual result object that matches
        for r in successful:
            if str(r.result) == most_common_str:
                logger.info(f"📊 Vote result: {most_common_str[:50]}... (from {len(successful)} results)")
                return r.result

        return successful[0].result

    def _merge(self, results: List[TaskResult]) -> str:
        """
        Concatenate all results as a string.

        Useful for combining multiple perspectives or analyses.

        Args:
            results: Task results

        Returns:
            Concatenated string of all results
        """
        successful = [r for r in results if r.success]

        if not successful:
            return ""

        merged = "\n\n---\n\n".join(str(r.result) for r in successful)
        logger.info(f"📝 Merged {len(successful)} results ({len(merged)} chars)")
        return merged

    def _best(self, results: List[TaskResult]) -> Any:
        """
        Return result from fastest/best execution.

        Selects based on duration (fastest) or could be extended
        to include quality metrics.

        Args:
            results: Task results

        Returns:
            Result from fastest successful execution
        """
        successful = [r for r in results if r.success]

        if not successful:
            return None

        best = min(successful, key=lambda r: r.duration_ms)
        logger.info(
            f"🏆 Best result from {best.node_url} "
            f"({best.duration_ms:.0f}ms, {len(successful)} candidates)"
        )
        return best.result

    def _consensus(
        self,
        results: List[TaskResult],
        threshold: float = 0.6
    ) -> Optional[Any]:
        """
        Return result only if consensus threshold is met.

        Requires a minimum percentage of results to agree.

        Args:
            results: Task results
            threshold: Minimum agreement fraction (0.0-1.0)

        Returns:
            Consensus result if threshold met, None otherwise
        """
        successful = [r for r in results if r.success]

        if not successful:
            return None

        # Count occurrences
        result_strings = [str(r.result) for r in successful]
        counts = Counter(result_strings)
        most_common_str, count = counts.most_common(1)[0]

        # Check if consensus threshold is met
        agreement_rate = count / len(successful)

        if agreement_rate >= threshold:
            # Find the actual result object
            for r in successful:
                if str(r.result) == most_common_str:
                    logger.info(
                        f"✅ Consensus reached: {agreement_rate:.1%} agreement "
                        f"({count}/{len(successful)} results)"
                    )
                    return r.result

        logger.warning(
            f"❌ Consensus failed: {agreement_rate:.1%} < {threshold:.1%} "
            f"(threshold not met)"
        )
        return None

    def quality_weighted_merge(
        self,
        results: List[TaskResult],
        quality_scores: List[float]
    ) -> Any:
        """
        Merge results weighted by quality scores.

        Advanced merging that considers result quality in addition
        to success/failure.

        Args:
            results: Task results
            quality_scores: Quality score for each result (0.0-1.0)

        Returns:
            Highest quality result
        """
        if len(results) != len(quality_scores):
            raise ValueError("Number of results must match number of quality scores")

        successful = [
            (r, q) for r, q in zip(results, quality_scores)
            if r.success and q > 0
        ]

        if not successful:
            return None

        # Select highest quality result
        best_result, best_quality = max(successful, key=lambda x: x[1])

        logger.info(
            f"🌟 Quality-weighted result: score={best_quality:.2f} "
            f"from {best_result.node_url}"
        )

        return best_result.result

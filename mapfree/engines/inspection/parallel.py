"""
Lightweight parallel execution helper using concurrent.futures.
Fallback to sequential on error or when max_workers < 2.
"""
import logging
from concurrent import futures
from typing import Callable, Iterable, List, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class ParallelExecutor:
    """
    Run a function over an iterable in parallel. Uses ThreadPoolExecutor.
    Falls back to sequential execution on error or if max_workers < 2.
    """

    @staticmethod
    def run_parallel(
        function: Callable[[T], R],
        iterable: Iterable[T],
        max_workers: int = 4,
    ) -> List[R]:
        """
        Apply function to each item in iterable in parallel.

        Args:
            function: Callable that takes one element and returns a result.
            iterable: Items to process.
            max_workers: Maximum worker threads (default 4). If < 2, runs sequentially.

        Returns:
            List of results in same order as iterable.
        """
        items = list(iterable)
        if not items:
            return []
        if max_workers < 2:
            return [function(x) for x in items]
        try:
            with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                return list(executor.map(function, items))
        except Exception as e:
            logger.warning("Parallel execution failed, falling back to sequential: %s", e)
            return [function(x) for x in items]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = ParallelExecutor.run_parallel(lambda x: x * 2, [1, 2, 3, 4, 5], max_workers=2)
    assert results == [2, 4, 6, 8, 10]
    logger.info("ParallelExecutor manual test passed.")

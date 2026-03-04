"""Tests for mapfree.engines.inspection.parallel.ParallelExecutor."""
from mapfree.engines.inspection.parallel import ParallelExecutor


class TestParallelExecutor:
    def test_empty_iterable(self):
        result = ParallelExecutor.run_parallel(lambda x: x, [])
        assert result == []

    def test_sequential_when_max_workers_lt_2(self):
        result = ParallelExecutor.run_parallel(lambda x: x * 2, [1, 2, 3], max_workers=1)
        assert result == [2, 4, 6]

    def test_parallel_execution(self):
        result = ParallelExecutor.run_parallel(lambda x: x * 3, [1, 2, 3, 4], max_workers=2)
        assert result == [3, 6, 9, 12]

    def test_order_preserved(self):
        result = ParallelExecutor.run_parallel(lambda x: x ** 2, list(range(10)), max_workers=4)
        assert result == [x ** 2 for x in range(10)]

    def test_single_item(self):
        result = ParallelExecutor.run_parallel(lambda x: x + 10, [5], max_workers=4)
        assert result == [15]

    def test_fallback_on_error(self, monkeypatch):
        """If ThreadPoolExecutor raises, should fall back to sequential."""

        def bad_executor(*args, **kwargs):
            raise RuntimeError("forced failure")

        monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor", bad_executor)
        result = ParallelExecutor.run_parallel(lambda x: x * 2, [1, 2, 3], max_workers=4)
        assert result == [2, 4, 6]

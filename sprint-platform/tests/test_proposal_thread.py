"""Tests that the proposal page does not spawn duplicate fill threads."""
import pytest
import threading
from routes.proposals import _active_fill_threads, _should_spawn_fill, _fill_done


def setup_function():
    _active_fill_threads.clear()


def test_first_load_spawns_thread():
    assert _should_spawn_fill("sprint-abc") is True


def test_second_load_skips_thread():
    _should_spawn_fill("sprint-abc")
    assert _should_spawn_fill("sprint-abc") is False


def test_different_sprint_can_spawn():
    _should_spawn_fill("sprint-abc")
    assert _should_spawn_fill("sprint-xyz") is True


def test_fill_done_allows_new_thread():
    _should_spawn_fill("sprint-abc")
    _fill_done("sprint-abc")
    assert _should_spawn_fill("sprint-abc") is True


def test_thread_safety_concurrent_access():
    results = []
    def worker(sprint_id):
        result = _should_spawn_fill(sprint_id)
        results.append(result)
    threads = [threading.Thread(target=worker, args=(f"sprint-{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert all(results), f"Not all workers succeeded: {results}"
    assert len(_active_fill_threads) == 10

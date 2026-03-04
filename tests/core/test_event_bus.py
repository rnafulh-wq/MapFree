"""
Comprehensive unit tests for mapfree.core.event_bus.EventBus.

Test cases:
1. test_subscribe_and_emit
2. test_multiple_subscribers
3. test_unsubscribe
4. test_emit_with_data
5. test_thread_safety
6. test_emit_unknown_event
7. test_subscriber_exception_isolation
"""
import threading

import pytest

from mapfree.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# 1. Subscribe and emit
# ---------------------------------------------------------------------------

def test_subscribe_and_emit():
    """Subscribed callback receives the emitted event."""
    bus = EventBus()
    received = []

    def on_event(name, data):
        received.append((name, data))

    bus.subscribe("test_event", on_event)
    bus.emit("test_event", {"key": "value"})

    assert len(received) == 1
    assert received[0] == ("test_event", {"key": "value"})


# ---------------------------------------------------------------------------
# 2. Multiple subscribers
# ---------------------------------------------------------------------------

def test_multiple_subscribers():
    """Two subscribers both receive the same emitted event."""
    bus = EventBus()
    calls_a = []
    calls_b = []

    bus.subscribe("ping", lambda n, d: calls_a.append(d))
    bus.subscribe("ping", lambda n, d: calls_b.append(d))

    bus.emit("ping", 42)

    assert calls_a == [42]
    assert calls_b == [42]


# ---------------------------------------------------------------------------
# 3. Unsubscribe
# ---------------------------------------------------------------------------

def test_unsubscribe():
    """After unsubscribe, the callback no longer receives events."""
    bus = EventBus()
    received = []

    def handler(name, data):
        received.append(data)

    bus.subscribe("evt", handler)
    bus.emit("evt", "first")
    bus.unsubscribe("evt", handler)
    bus.emit("evt", "second")

    assert received == ["first"]


def test_unsubscribe_nonexistent_is_safe():
    """Unsubscribing a callback that was never subscribed must not raise."""
    bus = EventBus()
    bus.unsubscribe("does_not_exist", lambda n, d: None)  # must not raise


# ---------------------------------------------------------------------------
# 4. Emit with data (various payload types)
# ---------------------------------------------------------------------------

def test_emit_with_data():
    """Payload is forwarded unchanged to subscribers."""
    bus = EventBus()
    payloads_received = []

    bus.subscribe("data_event", lambda n, d: payloads_received.append(d))

    test_payloads = [
        {"progress": 0.5, "stage": "sparse"},
        [1, 2, 3],
        "plain string",
        None,
        99,
    ]
    for p in test_payloads:
        bus.emit("data_event", p)

    assert payloads_received == test_payloads


# ---------------------------------------------------------------------------
# 5. Thread safety
# ---------------------------------------------------------------------------

def test_thread_safety():
    """Emitting from 10 concurrent threads does not cause race conditions."""
    bus = EventBus()
    received = []
    lock = threading.Lock()
    n_threads = 10
    n_events_per_thread = 50
    barrier = threading.Barrier(n_threads)

    def handler(name, data):
        with lock:
            received.append(data)

    bus.subscribe("concurrent", handler)

    def worker():
        barrier.wait()  # all threads start emitting at the same time
        for i in range(n_events_per_thread):
            bus.emit("concurrent", i)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(received) == n_threads * n_events_per_thread, (
        f"Expected {n_threads * n_events_per_thread} events, got {len(received)}"
    )


# ---------------------------------------------------------------------------
# 6. Emit unknown event (no subscribers)
# ---------------------------------------------------------------------------

def test_emit_unknown_event():
    """Emitting an event with no subscribers must not raise an exception."""
    bus = EventBus()
    bus.emit("no_one_is_listening", {"ignored": True})  # must not raise


# ---------------------------------------------------------------------------
# 7. Subscriber exception isolation
# ---------------------------------------------------------------------------

def test_subscriber_exception_isolation():
    """Exception in one subscriber must not prevent other subscribers from running."""
    bus = EventBus()
    calls = []

    def bad_handler(name, data):
        raise RuntimeError("subscriber crash")

    def good_handler(name, data):
        calls.append(data)

    bus.subscribe("isolated", bad_handler)
    bus.subscribe("isolated", good_handler)

    # Must not raise even though bad_handler raises
    bus.emit("isolated", "payload")

    assert calls == ["payload"], (
        "good_handler should have been called even after bad_handler raised"
    )


# ---------------------------------------------------------------------------
# Bonus: subscribe / unsubscribe same callback multiple times
# ---------------------------------------------------------------------------

def test_subscribe_same_callback_twice():
    """The same callback can be registered twice and will fire twice per emit."""
    bus = EventBus()
    count = []

    def handler(n, d):
        count.append(1)

    bus.subscribe("dup", handler)
    bus.subscribe("dup", handler)
    bus.emit("dup")

    assert len(count) == 2


def test_unsubscribe_removes_only_one_occurrence():
    """Unsubscribe removes exactly one registration when the same callback is subscribed twice."""
    bus = EventBus()
    count = []

    def handler(n, d):
        count.append(1)

    bus.subscribe("dup", handler)
    bus.subscribe("dup", handler)
    bus.unsubscribe("dup", handler)
    bus.emit("dup")

    assert len(count) == 1

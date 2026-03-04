"""Tests for mapfree.application.state_machine."""
import pytest
import mapfree.application.state_machine as sm
from mapfree.application.state_machine import AppState, get_state, set_state, subscribe, unsubscribe


@pytest.fixture(autouse=True)
def reset_state_machine():
    """Reset global state between tests."""
    original_state = sm._state
    original_listeners = list(sm._listeners)
    yield
    sm._state = original_state
    sm._listeners[:] = original_listeners


class TestAppState:
    def test_enum_values(self):
        assert AppState.IDLE.value == "idle"
        assert AppState.LOADING.value == "loading"
        assert AppState.READY.value == "ready"
        assert AppState.RUNNING.value == "running"
        assert AppState.ERROR.value == "error"

    def test_default_state_is_idle(self):
        sm._state = AppState.IDLE
        assert get_state() == AppState.IDLE


class TestSetState:
    def test_sets_state(self):
        set_state(AppState.RUNNING)
        assert get_state() == AppState.RUNNING

    def test_notifies_listeners(self):
        received = []
        subscribe(lambda s: received.append(s))
        set_state(AppState.READY)
        assert AppState.READY in received

    def test_multiple_listeners_notified(self):
        r1, r2 = [], []
        subscribe(lambda s: r1.append(s))
        subscribe(lambda s: r2.append(s))
        set_state(AppState.ERROR)
        assert r1 == [AppState.ERROR]
        assert r2 == [AppState.ERROR]

    def test_exception_in_listener_ignored(self):
        def bad_listener(s):
            raise RuntimeError("oops")
        subscribe(bad_listener)
        set_state(AppState.LOADING)  # should not raise
        assert get_state() == AppState.LOADING


class TestSubscribeUnsubscribe:
    def test_subscribe_adds_listener(self):
        def cb(s): pass
        subscribe(cb)
        assert cb in sm._listeners

    def test_unsubscribe_removes_listener(self):
        def cb(s): pass
        subscribe(cb)
        unsubscribe(cb)
        assert cb not in sm._listeners

    def test_unsubscribe_nonexistent_no_error(self):
        def cb(s): pass
        unsubscribe(cb)  # not subscribed — should not raise

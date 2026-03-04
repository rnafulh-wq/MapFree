"""Tests for mapfree.core.events.EventEmitter."""
from mapfree.core.events import Event, EventEmitter


class TestEvent:
    def test_creation(self):
        e = Event("started", message="hello", progress=0.5)
        assert e.type == "started"
        assert e.message == "hello"
        assert e.progress == 0.5

    def test_defaults_none(self):
        e = Event("tick")
        assert e.message is None
        assert e.progress is None


class TestEventEmitter:
    def test_on_and_emit(self):
        em = EventEmitter()
        received = []
        em.on("test", lambda **kw: received.append(kw))
        em.emit("test", key="value")
        assert received == [{"key": "value"}]

    def test_multiple_callbacks(self):
        em = EventEmitter()
        r1, r2 = [], []
        em.on("ev", lambda **kw: r1.append(kw))
        em.on("ev", lambda **kw: r2.append(kw))
        em.emit("ev", x=1)
        assert r1 == [{"x": 1}]
        assert r2 == [{"x": 1}]

    def test_emit_unknown_event_no_error(self):
        em = EventEmitter()
        em.emit("nonexistent")  # no exception

    def test_off_specific_callback(self):
        em = EventEmitter()
        received = []

        def cb(**kw):
            received.append(kw)

        em.on("ev", cb)
        em.off("ev", cb)
        em.emit("ev", x=1)
        assert received == []

    def test_off_all_callbacks(self):
        em = EventEmitter()
        received = []
        em.on("ev", lambda **kw: received.append(kw))
        em.on("ev", lambda **kw: received.append(kw))
        em.off("ev")  # remove all
        em.emit("ev", x=1)
        assert received == []

    def test_off_unknown_event_no_error(self):
        em = EventEmitter()
        em.off("nonexistent")  # no exception

    def test_exception_in_handler_ignored(self):
        em = EventEmitter()

        def bad(**kw):
            raise RuntimeError("error")

        received = []
        em.on("ev", bad)
        em.on("ev", lambda **kw: received.append(kw))
        em.emit("ev", x=1)  # should not raise; second handler still called
        assert received == [{"x": 1}]

    def test_emit_with_no_payload(self):
        em = EventEmitter()
        received = []
        em.on("empty", lambda **kw: received.append(kw))
        em.emit("empty")
        assert received == [{}]

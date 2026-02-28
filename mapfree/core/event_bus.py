"""
Lightweight in-process event bus: subscribe/emit with thread-safe callbacks.
"""
import threading
from collections import defaultdict
from typing import Any, Callable

from .logger import get_logger

logger = get_logger("event_bus")


class EventBus:
    """
    Thread-safe event bus: event_name -> list of callbacks.
    Callbacks are invoked with (event_name, data); errors are caught and logged.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        """Register callback for event_name. Same callback can be subscribed multiple times."""
        with self._lock:
            self._handlers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        """Remove one occurrence of callback for event_name."""
        with self._lock:
            if event_name not in self._handlers:
                return
            try:
                self._handlers[event_name].remove(callback)
            except ValueError:
                pass
            if not self._handlers[event_name]:
                del self._handlers[event_name]

    def emit(self, event_name: str, data: Any = None) -> None:
        """Invoke all callbacks for event_name with (event_name, data). Errors are logged, not raised."""
        with self._lock:
            callbacks = list(self._handlers.get(event_name, ()))
        for cb in callbacks:
            try:
                cb(event_name, data)
            except Exception as e:
                logger.exception("EventBus callback error [%s]: %s", event_name, e)

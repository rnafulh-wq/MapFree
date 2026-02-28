"""Application state machine. Production stub."""

from enum import Enum
from typing import Callable


class AppState(Enum):
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"


_state = AppState.IDLE
_listeners: list[Callable[[AppState], None]] = []


def get_state() -> AppState:
    return _state


def set_state(s: AppState) -> None:
    global _state
    _state = s
    for cb in _listeners:
        try:
            cb(s)
        except Exception:
            pass


def subscribe(cb: Callable[[AppState], None]) -> None:
    _listeners.append(cb)


def unsubscribe(cb: Callable[[AppState], None]) -> None:
    if cb in _listeners:
        _listeners.remove(cb)

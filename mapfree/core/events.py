class Event:
    def __init__(self, type_, message=None, progress=None):
        self.type = type_
        self.message = message
        self.progress = progress


class EventEmitter:
    """
    Simple backend event hook system. Register callbacks with on(), emit with emit().
    No GUI dependency. Used by Pipeline to notify step start/end and pipeline life cycle.
    """
    def __init__(self):
        self._handlers = {}  # event_name -> list of callables

    def on(self, event_name: str, callback):
        """Register a callback for event_name. Callback receives keyword arguments from emit()."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(callback)

    def off(self, event_name: str, callback=None):
        """Remove one callback, or all callbacks for event_name if callback is None."""
        if event_name not in self._handlers:
            return
        if callback is None:
            self._handlers[event_name] = []
        else:
            self._handlers[event_name] = [h for h in self._handlers[event_name] if h != callback]

    def emit(self, event_name: str, **payload):
        """Invoke all callbacks registered for event_name with **payload."""
        for h in self._handlers.get(event_name, ()):
            try:
                h(**payload)
            except Exception:
                pass  # don't let one handler break others

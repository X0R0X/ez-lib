from collections.abc import Callable
from enum import Enum
from logging import Logger


# Reason for existence of this enum is typing, we can really use any enum or
# actually any object instance or class.
class AbstractEvent(Enum):
    pass


class EventDispatcher:
    def __init__(self, log: Logger = None):
        self._log = log

        self._listeners: dict[
            AbstractEvent, set[Callable[..., ...]]
        ] = {}

    @property
    def num_listeners(self):
        n = 0
        for _, callbacks in self._listeners.items():
            n += len(callbacks)
        return n

    def register_listener(
            self, event: AbstractEvent, callback: Callable[..., ...]
    ):
        s = self._listeners.get(event)
        if s is not None:
            if callback in s:
                if self._log:
                    self._log.warning(
                        f"EventDispatcher: Unable to register listener "
                        f"'{callback.__name__}' for event "
                        f"'{event}', already "
                        f"registered."
                    )
        else:
            self._listeners.setdefault(event, set()).add(callback)

    def unregister_listener(
            self, event: AbstractEvent, callback: Callable[..., ...]
    ):
        s = self._listeners.get(event)
        if s is not None:
            if callback in s:
                s.remove(callback)
                if len(s) == 0:
                    del self._listeners[event]
            else:
                self._log_non_existent_listener(event, callback)
        else:
            self._log_non_existent_listener(event, callback)

    def dispatch_event(self, event: AbstractEvent, *args, **kwargs):
        s = self._listeners.get(event).copy()

        if s:
            for callback in s:
                callback(*args, **kwargs)
        else:
            if self._log:
                self._log.debug(
                    "EventDispatcher: There are no registered listeners for "
                    f"event='{event}'"
                )

    def _log_non_existent_listener(
            self, event: AbstractEvent, callback: Callable[..., ...]
    ):
        if self._log:
            self._log.warning(
                f"EventDispatcher: Unable to unregister not registered "
                f"listener, event='{event}', callback='{callback.__name__}'"
            )

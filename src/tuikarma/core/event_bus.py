"""Async Pub/Sub Event Bus for TUIKarma."""

from __future__ import annotations
import asyncio
from typing import Callable, Coroutine, Dict, List, Type, TypeVar, Any
import inspect
import logging

from tuikarma.core.events import BaseEvent

logger = logging.getLogger("tuikarma.bus")
T = TypeVar("T", bound=BaseEvent)
AsyncHandler = Callable[[T], Coroutine[Any, Any, None]]
SyncHandler = Callable[[T], None]


class EventBus:
    """Thread-safe and async-compatible Pub/Sub Event Bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[Type[BaseEvent], List[Callable[[Any], Any]]] = {}
        self._history: List[BaseEvent] = []
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: Type[T], handler: Callable[[T], Any]) -> None:
        """Register a subscriber callback for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[T], handler: Callable[[T], Any]) -> None:
        """Unregister a subscriber callback for an event type."""
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)


    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all registered subscribers."""
        async with self._lock:
            self._history.append(event)

        event_type = type(event)
        handlers = []

        # Find matching handlers (including superclasses)
        for sub_type, sub_handlers in self._subscribers.items():
            if issubclass(event_type, sub_type):
                handlers.extend(sub_handlers)

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error handling event {event_type.__name__}: {e}", exc_info=True)

    def get_history(self) -> List[BaseEvent]:
        """Return the complete trajectory history of all events."""
        return list(self._history)

    def clear(self) -> None:
        """Reset the bus history."""
        self._history.clear()

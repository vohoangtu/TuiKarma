"""Trajectory Recorder and Replay Engine (JSONL standard) for TUIKarma."""

from __future__ import annotations
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from tuikarma.core.events import (
    BaseEvent,
    MessageEvent,
    StateChangeEvent,
    ToolCallEvent,
    ToolResultEvent,
    MetricsEvent,
    EvaluationResultEvent,
    WorkflowStartedEvent,
    WorkflowNodeStartedEvent,
    WorkflowNodeCompletedEvent,
    WorkflowTransitionEvent,
    WorkflowCompletedEvent,
    WorkflowNodeRetryEvent,
    WorkflowFailedEvent,
    WorkflowRollbackStartedEvent,
    WorkflowNodeRollbackEvent,
    WorkflowRollbackCompletedEvent,
)
from tuikarma.core.event_bus import EventBus

EVENT_CLASS_MAP = {
    "MessageEvent": MessageEvent,
    "StateChangeEvent": StateChangeEvent,
    "ToolCallEvent": ToolCallEvent,
    "ToolResultEvent": ToolResultEvent,
    "MetricsEvent": MetricsEvent,
    "EvaluationResultEvent": EvaluationResultEvent,
    "WorkflowStartedEvent": WorkflowStartedEvent,
    "WorkflowNodeStartedEvent": WorkflowNodeStartedEvent,
    "WorkflowNodeCompletedEvent": WorkflowNodeCompletedEvent,
    "WorkflowTransitionEvent": WorkflowTransitionEvent,
    "WorkflowCompletedEvent": WorkflowCompletedEvent,
    "WorkflowNodeRetryEvent": WorkflowNodeRetryEvent,
    "WorkflowFailedEvent": WorkflowFailedEvent,
    "WorkflowRollbackStartedEvent": WorkflowRollbackStartedEvent,
    "WorkflowNodeRollbackEvent": WorkflowNodeRollbackEvent,
    "WorkflowRollbackCompletedEvent": WorkflowRollbackCompletedEvent,
}


class TrajectoryRecorder:
    """Listens to the EventBus and serializes all events to a JSONL trace file."""

    def __init__(self, bus: EventBus, output_dir: Optional[Path] = None) -> None:
        self.bus = bus
        self.output_dir = output_dir or (Path.cwd() / "traces")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.trace_file = self.output_dir / f"session_{timestamp}.jsonl"
        self._lock = asyncio.Lock()

        # Subscribe to all event classes
        for event_cls in EVENT_CLASS_MAP.values():
            self.bus.subscribe(event_cls, self._record_event)

    async def _record_event(self, event: BaseEvent) -> None:
        async with self._lock:
            payload = {
                "event_type": event.__class__.__name__,
                "data": json.loads(event.model_dump_json()),
            }
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")


class TrajectoryReplayer:
    """Reads a previously recorded session JSONL file and plays it back onto the EventBus."""

    def __init__(self, trace_file: Path, bus: EventBus, delay_seconds: float = 0.5) -> None:
        self.trace_file = trace_file
        self.bus = bus
        self.delay_seconds = delay_seconds

    async def replay(self) -> int:
        """Plays back all events from the trace file onto the bus."""
        if not self.trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {self.trace_file}")

        events_played = 0
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                event_type = item.get("event_type")
                data = item.get("data", {})

                cls = EVENT_CLASS_MAP.get(event_type)
                if cls:
                    event_instance = cls(**data)
                    await self.bus.publish(event_instance)
                    events_played += 1
                    await asyncio.sleep(self.delay_seconds)

        return events_played

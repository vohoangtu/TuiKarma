"""Workflow edge and transition rules for graph traversal."""

from __future__ import annotations
import inspect
from typing import Optional, Callable, Awaitable, Union
from tuikarma.workflow.state import WorkflowState


class WorkflowEdge:
    """Represents a directional connection between two nodes with optional guard condition."""

    def __init__(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Callable[[WorkflowState], Union[bool, Awaitable[bool]]]] = None,
        name: str = "",
    ) -> None:
        self.from_node = from_node
        self.to_node = to_node
        self.condition = condition
        self.name = name or f"{from_node} -> {to_node}"

    async def can_traverse(self, state: WorkflowState) -> bool:
        """Evaluates whether this edge can be traversed given the current state."""
        if self.condition is None:
            return True

        if inspect.iscoroutinefunction(self.condition):
            return await self.condition(state)
        return self.condition(state)

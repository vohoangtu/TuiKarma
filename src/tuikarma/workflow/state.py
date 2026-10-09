"""Workflow state and node execution results for TUIKarma Workflow Engine."""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class NodeResult(BaseModel):
    """Result returned by executing a single workflow node."""
    node_id: str
    success: bool = True
    output: Any = None
    next_node_override: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    """Shared mutable execution state passed across workflow nodes (Blackboard pattern)."""
    task_id: str = "DEFAULT"
    task_description: str = ""
    current_node_id: Optional[str] = None
    step_count: int = 0
    max_steps: int = 15
    is_failed: bool = False
    error_message: Optional[str] = None

    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    iterations: Dict[str, int] = Field(default_factory=dict)  # Count executions per node
    completed_nodes: List[str] = Field(default_factory=list)  # Chronological order of successful nodes
    rolled_back_nodes: List[str] = Field(default_factory=list)  # Nodes that underwent compensation
    checkpoints: Dict[str, Any] = Field(default_factory=dict)  # Snapshots for rollbacks
    shared_data: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)

    def get_output(self, node_id: str, default: Any = None) -> Any:
        return self.node_outputs.get(node_id, default)

    def set_output(self, node_id: str, output: Any) -> None:
        self.node_outputs[node_id] = output

    def get_shared(self, key: str, default: Any = None) -> Any:
        return self.shared_data.get(key, default)

    def set_shared(self, key: str, value: Any) -> None:
        self.shared_data[key] = value

    def mark_completed(self, node_id: str) -> None:
        if node_id not in self.completed_nodes:
            self.completed_nodes.append(node_id)

    def record_checkpoint(self, node_id: str, snapshot: Any) -> None:
        self.checkpoints[node_id] = snapshot

    def increment_iteration(self, node_id: str) -> int:
        count = self.iterations.get(node_id, 0) + 1
        self.iterations[node_id] = count
        return count

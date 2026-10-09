"""Typed async event definitions for TUIKarma multi-agent communication."""

from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import uuid


class AgentState(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    CALLING_TOOL = "CALLING_TOOL"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class AgentRole(str, Enum):
    SUPERVISOR = "SUPERVISOR"
    CODER = "CODER"
    TESTER = "TESTER"
    REVIEWER = "REVIEWER"
    RESEARCHER = "RESEARCHER"


class BaseEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.now)


class MessageEvent(BaseEvent):
    sender: str
    receiver: str = "ALL"  # "ALL" for broadcast, or specific agent name
    content: str
    is_thought: bool = False  # Chain-of-Thought reasoning
    step_index: int = 0


class ToolCallEvent(BaseEvent):
    agent_name: str
    tool_name: str
    arguments: Dict[str, Any]
    requires_approval: bool = False


class ToolResultEvent(BaseEvent):
    agent_name: str
    tool_name: str
    result: str
    is_error: bool = False
    duration_ms: float = 0.0


class StateChangeEvent(BaseEvent):
    agent_name: str
    old_state: AgentState
    new_state: AgentState
    details: Optional[str] = None


class MetricsEvent(BaseEvent):
    step: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float


class HITLAction(str, Enum):
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STEP = "STEP"
    INJECT = "INJECT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class HITLCommandEvent(BaseEvent):
    action: HITLAction
    payload: Optional[str] = None


class ToolApprovalRequestEvent(BaseEvent):
    agent_name: str
    tool_name: str
    arguments: Dict[str, Any]
    reason: str = "Thao tác yêu cầu phê duyệt bảo mật trước khi thực thi."


class ToolApprovalResponseEvent(BaseEvent):
    tool_name: str
    approved: bool
    reason: Optional[str] = None


class EvaluationResultEvent(BaseEvent):
    task_id: str
    score: float  # 0.0 - 1.0 (hoặc 0 - 100%)
    passed: bool
    criteria_scores: Dict[str, float] = Field(default_factory=dict)
    feedback: str = ""


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStartedEvent(BaseEvent):
    workflow_name: str
    total_nodes: int


class WorkflowNodeStartedEvent(BaseEvent):
    node_id: str
    node_type: str
    agent_name: Optional[str] = None
    iteration: int = 1


class WorkflowNodeCompletedEvent(BaseEvent):
    node_id: str
    status: str
    output_summary: str
    duration_ms: float = 0.0


class WorkflowTransitionEvent(BaseEvent):
    from_node: str
    to_node: str
    reason: Optional[str] = None


class WorkflowCompletedEvent(BaseEvent):
    workflow_name: str
    total_steps: int
    success: bool
    duration_ms: float = 0.0


class WorkflowNodeRetryEvent(BaseEvent):
    node_id: str
    attempt: int
    max_retries: int
    delay_seconds: float
    error_reason: str


class WorkflowFailedEvent(BaseEvent):
    workflow_name: str
    failed_node_id: str
    error_message: str


class WorkflowRollbackStartedEvent(BaseEvent):
    workflow_name: str
    failed_node_id: str
    nodes_to_rollback: List[str] = Field(default_factory=list)


class WorkflowNodeRollbackEvent(BaseEvent):
    node_id: str
    status: str  # "STARTING", "COMPLETED", "FAILED"
    details: Optional[str] = None


class WorkflowRollbackCompletedEvent(BaseEvent):
    workflow_name: str
    success: bool
    rolled_back_nodes: List[str] = Field(default_factory=list)

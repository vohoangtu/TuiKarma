"""Workflow node definitions for TUIKarma (Agent Nodes, Decision Nodes, Tool Nodes)."""

from __future__ import annotations
import time
import inspect
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable, Union

from tuikarma.core.agent import Agent
from tuikarma.core.events import MetricsEvent
from tuikarma.tools.base import BaseTool
from tuikarma.workflow.state import WorkflowState, NodeResult


class BaseWorkflowNode(ABC):
    """Abstract base class for nodes in the workflow execution graph with retry and rollback."""

    def __init__(
        self,
        node_id: str,
        name: str,
        node_type: str = "custom",
        max_retries: int = 3,
        retry_delay_seconds: float = 30.0,
        rollback_handler: Optional[Callable[[WorkflowState], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.rollback_handler = rollback_handler

    @abstractmethod
    async def execute(self, state: WorkflowState) -> NodeResult:
        """Executes node logic and returns NodeResult."""
        pass

    async def rollback(self, state: WorkflowState) -> None:
        """Compensating transaction to undo actions performed by this node."""
        if self.rollback_handler:
            if inspect.iscoroutinefunction(self.rollback_handler):
                await self.rollback_handler(state)
            else:
                self.rollback_handler(state)
        else:
            # Default rollback: revert node output
            if self.node_id in state.node_outputs:
                del state.node_outputs[self.node_id]


class AgentWorkflowNode(BaseWorkflowNode):
    """Executes an AI Agent with contextual prompt rendering and tool usage."""

    def __init__(
        self,
        node_id: str,
        name: str,
        agent: Agent,
        prompt_template: Optional[str] = None,
        prompt_builder: Optional[Callable[[WorkflowState], str]] = None,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 30.0,
        rollback_handler: Optional[Callable[[WorkflowState], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            name=name,
            node_type="agent",
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            rollback_handler=rollback_handler,
        )
        self.agent = agent
        self.model_name = model_name
        self.prompt_template = prompt_template
        self.prompt_builder = prompt_builder

    async def execute(self, state: WorkflowState) -> NodeResult:
        if self.prompt_builder:
            prompt = self.prompt_builder(state)
        elif self.prompt_template:
            context_dict = {
                "task_description": state.task_description,
                **state.node_outputs,
                **state.shared_data,
            }
            prompt = self.prompt_template
            for k, v in context_dict.items():
                placeholder = f"{{{k}}}"
                if placeholder in prompt:
                    prompt = prompt.replace(placeholder, str(v))
        else:
            prompt = f"Thực hiện bước {self.name} cho nhiệm vụ: {state.task_description}"

        start_time = time.monotonic()
        try:
            response = await self.agent.think_and_act(
                prompt,
                step=state.step_count,
                model_override=self.model_name
            )
            output_content = response.content or (response.thought or "")
            latency_ms = (time.monotonic() - start_time) * 1000.0

            await self.agent.bus.publish(
                MetricsEvent(
                    step=state.step_count,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                    cost_usd=response.cost_usd,
                    latency_ms=latency_ms
                )
            )

            # Check if agent reported an error in output
            if "[Local Gateway Error]" in output_content:
                return NodeResult(
                    node_id=self.node_id,
                    success=False,
                    output=output_content,
                    error_message=output_content
                )

            return NodeResult(
                node_id=self.node_id,
                success=True,
                output=output_content,
                metadata={
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "tool_calls_count": len(response.tool_calls),
                }
            )
        except Exception as e:
            return NodeResult(
                node_id=self.node_id,
                success=False,
                output=str(e),
                error_message=str(e)
            )


class DecisionWorkflowNode(BaseWorkflowNode):
    """Evaluates dynamic branching conditions to route to next node."""

    def __init__(
        self,
        node_id: str,
        name: str,
        decision_fn: Callable[[WorkflowState], Union[str, Awaitable[str]]],
        max_retries: int = 1,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        super().__init__(
            node_id=node_id,
            name=name,
            node_type="decision",
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        self.decision_fn = decision_fn

    async def execute(self, state: WorkflowState) -> NodeResult:
        try:
            if inspect.iscoroutinefunction(self.decision_fn):
                next_node = await self.decision_fn(state)
            else:
                next_node = self.decision_fn(state)

            return NodeResult(
                node_id=self.node_id,
                success=True,
                output=f"Branching to node '{next_node}'",
                next_node_override=next_node
            )
        except Exception as e:
            return NodeResult(
                node_id=self.node_id,
                success=False,
                output=str(e),
                error_message=str(e)
            )


class ToolWorkflowNode(BaseWorkflowNode):
    """Directly executes a tool in the workflow without requiring LLM inference."""

    def __init__(
        self,
        node_id: str,
        name: str,
        tool: BaseTool,
        args_builder: Callable[[WorkflowState], Dict[str, Any]],
        max_retries: int = 3,
        retry_delay_seconds: float = 30.0,
        rollback_handler: Optional[Callable[[WorkflowState], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            name=name,
            node_type="tool",
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            rollback_handler=rollback_handler,
        )
        self.tool = tool
        self.args_builder = args_builder

    async def execute(self, state: WorkflowState) -> NodeResult:
        args = self.args_builder(state)
        try:
            raw_result = await self.tool.execute(**args)
            return NodeResult(
                node_id=self.node_id,
                success=True,
                output=str(raw_result),
                metadata={"tool_name": self.tool.name, "args": args}
            )
        except Exception as e:
            return NodeResult(
                node_id=self.node_id,
                success=False,
                output=f"Error executing tool '{self.tool.name}': {e}",
                error_message=str(e),
                metadata={"tool_name": self.tool.name, "error": str(e)}
            )

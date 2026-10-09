"""Workflow node definitions for TUIKarma (Agent Nodes, Decision Nodes, Tool Nodes)."""

from __future__ import annotations
import time
import inspect
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable, Union, List

from tuikarma.core.agent import Agent
from tuikarma.core.event_bus import EventBus
from tuikarma.core.events import (
    MetricsEvent,
    HITLApprovalRequestEvent,
    HITLApprovalResponseEvent,
    HITLCommandEvent,
    HITLAction,
)
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


class ParallelWorkflowNode(BaseWorkflowNode):
    """Executes multiple child workflow nodes concurrently (Async Fork-Join pattern)."""

    def __init__(
        self,
        node_id: str,
        name: str,
        branches: List[BaseWorkflowNode],
        max_retries: int = 3,
        retry_delay_seconds: float = 30.0,
        rollback_handler: Optional[Callable[[WorkflowState], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            name=name,
            node_type="parallel",
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            rollback_handler=rollback_handler,
        )
        self.branches = branches

    async def execute(self, state: WorkflowState) -> NodeResult:
        """Executes all branch nodes concurrently via asyncio.gather and aggregates outputs."""
        results = await asyncio.gather(
            *(branch.execute(state) for branch in self.branches),
            return_exceptions=True
        )

        combined_outputs: Dict[str, Any] = {}
        all_success = True
        error_messages: List[str] = []

        for branch, res in zip(self.branches, results):
            if isinstance(res, Exception):
                all_success = False
                err_str = f"Branch '{branch.node_id}' raised exception: {res}"
                error_messages.append(err_str)
                state.set_output(branch.node_id, f"Error: {res}")
            elif isinstance(res, NodeResult):
                state.set_output(branch.node_id, res.output)
                combined_outputs[branch.node_id] = res.output
                if not res.success:
                    all_success = False
                    error_messages.append(f"Branch '{branch.node_id}': {res.error_message or 'Failed'}")
                else:
                    state.mark_completed(branch.node_id)
            else:
                combined_outputs[branch.node_id] = res

        if not all_success:
            return NodeResult(
                node_id=self.node_id,
                success=False,
                output=combined_outputs,
                error_message="; ".join(error_messages)
            )

        return NodeResult(
            node_id=self.node_id,
            success=True,
            output=combined_outputs,
            metadata={"branches": [b.node_id for b in self.branches]}
        )

    async def rollback(self, state: WorkflowState) -> None:
        """Compensates all parallel branches in reverse order."""
        if self.rollback_handler:
            if inspect.iscoroutinefunction(self.rollback_handler):
                await self.rollback_handler(state)
            else:
                self.rollback_handler(state)
        else:
            for branch in reversed(self.branches):
                await branch.rollback(state)
            if self.node_id in state.node_outputs:
                del state.node_outputs[self.node_id]


class HITLWorkflowNode(BaseWorkflowNode):
    """Workflow node that pauses execution until a human operator provides approval or guidance."""

    def __init__(
        self,
        node_id: str,
        name: str,
        prompt: str,
        bus: Optional[EventBus] = None,
        timeout_seconds: Optional[float] = None,
        auto_approve_in_headless: bool = True,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.0,
        rollback_handler: Optional[Callable[[WorkflowState], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            name=name,
            node_type="hitl",
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            rollback_handler=rollback_handler,
        )
        self.prompt = prompt
        self.bus = bus
        self.timeout_seconds = timeout_seconds
        self.auto_approve_in_headless = auto_approve_in_headless
        self._pending_future: Optional[asyncio.Future] = None

    def _format_prompt(self, state: WorkflowState) -> str:
        prompt_str = self.prompt
        for k, v in state.node_outputs.items():
            prompt_str = prompt_str.replace(f"{{{k}}}", str(v))
        for k, v in state.shared_data.items():
            prompt_str = prompt_str.replace(f"{{{k}}}", str(v))
        prompt_str = prompt_str.replace("{task_description}", state.task_description)
        return prompt_str

    async def execute(self, state: WorkflowState) -> NodeResult:
        formatted_prompt = self._format_prompt(state)

        # Quick auto-approval in automated headless execution mode
        if state.get_shared("headless_mode", False) and self.auto_approve_in_headless:
            out_msg = "Tự động phê duyệt theo chính sách Headless CI/CD"
            state.set_output(self.node_id, out_msg)
            return NodeResult(node_id=self.node_id, success=True, output=out_msg)

        state.set_shared("pending_hitl_node", self.node_id)
        state.set_shared("pending_hitl_prompt", formatted_prompt)

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_future = future

        async def on_approval_response(event: HITLApprovalResponseEvent) -> None:
            if event.node_id == self.node_id and not future.done():
                future.set_result((event.approved, event.guidance))

        async def on_hitl_command(event: HITLCommandEvent) -> None:
            if future.done():
                return
            if event.action == HITLAction.APPROVE:
                future.set_result((True, event.payload or "Approved by operator"))
            elif event.action == HITLAction.REJECT:
                future.set_result((False, event.payload or "Rejected by operator"))
            elif event.action == HITLAction.INJECT and event.payload:
                state.set_shared("hitl_guidance", event.payload)

        cleanup_handlers = []
        if self.bus:
            self.bus.subscribe(HITLApprovalResponseEvent, on_approval_response)
            self.bus.subscribe(HITLCommandEvent, on_hitl_command)
            cleanup_handlers.append((HITLApprovalResponseEvent, on_approval_response))
            cleanup_handlers.append((HITLCommandEvent, on_hitl_command))

            await self.bus.publish(
                HITLApprovalRequestEvent(
                    node_id=self.node_id,
                    prompt=formatted_prompt,
                    context={"outputs": state.node_outputs},
                    timeout_seconds=self.timeout_seconds,
                )
            )

        try:
            if self.timeout_seconds and self.timeout_seconds > 0:
                approved, guidance = await asyncio.wait_for(future, timeout=self.timeout_seconds)
            elif not self.bus and self.auto_approve_in_headless:
                approved, guidance = True, "Auto-approved in headless mode (no bus)"
            else:
                approved, guidance = await future
        except asyncio.TimeoutError:
            if self.auto_approve_in_headless:
                approved, guidance = True, f"Auto-approved after {self.timeout_seconds}s timeout"
            else:
                approved, guidance = False, f"Timed out after {self.timeout_seconds}s waiting for operator"
        except asyncio.CancelledError:
            approved, guidance = False, "Approval cancelled"
        finally:
            if self.bus:
                for evt_type, handler in cleanup_handlers:
                    self.bus.unsubscribe(evt_type, handler)
            if state.get_shared("pending_hitl_node") == self.node_id:
                state.shared_data.pop("pending_hitl_node", None)

        if approved:
            out_msg = guidance or "Approved by human operator"
            state.set_output(self.node_id, out_msg)
            return NodeResult(node_id=self.node_id, success=True, output=out_msg)
        else:
            err_msg = guidance or "Rejected by human operator"
            return NodeResult(
                node_id=self.node_id,
                success=False,
                output=err_msg,
                error_message=err_msg
            )

    async def rollback(self, state: WorkflowState) -> None:
        if self._pending_future and not self._pending_future.done():
            self._pending_future.cancel()
        state.shared_data.pop("pending_hitl_node", None)
        await super().rollback(state)


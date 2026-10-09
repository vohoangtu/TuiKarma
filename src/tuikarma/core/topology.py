"""Hybrid Hierarchical & Blackboard Multi-Agent Topology (2026 Best Practice)."""

from __future__ import annotations
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

from tuikarma.core.agent import Agent
from tuikarma.core.events import (
    AgentRole,
    AgentState,
    MetricsEvent,
    HITLAction,
    EvaluationResultEvent,
)
from tuikarma.core.event_bus import EventBus
from tuikarma.core.llm import BaseLLMProvider, get_default_llm_provider
from tuikarma.tools.base import ToolRegistry
from tuikarma.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
from tuikarma.tools.runner import ExecutePythonTool, RunCommandTool
from tuikarma.tools.graph import CodeGraphTool


class SwarmTopology:
    """Manages multi-agent hierarchy, coordination and execution lifecycle."""

    def __init__(
        self,
        bus: EventBus,
        workspace_dir: Optional[Path] = None,
        llm: Optional[BaseLLMProvider] = None,
    ) -> None:
        self.bus = bus
        self.workspace_dir = workspace_dir or (Path.cwd() / "sandbox_workspace")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm or get_default_llm_provider()

        self.tools = ToolRegistry()
        self._setup_tools()

        self.agents: Dict[str, Agent] = {}
        self.blackboard: Dict[str, Any] = {}
        self.active_workflow: Any = None
        self.is_paused = False
        self.step_event = asyncio.Event()
        self.step_event.set()  # Runs continuously by default

        self._setup_default_swarm()

    def _setup_tools(self) -> None:
        """Register sandboxed tools into central registry."""
        self.tools.register(ReadFileTool(workspace_root=self.workspace_dir))
        self.tools.register(WriteFileTool(workspace_root=self.workspace_dir))
        self.tools.register(ListDirTool(workspace_root=self.workspace_dir))
        self.tools.register(ExecutePythonTool(workspace_root=self.workspace_dir))
        self.tools.register(RunCommandTool(workspace_root=self.workspace_dir, requires_approval=True))
        self.tools.register(CodeGraphTool(workspace_root=self.workspace_dir))

    def _setup_default_swarm(self) -> None:
        """Initialize the standard modern swarm: Supervisor, Coder, Tester, Critic."""
        self.agents["Supervisor"] = Agent(
            name="Supervisor",
            role=AgentRole.SUPERVISOR,
            model_name="antigravity/claude-sonnet-4-6",
            system_prompt="Bạn là Supervisor Agent. Bạn phân rã nhiệm vụ, điều phối Coder, Tester, Critic và tổng hợp nghiệm thu bằng tiếng Việt.",
            bus=self.bus,
            tools=self.tools,
            llm=self.llm,
            color="magenta"
        )
        self.agents["Coder"] = Agent(
            name="Coder",
            role=AgentRole.CODER,
            model_name="antigravity/claude-sonnet-4-6",
            system_prompt="Bạn là Coder Agent. Bạn viết mã nguồn chuẩn, type annotation đầy đủ. Hãy sử dụng công cụ write_file để tạo mã nguồn vào sandbox.",
            bus=self.bus,
            tools=self.tools,
            llm=self.llm,
            color="green"
        )
        self.agents["Tester"] = Agent(
            name="Tester",
            role=AgentRole.TESTER,
            model_name="antigravity/gemini-3.1-flash-lite",
            system_prompt="Bạn là Tester Agent. Bạn tạo test suite và kiểm thử mã nguồn bằng pytest hoặc python runner.",
            bus=self.bus,
            tools=self.tools,
            llm=self.llm,
            color="yellow"
        )
        self.agents["Critic"] = Agent(
            name="Critic",
            role=AgentRole.REVIEWER,
            model_name="antigravity/claude-opus-4-6-thinking",
            system_prompt="Bạn là Critic Agent. Bạn phân tích kiến trúc, suy nghĩ kỹ lưỡng về bảo mật, edge cases và đưa ra kết luận chấp thuận.",
            bus=self.bus,
            tools=self.tools,
            llm=self.llm,
            color="cyan"
        )

    def set_paused(self, paused: bool) -> None:
        """Pause or resume swarm execution."""
        self.is_paused = paused
        if self.active_workflow:
            self.active_workflow.set_paused(paused)
        if not paused:
            self.step_event.set()
        else:
            self.step_event.clear()

    def step_forward(self) -> None:
        """Allow a single step forward during paused state."""
        if self.active_workflow:
            self.active_workflow.step_forward()
        self.step_event.set()

    async def _wait_if_paused(self) -> None:
        """Helper to pause execution until unpaused or single-stepped."""
        if self.is_paused:
            await self.step_event.wait()
            # If still paused after stepping, reset event for next step
            if self.is_paused:
                self.step_event.clear()

    async def execute_task_loop(self, task_description: str, max_iterations: int = 5) -> None:
        """Run the multi-agent collaboration loop through the Workflow Engine."""
        from tuikarma.workflow.builder import build_self_healing_coding_workflow
        from tuikarma.workflow.state import WorkflowState

        engine = build_self_healing_coding_workflow(self)
        self.active_workflow = engine
        engine.set_paused(self.is_paused)

        initial_state = WorkflowState(task_description=task_description, max_steps=12)
        await engine.execute(initial_state)

        # Mark all agents completed after workflow finishes
        for agent in self.agents.values():
            await agent.set_state(AgentState.COMPLETED)

    async def _emit_metrics(self, step: int, tokens_in: int, tokens_out: int, cost: float, latency: float) -> None:
        await self.bus.publish(
            MetricsEvent(
                step=step,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                latency_ms=latency
            )
        )

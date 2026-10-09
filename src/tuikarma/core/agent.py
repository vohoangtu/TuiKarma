"""Agent abstraction with sandboxed tool execution and LLM reasoning loop."""

from __future__ import annotations
import time
import asyncio
from typing import Optional, List, Dict, Any

from tuikarma.core.events import (
    AgentRole,
    AgentState,
    MessageEvent,
    StateChangeEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolApprovalRequestEvent,
)
from tuikarma.core.event_bus import EventBus
from tuikarma.core.llm import BaseLLMProvider, LLMResponse, get_default_llm_provider
from tuikarma.tools.base import ToolRegistry


class Agent:
    """Represents an autonomous collaborating agent equipped with tools and LLM reasoning."""

    def __init__(
        self,
        name: str,
        role: AgentRole,
        model_name: str,
        system_prompt: str,
        bus: EventBus,
        tools: Optional[ToolRegistry] = None,
        llm: Optional[BaseLLMProvider] = None,
        color: str = "cyan"
    ) -> None:
        self.name = name
        self.role = role
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.bus = bus
        self.tools = tools or ToolRegistry()
        self.llm = llm or get_default_llm_provider()
        self.color = color
        self.state = AgentState.IDLE
        self.memory: List[Dict[str, str]] = []

    async def set_state(self, new_state: AgentState, details: Optional[str] = None) -> None:
        """Update agent state and emit a StateChangeEvent."""
        old_state = self.state
        self.state = new_state
        await self.bus.publish(
            StateChangeEvent(
                agent_name=self.name,
                old_state=old_state,
                new_state=new_state,
                details=details
            )
        )

    async def speak(self, content: str, receiver: str = "ALL", is_thought: bool = False, step: int = 0) -> None:
        """Broadcast a message or internal reasoning chain."""
        self.memory.append({"role": "assistant" if not is_thought else "thought", "content": content})
        await self.bus.publish(
            MessageEvent(
                sender=self.name,
                receiver=receiver,
                content=content,
                is_thought=is_thought,
                step_index=step
            )
        )

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool via the sandboxed ToolRegistry or fallback simulation."""
        tool = self.tools.get(tool_name)
        requires_approval = tool.requires_approval if tool else False

        await self.set_state(AgentState.CALLING_TOOL, f"Chạy {tool_name}")
        await self.bus.publish(
            ToolCallEvent(
                agent_name=self.name,
                tool_name=tool_name,
                arguments=arguments,
                requires_approval=requires_approval
            )
        )

        if requires_approval:
            await self.bus.publish(
                ToolApprovalRequestEvent(
                    agent_name=self.name,
                    tool_name=tool_name,
                    arguments=arguments
                )
            )

        start_time = time.monotonic()
        is_error = False

        if tool:
            try:
                raw_result = await tool.execute(**arguments)
                result = str(raw_result)
            except Exception as e:
                is_error = True
                result = f"Error executing tool '{tool_name}': {e}"
        else:
            # Fallback simulated execution
            await asyncio.sleep(0.4)
            result = f"Simulated output of {tool_name} with {arguments}"

        duration_ms = (time.monotonic() - start_time) * 1000.0

        await self.bus.publish(
            ToolResultEvent(
                agent_name=self.name,
                tool_name=tool_name,
                result=result,
                is_error=is_error,
                duration_ms=duration_ms
            )
        )
        return result

    async def think_and_act(self, context: str, step: int = 0, model_override: Optional[str] = None) -> LLMResponse:
        """Execute one complete reasoning and action step for the agent."""
        await self.set_state(AgentState.THINKING)
        self.memory.append({"role": "user", "content": context})

        tools_schema = list(self.tools.list_tools().values()) if self.tools else None
        active_model = model_override or self.model_name

        response = await self.llm.generate(
            model_name=active_model,
            system_prompt=self.system_prompt,
            messages=self.memory,
            tools_schema=tools_schema
        )

        if response.thought:
            await self.speak(response.thought, is_thought=True, step=step)

        if response.content:
            await self.speak(response.content, step=step)

        for tc in response.tool_calls:
            await self.call_tool(tc.tool_name, tc.arguments)

        return response

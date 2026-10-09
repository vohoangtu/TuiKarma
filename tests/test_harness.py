"""Comprehensive unit tests for TUIKarma core, tools, evaluator, and trajectories."""

import pytest
import asyncio
from pathlib import Path

from tuikarma.core.event_bus import EventBus
from tuikarma.core.events import MessageEvent, AgentState, ToolCallEvent
from tuikarma.core.agent import Agent, AgentRole
from tuikarma.core.topology import SwarmTopology
from tuikarma.harness.task import TaskSpec, EvaluationCriterion
from tuikarma.harness.evaluator import TaskEvaluator
from tuikarma.harness.trajectory import TrajectoryRecorder, TrajectoryReplayer
from tuikarma.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool, resolve_sandboxed_path
from tuikarma.tools.runner import ExecutePythonTool


@pytest.mark.asyncio
async def test_event_bus_pub_sub():
    bus = EventBus()
    received = []

    async def on_message(event: MessageEvent):
        received.append(event)

    bus.subscribe(MessageEvent, on_message)

    msg = MessageEvent(sender="Tester", receiver="Coder", content="Hello test!")
    await bus.publish(msg)

    assert len(received) == 1
    assert received[0].content == "Hello test!"
    assert received[0].sender == "Tester"


@pytest.mark.asyncio
async def test_agent_state_transitions():
    bus = EventBus()
    agent = Agent(
        name="Coder",
        role=AgentRole.CODER,
        model_name="test-model",
        system_prompt="Test prompt",
        bus=bus
    )
    assert agent.state == AgentState.IDLE
    await agent.set_state(AgentState.THINKING)
    assert agent.state == AgentState.THINKING


def test_task_spec_loading():
    task = TaskSpec.from_yaml("tasks/example_task.yaml")
    assert task.id == "TASK-2026-001"
    assert len(task.criteria) == 3
    assert task.criteria[0].name == "Code Correctness"


@pytest.mark.asyncio
async def test_sandboxed_filesystem_tools(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    write_tool = WriteFileTool(workspace_root=sandbox)
    read_tool = ReadFileTool(workspace_root=sandbox)
    list_tool = ListDirTool(workspace_root=sandbox)

    # 1. Write file
    write_res = await write_tool.execute("module.py", "def add(a, b): return a + b\n")
    assert "Successfully wrote" in write_res
    assert (sandbox / "module.py").exists()

    # 2. Read file
    read_res = await read_tool.execute("module.py")
    assert "def add(a, b): return a + b" in read_res

    # 3. List directory
    list_res = await list_tool.execute(".")
    assert "module.py" in list_res

    # 4. Security Sandbox Breakout Test
    with pytest.raises(PermissionError):
        resolve_sandboxed_path("../../outside.txt", sandbox)


@pytest.mark.asyncio
async def test_sandboxed_python_runner(tmp_path: Path):
    py_tool = ExecutePythonTool(workspace_root=tmp_path)
    res = await py_tool.execute("print('Hello from isolated sub-process')")
    assert "Hello from isolated sub-process" in res
    assert "Exit code: 0" in res


@pytest.mark.asyncio
async def test_task_evaluator(tmp_path: Path):
    sandbox = tmp_path / "eval_sandbox"
    sandbox.mkdir()
    (sandbox / "algo.py").write_text("print('clean code')", encoding="utf-8")
    (sandbox / "test_algo.py").write_text("def test_dummy(): pass", encoding="utf-8")

    task = TaskSpec(
        id="EVAL-01",
        title="Sample Evaluation",
        description="Check code correctness and tests.",
        criteria=[
            EvaluationCriterion(name="Code Correctness", description="Valid python syntax", weight=0.5),
            EvaluationCriterion(name="Test Coverage", description="Has test files", weight=0.5),
        ]
    )

    evaluator = TaskEvaluator(workspace_dir=sandbox)
    result = await evaluator.evaluate_task(task)
    assert result.passed is True
    assert result.score >= 0.7
    assert "Code Correctness" in result.criteria_scores


@pytest.mark.asyncio
async def test_trajectory_recorder_and_replayer(tmp_path: Path):
    bus1 = EventBus()
    trace_dir = tmp_path / "traces"
    recorder = TrajectoryRecorder(bus=bus1, output_dir=trace_dir)

    # Emit some events
    await bus1.publish(MessageEvent(sender="Supervisor", content="Start mission"))
    await bus1.publish(MessageEvent(sender="Coder", content="Mission in progress"))

    assert recorder.trace_file.exists()

    # Play back on another bus
    bus2 = EventBus()
    replayed_msgs = []

    async def on_msg(ev: MessageEvent):
        replayed_msgs.append(ev.content)

    bus2.subscribe(MessageEvent, on_msg)
    replayer = TrajectoryReplayer(trace_file=recorder.trace_file, bus=bus2, delay_seconds=0.01)
    count = await replayer.replay()

    assert count == 2
    assert replayed_msgs == ["Start mission", "Mission in progress"]

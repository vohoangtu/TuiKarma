"""Comprehensive unit tests for TUIKarma Workflow Engine (DAGs, Cycles & Branching)."""

import pytest
import asyncio
from typing import Dict, Any

from tuikarma.core.event_bus import EventBus
from tuikarma.core.agent import Agent, AgentRole
from tuikarma.core.llm import ScenarioLLMProvider
from tuikarma.core.topology import SwarmTopology
from tuikarma.workflow.state import WorkflowState, NodeResult
from tuikarma.workflow.node import BaseWorkflowNode, AgentWorkflowNode, DecisionWorkflowNode
from tuikarma.workflow.engine import WorkflowEngine
from tuikarma.workflow.builder import build_self_healing_coding_workflow


class SimpleStepNode(BaseWorkflowNode):
    def __init__(self, node_id: str, value: str) -> None:
        super().__init__(node_id=node_id, name=node_id, node_type="simple")
        self.value = value

    async def execute(self, state: WorkflowState) -> NodeResult:
        return NodeResult(node_id=self.node_id, success=True, output=self.value)


@pytest.mark.asyncio
async def test_workflow_linear_execution():
    bus = EventBus()
    engine = WorkflowEngine(name="Linear Test", bus=bus)

    engine.add_node(SimpleStepNode("step1", "Output 1"), is_start=True)
    engine.add_node(SimpleStepNode("step2", "Output 2"))
    engine.add_node(SimpleStepNode("step3", "Output 3"), is_end=True)

    engine.add_edge("step1", "step2")
    engine.add_edge("step2", "step3")

    state = await engine.execute(WorkflowState(task_description="Linear Task"))

    assert state.step_count == 3
    assert state.get_output("step1") == "Output 1"
    assert state.get_output("step2") == "Output 2"
    assert state.get_output("step3") == "Output 3"


@pytest.mark.asyncio
async def test_workflow_conditional_branching():
    bus = EventBus()
    engine = WorkflowEngine(name="Branching Test", bus=bus)

    engine.add_node(SimpleStepNode("check", "fail"), is_start=True)
    
    def decide(state: WorkflowState) -> str:
        out = state.get_output("check")
        return "branch_b" if out == "fail" else "branch_a"

    engine.add_node(DecisionWorkflowNode("router", "Router", decision_fn=decide))
    engine.add_node(SimpleStepNode("branch_a", "A"), is_end=True)
    engine.add_node(SimpleStepNode("branch_b", "B"), is_end=True)

    engine.add_edge("check", "router")

    state = await engine.execute()
    assert state.current_node_id == "branch_b"
    assert state.get_output("branch_b") == "B"


@pytest.mark.asyncio
async def test_workflow_cyclic_self_healing():
    bus = EventBus()
    engine = WorkflowEngine(name="Cycle Test", bus=bus, max_steps=10)

    # Simulates test failing twice then succeeding
    class FlakyTestNode(BaseWorkflowNode):
        def __init__(self) -> None:
            super().__init__("test", "Test Node", max_retries=0)
            self.calls = 0

        async def execute(self, state: WorkflowState) -> NodeResult:
            self.calls += 1
            if self.calls < 3:
                return NodeResult(node_id=self.node_id, success=True, output="FAILED: Assertion error")
            return NodeResult(node_id=self.node_id, success=True, output="PASSED: 4/4")

    engine.add_node(SimpleStepNode("code", "Initial code"), is_start=True)
    engine.add_node(FlakyTestNode())

    def check_test(state: WorkflowState) -> str:
        test_out = str(state.get_output("test", ""))
        retries = state.iterations.get("patch", 0)
        if "FAILED" in test_out and retries < 3:
            return "patch"
        return "done"

    engine.add_node(DecisionWorkflowNode("decision", "Gateway", decision_fn=check_test))
    engine.add_node(SimpleStepNode("patch", "Patched code"))
    engine.add_node(SimpleStepNode("done", "Success"), is_end=True)

    engine.add_edge("code", "test")
    engine.add_edge("test", "decision")
    engine.add_edge("patch", "test")  # Cycle back!

    state = await engine.execute()
    assert state.iterations.get("test", 0) == 3
    assert state.iterations.get("patch", 0) == 2
    assert state.current_node_id == "done"


@pytest.mark.asyncio
async def test_workflow_pause_and_step():
    bus = EventBus()
    engine = WorkflowEngine(name="Pause Test", bus=bus)

    engine.add_node(SimpleStepNode("n1", "1"), is_start=True)
    engine.add_node(SimpleStepNode("n2", "2"))
    engine.add_node(SimpleStepNode("n3", "3"), is_end=True)

    engine.add_edge("n1", "n2")
    engine.add_edge("n2", "n3")

    engine.set_paused(True)

    task = asyncio.create_task(engine.execute())
    await asyncio.sleep(0.05)
    # Still waiting on first node
    assert engine.is_paused is True

    # Step once
    engine.step_forward()
    await asyncio.sleep(0.05)

    # Resume to completion
    engine.set_paused(False)
    state = await task
    assert state.step_count == 3


@pytest.mark.asyncio
async def test_self_healing_coding_workflow_with_swarm(tmp_path):
    bus = EventBus()
    swarm = SwarmTopology(bus, workspace_dir=tmp_path, llm=ScenarioLLMProvider())

    engine = build_self_healing_coding_workflow(swarm)
    initial_state = WorkflowState(task_description="Build Async Rate Limiter")
    final_state = await engine.execute(initial_state)

    assert final_state.step_count >= 5
    assert final_state.get_output("plan") is not None
    assert final_state.get_output("code") is not None
    assert final_state.get_output("test") is not None
    assert final_state.get_output("review") is not None
    assert final_state.get_output("synthesize") is not None


@pytest.mark.asyncio
async def test_5_step_workflow_retry_and_rollback():
    """Kiểm thử kịch bản: 5 bước, bước 1 & 2 thành công, bước 3 fail -> retry 3 lần -> rollback bước 2 & 1."""
    bus = EventBus()
    events_recorded = []

    # Thu thập toàn bộ sự kiện để kiểm tra tính traceable
    from tuikarma.core.events import (
        WorkflowNodeRetryEvent,
        WorkflowFailedEvent,
        WorkflowRollbackStartedEvent,
        WorkflowNodeRollbackEvent,
        WorkflowRollbackCompletedEvent,
    )

    bus.subscribe(WorkflowNodeRetryEvent, lambda e: events_recorded.append(e))
    bus.subscribe(WorkflowFailedEvent, lambda e: events_recorded.append(e))
    bus.subscribe(WorkflowRollbackStartedEvent, lambda e: events_recorded.append(e))
    bus.subscribe(WorkflowNodeRollbackEvent, lambda e: events_recorded.append(e))
    bus.subscribe(WorkflowRollbackCompletedEvent, lambda e: events_recorded.append(e))

    engine = WorkflowEngine(name="5-Step Pipeline", bus=bus)

    rollback_order = []

    async def rb_step1(state: WorkflowState):
        rollback_order.append("step1")

    async def rb_step2(state: WorkflowState):
        rollback_order.append("step2")

    # Step 1: thành công
    engine.add_node(
        SimpleStepNode("step1", "Data 1"),
        is_start=True
    )
    engine.nodes["step1"].rollback_handler = rb_step1

    # Step 2: thành công
    engine.add_node(
        SimpleStepNode("step2", "Data 2")
    )
    engine.nodes["step2"].rollback_handler = rb_step2

    # Step 3: luôn thất bại, cấu hình retry 3 lần (delay 0.02s trong test để chạy nhanh)
    class AlwaysFailingNode(BaseWorkflowNode):
        def __init__(self):
            super().__init__(
                node_id="step3",
                name="Failing Step 3",
                max_retries=3,
                retry_delay_seconds=0.02
            )
            self.attempts = 0

        async def execute(self, state: WorkflowState) -> NodeResult:
            self.attempts += 1
            return NodeResult(
                node_id=self.node_id,
                success=False,
                error_message=f"Timeout connecting to database (Lần {self.attempts})"
            )

    failing_node = AlwaysFailingNode()
    engine.add_node(failing_node)

    # Step 4 & 5: không bao giờ được gọi tới
    engine.add_node(SimpleStepNode("step4", "Data 4"))
    engine.add_node(SimpleStepNode("step5", "Data 5"), is_end=True)

    # Nối 5 bước tuần tự
    engine.add_edge("step1", "step2")
    engine.add_edge("step2", "step3")
    engine.add_edge("step3", "step4")
    engine.add_edge("step4", "step5")

    state = await engine.execute(WorkflowState(task_description="Test 5-Step Pipeline"))

    # 1. Xác minh workflow thất bại hoàn toàn
    assert state.is_failed is True
    assert "thất bại hoàn toàn sau 3 lần retry" in state.error_message

    # 2. Bước 3 phải được thử tổng cộng 4 lần (1 lần đầu + 3 lần retry)
    assert failing_node.attempts == 4

    # 3. Bước 4 và 5 không bao giờ được chạy
    assert "step4" not in state.node_outputs
    assert "step5" not in state.node_outputs

    # 4. Kiểm tra cơ chế Rollback theo thứ tự đảo ngược: step2 -> step1
    assert rollback_order == ["step2", "step1"]
    assert state.rolled_back_nodes == ["step2", "step1"]

    # 5. Kiểm tra tính Traceable (Mọi sự kiện đều được ghi nhận)
    retry_events = [e for e in events_recorded if isinstance(e, WorkflowNodeRetryEvent)]
    assert len(retry_events) == 3
    assert [e.attempt for e in retry_events] == [1, 2, 3]

    failed_events = [e for e in events_recorded if isinstance(e, WorkflowFailedEvent)]
    assert len(failed_events) == 1
    assert failed_events[0].failed_node_id == "step3"

    rb_start_events = [e for e in events_recorded if isinstance(e, WorkflowRollbackStartedEvent)]
    assert len(rb_start_events) == 1
    assert rb_start_events[0].nodes_to_rollback == ["step2", "step1"]

    rb_done_events = [e for e in events_recorded if isinstance(e, WorkflowRollbackCompletedEvent)]
    assert len(rb_done_events) == 1
    assert rb_done_events[0].success is True

"""Unit tests for HITL Controls during Workflow Execution (Immediate Retry, Skip, Force Rollback)."""

import asyncio
import pytest
from pathlib import Path
from tuikarma.core.event_bus import EventBus
from tuikarma.workflow.engine import WorkflowEngine
from tuikarma.workflow.node import BaseWorkflowNode
from tuikarma.workflow.state import WorkflowState, NodeResult


class FlakyNode(BaseWorkflowNode):
    def __init__(self, node_id: str, fail_count: int = 1, delay: float = 10.0):
        super().__init__(node_id=node_id, name=node_id, max_retries=3, retry_delay_seconds=delay)
        self.fail_count = fail_count
        self.call_count = 0

    async def execute(self, state: WorkflowState) -> NodeResult:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            return NodeResult(node_id=self.node_id, success=False, error_message=f"Flaky attempt {self.call_count}")
        return NodeResult(node_id=self.node_id, success=True, output="Now succeeded")


@pytest.mark.asyncio
async def test_hitl_immediate_retry():
    """Verify that trigger_immediate_retry() cuts short a long delay."""
    bus = EventBus()
    # Node fails once, configured with 10 seconds delay
    node = FlakyNode("flaky_1", fail_count=1, delay=10.0)
    engine = WorkflowEngine("Test Immediate Retry", bus=bus)
    engine.add_node(node, is_start=True, is_end=True)

    task = asyncio.create_task(engine.execute())

    # Wait briefly until the node fails and enters the 10s delay
    await asyncio.sleep(0.05)

    # Human hits immediate retry
    engine.trigger_immediate_retry()

    # The engine should complete well before 10s
    state = await asyncio.wait_for(task, timeout=2.0)
    assert not state.is_failed
    assert "flaky_1" in state.completed_nodes
    assert node.call_count == 2


@pytest.mark.asyncio
async def test_hitl_skip_node():
    """Verify that skip_current_node() bypasses remaining retries and proceeds."""
    bus = EventBus()
    # Node that always fails
    node1 = FlakyNode("flaky_forever", fail_count=10, delay=10.0)

    class SucceedNode(BaseWorkflowNode):
        async def execute(self, state: WorkflowState) -> NodeResult:
            return NodeResult(node_id=self.node_id, success=True, output="Success")

    node2 = SucceedNode("final_node", "final_node")

    engine = WorkflowEngine("Test Skip", bus=bus)
    engine.add_node(node1, is_start=True)
    engine.add_node(node2, is_end=True)
    engine.add_edge("flaky_forever", "final_node")

    task = asyncio.create_task(engine.execute())
    await asyncio.sleep(0.05)

    # Human skips the failing node
    engine.skip_current_node()

    state = await asyncio.wait_for(task, timeout=2.0)
    assert not state.is_failed
    assert "flaky_forever" in state.completed_nodes
    assert "final_node" in state.completed_nodes


@pytest.mark.asyncio
async def test_hitl_force_rollback():
    """Verify that force_rollback() immediately cancels retries and executes reverse rollback."""
    bus = EventBus()

    class NormalNode(BaseWorkflowNode):
        async def execute(self, state: WorkflowState) -> NodeResult:
            return NodeResult(node_id=self.node_id, success=True, output="OK")

    step1 = NormalNode("step1", "step1")
    step2 = FlakyNode("step2_fail", fail_count=10, delay=10.0)

    engine = WorkflowEngine("Test Force Rollback", bus=bus)
    engine.add_node(step1, is_start=True)
    engine.add_node(step2, is_end=True)
    engine.add_edge("step1", "step2_fail")

    task = asyncio.create_task(engine.execute())
    await asyncio.sleep(0.05)

    # Human forces rollback instead of waiting out retries
    engine.force_rollback()

    state = await asyncio.wait_for(task, timeout=2.0)
    assert state.is_failed is True
    assert "step1" in state.rolled_back_nodes

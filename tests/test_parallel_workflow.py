import asyncio
import time
from pathlib import Path
import pytest

from tuikarma.core.event_bus import EventBus
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import ScenarioLLMProvider
from tuikarma.workflow.engine import WorkflowEngine
from tuikarma.workflow.state import WorkflowState
from tuikarma.workflow.node import (
    BaseWorkflowNode,
    NodeResult,
    ParallelWorkflowNode,
    AgentWorkflowNode,
)
from tuikarma.workflow.edge import WorkflowEdge
from tuikarma.workflow.parser import WorkflowParser


class DummyAsyncNode(BaseWorkflowNode):
    """A dummy node for testing concurrent execution with simulated delay."""

    def __init__(self, node_id: str, delay: float, should_fail: bool = False):
        super().__init__(node_id=node_id, name=node_id, node_type="dummy")
        self.delay = delay
        self.should_fail = should_fail
        self.rolled_back = False

    async def execute(self, state: WorkflowState) -> NodeResult:
        await asyncio.sleep(self.delay)
        if self.should_fail:
            return NodeResult(node_id=self.node_id, success=False, error_message=f"Failed {self.node_id}")
        return NodeResult(node_id=self.node_id, success=True, output=f"Result of {self.node_id}")

    async def rollback(self, state: WorkflowState) -> None:
        self.rolled_back = True
        await super().rollback(state)


@pytest.mark.asyncio
async def test_parallel_workflow_node_concurrent_execution():
    """Verify ParallelWorkflowNode executes branches concurrently and collects outputs."""
    branch1 = DummyAsyncNode("branch_1", delay=0.1)
    branch2 = DummyAsyncNode("branch_2", delay=0.1)

    parallel_node = ParallelWorkflowNode(
        node_id="fork_node",
        name="Concurrent Fork",
        branches=[branch1, branch2],
    )

    state = WorkflowState(task_description="Test parallel execution")

    start_time = time.monotonic()
    result = await parallel_node.execute(state)
    elapsed = time.monotonic() - start_time

    assert result.success is True
    # If sequential, 0.1 + 0.1 = 0.2s; concurrent should be ~0.1s (< 0.18s)
    assert elapsed < 0.18
    assert "branch_1" in state.node_outputs
    assert "branch_2" in state.node_outputs
    assert state.node_outputs["branch_1"] == "Result of branch_1"
    assert state.node_outputs["branch_2"] == "Result of branch_2"
    assert isinstance(result.output, dict)
    assert result.output["branch_1"] == "Result of branch_1"
    assert result.output["branch_2"] == "Result of branch_2"


@pytest.mark.asyncio
async def test_parallel_workflow_node_failure_and_rollback():
    """Verify ParallelWorkflowNode propagates failure if any branch fails, and rolls back branches."""
    branch1 = DummyAsyncNode("branch_ok", delay=0.05)
    branch2 = DummyAsyncNode("branch_fail", delay=0.05, should_fail=True)

    parallel_node = ParallelWorkflowNode(
        node_id="fork_fail_node",
        name="Concurrent Fork with Failure",
        branches=[branch1, branch2],
    )

    state = WorkflowState(task_description="Test parallel failure")
    result = await parallel_node.execute(state)

    assert result.success is False
    assert "branch_fail" in result.error_message

    # Trigger rollback
    await parallel_node.rollback(state)
    assert branch1.rolled_back is True
    assert branch2.rolled_back is True


@pytest.mark.asyncio
async def test_parallel_tdd_pipeline_yaml_parsing_and_execution():
    """Verify loading and executing tasks/pipelines/parallel_tdd_pipeline.yaml end-to-end."""
    yaml_path = Path("tasks/pipelines/parallel_tdd_pipeline.yaml")
    assert yaml_path.exists(), "Parallel pipeline YAML file should exist"

    bus = EventBus()
    llm = ScenarioLLMProvider()
    swarm = SwarmTopology(bus, llm=llm)

    engine = WorkflowParser.load_from_yaml(yaml_path, swarm)
    assert engine.name == "Parallel Fork-Join TDD Pipeline"
    assert "parallel_dev" in engine.nodes
    parallel_node = engine.nodes["parallel_dev"]
    assert isinstance(parallel_node, ParallelWorkflowNode)
    assert len(parallel_node.branches) == 2
    branch_ids = [b.node_id for b in parallel_node.branches]
    assert "code" in branch_ids
    assert "test_suite" in branch_ids

    # Execute workflow
    state = WorkflowState(task_description="Implement Async Rate Limiter")
    final_state = await engine.execute(state)

    assert final_state.is_failed is False
    assert "plan" in final_state.completed_nodes
    assert "parallel_dev" in state.completed_nodes
    assert "code" in state.node_outputs
    assert "test_suite" in state.node_outputs
    assert "review" in state.completed_nodes
    assert "synthesize" in state.completed_nodes

import asyncio
from pathlib import Path
import pytest

from tuikarma.core.event_bus import EventBus
from tuikarma.core.events import (
    HITLApprovalRequestEvent,
    HITLApprovalResponseEvent,
    HITLCommandEvent,
    HITLAction,
)
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import ScenarioLLMProvider
from tuikarma.workflow.state import WorkflowState
from tuikarma.workflow.expression import safe_evaluate_condition
from tuikarma.workflow.edge import WorkflowEdge
from tuikarma.workflow.node import HITLWorkflowNode, NodeResult
from tuikarma.workflow.parser import WorkflowParser


def test_safe_evaluate_condition():
    """Verify safe condition expression evaluation with various scopes and edge cases."""
    state = WorkflowState(task_description="Build secure API")
    state.set_output("review", "Security analysis: PASSED with 0 vulnerabilities")
    state.set_output("score", 95)
    state.iterations["coder"] = 2

    # Basic truths
    assert safe_evaluate_condition("true", state) is True
    assert safe_evaluate_condition("default", state) is True
    assert safe_evaluate_condition("*", state) is True
    assert safe_evaluate_condition("false", state) is False

    # Expressions with helpers and outputs
    assert safe_evaluate_condition("contains(outputs.get('review', ''), 'PASSED')", state) is True
    assert safe_evaluate_condition("contains(outputs.get('review', ''), 'FAILED')", state) is False
    assert safe_evaluate_condition("has('score') and score >= 90", state) is True
    assert safe_evaluate_condition("iterations.get('coder', 0) == 2", state) is True

    # Error resilience (bad syntax or missing variables should evaluate to False, not crash)
    assert safe_evaluate_condition("non_existent_var == 123", state) is False
    assert safe_evaluate_condition("this is not valid python !!!", state) is False


@pytest.mark.asyncio
async def test_workflow_edge_with_expression_condition():
    """Verify WorkflowEdge evaluates string conditions dynamically."""
    state = WorkflowState(task_description="Test edge")
    state.set_output("test_result", "ALL TESTS PASSED")

    passing_edge = WorkflowEdge(
        from_node="test",
        to_node="deploy",
        condition="'PASSED' in outputs.get('test_result', '')",
    )
    failing_edge = WorkflowEdge(
        from_node="test",
        to_node="rollback",
        condition="'FAILED' in outputs.get('test_result', '')",
    )

    assert await passing_edge.can_traverse(state) is True
    assert await failing_edge.can_traverse(state) is False


@pytest.mark.asyncio
async def test_hitl_workflow_node_manual_approval():
    """Verify HITLWorkflowNode pauses until approval is published via event bus."""
    bus = EventBus()
    node = HITLWorkflowNode(
        node_id="approval_gate",
        name="Security Gate",
        prompt="Review code: {code}",
        bus=bus,
        timeout_seconds=5.0,
        auto_approve_in_headless=False,
    )

    state = WorkflowState(task_description="Test HITL")
    state.set_output("code", "def secure(): pass")

    received_request = False

    async def on_request(event: HITLApprovalRequestEvent):
        nonlocal received_request
        received_request = True
        assert event.node_id == "approval_gate"
        assert "def secure(): pass" in event.prompt
        # Operator approves after a brief delay
        await asyncio.sleep(0.05)
        await bus.publish(
            HITLApprovalResponseEvent(
                node_id="approval_gate",
                approved=True,
                guidance="Approved by Lead SecOps",
            )
        )

    bus.subscribe(HITLApprovalRequestEvent, on_request)

    result = await node.execute(state)
    assert received_request is True
    assert result.success is True
    assert "Approved by Lead SecOps" in result.output
    assert state.get_output("approval_gate") == "Approved by Lead SecOps"


@pytest.mark.asyncio
async def test_hitl_workflow_node_rejection():
    """Verify HITLWorkflowNode returns failure when human operator rejects."""
    bus = EventBus()
    node = HITLWorkflowNode(
        node_id="reject_gate",
        name="Security Gate Reject",
        prompt="Deploy to production?",
        bus=bus,
        timeout_seconds=5.0,
        auto_approve_in_headless=False,
    )

    state = WorkflowState(task_description="Test Rejection")

    async def on_request(event: HITLApprovalRequestEvent):
        await asyncio.sleep(0.05)
        await bus.publish(
            HITLApprovalResponseEvent(
                node_id="reject_gate",
                approved=False,
                guidance="Vulnerability detected in auth module",
            )
        )

    bus.subscribe(HITLApprovalRequestEvent, on_request)

    result = await node.execute(state)
    assert result.success is False
    assert "Vulnerability detected" in result.error_message


@pytest.mark.asyncio
async def test_hitl_workflow_node_command_event_approval():
    """Verify HITLWorkflowNode accepts approval via HITLCommandEvent(APPROVE)."""
    bus = EventBus()
    node = HITLWorkflowNode(
        node_id="cmd_gate",
        name="Command Gate",
        prompt="Confirm step?",
        bus=bus,
        timeout_seconds=5.0,
        auto_approve_in_headless=False,
    )

    state = WorkflowState(task_description="Test Command Event")

    async def on_request(event: HITLApprovalRequestEvent):
        await asyncio.sleep(0.05)
        await bus.publish(HITLCommandEvent(action=HITLAction.APPROVE, payload="Signed off"))

    bus.subscribe(HITLApprovalRequestEvent, on_request)

    result = await node.execute(state)
    assert result.success is True
    assert "Signed off" in result.output


@pytest.mark.asyncio
async def test_hitl_workflow_node_headless_auto_approve():
    """Verify HITLWorkflowNode auto-approves in headless environment if configured."""
    bus = EventBus()
    node = HITLWorkflowNode(
        node_id="headless_gate",
        name="Headless Auto Gate",
        prompt="Auto approval test",
        bus=bus,
        timeout_seconds=0.1,
        auto_approve_in_headless=True,
    )

    state = WorkflowState(task_description="Test Headless Auto")
    result = await node.execute(state)
    assert result.success is True
    assert "Auto-approved" in result.output


@pytest.mark.asyncio
async def test_dynamic_hitl_pipeline_yaml_end_to_end():
    """Verify declarative YAML pipeline loading and execution with dynamic edges and HITL gate."""
    yaml_path = Path("tasks/pipelines/dynamic_hitl_pipeline.yaml")
    assert yaml_path.exists(), "dynamic_hitl_pipeline.yaml should exist"

    bus = EventBus()
    llm = ScenarioLLMProvider()
    swarm = SwarmTopology(bus, llm=llm)

    engine = WorkflowParser.load_from_yaml(yaml_path, swarm)
    assert engine.name == "Dynamic Routing & HITL Approval Pipeline"
    assert "security_gate" in engine.nodes
    # Auto-respond immediately to approval request to speed up test execution
    async def auto_respond(event: HITLApprovalRequestEvent):
        await bus.publish(
            HITLApprovalResponseEvent(
                node_id=event.node_id,
                approved=True,
                guidance="Pipeline Gate Approved by SecOps"
            )
        )

    bus.subscribe(HITLApprovalRequestEvent, auto_respond)

    # Execute workflow
    state = WorkflowState(task_description="Implement Async Rate Limiter")
    final_state = await engine.execute(state)

    assert final_state.is_failed is False
    assert "plan" in final_state.completed_nodes
    assert "code" in final_state.completed_nodes
    assert "test" in final_state.completed_nodes
    assert "eval_gate" in final_state.completed_nodes
    assert "security_gate" in final_state.completed_nodes
    assert "deploy" in final_state.completed_nodes

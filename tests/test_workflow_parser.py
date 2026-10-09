"""Unit tests for Declarative Workflow Parser."""

import pytest
from pathlib import Path
from tuikarma.core.event_bus import EventBus
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import ScenarioLLMProvider
from tuikarma.workflow.parser import WorkflowParser
from tuikarma.workflow.state import WorkflowState


@pytest.mark.asyncio
async def test_workflow_parser_from_yaml_file(tmp_path: Path):
    yaml_content = """
name: "Test YAML Pipeline"
max_steps: 10
default_retry_policy:
  max_retries: 2
  delay_seconds: 0.01

nodes:
  - id: "step_plan"
    name: "Planning"
    type: "agent"
    agent: "Supervisor"
    model: "antigravity/claude-sonnet-4-6"
    prompt: "Plan for: {task_description}"
    is_start: true

  - id: "step_code"
    name: "Coding"
    type: "agent"
    agent: "Coder"
    prompt: "Code for: {step_plan}"

  - id: "branch"
    name: "Check Decision"
    type: "decision"
    rules:
      - condition: "'error' in str(step_code).lower()"
        target: "step_fix"
      - condition: "default"
        target: "step_done"

  - id: "step_fix"
    name: "Fixing"
    type: "agent"
    agent: "Coder"
    prompt: "Fix code"

  - id: "step_done"
    name: "Finished"
    type: "agent"
    agent: "Critic"
    prompt: "Review code: {step_code}"
    is_end: true

edges:
  - from: "step_plan"
    to: "step_code"
  - from: "step_code"
    to: "branch"
  - from: "step_fix"
    to: "step_done"
"""
    yaml_file = tmp_path / "test_pipeline.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    bus = EventBus()
    llm = ScenarioLLMProvider()
    swarm = SwarmTopology(bus=bus, workspace_dir=tmp_path, llm=llm)

    engine = WorkflowParser.load_from_yaml(yaml_file, swarm)

    assert engine.name == "Test YAML Pipeline"
    assert len(engine.nodes) == 5
    assert len(engine.edges) == 3
    assert engine.start_node_id == "step_plan"
    assert "step_done" in engine.end_node_ids

    # Execute workflow parsed from YAML
    initial_state = WorkflowState(task_description="Build Async Limiter")
    state = await engine.execute(initial_state)

    assert not state.is_failed
    assert "step_plan" in state.completed_nodes
    assert "step_code" in state.completed_nodes
    assert "branch" in state.completed_nodes
    assert "step_done" in state.completed_nodes

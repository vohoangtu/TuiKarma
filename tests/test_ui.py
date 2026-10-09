"""UI tests for Textual TUI dashboard."""

import pytest
import asyncio
from tuikarma.ui.app import TUIKarmaApp
from tuikarma.harness.task import TaskSpec
from tuikarma.core.llm import ScenarioLLMProvider


@pytest.mark.asyncio
async def test_app_mount_and_pilot_flow():
    task = TaskSpec.from_yaml("tasks/example_task.yaml")
    app = TUIKarmaApp(task_spec=task, llm=ScenarioLLMProvider())
    async with app.run_test() as pilot:
        # Step through initial rendering
        await pilot.pause(1.0)
        assert app.is_running

        # Test pause toggle
        app.action_toggle_pause()
        assert app.is_paused is True

        # Test resume
        app.action_toggle_pause()
        assert app.is_paused is False

        # Test single step forward
        app.action_step_forward()

        # Let the task finish
        await pilot.pause(3.5)
        metrics = app.query_one("#metrics-panel")
        assert metrics.total_tokens > 0
        assert metrics.eval_score != "Pending..."

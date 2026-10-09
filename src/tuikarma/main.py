"""Entry point for running TUIKarma Multi-Agent Harness."""

from __future__ import annotations
import sys
import asyncio
import argparse
from pathlib import Path

from tuikarma.ui.app import TUIKarmaApp
from tuikarma.harness.task import TaskSpec
from tuikarma.core.event_bus import EventBus
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import get_default_llm_provider, BaseLLMProvider
from tuikarma.harness.evaluator import TaskEvaluator
from tuikarma.harness.trajectory import TrajectoryRecorder


# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_headless_eval(task_spec: TaskSpec, llm: BaseLLMProvider, workflow_file: Optional[Path] = None) -> None:
    """Run benchmark task in headless mode (ideal for CI/CD and automated batch testing)."""
    provider_name = llm.__class__.__name__
    wf_desc = f" | Pipeline: {workflow_file.name}" if workflow_file else ""
    print(f"\n[HARNESS HEADLESS] Chạy benchmark cho task: {task_spec.title} ({task_spec.id}) [Backend: {provider_name}{wf_desc}]")
    bus = EventBus()
    topology = SwarmTopology(bus, llm=llm)
    recorder = TrajectoryRecorder(bus)
    evaluator = TaskEvaluator(topology.workspace_dir, bus=bus)

    async def _execute():
        if workflow_file and workflow_file.exists():
            from tuikarma.workflow.parser import WorkflowParser
            from tuikarma.workflow.state import WorkflowState
            engine = WorkflowParser.load_from_yaml(workflow_file, topology)
            topology.active_workflow = engine
            initial_state = WorkflowState(task_description=task_spec.description, max_steps=engine.max_steps)
            initial_state.set_shared("headless_mode", True)
            await engine.execute(initial_state)
        else:
            await topology.execute_task_loop(task_spec.description)

        result = await evaluator.evaluate_task(task_spec)
        print("\n" + "=" * 60)
        print(f"KẾT QUẢ ĐÁNH GIÁ (HARNESS VERDICT): {'PASSED' if result.passed else 'FAILED'}")
        print(f"Điểm số: {result.score * 100:.1f}%")
        print("Chi tiết tiêu chí:")
        print(result.feedback)
        print(f"Trace ghi tại: {recorder.trace_file}")
        print("=" * 60)
        return result.passed

    success = asyncio.run(_execute())
    sys.exit(0 if success else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="TUIKarma - Multi-Agent Harness & TUI Runner (2026)")
    parser.add_argument("--task", type=str, default="tasks/example_task.yaml", help="Path to task YAML specification")
    parser.add_argument("--prompt", "-p", type=str, default=None, help="Giao việc nhanh trực tiếp bằng mô tả văn bản")
    parser.add_argument("--workflow", type=str, default=None, help="Path to declarative YAML workflow pipeline")
    parser.add_argument("--replay", type=str, default=None, help="Path to JSONL session trace file to replay")
    parser.add_argument("--backend", type=str, choices=["auto", "local", "scenario"], default="auto",
                        help="LLM backend: 'local' (http://localhost:20128/v1), 'scenario' (mock), or 'auto' (detect)")
    parser.add_argument("--no-tui", action="store_true", help="Run in headless benchmark mode without TUI")
    parser.add_argument("--web", action="store_true", help="Khởi chạy Light Fluent 2 Mica Web UI Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Cổng chạy Web UI (mặc định: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host chạy Web UI (mặc định: 127.0.0.1)")
    args = parser.parse_args()

    if args.web:
        from tuikarma.web.server import run_web_server
        run_web_server(host=args.host, port=args.port)
        return

    if args.prompt:
        task = TaskSpec(
            id="CUSTOM-TASK",
            title="Ad-hoc Task Assignment",
            description=args.prompt,
        )
    else:
        task_path = Path(args.task)
        if task_path.exists():
            task = TaskSpec.from_yaml(str(task_path))
        else:
            task = TaskSpec(
                id="DEFAULT-01",
                title="Async Multi-Agent Co-Development",
                description="Mô phỏng phối hợp phân tán giữa Supervisor, Coder, Tester và Critic.",
            )

    llm = get_default_llm_provider(force_backend=args.backend)
    replay_path = Path(args.replay) if args.replay else None
    workflow_path = Path(args.workflow) if args.workflow else None

    if args.no_tui:
        run_headless_eval(task, llm=llm, workflow_file=workflow_path)
    else:
        app = TUIKarmaApp(task_spec=task, workflow_file=workflow_path, replay_file=replay_path, llm=llm)
        app.run()


if __name__ == "__main__":
    main()

"""Main Textual Application for TUIKarma Multi-Agent Harness (2026)."""

from __future__ import annotations
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, Input
from textual.reactive import reactive
from textual.binding import Binding

from tuikarma.core.events import (
    MessageEvent,
    StateChangeEvent,
    ToolCallEvent,
    ToolResultEvent,
    MetricsEvent,
    ToolApprovalRequestEvent,
    EvaluationResultEvent,
    AgentState,
)
from tuikarma.core.event_bus import EventBus
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import BaseLLMProvider
from tuikarma.harness.task import TaskSpec
from tuikarma.harness.evaluator import TaskEvaluator
from tuikarma.harness.trajectory import TrajectoryRecorder, TrajectoryReplayer


class AgentMatrixWidget(Static):
    """Displays real-time status of all agents in the swarm."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_states: Dict[str, str] = {
            "Supervisor": "IDLE",
            "Coder": "IDLE",
            "Tester": "IDLE",
            "Critic": "IDLE",
        }
        self.agent_models: Dict[str, str] = {
            "Supervisor": "antigravity/claude-sonnet-4-6",
            "Coder": "antigravity/claude-sonnet-4-6",
            "Tester": "antigravity/gemini-3.1-flash-lite",
            "Critic": "antigravity/claude-opus-4-6",
        }

    def on_mount(self) -> None:
        self.update_content()

    def update_agent_state(self, agent_name: str, state: AgentState) -> None:
        self.agent_states[agent_name] = state.value
        self.update_content()

    def update_content(self) -> None:
        lines = ["[bold cyan]═══ AGENT SWARM TOPOLOGY ═══[/bold cyan]\n"]
        icons = {
            "IDLE": "[dim]● IDLE[/dim]",
            "THINKING": "[bold yellow]⚙ THINKING...[/bold yellow]",
            "CALLING_TOOL": "[bold magenta]🛠 CALLING TOOL[/bold magenta]",
            "WAITING": "[yellow]◌ WAITING[/yellow]",
            "COMPLETED": "[bold green]✔ COMPLETED[/bold green]",
            "ERROR": "[bold red]✖ ERROR[/bold red]",
        }

        for name, state in self.agent_states.items():
            icon = icons.get(state, state)
            model = self.agent_models.get(name, "")
            lines.append(f"[bold white]{name:<12}[/bold white] {icon}")
            lines.append(f"  [dim italic]Model: {model}[/dim italic]\n")

        self.update("\n".join(lines))


class MetricsWidget(Static):
    """Displays real-time execution telemetry and resource usage."""

    total_tokens = reactive(0)
    total_cost = reactive(0.0)
    current_step = reactive(0)
    latency_ms = reactive(0.0)
    eval_score = reactive("Pending...")
    eval_status = reactive("[dim]In Progress[/dim]")

    def on_mount(self) -> None:
        self.update_display()

    def update_metrics(self, event: MetricsEvent) -> None:
        self.current_step = event.step
        self.total_tokens += (event.tokens_in + event.tokens_out)
        self.total_cost += event.cost_usd
        self.latency_ms = event.latency_ms
        self.update_display()

    def update_eval(self, event: EvaluationResultEvent) -> None:
        score_pct = event.score * 100.0
        if event.passed:
            self.eval_score = f"{score_pct:.1f}%"
            self.eval_status = "[bold green]PASSED ✔[/bold green]"
        else:
            self.eval_score = f"{score_pct:.1f}%"
            self.eval_status = "[bold red]FAILED ✖[/bold red]"
        self.update_display()

    def update_display(self) -> None:
        content = (
            "[bold cyan]═══ HARNESS TELEMETRY ═══[/bold cyan]\n\n"
            f"[dim]Current Step:[/dim]      [bold yellow]{self.current_step} / 5[/bold yellow]\n"
            f"[dim]Total Tokens:[/dim]      [bold green]{self.total_tokens:,}[/bold green]\n"
            f"[dim]Estimated Cost:[/dim]    [bold green]${self.total_cost:.4f}[/bold green]\n"
            f"[dim]Step Latency:[/dim]      [bold white]{self.latency_ms:.0f} ms[/bold white]\n"
            f"[dim]Sandbox Status:[/dim]    [bold green]Active (Isolated)[/bold green]\n"
            f"[dim]Eval Score:[/dim]        [bold bright_yellow]{self.eval_score}[/bold bright_yellow]\n"
            f"[dim]Benchmark Result:[/dim]  {self.eval_status}"
        )
        self.update(content)


class TUIKarmaApp(App):
    """Full-featured Multi-Agent Harness Dashboard in Textual."""

    CSS_PATH = "styles.tcss"
    TITLE = "TUIKarma | Multi-Agent Harness (2026)"
    SUB_TITLE = "Reactive Terminal Orchestrator & Benchmark Evaluator"

    BINDINGS = [
        Binding("p", "toggle_pause", "Pause/Resume", show=True),
        Binding("s", "step_forward", "Step (Debug)", show=True),
        Binding("a", "approve_tool", "Approve Tool", show=True),
        Binding("r", "restart_task", "Restart Task", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        task_spec: Optional[TaskSpec] = None,
        replay_file: Optional[Path] = None,
        llm: Optional[BaseLLMProvider] = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.bus = EventBus()
        self.task_spec = task_spec or TaskSpec(
            id="DEMO-01",
            title="Async Token Bucket Rate Limiter",
            description="Multi-agent co-development and evaluation harness demo.",
        )
        self.replay_file = replay_file
        self.llm = llm
        self.topology = SwarmTopology(self.bus, llm=self.llm)
        self.evaluator = TaskEvaluator(self.topology.workspace_dir, bus=self.bus)
        self.is_paused = False
        self._task_coro: Optional[asyncio.Task] = None
        self.recorder: Optional[TrajectoryRecorder] = None
        self.pending_approval = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Vertical(id="left-sidebar"):
                with Container(classes="box-panel", id="agent-matrix-box"):
                    yield AgentMatrixWidget(id="agent-matrix")
                with Container(classes="box-panel", id="metrics-box"):
                    yield MetricsWidget(id="metrics-panel")

            with Vertical(id="right-content"):
                with Container(classes="box-panel", id="stream-box"):
                    yield Static("[bold cyan]═══ LIVE INTER-AGENT DIALOGUE & REASONING ═══[/bold cyan]")
                    yield RichLog(id="stream-log", highlight=True, markup=True, wrap=True)
                with Container(classes="box-panel", id="inspector-box"):
                    yield Static("[bold cyan]═══ TOOL INSPECTOR & TRACE ═══[/bold cyan]")
                    yield RichLog(id="inspector-log", highlight=True, markup=True, wrap=True)

        with Horizontal(id="hitl-container"):
            yield Static("⚡ HITL Injection:", id="hitl-label")
            yield Input(placeholder="Type command or feedback for agents... (Press Enter to send)", id="hitl-input")
            yield Static(r"[P] Pause | [S] Step | [A] Approve | [Q] Quit", id="hitl-key-guide")

        yield Footer()

    async def on_mount(self) -> None:
        # Register bus event handlers
        self.bus.subscribe(MessageEvent, self.handle_message_event)
        self.bus.subscribe(StateChangeEvent, self.handle_state_event)
        self.bus.subscribe(ToolCallEvent, self.handle_tool_call)
        self.bus.subscribe(ToolResultEvent, self.handle_tool_result)
        self.bus.subscribe(MetricsEvent, self.handle_metrics_event)
        self.bus.subscribe(ToolApprovalRequestEvent, self.handle_approval_request)
        self.bus.subscribe(EvaluationResultEvent, self.handle_eval_event)

        # Setup recording if not replaying
        if not self.replay_file:
            self.recorder = TrajectoryRecorder(self.bus)

        # Log launch banner
        stream_log = self.query_one("#stream-log", RichLog)
        mode_str = f"REPLAY: {self.replay_file.name}" if self.replay_file else "LIVE EXECUTION"
        stream_log.write(f"[bold magenta]▶ [HARNESS LAUNCH - {mode_str}][/bold magenta] Task: [bold white]{self.task_spec.title}[/bold white]")
        stream_log.write(f"[dim]{self.task_spec.description}[/dim]\n" + "─" * 70)

        # Start execution or replay loop
        if self.replay_file:
            self._task_coro = asyncio.create_task(self._run_replay())
        else:
            self._task_coro = asyncio.create_task(self._run_task())

    async def _run_task(self) -> None:
        """Run execution loop and trigger evaluator upon completion."""
        try:
            await self.topology.execute_task_loop(self.task_spec.description)
            # Run automated evaluation
            await asyncio.sleep(0.5)
            await self.evaluator.evaluate_task(self.task_spec)
        except asyncio.CancelledError:
            pass

    async def _run_replay(self) -> None:
        """Replay past session trace."""
        replayer = TrajectoryReplayer(trace_file=self.replay_file, bus=self.bus, delay_seconds=0.4)
        count = await replayer.replay()
        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write(f"\n[bold green]✔ Replay completed! Total {count} events reproduced.[/bold green]")

    def handle_message_event(self, event: MessageEvent) -> None:
        stream_log = self.query_one("#stream-log", RichLog)
        time_str = event.timestamp.strftime("%H:%M:%S")

        colors = {
            "Supervisor": "magenta",
            "Coder": "green",
            "Tester": "yellow",
            "Critic": "cyan",
            "HUMAN [HITL]": "bright_yellow",
        }
        color = colors.get(event.sender, "white")

        if event.is_thought:
            stream_log.write(
                f"[dim]{time_str}[/dim] [italic {color}]⚙ {event.sender} (Chain-of-Thought):[/italic {color}]\n"
                f"   [dim]{event.content}[/dim]\n"
            )
        else:
            stream_log.write(
                f"[dim]{time_str}[/dim] [bold {color}]● {event.sender}[/bold {color}] → [dim]{event.receiver}:[/dim]\n"
                f"{event.content}\n"
            )

    def handle_state_event(self, event: StateChangeEvent) -> None:
        matrix = self.query_one("#agent-matrix", AgentMatrixWidget)
        matrix.update_agent_state(event.agent_name, event.new_state)

    def handle_tool_call(self, event: ToolCallEvent) -> None:
        inspector = self.query_one("#inspector-log", RichLog)
        time_str = event.timestamp.strftime("%H:%M:%S")
        inspector.write(
            f"[dim]{time_str}[/dim] [bold magenta]TOOL CALL[/bold magenta] by [bold white]{event.agent_name}[/bold white]: "
            f"[bold cyan]{event.tool_name}[/bold cyan]({event.arguments})"
        )

    def handle_tool_result(self, event: ToolResultEvent) -> None:
        inspector = self.query_one("#inspector-log", RichLog)
        time_str = event.timestamp.strftime("%H:%M:%S")
        inspector.write(
            f"[dim]{time_str}[/dim] [bold green]TOOL OUTPUT[/bold green] [{event.duration_ms:.0f}ms]:\n"
            f"[dim]{event.result}[/dim]\n"
        )

    def handle_approval_request(self, event: ToolApprovalRequestEvent) -> None:
        self.pending_approval = True
        inspector = self.query_one("#inspector-log", RichLog)
        inspector.write(
            f"[bold bright_red]🚨 [SECURITY GATE][/bold bright_red] Agent [bold white]{event.agent_name}[/bold white] "
            f"yêu cầu thực thi lệnh nguy hiểm [bold yellow]{event.tool_name}[/bold yellow]!\n"
            f"   [yellow]→ Nhấn [bold white][A][/bold white] để Duyệt hoặc gõ '/deny' vào ô lệnh.[/yellow]\n"
        )

    def handle_metrics_event(self, event: MetricsEvent) -> None:
        metrics_panel = self.query_one("#metrics-panel", MetricsWidget)
        metrics_panel.update_metrics(event)

    def handle_eval_event(self, event: EvaluationResultEvent) -> None:
        metrics_panel = self.query_one("#metrics-panel", MetricsWidget)
        metrics_panel.update_eval(event)

        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write("\n" + "═" * 70)
        badge = "[bold green]PASSED[/bold green]" if event.passed else "[bold red]FAILED[/bold red]"
        stream_log.write(f"[bold bright_yellow]🏆 [HARNESS EVALUATION VERDICT: {badge} - Score: {event.score*100:.1f}%][/bold bright_yellow]")
        stream_log.write(f"[dim]{event.feedback}[/dim]\n" + "═" * 70)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        input_widget = self.query_one("#hitl-input", Input)
        input_widget.value = ""

        # Check special commands
        cmd_lower = text.lower()
        if cmd_lower in ["/pause", "p"]:
            self.action_toggle_pause()
        elif cmd_lower in ["/step", "s"]:
            self.action_step_forward()
        elif cmd_lower in ["/approve", "a"]:
            self.action_approve_tool()
        elif cmd_lower in ["/restart", "r"]:
            self.action_restart_task()
        elif cmd_lower in ["/quit", "q"]:
            self.action_quit()
        else:
            # Human Injection
            asyncio.create_task(
                self.bus.publish(
                    MessageEvent(
                        sender="HUMAN [HITL]",
                        receiver="Supervisor",
                        content=text
                    )
                )
            )

    def action_toggle_pause(self) -> None:
        self.is_paused = not self.is_paused
        self.topology.set_paused(self.is_paused)
        stream_log = self.query_one("#stream-log", RichLog)
        status = "[bold red]PAUSED (Human Intervention Mode)[/bold red]" if self.is_paused else "[bold green]RESUMED[/bold green]"
        stream_log.write(f"\n[bold yellow]⚡ [HITL ACTION][/bold yellow] Execution {status}\n")

    def action_step_forward(self) -> None:
        if not self.is_paused:
            self.action_toggle_pause()
        self.topology.step_forward()
        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write("[bold yellow]⚡ [HITL STEP][/bold yellow] Stepping forward 1 iteration...\n")

    def action_approve_tool(self) -> None:
        inspector = self.query_one("#inspector-log", RichLog)
        if self.pending_approval:
            self.pending_approval = False
            inspector.write("[bold green]✔ [APPROVED BY HUMAN][/bold green] Lệnh nguy hiểm đã được cấp phép thực thi.\n")
        else:
            inspector.write("[dim]Không có công cụ nào đang chờ phê duyệt.[/dim]\n")

    def action_restart_task(self) -> None:
        if self._task_coro and not self._task_coro.done():
            self._task_coro.cancel()

        stream_log = self.query_one("#stream-log", RichLog)
        inspector_log = self.query_one("#inspector-log", RichLog)
        stream_log.clear()
        inspector_log.clear()

        stream_log.write(f"[bold magenta]▶ [HARNESS RESTARTED][/bold magenta] Task: [bold white]{self.task_spec.title}[/bold white]\n")
        self._task_coro = asyncio.create_task(self._run_task())

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
    WorkflowStartedEvent,
    WorkflowNodeStartedEvent,
    WorkflowNodeCompletedEvent,
    WorkflowTransitionEvent,
    WorkflowCompletedEvent,
    WorkflowNodeRetryEvent,
    WorkflowFailedEvent,
    WorkflowRollbackStartedEvent,
    WorkflowNodeRollbackEvent,
    WorkflowRollbackCompletedEvent,
    HITLApprovalRequestEvent,
    HITLApprovalResponseEvent,
    HITLCommandEvent,
    HITLAction,
    AgentState,
)
from tuikarma.core.event_bus import EventBus
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import BaseLLMProvider
from tuikarma.harness.task import TaskSpec
from tuikarma.harness.evaluator import TaskEvaluator
from tuikarma.harness.trajectory import TrajectoryRecorder, TrajectoryReplayer
from tuikarma.ui.widgets.dag_view import WorkflowDAGWidget


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
    active_node = reactive("Initializing...")
    eval_score = reactive("Pending...")
    eval_status = reactive("[dim]In Progress[/dim]")

    def on_mount(self) -> None:
        self.update_display()

    def update_node(self, event: WorkflowNodeStartedEvent) -> None:
        self.active_node = f"{event.node_id} (Loop #{event.iteration})"
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
            f"[dim]Workflow Engine:[/dim]   [bold magenta]Active (DAG)[/bold magenta]\n"
            f"[dim]Active Node:[/dim]       [bold yellow]{self.active_node}[/bold yellow]\n"
            f"[dim]Workflow Steps:[/dim]    [bold yellow]{self.current_step}[/bold yellow]\n"
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
        Binding("n", "immediate_retry", "Retry Now", show=True),
        Binding("k", "skip_node", "Skip Node", show=True),
        Binding("b", "force_rollback", "Rollback", show=True),
        Binding("a", "approve_tool", "Approve Tool", show=True),
        Binding("r", "restart_task", "Restart Task", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        task_spec: Optional[TaskSpec] = None,
        workflow_file: Optional[Path] = None,
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
        self.workflow_file = workflow_file
        self.replay_file = replay_file
        self.llm = llm
        self.topology = SwarmTopology(self.bus, llm=self.llm)
        self.evaluator = TaskEvaluator(self.topology.workspace_dir, bus=self.bus)
        self.is_paused = False
        self._task_coro: Optional[asyncio.Task] = None
        self.recorder: Optional[TrajectoryRecorder] = None
        self.pending_approval = False
        self.pending_hitl_node: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Vertical(id="left-sidebar"):
                with Container(classes="box-panel", id="agent-matrix-box"):
                    yield AgentMatrixWidget(id="agent-matrix")
                with Container(classes="box-panel", id="metrics-box"):
                    yield MetricsWidget(id="metrics-panel")

            with Vertical(id="right-content"):
                yield WorkflowDAGWidget(id="workflow-dag-widget")
                with Container(classes="box-panel", id="stream-box"):
                    yield Static("[bold cyan]═══ LIVE INTER-AGENT DIALOGUE & REASONING ═══[/bold cyan]")
                    yield RichLog(id="stream-log", highlight=True, markup=True, wrap=True)
                with Container(classes="box-panel", id="inspector-box"):
                    yield Static("[bold cyan]═══ TOOL INSPECTOR & TRACE ═══[/bold cyan]")
                    yield RichLog(id="inspector-log", highlight=True, markup=True, wrap=True)

        with Horizontal(id="hitl-container"):
            yield Static("⚡ HITL:", id="hitl-label")
            yield Input(placeholder="Commands: /retry-now, /skip, /rollback, /inject <guidance> or message...", id="hitl-input")
            yield Static(r"[P] Pause | [N] Retry-Now | [K] Skip | [B] Rollback | [A] Approve", id="hitl-key-guide")

        yield Footer()

    async def on_mount(self) -> None:
        # Register bus event handlers
        self.bus.subscribe(MessageEvent, self.handle_message_event)
        self.bus.subscribe(StateChangeEvent, self.handle_state_event)
        self.bus.subscribe(ToolCallEvent, self.handle_tool_call)
        self.bus.subscribe(ToolResultEvent, self.handle_tool_result)
        self.bus.subscribe(MetricsEvent, self.handle_metrics_event)
        self.bus.subscribe(ToolApprovalRequestEvent, self.handle_approval_request)
        self.bus.subscribe(HITLApprovalRequestEvent, self.handle_hitl_approval_request)
        self.bus.subscribe(EvaluationResultEvent, self.handle_eval_event)
        self.bus.subscribe(WorkflowStartedEvent, self.handle_workflow_started)
        self.bus.subscribe(WorkflowNodeStartedEvent, self.handle_workflow_node_started)
        self.bus.subscribe(WorkflowNodeCompletedEvent, self.handle_workflow_node_completed)
        self.bus.subscribe(WorkflowTransitionEvent, self.handle_workflow_transition)
        self.bus.subscribe(WorkflowCompletedEvent, self.handle_workflow_completed)
        self.bus.subscribe(WorkflowNodeRetryEvent, self.handle_workflow_retry)
        self.bus.subscribe(WorkflowFailedEvent, self.handle_workflow_failed)
        self.bus.subscribe(WorkflowRollbackStartedEvent, self.handle_rollback_started)
        self.bus.subscribe(WorkflowNodeRollbackEvent, self.handle_node_rollback)
        self.bus.subscribe(WorkflowRollbackCompletedEvent, self.handle_rollback_completed)

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
            if self.workflow_file and self.workflow_file.exists():
                from tuikarma.workflow.parser import WorkflowParser
                from tuikarma.workflow.state import WorkflowState
                engine = WorkflowParser.load_from_yaml(self.workflow_file, self.topology)
                self.topology.active_workflow = engine
                engine.set_paused(self.is_paused)
                dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
                dag_widget.set_pipeline_nodes(list(engine.nodes.keys()), workflow_name=engine.name)
                initial_state = WorkflowState(task_description=self.task_spec.description, max_steps=engine.max_steps)
                await engine.execute(initial_state)
            else:
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

    def handle_hitl_approval_request(self, event: HITLApprovalRequestEvent) -> None:
        self.pending_hitl_node = event.node_id
        stream_log = self.query_one("#stream-log", RichLog)
        inspector = self.query_one("#inspector-log", RichLog)
        msg = (
            f"\n[bold bright_yellow]✋ [HITL APPROVAL GATE][/bold bright_yellow] Nút [bold white]'{event.node_id}'[/bold white] "
            f"đang chờ phê duyệt từ người vận hành!\n"
            f"   [yellow]Yêu cầu: {event.prompt}[/yellow]\n"
            f"   [dim yellow]→ Nhấn [bold white][A][/bold white] hoặc gõ [bold white]/approve[/bold white] để Duyệt; gõ [bold white]/reject[/bold white] để Từ chối; gõ [bold white]/inject <chỉ dẫn>[/bold white] để chỉ dẫn.[/dim yellow]\n"
        )
        stream_log.write(msg)
        inspector.write(msg)


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

    def handle_workflow_started(self, event: WorkflowStartedEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_started(event)
        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write(f"\n[bold dark_orange]🔄 [WORKFLOW LAUNCH][/bold dark_orange] DAG: [bold white]{event.workflow_name}[/bold white] ({event.total_nodes} nodes)\n")

    def handle_workflow_node_started(self, event: WorkflowNodeStartedEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_node_started(event)
        metrics_panel = self.query_one("#metrics-panel", MetricsWidget)
        metrics_panel.update_node(event)
        stream_log = self.query_one("#stream-log", RichLog)
        agent_info = f" [bold magenta]({event.agent_name})[/bold magenta]" if event.agent_name else ""
        stream_log.write(f"[bold yellow]▶ [NODE ENTER][/bold yellow] [bold white]{event.node_id}[/bold white]{agent_info} [dim](Loop #{event.iteration})[/dim]")

    def handle_workflow_node_completed(self, event: WorkflowNodeCompletedEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_node_completed(event)

    def handle_workflow_transition(self, event: WorkflowTransitionEvent) -> None:
        stream_log = self.query_one("#stream-log", RichLog)
        reason_str = f" [dim]({event.reason})[/dim]" if event.reason else ""
        stream_log.write(f"[bold cyan]➔ [DAG TRANSITION][/bold cyan] {event.from_node} ➔ [bold white]{event.to_node}[/bold white]{reason_str}\n")

    def handle_workflow_completed(self, event: WorkflowCompletedEvent) -> None:
        stream_log = self.query_one("#stream-log", RichLog)
        status_msg = "[bold green]🏁 [WORKFLOW HOÀN TẤT THÀNH CÔNG][/bold green]" if event.success else "[bold red]✖ [WORKFLOW THẤT BẠI][/bold red]"
        stream_log.write(f"\n{status_msg} Total Steps: {event.total_steps} ({event.duration_ms:.0f}ms)\n")

    def handle_workflow_retry(self, event: WorkflowNodeRetryEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_node_retry(event)
        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write(
            f"\n[bold yellow]⏳ [RETRY POLICY #{event.attempt}/{event.max_retries}][/bold yellow] "
            f"Nút [bold white]'{event.node_id}'[/bold white] gặp sự cố: [italic]{event.error_reason}[/italic]\n"
            f"   [dim yellow]Đang chờ {event.delay_seconds:.0f}s... (Gõ '/retry-now' hoặc [bold white][N][/bold white] để retry ngay; [bold white][K][/bold white] để skip)[/dim yellow]"
        )

    def handle_workflow_failed(self, event: WorkflowFailedEvent) -> None:
        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write(
            f"\n[bold red]✖ [WORKFLOW FAILED][/bold red] Nút [bold white]'{event.failed_node_id}'[/bold white] "
            f"đã vượt quá số lần retry cho phép! Đang kích hoạt cơ chế bồi hoàn Rollback...\n"
        )

    def handle_rollback_started(self, event: WorkflowRollbackStartedEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_rollback_started(event)
        inspector = self.query_one("#inspector-log", RichLog)
        nodes_str = " ➔ ".join(event.nodes_to_rollback) if event.nodes_to_rollback else "(Không có bước nào)"
        inspector.write(
            f"\n[bold bright_red]↩ [ROLLBACK INITIATED][/bold bright_red] "
            f"Thứ tự hoàn tác đảo ngược: [yellow]{nodes_str}[/yellow]\n"
        )

    def handle_node_rollback(self, event: WorkflowNodeRollbackEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_node_rollback(event)
        inspector = self.query_one("#inspector-log", RichLog)
        status_color = "yellow" if event.status == "STARTING" else "green" if event.status == "COMPLETED" else "red"
        inspector.write(
            f"[{status_color}]↩ [ROLLBACK {event.status}][/{status_color}] Nút '{event.node_id}': {event.details or ''}"
        )

    def handle_rollback_completed(self, event: WorkflowRollbackCompletedEvent) -> None:
        dag_widget = self.query_one("#workflow-dag-widget", WorkflowDAGWidget)
        dag_widget.handle_rollback_completed(event)
        stream_log = self.query_one("#stream-log", RichLog)
        inspector = self.query_one("#inspector-log", RichLog)
        summary = f"Đã hoàn tất hoàn tác các nút: {event.rolled_back_nodes}"
        stream_log.write(f"[bold bright_cyan]✔ [ROLLBACK HOÀN TẤT][/bold bright_cyan] {summary}\n")
        inspector.write(f"[bold bright_cyan]✔ [ROLLBACK HOÀN TẤT][/bold bright_cyan] {summary}\n")

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
        elif cmd_lower in ["/retry-now", "/retry", "n"]:
            self.action_immediate_retry()
        elif cmd_lower in ["/skip", "k"]:
            self.action_skip_node()
        elif cmd_lower in ["/rollback", "b"]:
            self.action_force_rollback()
        elif cmd_lower.startswith("/inject "):
            guidance = text[8:].strip()
            self.action_inject_guidance(guidance)
        elif cmd_lower in ["/approve", "a"]:
            self.action_approve_tool()
        elif cmd_lower in ["/reject", "/deny", "d"]:
            self.action_reject_hitl()
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

    def action_immediate_retry(self) -> None:
        if self.topology.active_workflow:
            self.topology.active_workflow.trigger_immediate_retry()
            stream_log = self.query_one("#stream-log", RichLog)
            stream_log.write("\n[bold yellow]⚡ [HITL ACTION][/bold yellow] Kích hoạt [bold white]RETRY NGAY LẬP TỨC[/bold white] (bỏ qua đếm lùi)!\n")

    def action_skip_node(self) -> None:
        if self.topology.active_workflow:
            self.topology.active_workflow.skip_current_node()
            stream_log = self.query_one("#stream-log", RichLog)
            stream_log.write("\n[bold yellow]⚡ [HITL ACTION][/bold yellow] Bỏ qua nút hiện tại [bold white](SKIP NODE)[/bold white] và tiếp tục!\n")

    def action_force_rollback(self) -> None:
        if self.topology.active_workflow:
            self.topology.active_workflow.force_rollback()
            stream_log = self.query_one("#stream-log", RichLog)
            stream_log.write("\n[bold bright_red]⚡ [HITL ACTION][/bold bright_red] Dừng retry và [bold white]KÍCH HOẠT SAGA ROLLBACK[/bold white] ngay lập tức!\n")

    def action_inject_guidance(self, guidance: str) -> None:
        if self.topology.active_workflow:
            self.topology.active_workflow.inject_guidance(guidance)
        stream_log = self.query_one("#stream-log", RichLog)
        stream_log.write(f"\n[bold yellow]⚡ [HITL INJECTION][/bold yellow] Đã nạp chỉ dẫn cho lần retry kế tiếp: [italic]{guidance}[/italic]\n")

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
        asyncio.create_task(self.bus.publish(HITLCommandEvent(action=HITLAction.APPROVE)))
        inspector = self.query_one("#inspector-log", RichLog)
        stream_log = self.query_one("#stream-log", RichLog)
        if getattr(self, "pending_hitl_node", None):
            node_id = self.pending_hitl_node
            self.pending_hitl_node = None
            asyncio.create_task(
                self.bus.publish(
                    HITLApprovalResponseEvent(
                        node_id=node_id,
                        approved=True,
                        guidance="Chấp thuận bởi người vận hành (UI)"
                    )
                )
            )
            stream_log.write(f"\n[bold green]✔ [APPROVED BY OPERATOR][/bold green] Đã chấp thuận bước [bold white]'{node_id}'[/bold white].\n")
        elif self.pending_approval:
            self.pending_approval = False
            inspector.write("[bold green]✔ [APPROVED BY HUMAN][/bold green] Lệnh nguy hiểm đã được cấp phép thực thi.\n")
        else:
            inspector.write("[dim]Đã gửi tín hiệu Approve.[/dim]\n")

    def action_reject_hitl(self) -> None:
        asyncio.create_task(self.bus.publish(HITLCommandEvent(action=HITLAction.REJECT)))
        stream_log = self.query_one("#stream-log", RichLog)
        if getattr(self, "pending_hitl_node", None):
            node_id = self.pending_hitl_node
            self.pending_hitl_node = None
            asyncio.create_task(
                self.bus.publish(
                    HITLApprovalResponseEvent(
                        node_id=node_id,
                        approved=False,
                        guidance="Bị từ chối bởi người vận hành (UI)"
                    )
                )
            )
            stream_log.write(f"\n[bold red]✖ [REJECTED BY OPERATOR][/bold red] Đã từ chối bước [bold white]'{node_id}'[/bold white].\n")
        else:
            stream_log.write("[dim]Không có bước HITL nào đang chờ duyệt để từ chối.[/dim]\n")


    def action_restart_task(self) -> None:
        if self._task_coro and not self._task_coro.done():
            self._task_coro.cancel()

        stream_log = self.query_one("#stream-log", RichLog)
        inspector_log = self.query_one("#inspector-log", RichLog)
        stream_log.clear()
        inspector_log.clear()

        stream_log.write(f"[bold magenta]▶ [HARNESS RESTARTED][/bold magenta] Task: [bold white]{self.task_spec.title}[/bold white]\n")
        self._task_coro = asyncio.create_task(self._run_task())

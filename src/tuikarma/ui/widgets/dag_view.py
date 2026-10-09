"""Workflow DAG Visualizer Widget for Textual TUI (2026 Cyber Dark Edition)."""

from __future__ import annotations
from typing import Dict, List, Optional
from textual.widgets import Static
from rich.text import Text
from rich.panel import Panel

from tuikarma.core.events import (
    WorkflowStartedEvent,
    WorkflowNodeStartedEvent,
    WorkflowNodeCompletedEvent,
    WorkflowNodeRetryEvent,
    WorkflowFailedEvent,
    WorkflowRollbackStartedEvent,
    WorkflowNodeRollbackEvent,
    WorkflowRollbackCompletedEvent,
    WorkflowTransitionEvent,
)


class WorkflowDAGWidget(Static):
    """Real-time visualization of workflow pipeline DAG execution, retries and rollback."""

    DEFAULT_CSS = """
    WorkflowDAGWidget {
        height: 4;
        width: 100%;
        margin-bottom: 1;
        background: #0d1117;
        color: #e6edf3;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.workflow_name: str = "Multi-Agent DAG"
        self.node_order: List[str] = ["plan", "code", "test", "evaluate_test", "review", "synthesize"]
        self.node_states: Dict[str, Dict[str, Any]] = {}
        self.active_node: Optional[str] = None
        self.is_rollback: bool = False
        self._init_nodes()

    def _init_nodes(self) -> None:
        for nid in self.node_order:
            self.node_states[nid] = {
                "status": "PENDING",
                "attempt": 0,
                "max_retries": 3,
                "delay": 30.0,
            }

    def on_mount(self) -> None:
        self.render_graph()

    def set_pipeline_nodes(self, node_ids: List[str], workflow_name: str = "Multi-Agent DAG") -> None:
        """Dynamically configure nodes in this pipeline."""
        self.workflow_name = workflow_name
        self.node_order = list(node_ids)
        self._init_nodes()
        self.render_graph()

    def handle_started(self, event: WorkflowStartedEvent) -> None:
        self.workflow_name = event.workflow_name
        self.is_rollback = False
        self.render_graph()

    def handle_node_started(self, event: WorkflowNodeStartedEvent) -> None:
        nid = event.node_id
        if nid not in self.node_order:
            self.node_order.append(nid)
        st_dict = self.node_states.setdefault(nid, {})
        st_dict["status"] = "RUNNING"
        st_dict["type"] = event.node_type
        self.active_node = nid
        self.render_graph()

    def handle_node_completed(self, event: WorkflowNodeCompletedEvent) -> None:
        nid = event.node_id
        if nid in self.node_states:
            self.node_states[nid]["status"] = event.status
        self.render_graph()

    def handle_node_retry(self, event: WorkflowNodeRetryEvent) -> None:
        nid = event.node_id
        if nid in self.node_states:
            self.node_states[nid]["status"] = "RETRYING"
            self.node_states[nid]["attempt"] = event.attempt
            self.node_states[nid]["max_retries"] = event.max_retries
            self.node_states[nid]["delay"] = event.delay_seconds
        self.render_graph()

    def handle_rollback_started(self, event: WorkflowRollbackStartedEvent) -> None:
        self.is_rollback = True
        self.render_graph()

    def handle_node_rollback(self, event: WorkflowNodeRollbackEvent) -> None:
        nid = event.node_id
        if nid in self.node_states:
            if event.status == "STARTING":
                self.node_states[nid]["status"] = "ROLLING_BACK"
            elif event.status == "COMPLETED":
                self.node_states[nid]["status"] = "ROLLED_BACK"
            elif event.status == "FAILED":
                self.node_states[nid]["status"] = "ROLLBACK_FAILED"
        self.render_graph()

    def handle_rollback_completed(self, event: WorkflowRollbackCompletedEvent) -> None:
        self.render_graph()

    def render_graph(self) -> None:
        """Renders rich terminal badges for each node and directional arrows."""
        segments: List[str] = []

        arrow = " [bold magenta]◄──[/bold magenta] " if self.is_rollback else " [dim cyan]──►[/dim cyan] "

        for i, nid in enumerate(self.node_order):
            st = self.node_states.get(nid, {}).get("status", "PENDING")
            ntype = self.node_states.get(nid, {}).get("type", "")
            attempt = self.node_states.get(nid, {}).get("attempt", 0)
            max_r = self.node_states.get(nid, {}).get("max_retries", 3)
            delay = self.node_states.get(nid, {}).get("delay", 30.0)

            if st == "PENDING":
                badge = f"[dim cyan]○ {nid}[/dim cyan]"
            elif st == "RUNNING":
                if ntype == "parallel":
                    badge = f"[bold bright_cyan on #1e3a5f] ⫽ {nid} (PARALLEL) [/bold bright_cyan on #1e3a5f]"
                elif ntype == "hitl":
                    badge = f"[bold bright_yellow on #78350f] ✋ {nid} (CHỜ DUYỆT) [/bold bright_yellow on #78350f]"
                else:
                    badge = f"[bold bright_yellow on #1f2937] ▶ {nid} [/bold bright_yellow on #1f2937]"
            elif st == "SUCCESS":
                suffix = " (⫽)" if ntype == "parallel" else " (✋)" if ntype == "hitl" else ""
                badge = f"[bold green]✔ {nid}{suffix}[/bold green]"
            elif st == "SKIPPED":
                badge = f"[bold yellow]⤼ {nid} (skip)[/bold yellow]"
            elif st == "RETRYING":
                badge = f"[bold black on yellow] ⏳ {nid} ({attempt}/{max_r}) [/bold black on yellow]"
            elif st == "FAILED":
                badge = f"[bold white on red] ✖ {nid} [/bold white on red]"
            elif st == "ROLLING_BACK":
                badge = f"[bold white on #7e22ce] ↩ {nid} [/bold white on #7e22ce]"
            elif st == "ROLLED_BACK":
                badge = f"[dim magenta]↩ {nid}[/dim magenta]"
            elif st == "ROLLBACK_FAILED":
                badge = f"[bold red]⚠ {nid} [/bold red]"
            else:
                badge = f"[white]{nid}[/white]"

            segments.append(badge)

        flow_line = arrow.join(segments)
        title_suffix = " [bold bright_red](SAGA ROLLBACK IN PROGRESS)[/bold bright_red]" if self.is_rollback else ""
        title = f"[bold cyan]⚡ WORKFLOW PIPELINE:[/bold cyan] [bold white]{self.workflow_name}[/bold white]{title_suffix}"

        panel = Panel(
            flow_line,
            title=title,
            border_style="magenta" if self.is_rollback else "cyan",
            padding=(0, 1),
        )
        self.update(panel)

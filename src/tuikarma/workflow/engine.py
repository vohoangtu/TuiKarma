"""Core Workflow Execution Engine for orchestrating Multi-Agent DAGs with Retry & Rollback."""

from __future__ import annotations
import time
import asyncio
from typing import Dict, List, Set, Optional, Any

from pathlib import Path
from tuikarma.tools.snapshot import SandboxSnapshotManager
from tuikarma.core.event_bus import EventBus
from tuikarma.core.events import (
    WorkflowStatus,
    WorkflowStartedEvent,
    WorkflowNodeStartedEvent,
    WorkflowNodeCompletedEvent,
    WorkflowNodeRetryEvent,
    WorkflowFailedEvent,
    WorkflowRollbackStartedEvent,
    WorkflowNodeRollbackEvent,
    WorkflowRollbackCompletedEvent,
    WorkflowTransitionEvent,
    WorkflowCompletedEvent,
)
from tuikarma.workflow.state import WorkflowState, NodeResult
from tuikarma.workflow.node import BaseWorkflowNode, AgentWorkflowNode
from tuikarma.workflow.edge import WorkflowEdge


class WorkflowEngine:
    """Orchestrates execution of graph-based workflows with retries and compensating rollbacks."""

    def __init__(
        self,
        name: str = "Multi-Agent Workflow",
        bus: Optional[EventBus] = None,
        max_steps: int = 15,
        workspace_dir: Optional[Path] = None,
        snapshot_manager: Optional[SandboxSnapshotManager] = None,
    ) -> None:
        self.name = name
        self.bus = bus or EventBus()
        self.max_steps = max_steps
        self.nodes: Dict[str, BaseWorkflowNode] = {}
        self.edges: List[WorkflowEdge] = []
        self.start_node_id: Optional[str] = None
        self.end_node_ids: Set[str] = set()

        if snapshot_manager:
            self.snapshot_manager: Optional[SandboxSnapshotManager] = snapshot_manager
        elif workspace_dir:
            self.snapshot_manager = SandboxSnapshotManager(workspace_dir)
        else:
            self.snapshot_manager = None

        self.status = WorkflowStatus.PENDING
        self.is_paused = False
        self.step_event = asyncio.Event()
        self.step_event.set()

        # HITL control flags & events
        self._retry_interrupt_event = asyncio.Event()
        self._skip_requested = False
        self._force_rollback_requested = False
        self.hitl_guidance: Optional[str] = None

    def trigger_immediate_retry(self) -> None:
        """Interrupts waiting delay during retry and triggers immediate attempt."""
        self._retry_interrupt_event.set()

    def skip_current_node(self) -> None:
        """Bypasses remaining retries and forces current node to proceed as skipped."""
        self._skip_requested = True
        self._retry_interrupt_event.set()

    def force_rollback(self) -> None:
        """Aborts retries and immediately initiates Saga rollback."""
        self._force_rollback_requested = True
        self._retry_interrupt_event.set()

    def inject_guidance(self, text: str) -> None:
        """Injects human guidance context into workflow state for next attempt."""
        self.hitl_guidance = text

    def add_node(self, node: BaseWorkflowNode, is_start: bool = False, is_end: bool = False) -> WorkflowEngine:
        """Adds a node to the workflow graph."""
        self.nodes[node.node_id] = node
        if is_start or self.start_node_id is None:
            self.start_node_id = node.node_id
        if is_end:
            self.end_node_ids.add(node.node_id)
        return self

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Any] = None,
        name: str = ""
    ) -> WorkflowEngine:
        """Adds a directional edge with optional condition."""
        edge = WorkflowEdge(from_node=from_node, to_node=to_node, condition=condition, name=name)
        self.edges.append(edge)
        return self

    def set_paused(self, paused: bool) -> None:
        """Pause or resume workflow execution."""
        self.is_paused = paused
        if not paused:
            self.step_event.set()
        else:
            self.step_event.clear()

    def step_forward(self) -> None:
        """Advance one node in the workflow during paused state."""
        self.step_event.set()

    async def _wait_if_paused(self) -> None:
        """Pauses execution loop until user steps or resumes."""
        if self.is_paused:
            await self.step_event.wait()
            if self.is_paused:
                self.step_event.clear()

    async def _execute_rollback(self, state: WorkflowState, failed_node_id: str) -> None:
        """Executes compensation transactions in reverse order of successfully completed nodes."""
        nodes_to_rollback = list(reversed(state.completed_nodes))

        await self.bus.publish(
            WorkflowRollbackStartedEvent(
                workflow_name=self.name,
                failed_node_id=failed_node_id,
                nodes_to_rollback=nodes_to_rollback
            )
        )

        for nid in nodes_to_rollback:
            node = self.nodes.get(nid)
            await self.bus.publish(
                WorkflowNodeRollbackEvent(
                    node_id=nid,
                    status="STARTING",
                    details=f"Đang bồi hoàn/rollback thay đổi của nút '{nid}'"
                )
            )

            disk_actions = []
            if self.snapshot_manager and f"checkpoint_before_{nid}" in self.snapshot_manager.checkpoints:
                try:
                    disk_actions = self.snapshot_manager.restore_checkpoint(f"checkpoint_before_{nid}")
                except Exception as e:
                    disk_actions = [f"Lỗi restore disk snapshot: {e}"]

            if node:
                try:
                    await node.rollback(state)
                    state.rolled_back_nodes.append(nid)
                    details = f"Rollback thành công cho nút '{nid}'"
                    if disk_actions:
                        details += f" (Khôi phục file: {', '.join(disk_actions[:3])})"
                    await self.bus.publish(
                        WorkflowNodeRollbackEvent(
                            node_id=nid,
                            status="COMPLETED",
                            details=details
                        )
                    )
                except Exception as e:
                    await self.bus.publish(
                        WorkflowNodeRollbackEvent(
                            node_id=nid,
                            status="FAILED",
                            details=f"Lỗi khi rollback nút '{nid}': {e}"
                        )
                    )

        await self.bus.publish(
            WorkflowRollbackCompletedEvent(
                workflow_name=self.name,
                success=True,
                rolled_back_nodes=state.rolled_back_nodes
            )
        )

    async def execute(self, initial_state: Optional[WorkflowState] = None) -> WorkflowState:
        """Executes the workflow with retries on failure and automated rollback."""
        if not self.start_node_id or self.start_node_id not in self.nodes:
            raise ValueError(f"Invalid workflow '{self.name}': start_node_id is not set or missing.")

        state = initial_state or WorkflowState(max_steps=self.max_steps)
        state.max_steps = self.max_steps
        self.status = WorkflowStatus.RUNNING

        start_time = time.monotonic()
        await self.bus.publish(
            WorkflowStartedEvent(
                workflow_name=self.name,
                total_nodes=len(self.nodes)
            )
        )

        current_node_id: Optional[str] = self.start_node_id

        while current_node_id and state.step_count < state.max_steps:
            await self._wait_if_paused()

            node = self.nodes.get(current_node_id)
            if not node:
                break

            # Capture pre-node filesystem snapshot
            if self.snapshot_manager:
                self.snapshot_manager.create_checkpoint(f"checkpoint_before_{current_node_id}")

            state.current_node_id = current_node_id
            state.step_count += 1
            iteration = state.increment_iteration(current_node_id)

            agent_name = node.agent.name if isinstance(node, AgentWorkflowNode) else None
            await self.bus.publish(
                WorkflowNodeStartedEvent(
                    node_id=current_node_id,
                    node_type=node.node_type,
                    agent_name=agent_name,
                    iteration=iteration
                )
            )

            # Execution with Retry Policy
            attempt = 0
            node_succeeded = False
            last_result: Optional[NodeResult] = None

            while not node_succeeded:
                if self.hitl_guidance:
                    state.set_shared("hitl_guidance", self.hitl_guidance)
                    self.hitl_guidance = None

                node_start = time.monotonic()
                result = await node.execute(state)
                node_duration = (time.monotonic() - node_start) * 1000.0
                last_result = result

                if result.success:
                    node_succeeded = True
                    state.mark_completed(current_node_id)
                    state.set_output(current_node_id, result.output)
                    summary_text = str(result.output)[:120] if result.output else "Done"

                    await self.bus.publish(
                        WorkflowNodeCompletedEvent(
                            node_id=current_node_id,
                            status="SUCCESS",
                            output_summary=summary_text,
                            duration_ms=node_duration
                        )
                    )
                else:
                    error_reason = result.error_message or str(result.output)
                    if attempt < node.max_retries:
                        attempt += 1
                        await self.bus.publish(
                            WorkflowNodeRetryEvent(
                                node_id=current_node_id,
                                attempt=attempt,
                                max_retries=node.max_retries,
                                delay_seconds=node.retry_delay_seconds,
                                error_reason=error_reason
                            )
                        )
                        # Wait between retry attempts with interrupt support
                        self._retry_interrupt_event.clear()
                        self._skip_requested = False
                        self._force_rollback_requested = False

                        if node.retry_delay_seconds > 0:
                            try:
                                await asyncio.wait_for(
                                    self._retry_interrupt_event.wait(),
                                    timeout=node.retry_delay_seconds
                                )
                            except asyncio.TimeoutError:
                                pass

                        if self._force_rollback_requested:
                            # User requested early force rollback
                            break

                        if self._skip_requested:
                            node_succeeded = True
                            state.mark_completed(current_node_id)
                            state.set_output(current_node_id, f"Skipped by Human HITL: {error_reason}")
                            await self.bus.publish(
                                WorkflowNodeCompletedEvent(
                                    node_id=current_node_id,
                                    status="SKIPPED",
                                    output_summary="Bỏ qua bởi người dùng qua HITL",
                                    duration_ms=node_duration
                                )
                            )
                            break
                    else:
                        # Retries exhausted
                        await self.bus.publish(
                            WorkflowNodeCompletedEvent(
                                node_id=current_node_id,
                                status="FAILED",
                                output_summary=f"Thất bại sau {attempt} lần retry: {error_reason}"[:120],
                                duration_ms=node_duration
                            )
                        )
                        break

            # If node permanently failed, trigger Rollback and terminate
            if not node_succeeded:
                err_msg = f"Nút '{current_node_id}' thất bại hoàn toàn sau {node.max_retries} lần retry."
                state.is_failed = True
                state.error_message = err_msg
                self.status = WorkflowStatus.FAILED

                await self.bus.publish(
                    WorkflowFailedEvent(
                        workflow_name=self.name,
                        failed_node_id=current_node_id,
                        error_message=err_msg
                    )
                )

                # Rollback all preceding completed nodes in reverse
                await self._execute_rollback(state, failed_node_id=current_node_id)

                total_duration = (time.monotonic() - start_time) * 1000.0
                await self.bus.publish(
                    WorkflowCompletedEvent(
                        workflow_name=self.name,
                        total_steps=state.step_count,
                        success=False,
                        duration_ms=total_duration
                    )
                )
                return state

            # Record in state history
            state.history.append({
                "step": state.step_count,
                "node_id": current_node_id,
                "iteration": iteration,
                "success": True,
                "duration_ms": node_duration
            })

            # Check terminal condition
            if current_node_id in self.end_node_ids:
                break

            # Find next node
            next_node_id = None
            transition_reason = None

            if last_result and last_result.next_node_override:
                next_node_id = last_result.next_node_override
                transition_reason = f"Decision Override -> {next_node_id}"
            else:
                for edge in self.edges:
                    if edge.from_node == current_node_id and await edge.can_traverse(state):
                        next_node_id = edge.to_node
                        transition_reason = edge.name
                        break

            if next_node_id:
                await self.bus.publish(
                    WorkflowTransitionEvent(
                        from_node=current_node_id,
                        to_node=next_node_id,
                        reason=transition_reason
                    )
                )
                current_node_id = next_node_id
            else:
                break

        total_duration = (time.monotonic() - start_time) * 1000.0
        self.status = WorkflowStatus.COMPLETED

        await self.bus.publish(
            WorkflowCompletedEvent(
                workflow_name=self.name,
                total_steps=state.step_count,
                success=True,
                duration_ms=total_duration
            )
        )

        return state

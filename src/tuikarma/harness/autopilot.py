"""AutoPilot Autonomous Execution Engine for TUIKarma.
Orchestrates multi-milestone project lifecycle, self-learning reflexion, and disk checkpoints.
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable

from tuikarma.core.event_bus import EventBus
from tuikarma.core.events import (
    BaseEvent,
    MessageEvent,
    WorkflowStartedEvent,
    WorkflowCompletedEvent,
)
from tuikarma.core.topology import SwarmTopology
from tuikarma.core.llm import BaseLLMProvider
from tuikarma.project.manager import ProjectMetadata, ProjectManager
from tuikarma.memory.reflexion import ExperienceStore
from tuikarma.harness.planner import AutonomousPlanner, ProjectPlan, Milestone
from tuikarma.workflow.parser import WorkflowParser
from tuikarma.workflow.state import WorkflowState
from tuikarma.tools.snapshot import SandboxSnapshotManager

logger = logging.getLogger("tuikarma.autopilot")


class AutoPilotRunner:
    """Autonomous engine that plans, decomposes, executes, reflects, and persists projects."""

    def __init__(
        self,
        project: ProjectMetadata,
        llm: BaseLLMProvider,
        bus: Optional[EventBus] = None,
        memory_store: Optional[ExperienceStore] = None,
        project_manager: Optional[ProjectManager] = None,
    ) -> None:
        self.project = project
        self.llm = llm
        self.bus = bus or EventBus()
        self.memory_store = memory_store or ExperienceStore()
        self.project_manager = project_manager or ProjectManager()
        self.planner = AutonomousPlanner(llm=self.llm)
        self.is_running = False
        self.current_milestone: Optional[Milestone] = None
        self.plan: Optional[ProjectPlan] = None

    async def run(self) -> Dict[str, Any]:
        """Main autonomous execution loop from high-level goal to final deliverables."""
        self.is_running = True
        proj_dir = Path(self.project.path)
        proj_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting AutoPilot for project '{self.project.name}' at {proj_dir}")

        # Step 1: Scan codebase if opening existing folder
        codebase_summary = self.project_manager.scan_project_codebase(self.project.path)

        # Step 2: Retrieve relevant cumulative lessons learned
        lessons_context = self.memory_store.format_lessons_for_prompt(self.project.goal)

        # Step 3: Autonomous Planning & Milestone Decomposition
        await self.bus.publish(
            MessageEvent(
                sender="AutoPilot [Planner]",
                receiver="Supervisor",
                content=f"Bắt đầu phân tích dự án '{self.project.name}'. Mục tiêu: {self.project.goal}"
            )
        )

        self.plan = await self.planner.plan_project(
            goal=self.project.goal,
            codebase_summary=codebase_summary,
            lessons_context=lessons_context,
        )

        self.project.milestones = [m.model_dump() for m in self.plan.milestones]
        self.project.status = "IN_PROGRESS"
        self.project_manager._save_registry()

        plan_summary = "\n".join([f"- [{m.id}] {m.title}: {m.goal}" for m in self.plan.milestones])
        await self.bus.publish(
            MessageEvent(
                sender="AutoPilot [Planner]",
                receiver="Swarm",
                content=f"Đã lập kế hoạch gồm {len(self.plan.milestones)} Cột mốc (Milestones):\n{plan_summary}"
            )
        )

        # Step 4: Execute Milestones sequentially
        snapshot_mgr = SandboxSnapshotManager(proj_dir)
        completed_count = 0

        for m_data in self.project.milestones:
            m = Milestone(**m_data)
            if m.status == "COMPLETED":
                completed_count += 1
                continue

            self.current_milestone = m
            m.status = "IN_PROGRESS"

            await self.bus.publish(
                MessageEvent(
                    sender="AutoPilot [Engine]",
                    receiver="Supervisor",
                    content=f"▶ Bắt đầu thực thi Cột mốc [{m.id}]: {m.title}"
                )
            )

            # Create checkpoint before milestone
            snapshot_mgr.create_checkpoint(f"checkpoint_before_{m.id}")

            # Instantiate Swarm Topology bound to project directory
            swarm = SwarmTopology(self.bus, workspace_dir=proj_dir, llm=self.llm)

            # Build enriched milestone prompt with cumulative lessons
            enriched_prompt = (
                f"Mục tiêu Cột mốc [{m.id} - {m.title}]: {m.goal}\n"
                f"Sản phẩm bàn giao cần tạo/sửa: {', '.join(m.deliverables)}\n"
                f"Tiêu chuẩn nghiệm thu: {', '.join(m.acceptance_criteria)}\n"
                f"{lessons_context}"
            )

            # Run milestone using parallel TDD pipeline if available, or direct task loop
            pipeline_file = Path("tasks/pipelines/parallel_tdd_pipeline.yaml")
            success = False

            if pipeline_file.exists():
                try:
                    engine = WorkflowParser.load_from_yaml(pipeline_file, swarm)
                    swarm.active_workflow = engine
                    initial_state = WorkflowState(task_description=enriched_prompt, max_steps=engine.max_steps)
                    initial_state.set_shared("headless_mode", True)
                    final_state = await engine.execute(initial_state)
                    success = not final_state.is_failed
                    m.result_summary = f"Hoàn thành các bước: {final_state.completed_nodes}"
                except Exception as e:
                    logger.warning(f"Pipeline execution error on {m.id}: {e}")
                    success = False
            else:
                try:
                    await swarm.execute_task_loop(enriched_prompt)
                    success = True
                    m.result_summary = "Thực thi hoàn tất qua Swarm coordination."
                except Exception as e:
                    logger.error(f"Execution error on {m.id}: {e}")
                    success = False

            if success:
                m.status = "COMPLETED"
                completed_count += 1
                # Self-learning: record positive pattern reinforcement
                if "concurrency" in m.goal.lower() or "async" in m.goal.lower():
                    self.memory_store.record_lesson(
                        domain="concurrency",
                        trigger_error="Xử lý tải cao và bảo vệ race condition",
                        root_cause="Thành công áp dụng async locks và token bucket",
                        lesson_learned=f"Thành công triển khai cột mốc {m.id} chuẩn thread-safety.",
                        recommended_pattern="# Clean verified async pattern",
                    )
            else:
                m.status = "FAILED"
                # Record failure lesson for future self-healing
                self.memory_store.record_lesson(
                    domain="workflow",
                    trigger_error=f"Thất bại tại cột mốc {m.id}",
                    root_cause="Vượt quá số lần thử hoặc xung đột cấu trúc",
                    lesson_learned=f"Cần phân rã nhỏ hơn hoặc nạp spec chi tiết hơn cho {m.title}.",
                )
                break

            # Update registry
            for idx, item in enumerate(self.project.milestones):
                if item["id"] == m.id:
                    self.project.milestones[idx] = m.model_dump()
            self.project.updated_at = time.time()
            self.project_manager._save_registry()

        # Step 5: Final Wrap Up
        all_done = completed_count == len(self.project.milestones)
        self.project.status = "COMPLETED" if all_done else "PAUSED"
        self.project.updated_at = time.time()
        self.project_manager._save_registry()
        self.is_running = False

        status_msg = "✔ Toàn bộ dự án đã hoàn thành thắng lợi!" if all_done else "⚠ Dự án tạm dừng tại cột mốc dở dang."
        await self.bus.publish(
            MessageEvent(
                sender="AutoPilot [Engine]",
                receiver="User",
                content=f"{status_msg} ({completed_count}/{len(self.project.milestones)} milestones hoàn tất). Mã nguồn lưu tại: {proj_dir}"
            )
        )

        return {
            "project_id": self.project.id,
            "status": self.project.status,
            "completed_milestones": completed_count,
            "total_milestones": len(self.project.milestones),
            "project_path": str(proj_dir),
        }

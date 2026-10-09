"""Autonomous Project Planner for TUIKarma.
Decomposes high-level user goals into structured milestone sub-tasks with acceptance criteria.
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from tuikarma.core.llm import BaseLLMProvider

logger = logging.getLogger("tuikarma.planner")


class Milestone(BaseModel):
    """Represents an autonomous sub-goal / milestone in a multi-stage project."""
    id: str
    title: str
    goal: str
    deliverables: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    result_summary: Optional[str] = None


class ProjectPlan(BaseModel):
    """The complete structured execution roadmap for a project."""
    project_name: str
    high_level_goal: str
    milestones: List[Milestone] = Field(default_factory=list)


class AutonomousPlanner:
    """Decomposes complex requests into achievable milestones."""

    def __init__(self, llm: Optional[BaseLLMProvider] = None) -> None:
        self.llm = llm

    async def plan_project(
        self,
        goal: str,
        codebase_summary: Optional[Dict[str, Any]] = None,
        lessons_context: str = ""
    ) -> ProjectPlan:
        """Analyzes goal and generates hierarchical milestones."""
        if self.llm and self.llm.__class__.__name__ != "ScenarioLLMProvider":
            try:
                return await self._plan_with_llm(goal, codebase_summary, lessons_context)
            except Exception as e:
                logger.warning(f"LLM planning failed, falling back to heuristic planner: {e}")

        return self._plan_heuristic(goal, codebase_summary)

    async def _plan_with_llm(
        self,
        goal: str,
        codebase_summary: Optional[Dict[str, Any]],
        lessons_context: str
    ) -> ProjectPlan:
        cb_text = ""
        if codebase_summary and codebase_summary.get("total_files", 0) > 0:
            compact_cb = {
                "project_name": codebase_summary.get("project_name"),
                "total_files": codebase_summary.get("total_files"),
                "key_configs": codebase_summary.get("key_configs"),
                "file_types": codebase_summary.get("file_types"),
                "sample_files": (codebase_summary.get("files_sample") or [])[:25],
            }
            cb_text = f"\nThông tin Codebase ({compact_cb['total_files']} files):\n" + json.dumps(compact_cb, indent=2, ensure_ascii=False)

        prompt = f"""Bạn là Trưởng nhóm Kiến trúc sư Phần mềm (Chief Software Architect & Lead Product Manager).
Mục tiêu cấp cao của người dùng:
"{goal}"
{cb_text}
{lessons_context}

Hãy phân tích và phân rã mục tiêu trên thành từ 3 đến 5 Cột mốc (Milestones) tuần tự để đàn Agent (Coder, Tester, Critic) thi công độc lập.
Trả về định dạng JSON DUY NHẤT (không kèm markdown) theo cấu trúc:
{{
  "project_name": "Tên dự án ngắn gọn",
  "high_level_goal": "{goal}",
  "milestones": [
    {{
      "id": "M1",
      "title": "Tên cột mốc 1",
      "goal": "Yêu cầu chi tiết",
      "deliverables": ["file1.py", "file2.py"],
      "acceptance_criteria": ["Đạt chuẩn PEP-8", "Xử lý lỗi đầy đủ"]
    }}
  ]
}}
"""
        response = await self.llm.generate(
            model_name="antigravity/claude-sonnet-4-6",
            system_prompt="You are a Chief Software Architect. Return valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content.strip()
        # Clean potential markdown wrapping
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        data = json.loads(raw.strip())
        return ProjectPlan(**data)

    def _plan_heuristic(
        self,
        goal: str,
        codebase_summary: Optional[Dict[str, Any]]
    ) -> ProjectPlan:
        """Deterministic heuristic fallback when running offline or testing."""
        is_existing = bool(codebase_summary and codebase_summary.get("total_files", 0) > 0)
        proj_name = codebase_summary.get("project_name", "Autonomous Project") if is_existing else "Autonomous Project"

        if is_existing:
            milestones = [
                Milestone(
                    id="M1",
                    title="Khảo sát Codebase & Lập kế hoạch Tích hợp",
                    goal=f"Phân tích cấu trúc thư mục hiện tại và phác thảo giải pháp đáp ứng: {goal}",
                    deliverables=["docs/integration_plan.md"],
                    acceptance_criteria=["Xác định đúng các module cần sửa", "Không làm vỡ API hiện tại"],
                ),
                Milestone(
                    id="M2",
                    title="Triển khai Tính năng Core & Refactoring",
                    goal=f"Viết mã nguồn tính năng mới vào codebase: {goal}",
                    deliverables=["src/", "core_feature.py"],
                    acceptance_criteria=["Type hints đầy đủ", "Thread-safe & async chuẩn mực"],
                ),
                Milestone(
                    id="M3",
                    title="Bộ kiểm thử TDD & Nghiệm thu Toàn diện",
                    goal="Tạo test suite kiểm thử tính năng mới và hồi quy (regression tests)",
                    deliverables=["tests/test_feature.py"],
                    acceptance_criteria=["100% test cases pass", "Không sinh lỗi phụ"],
                ),
            ]
        else:
            milestones = [
                Milestone(
                    id="M1",
                    title="Kiến trúc Nền tảng & Thiết kế Module Core",
                    goal=f"Thiết kế kiến trúc hệ thống và xây dựng các cấu trúc dữ liệu cốt lõi cho: {goal}",
                    deliverables=["core.py", "config.py"],
                    acceptance_criteria=["Kiến trúc module hóa rõ ràng", "Thiết kế API clean"],
                ),
                Milestone(
                    id="M2",
                    title="Triển khai Logic Nghiệp vụ & Xử lý Ngoại lệ",
                    goal="Lập trình toàn bộ logic chính, xử lý biên và bảo vệ lỗi hệ thống",
                    deliverables=["engine.py", "handlers.py"],
                    acceptance_criteria=["Bảo vệ race conditions", "Clean error handling"],
                ),
                Milestone(
                    id="M3",
                    title="Xây dựng Bộ Test Suite TDD & Tối ưu Hiệu năng",
                    goal="Thiết kế các kịch bản kiểm thử tự động, đo lường độ trễ và tối ưu mã nguồn",
                    deliverables=["tests/test_engine.py"],
                    acceptance_criteria=["Đạt 100% pass unit tests", "Bảo mật và hiệu năng cao"],
                ),
            ]

        return ProjectPlan(
            project_name=proj_name,
            high_level_goal=goal,
            milestones=milestones,
        )

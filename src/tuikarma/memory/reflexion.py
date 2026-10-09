"""Reflexion & Long-Term Experience Memory Engine for TUIKarma.
Enables self-learning, post-mortem reflection and knowledge accumulation across tasks and projects.
"""

from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("tuikarma.memory")


class ExperienceLesson(BaseModel):
    """Represents a structured lesson learned from a bug, failure, or successful refactoring."""
    id: str
    domain: str  # e.g., 'concurrency', 'testing', 'api', 'syntax', 'security', 'architecture'
    trigger_error: str
    root_cause: str
    lesson_learned: str
    recommended_pattern: str
    applied_count: int = 0
    created_at: float = Field(default_factory=time.time)


class ExperienceStore:
    """Persistent storage and keyword/domain retriever for cumulative agent learning."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        if storage_path is None:
            self.storage_path = Path("memory/experience_base.json")
        else:
            self.storage_path = Path(storage_path)

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.lessons: List[ExperienceLesson] = []
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.lessons = [ExperienceLesson(**item) for item in data]
                logger.info(f"Loaded {len(self.lessons)} experience lessons from {self.storage_path}")
            except Exception as e:
                logger.warning(f"Failed to load lessons from {self.storage_path}: {e}")
                self.lessons = []
        else:
            # Seed default high-value software engineering rules if brand new
            self._seed_default_lessons()
            self._save()

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [item.model_dump() for item in self.lessons]
            self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save experience lessons to {self.storage_path}: {e}")

    def _seed_default_lessons(self) -> None:
        default_lessons = [
            ExperienceLesson(
                id="LESSON-001",
                domain="concurrency",
                trigger_error="AssertionError: Race condition detected when multiple async tasks acquire tokens simultaneously",
                root_cause="Shared mutable state without mutex lock in Python asyncio",
                lesson_learned="Khi cập nhật state dùng chung trong async code, luôn phải bảo vệ bằng `async with self._lock:`.",
                recommended_pattern="self._lock = asyncio.Lock()\nasync with self._lock:\n    # update shared counters safe from race conditions",
            ),
            ExperienceLesson(
                id="LESSON-002",
                domain="testing",
                trigger_error="ModuleNotFoundError: No module named 'src'",
                root_cause="Import path discrepancy between test execution cwd and source root",
                lesson_learned="Thiết lập sys.path chuẩn hoặc dùng relative/absolute package imports đồng nhất trong test suite.",
                recommended_pattern="import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent.parent))",
            ),
            ExperienceLesson(
                id="LESSON-003",
                domain="syntax",
                trigger_error="KeyError or ValueError during string format with Python code containing curly braces {}",
                root_cause="str.format() treats raw python code braces {dictionary} as template placeholders",
                lesson_learned="Không dùng str.format() với code có ngoặc nhọn; hãy dùng explicit replace placeholder an toàn.",
                recommended_pattern="prompt.replace(f'{{{key}}}', str(value))",
            ),
        ]
        self.lessons.extend(default_lessons)

    def record_lesson(
        self,
        domain: str,
        trigger_error: str,
        root_cause: str,
        lesson_learned: str,
        recommended_pattern: str = ""
    ) -> ExperienceLesson:
        """Records a new learned experience lesson and saves it to persistent storage."""
        lesson_id = f"LESSON-{len(self.lessons) + 1:03d}"
        lesson = ExperienceLesson(
            id=lesson_id,
            domain=domain.lower(),
            trigger_error=trigger_error.strip(),
            root_cause=root_cause.strip(),
            lesson_learned=lesson_learned.strip(),
            recommended_pattern=recommended_pattern.strip(),
        )
        self.lessons.append(lesson)
        self._save()
        logger.info(f"Recorded new experience lesson: {lesson_id} [{domain}]")
        return lesson

    def retrieve_relevant_lessons(self, query: str, limit: int = 3) -> List[ExperienceLesson]:
        """Retrieves top relevant lessons based on domain and keyword matching."""
        if not self.lessons:
            return []

        query_lower = query.lower()
        scored: List[tuple[int, ExperienceLesson]] = []

        for lesson in self.lessons:
            score = 0
            if lesson.domain in query_lower:
                score += 5
            # Word overlap
            keywords = [w for w in (lesson.root_cause + " " + lesson.lesson_learned).lower().split() if len(w) > 3]
            for kw in keywords:
                if kw in query_lower:
                    score += 1
            if score > 0:
                scored.append((score, lesson))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [l for _, l in scored[:limit]]

        # If no specific match, return latest general lessons
        if not results:
            results = self.lessons[-limit:]

        for r in results:
            r.applied_count += 1
        self._save()

        return results

    def format_lessons_for_prompt(self, query: str) -> str:
        """Formats relevant lessons into a prompt injection block for Agent guidance."""
        relevant = self.retrieve_relevant_lessons(query)
        if not relevant:
            return ""

        lines = ["\n[BÀI HỌC KINH NGHIỆM ĐÃ TÍCH LŨY (SELF-LEARNING KNOWLEDGE BASE)]:"]
        for idx, l in enumerate(relevant, 1):
            lines.append(f"{idx}. [{l.domain.upper()}] Khi gặp: {l.trigger_error[:90]}...")
            lines.append(f"   ➔ Nguyên nhân: {l.root_cause}")
            lines.append(f"   ➔ Rút kinh nghiệm: {l.lesson_learned}")
            if l.recommended_pattern:
                lines.append(f"   ➔ Khuyến nghị áp dụng:\n{l.recommended_pattern}")
        lines.append("[Hãy tuân thủ các kinh nghiệm trên để tránh lặp lại lỗi cũ]\n")
        return "\n".join(lines)

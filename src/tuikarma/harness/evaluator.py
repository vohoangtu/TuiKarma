"""Automated Evaluation & Benchmarking for Multi-Agent Tasks."""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from tuikarma.harness.task import TaskSpec, EvaluationCriterion
from tuikarma.core.events import EvaluationResultEvent
from tuikarma.core.event_bus import EventBus


class TaskEvaluator:
    """Evaluates agent swarm artifacts against task criteria."""

    def __init__(self, workspace_dir: Path, bus: Optional[EventBus] = None) -> None:
        self.workspace_dir = workspace_dir
        self.bus = bus

    async def evaluate_task(self, task_spec: TaskSpec) -> EvaluationResultEvent:
        """Run comprehensive checks against task criteria."""
        criteria_scores: Dict[str, float] = {}
        total_weight = 0.0
        weighted_score = 0.0

        for crit in task_spec.criteria:
            weight = crit.weight
            total_weight += weight
            score = await self._evaluate_criterion(crit)
            criteria_scores[crit.name] = score
            weighted_score += score * weight

        final_score = (weighted_score / total_weight) if total_weight > 0 else 1.0
        passed = final_score >= 0.7  # Passing threshold: 70%

        feedback = []
        for name, score in criteria_scores.items():
            status = "PASS" if score >= 0.7 else "FAIL"
            feedback.append(f"- {name}: {score*100:.1f}% [{status}]")
        feedback_str = "\n".join(feedback)

        eval_event = EvaluationResultEvent(
            task_id=task_spec.id,
            score=final_score,
            passed=passed,
            criteria_scores=criteria_scores,
            feedback=feedback_str
        )

        if self.bus:
            await self.bus.publish(eval_event)

        return eval_event

    async def _evaluate_criterion(self, criterion: EvaluationCriterion) -> float:
        """Evaluates a single criterion based on generated artifacts in sandbox."""
        crit_name_lower = criterion.name.lower()

        # Check code correctness & files
        if "correctness" in crit_name_lower or "code" in crit_name_lower:
            py_files = list(self.workspace_dir.glob("*.py"))
            if not py_files:
                return 0.0
            # Check syntax validity of generated files
            valid_syntax = True
            for f in py_files:
                try:
                    compile(f.read_text(encoding="utf-8"), str(f), "exec")
                except SyntaxError:
                    valid_syntax = False
            return 1.0 if valid_syntax else 0.4

        # Check test coverage
        elif "test" in crit_name_lower or "coverage" in crit_name_lower:
            test_files = list(self.workspace_dir.glob("**/test_*.py")) + list(self.workspace_dir.glob("tests/*.py"))
            if test_files:
                return 1.0
            return 0.3

        # Check security / review
        elif "security" in crit_name_lower or "review" in crit_name_lower:
            # Check if any dangerous calls exist
            for f in self.workspace_dir.glob("**/*.py"):
                content = f.read_text(encoding="utf-8")
                if "eval(" in content or "exec(" in content:
                    return 0.2
            return 1.0

        return 0.85

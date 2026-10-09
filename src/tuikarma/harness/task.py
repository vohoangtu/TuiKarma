"""Task and evaluation specification for Multi-Agent Harness."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import yaml


class EvaluationCriterion(BaseModel):
    name: str
    description: str
    weight: float = 1.0


class TaskSpec(BaseModel):
    id: str
    title: str
    description: str
    max_steps: int = 10
    timeout_seconds: int = 120
    criteria: List[EvaluationCriterion] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> TaskSpec:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

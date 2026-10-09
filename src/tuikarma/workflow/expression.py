"""Safe expression evaluator for workflow edge conditions and decision gates."""

from __future__ import annotations
import logging
from typing import Any, Dict
from tuikarma.workflow.state import WorkflowState

logger = logging.getLogger(__name__)


def safe_evaluate_condition(expr: str, state: WorkflowState) -> bool:
    """Evaluates a condition expression string safely against the current WorkflowState.

    Available variables in evaluation scope:
      - `state`: full WorkflowState object
      - `outputs`: dict of all node outputs (state.node_outputs)
      - `completed`: list of completed node IDs
      - `iterations`: dict of node iteration counts
      - `task`: task description string
      - `shared`: dict of shared workflow data
      - Helper functions: `contains(text, sub)`, `has(key)`, `get(key, default)`
      - Unpacked node outputs for valid identifier keys (e.g., if node 'review' exists, `review` is available)
    """
    cleaned_expr = expr.strip()
    if not cleaned_expr:
        return True

    if cleaned_expr.lower() in ("true", "1", "yes", "*", "default"):
        return True
    if cleaned_expr.lower() in ("false", "0", "no"):
        return False

    def _contains(target: Any, substring: str) -> bool:
        if target is None:
            return False
        return substring.lower() in str(target).lower()

    def _has(key: str) -> bool:
        return key in state.node_outputs

    def _get(key: str, default: Any = "") -> Any:
        return state.node_outputs.get(key, default)

    eval_globals: Dict[str, Any] = {
        "__builtins__": {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "len": len,
            "any": any,
            "all": all,
            "min": min,
            "max": max,
            "isinstance": isinstance,
            "dict": dict,
            "list": list,
        }
    }

    eval_locals: Dict[str, Any] = {
        "state": state,
        "outputs": state.node_outputs,
        "completed": state.completed_nodes,
        "iterations": state.iterations,
        "task": state.task_description,
        "shared": state.shared_data,
        "contains": _contains,
        "has": _has,
        "get": _get,
    }

    # Unpack valid identifier node outputs into locals for clean expressions
    for k, v in state.node_outputs.items():
        if k.isidentifier() and k not in eval_locals:
            eval_locals[k] = v

    for k, v in state.shared_data.items():
        if k.isidentifier() and k not in eval_locals:
            eval_locals[k] = v

    try:
        result = eval(cleaned_expr, eval_globals, eval_locals)
        return bool(result)
    except Exception as exc:
        logger.debug("Failed evaluating condition expression '%s': %s", cleaned_expr, exc)
        return False

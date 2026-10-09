"""Declarative YAML Workflow DSL Parser for TUIKarma."""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING
import yaml

from tuikarma.workflow.engine import WorkflowEngine
from tuikarma.workflow.node import (
    BaseWorkflowNode,
    AgentWorkflowNode,
    DecisionWorkflowNode,
    ToolWorkflowNode,
    ParallelWorkflowNode,
    HITLWorkflowNode,
)
from tuikarma.workflow.edge import WorkflowEdge
from tuikarma.workflow.expression import safe_evaluate_condition
from tuikarma.workflow.state import WorkflowState

if TYPE_CHECKING:
    from tuikarma.core.topology import SwarmTopology


class WorkflowParser:
    """Parses declarative YAML specifications into executable WorkflowEngine DAG graphs."""

    @classmethod
    def _parse_node(
        cls,
        n_conf: Dict[str, Any],
        swarm: SwarmTopology,
        default_max_retries: int,
        default_retry_delay: float
    ) -> BaseWorkflowNode:
        """Recursively parses a node configuration dictionary into a BaseWorkflowNode instance."""
        node_id = n_conf["id"]
        node_name = n_conf.get("name", node_id)
        node_type = n_conf.get("type", "agent").lower()

        retry_conf = n_conf.get("retry_policy", {})
        max_retries = int(retry_conf.get("max_retries", default_max_retries))
        retry_delay = float(retry_conf.get("delay_seconds", default_retry_delay))

        if node_type == "agent":
            agent_name = n_conf.get("agent", "Supervisor")
            agent = swarm.agents.get(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' defined in node '{node_id}' not found in Swarm.")

            prompt_tmpl = n_conf.get("prompt", "")
            model_name = n_conf.get("model", None)

            return AgentWorkflowNode(
                node_id=node_id,
                name=node_name,
                agent=agent,
                prompt_template=prompt_tmpl,
                model_name=model_name,
                max_retries=max_retries,
                retry_delay_seconds=retry_delay,
            )
        elif node_type == "parallel":
            branch_confs = n_conf.get("branches", [])
            branch_nodes = [
                cls._parse_node(b, swarm, default_max_retries, default_retry_delay)
                for b in branch_confs
            ]
            return ParallelWorkflowNode(
                node_id=node_id,
                name=node_name,
                branches=branch_nodes,
                max_retries=max_retries,
                retry_delay_seconds=retry_delay,
            )
        elif node_type == "decision":
            rules = n_conf.get("rules", [])

            def _build_decision_fn(rules_list: List[Dict[str, str]]) -> Callable[[WorkflowState], str]:
                def _evaluate(state: WorkflowState) -> str:
                    for rule in rules_list:
                        cond = rule.get("condition", "").strip()
                        target = rule.get("target") or rule.get("to") or rule.get("next")
                        if not target:
                            continue
                        if safe_evaluate_condition(cond, state):
                            return target
                    if rules_list:
                        first = rules_list[0]
                        return first.get("target") or first.get("to") or first.get("next") or ""
                    return ""

                return _evaluate

            return DecisionWorkflowNode(
                node_id=node_id,
                name=node_name,
                decision_fn=_build_decision_fn(rules),
            )
        elif node_type == "hitl":
            prompt = n_conf.get("prompt", "Vui lòng xem xét và phê duyệt bước này.")
            timeout_sec = n_conf.get("timeout_seconds")
            timeout_val = float(timeout_sec) if timeout_sec is not None else None
            auto_approve = bool(n_conf.get("auto_approve_in_headless", True))
            return HITLWorkflowNode(
                node_id=node_id,
                name=node_name,
                prompt=prompt,
                bus=swarm.bus,
                timeout_seconds=timeout_val,
                auto_approve_in_headless=auto_approve,
                max_retries=max_retries,
                retry_delay_seconds=retry_delay,
            )
        elif node_type == "tool":
            tool_name = n_conf.get("tool", "")
            tool = swarm.tools.get(tool_name)
            if not tool:
                raise ValueError(f"Tool '{tool_name}' for node '{node_id}' not found in registry.")

            args_extractor = None
            args_tmpl = n_conf.get("args")
            if isinstance(args_tmpl, dict):
                args_extractor = lambda st, tmpl=args_tmpl: {
                    k: str(v).format(**st.node_outputs, **st.shared_data, task_description=st.task_description)
                    for k, v in tmpl.items()
                }

            return ToolWorkflowNode(
                node_id=node_id,
                name=node_name,
                tool=tool,
                args_extractor=args_extractor,
                max_retries=max_retries,
                retry_delay_seconds=retry_delay,
            )
        else:
            raise ValueError(f"Unsupported node type '{node_type}' for node '{node_id}'.")

    @classmethod
    def load_from_yaml(cls, yaml_input: str | Path, swarm: SwarmTopology) -> WorkflowEngine:
        """Parses a YAML string or file path into a configured WorkflowEngine."""
        path = Path(yaml_input)
        if path.exists() and path.is_file():
            raw_content = path.read_text(encoding="utf-8")
        else:
            raw_content = str(yaml_input)

        data = yaml.safe_load(raw_content)
        if not isinstance(data, dict):
            raise ValueError("Workflow YAML root must be a mapping/dict.")

        name = data.get("name", "Declarative YAML Workflow")
        max_steps = int(data.get("max_steps", 15))

        default_retry = data.get("default_retry_policy", {})
        default_max_retries = int(default_retry.get("max_retries", 3))
        default_retry_delay = float(default_retry.get("delay_seconds", 30.0))

        engine = WorkflowEngine(
            name=name,
            bus=swarm.bus,
            max_steps=max_steps,
            workspace_dir=swarm.workspace_dir,
        )

        nodes_data = data.get("nodes", [])
        for n_conf in nodes_data:
            node = cls._parse_node(n_conf, swarm, default_max_retries, default_retry_delay)
            is_start = bool(n_conf.get("is_start", False))
            is_end = bool(n_conf.get("is_end", False))
            engine.add_node(node, is_start=is_start, is_end=is_end)

        edges_data = data.get("edges", [])
        for e_conf in edges_data:
            from_node = e_conf["from"]
            to_node = e_conf["to"]
            edge_name = e_conf.get("name", f"{from_node} -> {to_node}")
            cond_str = e_conf.get("condition")

            engine.add_edge(from_node=from_node, to_node=to_node, condition=cond_str, name=edge_name)

        return engine


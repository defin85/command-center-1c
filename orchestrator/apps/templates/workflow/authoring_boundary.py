from __future__ import annotations

from typing import Any

from apps.templates.workflow.schema import DAGStructure


WORKFLOW_AUTHORING_BOUNDARY_VIOLATION_CODE = "WORKFLOW_AUTHORING_BOUNDARY_VIOLATION"
_RUNTIME_ONLY_NODE_TYPES = frozenset({"parallel", "loop"})


def _compiled_decision_expression(decision_key: str) -> str:
    return f"{{{{ decisions.{decision_key} }}}}"


def collect_authoring_boundary_violations(dag_structure: object) -> list[dict[str, Any]]:
    try:
        dag = dag_structure if isinstance(dag_structure, DAGStructure) else DAGStructure(**dag_structure)
    except Exception:
        return []

    violations: list[dict[str, Any]] = []

    for node in dag.nodes:
        if node.type in _RUNTIME_ONLY_NODE_TYPES:
            violations.append(
                {
                    "kind": "runtime_only_node_type",
                    "node_id": node.id,
                    "node_type": node.type,
                    "message": (
                        f"Node type '{node.type}' is runtime-only and cannot be authored "
                        "on the default workflow surface."
                    ),
                }
            )
            continue

        if node.type != "condition":
            continue

        if node.decision_ref is None:
            violations.append(
                {
                    "kind": "condition_requires_decision_ref",
                    "node_id": node.id,
                    "node_type": node.type,
                    "message": (
                        "Condition nodes must pin a decision_ref on the default workflow surface."
                    ),
                }
            )
            continue

        expected_expression = _compiled_decision_expression(node.decision_ref.decision_key)
        if node.config.expression != expected_expression:
            violations.append(
                {
                    "kind": "condition_expression_must_match_decision_ref",
                    "node_id": node.id,
                    "node_type": node.type,
                    "message": (
                        "Condition expressions are compatibility-only and must match the pinned "
                        "decision_ref compiled expression."
                    ),
                    "details": {
                        "expected_expression": expected_expression,
                        "actual_expression": node.config.expression,
                    },
                }
            )

    for edge in dag.edges:
        edge_condition = str(edge.condition or "").strip()
        if not edge_condition:
            continue
        violations.append(
            {
                "kind": "edge_condition_not_supported",
                "from_node": edge.from_node,
                "to_node": edge.to_node,
                "message": (
                    "Edge-level conditions are compatibility-only and cannot be authored on the "
                    "default workflow surface."
                ),
                "details": {
                    "condition": edge_condition,
                },
            }
        )

    return violations

from __future__ import annotations

from typing import Any, Mapping

from apps.templates.workflow.authoring_contract import (
    DecisionTableContract,
    DecisionTableRef,
    DecisionValidationMode,
    DecisionHitPolicy,
)
from apps.templates.workflow.models import DecisionTable


def build_decision_table_contract(*, decision_table: DecisionTable) -> DecisionTableContract:
    return DecisionTableContract(
        decision_table_id=decision_table.decision_table_id,
        decision_key=decision_table.decision_key,
        decision_revision=decision_table.version_number,
        name=decision_table.name,
        inputs=list(decision_table.inputs or []),
        outputs=list(decision_table.outputs or []),
        rules=list(decision_table.rules or []),
        hit_policy=DecisionHitPolicy(str(decision_table.hit_policy or DecisionHitPolicy.FIRST_MATCH.value)),
        validation_mode=DecisionValidationMode(
            str(decision_table.validation_mode or DecisionValidationMode.FAIL_CLOSED.value)
        ),
    )


def build_decision_table_ref(*, decision_table: DecisionTable) -> DecisionTableRef:
    return DecisionTableRef(
        decision_table_id=decision_table.decision_table_id,
        decision_key=decision_table.decision_key,
        decision_revision=decision_table.version_number,
    )


def create_decision_table_revision(
    *,
    contract: Mapping[str, Any] | DecisionTableContract,
    created_by=None,
    parent_version: DecisionTable | None = None,
) -> DecisionTable:
    payload = dict(contract) if isinstance(contract, Mapping) else contract.model_dump(mode="json")
    parent = parent_version
    if parent is None and payload.get("parent_version_id"):
        parent = (
            DecisionTable.objects.filter(id=payload["parent_version_id"])
            .only("id", "decision_table_id", "decision_key", "version_number")
            .first()
        )
        if parent is None:
            raise ValueError("parent_version_id does not reference an existing decision table")

    version_number = int(parent.version_number + 1) if parent is not None else 1
    parsed = DecisionTableContract(
        decision_table_id=str(
            payload.get("decision_table_id")
            or (parent.decision_table_id if parent is not None else "")
        ),
        decision_key=str(
            payload.get("decision_key")
            or (parent.decision_key if parent is not None else "")
        ),
        decision_revision=version_number,
        name=str(payload.get("name") or ""),
        inputs=list(payload.get("inputs") or []),
        outputs=list(payload.get("outputs") or []),
        rules=list(payload.get("rules") or []),
        hit_policy=str(payload.get("hit_policy") or DecisionHitPolicy.FIRST_MATCH.value),
        validation_mode=str(
            payload.get("validation_mode") or DecisionValidationMode.FAIL_CLOSED.value
        ),
    )
    if parent is not None:
        if parsed.decision_table_id != parent.decision_table_id:
            raise ValueError("decision_table_id must match parent_version decision_table_id")
        if parsed.decision_key != parent.decision_key:
            raise ValueError("decision_key must match parent_version decision_key")

    return DecisionTable.objects.create(
        decision_table_id=parsed.decision_table_id,
        decision_key=parsed.decision_key,
        name=parsed.name,
        description=str(payload.get("description") or ""),
        inputs=[field.model_dump(mode="json") for field in parsed.inputs],
        outputs=[field.model_dump(mode="json") for field in parsed.outputs],
        rules=[rule.model_dump(mode="json") for rule in parsed.rules],
        hit_policy=parsed.hit_policy.value,
        validation_mode=parsed.validation_mode.value,
        is_active=bool(payload.get("is_active", True)),
        created_by=created_by,
        parent_version=parent,
        version_number=version_number,
    )


def resolve_pinned_decision_table(
    *,
    decision_table_id: str,
    decision_revision: int,
) -> DecisionTable:
    decision = (
        DecisionTable.objects.filter(
            decision_table_id=decision_table_id,
            version_number=decision_revision,
            is_active=True,
        )
        .order_by("-created_at")
        .first()
    )
    if decision is None:
        raise ValueError(
            f"Decision table '{decision_table_id}' revision '{decision_revision}' was not found."
        )
    return decision


def evaluate_decision_table(
    *,
    decision_table: DecisionTable | DecisionTableContract,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    contract = (
        decision_table
        if isinstance(decision_table, DecisionTableContract)
        else build_decision_table_contract(decision_table=decision_table)
    )
    raw_inputs = dict(inputs or {})
    normalized_inputs = {
        field.name: raw_inputs.get(field.name)
        for field in contract.inputs
    }
    missing_required = [
        field.name
        for field in contract.inputs
        if field.required and field.name not in raw_inputs
    ]
    if missing_required:
        raise ValueError(
            "Decision evaluation missing required inputs: " + ", ".join(sorted(missing_required))
        )

    matched_rule = None
    for rule in sorted(contract.rules, key=lambda item: item.priority):
        if _rule_matches(conditions=rule.conditions, inputs=normalized_inputs):
            matched_rule = rule
            break
    if matched_rule is None:
        raise ValueError(
            "Decision evaluation produced no matching rule for "
            f"{contract.decision_table_id} v{contract.decision_revision}"
        )

    return dict(matched_rule.outputs)


def _rule_matches(*, conditions: Mapping[str, Any], inputs: Mapping[str, Any]) -> bool:
    for field_name, expected_value in dict(conditions or {}).items():
        if inputs.get(field_name) != expected_value:
            return False
    return True


__all__ = [
    "build_decision_table_contract",
    "build_decision_table_ref",
    "create_decision_table_revision",
    "evaluate_decision_table",
    "resolve_pinned_decision_table",
]

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from django.contrib.auth import get_user_model

from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.templates.workflow.models_django import DecisionTable
from apps.tenancy.models import Tenant

from .binding_profiles_store import revise_canonical_binding_profile
from .document_policy_contract import DOCUMENT_POLICY_VERSION, validate_document_policy_v1
from .models import BindingProfile, BindingProfileRevision, PoolWorkflowBinding
from .workflow_binding_attachments_store import upsert_pool_workflow_binding_attachment


TOP_DOWN_EXECUTION_PACK_CODE = "top-down-execution-pack"
DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID = "osnovnoy"
_DOCUMENT_POLICY_DECISION_KEY = "document_policy"
_SALE_SLOT_KEY = "sale"
_RECEIPT_SLOT_KEYS = {"receipt_internal", "receipt_leaf"}

_REALIZATION_HEADER_REPLACEMENTS = {
    "Организация_Key": "master_data.party.edge.parent.organization.ref",
    "Контрагент_Key": "master_data.party.edge.child.counterparty.ref",
    "ДоговорКонтрагента_Key": (
        f"master_data.contract.{DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID}.edge.child.ref"
    ),
}
_RECEIPT_HEADER_REPLACEMENTS = {
    "Организация_Key": "master_data.party.edge.child.organization.ref",
    "Контрагент_Key": "master_data.party.edge.parent.counterparty.ref",
    "ДоговорКонтрагента_Key": (
        f"master_data.contract.{DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID}.edge.parent.ref"
    ),
}


def adopt_top_down_execution_pack_aliases(
    *,
    actor_username: str,
    tenant_slug: str | None = None,
    binding_profile_code: str = TOP_DOWN_EXECUTION_PACK_CODE,
    contract_canonical_id: str = DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID,
) -> dict[str, Any]:
    profile = _resolve_binding_profile(
        binding_profile_code=binding_profile_code,
        tenant_slug=tenant_slug,
    )
    latest_revision = (
        BindingProfileRevision.objects.filter(profile=profile)
        .order_by("-revision_number")
        .first()
    )
    if latest_revision is None:
        raise ValueError(f"Execution pack '{binding_profile_code}' has no revisions.")

    realization_decision = _resolve_pinned_slot_decision(
        profile_revision=latest_revision,
        slot_key=_SALE_SLOT_KEY,
    )
    receipt_decision = _resolve_pinned_receipt_decision(profile_revision=latest_revision)

    realization_target_policy = build_top_down_realization_alias_policy(
        policy=_extract_default_document_policy(realization_decision),
        contract_canonical_id=contract_canonical_id,
    )
    receipt_target_policy = build_top_down_receipt_alias_policy(
        policy=_extract_default_document_policy(receipt_decision),
        contract_canonical_id=contract_canonical_id,
    )

    realization_revision = _ensure_decision_revision(
        base_decision=realization_decision,
        target_policy=realization_target_policy,
        actor_username=actor_username,
    )
    receipt_revision = _ensure_decision_revision(
        base_decision=receipt_decision,
        target_policy=receipt_target_policy,
        actor_username=actor_username,
    )

    decision_updates = {
        _SALE_SLOT_KEY: realization_revision,
        "receipt_internal": receipt_revision,
        "receipt_leaf": receipt_revision,
    }
    latest_decisions = list(latest_revision.decisions) if isinstance(latest_revision.decisions, list) else []
    revised_decisions = _rewrite_binding_profile_decisions(
        decisions=latest_decisions,
        decision_updates=decision_updates,
    )
    profile_revision_reused = revised_decisions == latest_decisions

    if profile_revision_reused:
        target_revision = latest_revision
    else:
        revised_profile = revise_canonical_binding_profile(
            tenant=profile.tenant,
            binding_profile_id=str(profile.id),
            revision={
                "workflow": {
                    "workflow_definition_key": latest_revision.workflow_definition_key,
                    "workflow_revision_id": latest_revision.workflow_revision_id,
                    "workflow_revision": latest_revision.workflow_revision,
                    "workflow_name": latest_revision.workflow_name,
                },
                "decisions": revised_decisions,
                "parameters": dict(latest_revision.parameters) if isinstance(latest_revision.parameters, Mapping) else {},
                "role_mapping": dict(latest_revision.role_mapping) if isinstance(latest_revision.role_mapping, Mapping) else {},
                "metadata": dict(latest_revision.metadata) if isinstance(latest_revision.metadata, Mapping) else {},
            },
            actor_username=actor_username,
        )
        target_revision_id = revised_profile["latest_revision"]["binding_profile_revision_id"]
        target_revision = BindingProfileRevision.objects.get(binding_profile_revision_id=target_revision_id)

    updated_bindings: list[str] = []
    reused_bindings: list[str] = []
    attachments = list(
        PoolWorkflowBinding.objects.filter(binding_profile=profile)
        .select_related("pool")
        .order_by("binding_id")
    )
    for attachment in attachments:
        if attachment.binding_profile_revision_id == target_revision.binding_profile_revision_id:
            reused_bindings.append(attachment.binding_id)
            continue
        upsert_pool_workflow_binding_attachment(
            pool=attachment.pool,
            workflow_binding={
                "binding_id": attachment.binding_id,
                "revision": attachment.revision,
                "pool_id": str(attachment.pool_id),
                "binding_profile_revision_id": target_revision.binding_profile_revision_id,
                "selector": {
                    "direction": attachment.direction or None,
                    "mode": attachment.mode or None,
                    "tags": list(attachment.selector_tags or []),
                },
                "effective_from": attachment.effective_from.isoformat(),
                "effective_to": attachment.effective_to.isoformat() if attachment.effective_to else None,
                "status": attachment.status,
            },
            actor_username=actor_username,
        )
        updated_bindings.append(attachment.binding_id)

    return {
        "binding_profile_id": str(profile.id),
        "binding_profile_code": profile.code,
        "binding_profile_revision_id": target_revision.binding_profile_revision_id,
        "binding_profile_revision_number": target_revision.revision_number,
        "profile_revision_reused": profile_revision_reused,
        "realization_decision_revision": realization_revision.version_number,
        "receipt_decision_revision": receipt_revision.version_number,
        "updated_binding_ids": updated_bindings,
        "reused_binding_ids": reused_bindings,
    }


def adopt_top_down_execution_pack_aliases_for_all_tenants(
    *,
    actor_username: str,
    binding_profile_code: str = TOP_DOWN_EXECUTION_PACK_CODE,
    contract_canonical_id: str = DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    tenant_slugs = tuple(
        Tenant.objects.filter(binding_profiles__code=binding_profile_code)
        .order_by("slug")
        .values_list("slug", flat=True)
        .distinct()
    )
    for tenant_slug in tenant_slugs:
        try:
            result = adopt_top_down_execution_pack_aliases(
                actor_username=actor_username,
                tenant_slug=tenant_slug,
                binding_profile_code=binding_profile_code,
                contract_canonical_id=contract_canonical_id,
            )
        except Exception as exc:
            raise ValueError(
                "Top-down execution-pack alias adoption failed for "
                f"tenant '{tenant_slug}': {exc}"
            ) from exc
        results.append({"tenant_slug": tenant_slug, **result})
    return results


def build_top_down_realization_alias_policy(
    *,
    policy: Mapping[str, Any],
    contract_canonical_id: str,
) -> dict[str, Any]:
    header_replacements = {
        **_REALIZATION_HEADER_REPLACEMENTS,
        "ДоговорКонтрагента_Key": f"master_data.contract.{contract_canonical_id}.edge.child.ref",
    }
    return _rewrite_document_policy_fields(
        policy=policy,
        header_replacements=header_replacements,
    )


def build_top_down_receipt_alias_policy(
    *,
    policy: Mapping[str, Any],
    contract_canonical_id: str,
) -> dict[str, Any]:
    header_replacements = {
        **_RECEIPT_HEADER_REPLACEMENTS,
        "ДоговорКонтрагента_Key": f"master_data.contract.{contract_canonical_id}.edge.parent.ref",
    }
    return _rewrite_document_policy_fields(
        policy=policy,
        header_replacements=header_replacements,
    )


def _resolve_binding_profile(*, binding_profile_code: str, tenant_slug: str | None) -> BindingProfile:
    queryset = BindingProfile.objects.filter(code=binding_profile_code)
    if tenant_slug:
        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if tenant is None:
            raise ValueError(f"Tenant '{tenant_slug}' was not found.")
        queryset = queryset.filter(tenant=tenant)
    profile = queryset.select_related("tenant").first()
    if profile is None:
        raise ValueError(f"Execution pack '{binding_profile_code}' was not found.")
    return profile


def _resolve_pinned_slot_decision(
    *,
    profile_revision: BindingProfileRevision,
    slot_key: str,
) -> DecisionTable:
    decision_ref = next(
        (
            decision
            for decision in list(profile_revision.decisions or [])
            if str(decision.get("decision_key") or "").strip() == _DOCUMENT_POLICY_DECISION_KEY
            and str(decision.get("slot_key") or "").strip() == slot_key
        ),
        None,
    )
    if decision_ref is None:
        raise ValueError(
            f"Execution-pack revision '{profile_revision.binding_profile_revision_id}' does not pin slot '{slot_key}'."
        )
    decision_table_id = str(decision_ref.get("decision_table_id") or "").strip()
    decision_revision = int(decision_ref.get("decision_revision") or 0)
    decision = DecisionTable.objects.filter(
        decision_table_id=decision_table_id,
        version_number=decision_revision,
        is_active=True,
    ).first()
    if decision is None:
        raise ValueError(
            f"Pinned decision '{decision_table_id}' r{decision_revision} for slot '{slot_key}' was not found."
        )
    return decision


def _resolve_pinned_receipt_decision(*, profile_revision: BindingProfileRevision) -> DecisionTable:
    decisions = [
        _resolve_pinned_slot_decision(profile_revision=profile_revision, slot_key=slot_key)
        for slot_key in sorted(_RECEIPT_SLOT_KEYS)
    ]
    first = decisions[0]
    if any(
        decision.decision_table_id != first.decision_table_id
        or decision.version_number != first.version_number
        for decision in decisions[1:]
    ):
        raise ValueError(
            "Pinned receipt slots are divergent; expected one reusable receipt decision across receipt_internal/receipt_leaf."
        )
    return first


def _extract_default_document_policy(decision: DecisionTable) -> dict[str, Any]:
    for rule in list(decision.rules or []):
        if not isinstance(rule, Mapping):
            continue
        outputs = dict(rule.get("outputs") or {})
        raw_policy = outputs.get("document_policy")
        if isinstance(raw_policy, Mapping):
            return validate_document_policy_v1(policy=raw_policy)
    raise ValueError(f"Decision '{decision.decision_table_id}' r{decision.version_number} has no document_policy output.")


def _ensure_decision_revision(
    *,
    base_decision: DecisionTable,
    target_policy: Mapping[str, Any],
    actor_username: str,
) -> DecisionTable:
    latest = (
        DecisionTable.objects.filter(decision_table_id=base_decision.decision_table_id, is_active=True)
        .order_by("-version_number")
        .first()
    )
    if latest is None:
        latest = base_decision
    latest_policy = _extract_default_document_policy(latest)
    if latest_policy == target_policy:
        return latest

    updated_rules = _rewrite_decision_rules_with_document_policy(
        rules=base_decision.rules,
        policy=target_policy,
    )
    return create_decision_table_revision(
        contract={
            "decision_table_id": base_decision.decision_table_id,
            "decision_key": base_decision.decision_key,
            "name": base_decision.name,
            "description": base_decision.description,
            "inputs": list(base_decision.inputs or []),
            "outputs": list(base_decision.outputs or []),
            "rules": updated_rules,
            "metadata_context": dict(base_decision.metadata_context or {}),
            "source_provenance": dict(base_decision.source_provenance or {}),
            "hit_policy": base_decision.hit_policy,
            "validation_mode": base_decision.validation_mode,
            "is_active": base_decision.is_active,
        },
        created_by=_resolve_actor(actor_username=actor_username) or base_decision.created_by,
        parent_version=latest,
    )


def _rewrite_decision_rules_with_document_policy(
    *,
    rules: list[Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rewritten_rules: list[dict[str, Any]] = []
    replaced = False
    for raw_rule in list(rules or []):
        rule = deepcopy(dict(raw_rule)) if isinstance(raw_rule, Mapping) else {}
        outputs = deepcopy(dict(rule.get("outputs") or {}))
        if isinstance(outputs.get("document_policy"), Mapping):
            outputs["document_policy"] = dict(policy)
            replaced = True
        rule["outputs"] = outputs
        rewritten_rules.append(rule)
    if not replaced:
        raise ValueError("Decision rules do not contain document_policy output to rewrite.")
    return rewritten_rules


def _rewrite_binding_profile_decisions(
    *,
    decisions: list[Any],
    decision_updates: Mapping[str, DecisionTable],
) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    for raw_decision in decisions:
        decision = deepcopy(dict(raw_decision)) if isinstance(raw_decision, Mapping) else {}
        slot_key = str(decision.get("slot_key") or "").strip()
        if str(decision.get("decision_key") or "").strip() == _DOCUMENT_POLICY_DECISION_KEY and slot_key in decision_updates:
            target_decision = decision_updates[slot_key]
            decision["decision_table_id"] = target_decision.decision_table_id
            decision["decision_revision"] = target_decision.version_number
        rewritten.append(decision)
    return rewritten


def _rewrite_document_policy_fields(
    *,
    policy: Mapping[str, Any],
    header_replacements: Mapping[str, str],
) -> dict[str, Any]:
    normalized_policy = validate_document_policy_v1(policy=policy)
    rewritten_policy = deepcopy(normalized_policy)
    replaced_header_keys: set[str] = set()

    for chain in list(rewritten_policy.get("chains") or []):
        if not isinstance(chain, dict):
            continue
        for document in list(chain.get("documents") or []):
            if not isinstance(document, dict):
                continue
            field_mapping = dict(document.get("field_mapping") or {})
            for field_name, replacement in header_replacements.items():
                if field_name in field_mapping:
                    field_mapping[field_name] = replacement
                    replaced_header_keys.add(field_name)
            document["field_mapping"] = field_mapping

            table_parts_mapping = dict(document.get("table_parts_mapping") or {})
            for table_name, raw_rows in list(table_parts_mapping.items()):
                if not isinstance(raw_rows, list):
                    continue
                rewritten_rows: list[dict[str, Any]] = []
                for raw_row in raw_rows:
                    row = deepcopy(dict(raw_row)) if isinstance(raw_row, Mapping) else {}
                    if "Контрагент_Key" in row:
                        row["Контрагент_Key"] = header_replacements["Контрагент_Key"]
                    if "ДоговорКонтрагента_Key" in row:
                        row["ДоговорКонтрагента_Key"] = header_replacements["ДоговорКонтрагента_Key"]
                    rewritten_rows.append(row)
                table_parts_mapping[table_name] = rewritten_rows
            document["table_parts_mapping"] = table_parts_mapping

    missing_header_keys = sorted(set(header_replacements) - replaced_header_keys)
    if missing_header_keys:
        raise ValueError(
            "Top-down execution-pack adoption could not rewrite required header fields: "
            + ", ".join(missing_header_keys)
        )
    validated = validate_document_policy_v1(policy=rewritten_policy)
    if validated.get("version") != DOCUMENT_POLICY_VERSION:
        raise ValueError("Unexpected document_policy version after top-down alias rewrite.")
    return validated


def _resolve_actor(*, actor_username: str):
    normalized = str(actor_username or "").strip()
    if not normalized:
        return None
    return get_user_model().objects.filter(username=normalized).first()


__all__ = [
    "DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID",
    "TOP_DOWN_EXECUTION_PACK_CODE",
    "adopt_top_down_execution_pack_aliases",
    "adopt_top_down_execution_pack_aliases_for_all_tenants",
    "build_top_down_realization_alias_policy",
    "build_top_down_receipt_alias_policy",
]

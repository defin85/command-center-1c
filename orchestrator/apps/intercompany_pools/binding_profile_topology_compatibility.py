from __future__ import annotations

from typing import Any, Iterable, Mapping

from apps.templates.workflow.decision_tables import resolve_pinned_decision_table

from .document_policy_contract import DOCUMENT_POLICY_METADATA_KEY, validate_document_policy_v1


EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED = "EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED"
EXECUTION_PACK_TEMPLATE_INCOMPATIBLE = "EXECUTION_PACK_TEMPLATE_INCOMPATIBLE"
BINDING_PROFILE_TOPOLOGY_COMPATIBILITY_METADATA_KEY = "_topology_template_compatibility"

_MASTER_DATA_PREFIX = "master_data."
_MASTER_DATA_SUFFIX = ".ref"
_PARTY_ROLES = {"organization", "counterparty"}
_PARTICIPANT_SIDES = {"parent", "child"}


class ExecutionPackTopologyCompatibilityError(ValueError):
    def __init__(self, *, detail: str, errors: list[dict[str, Any]]) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors


def validate_execution_pack_topology_authoring(
    *,
    decisions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    summary = build_execution_pack_topology_compatibility_summary(
        decisions=decisions,
        strict_resolution=True,
    )
    diagnostics = list(summary.get("diagnostics") or [])
    if diagnostics:
        raise ExecutionPackTopologyCompatibilityError(
            detail=(
                "Execution pack revision is not reusable for template-based topology. "
                "Publish topology-aware decision revisions in /decisions before saving /pools/execution-packs."
            ),
            errors=diagnostics,
        )
    return summary


def build_execution_pack_topology_compatibility_summary(
    *,
    decisions: Iterable[Mapping[str, Any]],
    strict_resolution: bool,
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    covered_slot_keys: list[str] = []
    seen_slot_keys: set[str] = set()

    for decision_ref in decisions:
        if not isinstance(decision_ref, Mapping):
            continue
        decision_key = str(decision_ref.get("decision_key") or "").strip()
        decision_table_id = str(decision_ref.get("decision_table_id") or "").strip()
        if decision_key != DOCUMENT_POLICY_METADATA_KEY or not decision_table_id:
            continue
        slot_key = str(decision_ref.get("slot_key") or decision_key).strip()
        if slot_key and slot_key not in seen_slot_keys:
            seen_slot_keys.add(slot_key)
            covered_slot_keys.append(slot_key)
        try:
            decision_revision = int(decision_ref.get("decision_revision") or 0)
        except (TypeError, ValueError):
            decision_revision = 0
        if decision_revision < 1:
            continue
        try:
            decision = resolve_pinned_decision_table(
                decision_table_id=decision_table_id,
                decision_revision=decision_revision,
            )
        except ValueError:
            if strict_resolution:
                raise
            diagnostics.append(
                {
                    "code": EXECUTION_PACK_TEMPLATE_INCOMPATIBLE,
                    "slot_key": slot_key,
                    "decision_table_id": decision_table_id,
                    "decision_revision": decision_revision,
                    "field_or_table_path": "",
                    "detail": (
                        "Pinned decision revision is unavailable, so topology compatibility "
                        "cannot be confirmed for this reusable execution pack."
                    ),
                }
            )
            continue

        diagnostics.extend(
            _inspect_decision_document_policy(
                slot_key=slot_key,
                decision_table_id=decision_table_id,
                decision_revision=decision_revision,
                decision_rules=decision.rules,
            )
        )

    normalized_diagnostics = sorted(
        diagnostics,
        key=lambda item: (
            str(item.get("slot_key") or ""),
            str(item.get("decision_table_id") or ""),
            int(item.get("decision_revision") or 0),
            str(item.get("field_or_table_path") or ""),
        ),
    )
    return {
        "status": "compatible" if not normalized_diagnostics else "incompatible",
        "topology_aware_ready": not normalized_diagnostics,
        "covered_slot_keys": covered_slot_keys,
        "diagnostics": normalized_diagnostics,
    }


def get_execution_pack_topology_compatibility_summary(
    *,
    decisions: Iterable[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    cached = _normalize_cached_summary(metadata)
    if cached is not None:
        return cached
    return build_execution_pack_topology_compatibility_summary(
        decisions=decisions,
        strict_resolution=False,
    )


def attach_execution_pack_topology_compatibility_summary(
    *,
    metadata: Mapping[str, Any] | None,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(metadata) if isinstance(metadata, Mapping) else {}
    payload[BINDING_PROFILE_TOPOLOGY_COMPATIBILITY_METADATA_KEY] = _normalize_summary(summary)
    return payload


def strip_execution_pack_topology_compatibility_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata) if isinstance(metadata, Mapping) else {}
    payload.pop(BINDING_PROFILE_TOPOLOGY_COMPATIBILITY_METADATA_KEY, None)
    return payload


def build_execution_pack_template_incompatibility_problem(
    *,
    profile_code: str,
    summary: Mapping[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    diagnostics = [
        dict(item)
        for item in list(summary.get("diagnostics") or [])
        if isinstance(item, Mapping)
    ]
    first = diagnostics[0] if diagnostics else {}
    slot_key = str(first.get("slot_key") or "").strip()
    decision_table_id = str(first.get("decision_table_id") or "").strip()
    field_or_table_path = str(first.get("field_or_table_path") or "").strip()
    parts = [
        f"Execution pack '{profile_code}' is not compatible with template-based topology authoring.",
        "Publish topology-aware decision revisions in /decisions and revise /pools/execution-packs before attach, preview, or run start.",
    ]
    if slot_key:
        parts.append(f"First incompatible slot: {slot_key}.")
    if decision_table_id:
        parts.append(f"Decision: {decision_table_id}.")
    if field_or_table_path:
        parts.append(f"Field path: {field_or_table_path}.")
    return " ".join(parts), diagnostics


def _inspect_decision_document_policy(
    *,
    slot_key: str,
    decision_table_id: str,
    decision_revision: int,
    decision_rules: Any,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for rule in list(decision_rules or []):
        if not isinstance(rule, Mapping):
            continue
        outputs = dict(rule.get("outputs") or {})
        raw_policy = outputs.get("document_policy")
        if not isinstance(raw_policy, Mapping):
            continue
        policy = validate_document_policy_v1(policy=raw_policy)
        for chain_index, chain in enumerate(policy.get("chains") or []):
            if not isinstance(chain, Mapping):
                continue
            for document_index, document in enumerate(chain.get("documents") or []):
                if not isinstance(document, Mapping):
                    continue
                diagnostics.extend(
                    _inspect_mapping_value(
                        value=document.get("field_mapping"),
                        path=(
                            "document_policy."
                            f"chains[{chain_index}].documents[{document_index}].field_mapping"
                        ),
                        slot_key=slot_key,
                        decision_table_id=decision_table_id,
                        decision_revision=decision_revision,
                    )
                )
                diagnostics.extend(
                    _inspect_mapping_value(
                        value=document.get("table_parts_mapping"),
                        path=(
                            "document_policy."
                            f"chains[{chain_index}].documents[{document_index}].table_parts_mapping"
                        ),
                        slot_key=slot_key,
                        decision_table_id=decision_table_id,
                        decision_revision=decision_revision,
                    )
                )
    return diagnostics


def _inspect_mapping_value(
    *,
    value: Any,
    path: str,
    slot_key: str,
    decision_table_id: str,
    decision_revision: int,
) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        diagnostics: list[dict[str, Any]] = []
        for raw_key, raw_item in value.items():
            key = str(raw_key)
            diagnostics.extend(
                _inspect_mapping_value(
                    value=raw_item,
                    path=f"{path}.{key}",
                    slot_key=slot_key,
                    decision_table_id=decision_table_id,
                    decision_revision=decision_revision,
                )
            )
        return diagnostics
    if isinstance(value, list):
        diagnostics: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            diagnostics.extend(
                _inspect_mapping_value(
                    value=item,
                    path=f"{path}[{index}]",
                    slot_key=slot_key,
                    decision_table_id=decision_table_id,
                    decision_revision=decision_revision,
                )
            )
        return diagnostics
    if not isinstance(value, str):
        return []

    token = value.strip()
    if not _is_concrete_participant_master_data_ref(token):
        return []
    return [
        {
            "code": EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED,
            "slot_key": slot_key,
            "decision_table_id": decision_table_id,
            "decision_revision": decision_revision,
            "field_or_table_path": path,
            "detail": (
                "Reusable execution-pack participant refs must use topology-aware aliases "
                "instead of concrete master_data.party/master_data.contract refs."
            ),
        }
    ]


def _is_concrete_participant_master_data_ref(token: str) -> bool:
    if not token.startswith(_MASTER_DATA_PREFIX) or not token.endswith(_MASTER_DATA_SUFFIX):
        return False
    body = token.removeprefix(_MASTER_DATA_PREFIX).removesuffix(_MASTER_DATA_SUFFIX)
    segments = [segment.strip() for segment in body.split(".") if segment.strip()]
    if not segments:
        return False
    if segments[0] == "party":
        if _is_topology_party_alias(segments):
            return False
        return len(segments) >= 3 and segments[-1] in _PARTY_ROLES
    if segments[0] == "contract":
        if _is_topology_contract_alias(segments):
            return False
        return len(segments) >= 3
    return False


def _is_topology_party_alias(segments: list[str]) -> bool:
    return (
        len(segments) == 4
        and segments[0] == "party"
        and segments[1] == "edge"
        and segments[2] in _PARTICIPANT_SIDES
        and segments[3] in _PARTY_ROLES
    )


def _is_topology_contract_alias(segments: list[str]) -> bool:
    return (
        len(segments) == 4
        and segments[0] == "contract"
        and bool(segments[1])
        and segments[2] == "edge"
        and segments[3] in _PARTICIPANT_SIDES
    )


def _normalize_cached_summary(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, Mapping):
        return None
    raw = metadata.get(BINDING_PROFILE_TOPOLOGY_COMPATIBILITY_METADATA_KEY)
    if not isinstance(raw, Mapping):
        return None
    return _normalize_summary(raw)


def _normalize_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    for item in list(summary.get("diagnostics") or []):
        if not isinstance(item, Mapping):
            continue
        diagnostics.append(
            {
                "code": str(item.get("code") or EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED),
                "slot_key": str(item.get("slot_key") or "").strip(),
                "decision_table_id": str(item.get("decision_table_id") or "").strip(),
                "decision_revision": int(item.get("decision_revision") or 0),
                "field_or_table_path": str(item.get("field_or_table_path") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
            }
        )
    covered_slot_keys = [
        str(item).strip()
        for item in list(summary.get("covered_slot_keys") or [])
        if str(item).strip()
    ]
    topology_aware_ready = bool(summary.get("topology_aware_ready")) and not diagnostics
    return {
        "status": "compatible" if topology_aware_ready else "incompatible",
        "topology_aware_ready": topology_aware_ready,
        "covered_slot_keys": covered_slot_keys,
        "diagnostics": diagnostics,
    }


__all__ = [
    "BINDING_PROFILE_TOPOLOGY_COMPATIBILITY_METADATA_KEY",
    "EXECUTION_PACK_TEMPLATE_INCOMPATIBLE",
    "EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED",
    "ExecutionPackTopologyCompatibilityError",
    "attach_execution_pack_topology_compatibility_summary",
    "build_execution_pack_template_incompatibility_problem",
    "build_execution_pack_topology_compatibility_summary",
    "get_execution_pack_topology_compatibility_summary",
    "strip_execution_pack_topology_compatibility_metadata",
    "validate_execution_pack_topology_authoring",
]

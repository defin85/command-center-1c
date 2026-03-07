from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DEFAULT_DOCUMENT_COMPLETENESS_PROFILE_ID = "minimal_documents_full_payload"


def normalize_completeness_profiles(
    *,
    raw_profiles: Any,
    field_name: str,
    error_code: str,
) -> dict[str, Any]:
    if raw_profiles is None:
        return {}
    if not isinstance(raw_profiles, Mapping):
        raise ValueError(f"{error_code}: {field_name} must be an object")

    normalized_profiles: dict[str, Any] = {}
    for raw_profile_id, raw_profile in raw_profiles.items():
        profile_id = str(raw_profile_id or "").strip()
        if not profile_id:
            raise ValueError(f"{error_code}: {field_name} profile id must be a non-empty string")
        if not isinstance(raw_profile, Mapping):
            raise ValueError(f"{error_code}: {field_name}.{profile_id} must be an object")

        raw_entities = raw_profile.get("entities")
        if not isinstance(raw_entities, Mapping) or not raw_entities:
            raise ValueError(f"{error_code}: {field_name}.{profile_id}.entities must be a non-empty object")

        entities: dict[str, Any] = {}
        for raw_entity_name, raw_requirements in raw_entities.items():
            entity_name = str(raw_entity_name or "").strip()
            if not entity_name:
                raise ValueError(
                    f"{error_code}: {field_name}.{profile_id}.entities keys must be non-empty strings"
                )
            if not isinstance(raw_requirements, Mapping):
                raise ValueError(
                    f"{error_code}: {field_name}.{profile_id}.entities.{entity_name} must be an object"
                )
            entities[entity_name] = _normalize_completeness_requirements_payload(
                raw_requirements,
                field_name=f"{field_name}.{profile_id}.entities.{entity_name}",
                error_code=error_code,
            )

        normalized_profiles[profile_id] = {
            "entities": entities,
        }

    return normalized_profiles


def resolve_document_completeness_requirements(
    *,
    policy: Mapping[str, Any],
    entity_name: str,
    profile_id: str = DEFAULT_DOCUMENT_COMPLETENESS_PROFILE_ID,
    document: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized_entity_name = str(entity_name or "").strip()
    if not normalized_entity_name:
        return None
    raw_profiles = policy.get("completeness_profiles")
    if not isinstance(raw_profiles, Mapping):
        return None
    raw_profile = raw_profiles.get(profile_id)
    if not isinstance(raw_profile, Mapping):
        return None
    raw_entities = raw_profile.get("entities")
    if not isinstance(raw_entities, Mapping):
        return None
    raw_requirements = raw_entities.get(normalized_entity_name)
    if not isinstance(raw_requirements, Mapping):
        return None
    base_requirements = _build_completeness_requirements_payload(raw_requirements)
    raw_variants = raw_requirements.get("variants")
    if not isinstance(raw_variants, Mapping) or not raw_variants:
        return base_requirements
    if not isinstance(document, Mapping):
        raise ValueError(
            f"POOL_DOCUMENT_POLICY_MAPPING_INVALID: completeness profile for entity "
            f"'{normalized_entity_name}' requires variant-aware document mapping"
        )

    matching_variants: list[tuple[str, Mapping[str, Any]]] = []
    for raw_variant_id, raw_variant_requirements in raw_variants.items():
        variant_id = str(raw_variant_id or "").strip()
        if not variant_id or not isinstance(raw_variant_requirements, Mapping):
            continue
        if _variant_matches_document(
            variant_requirements=raw_variant_requirements,
            document=document,
        ):
            matching_variants.append((variant_id, raw_variant_requirements))

    if not matching_variants:
        raise ValueError(
            f"POOL_DOCUMENT_POLICY_MAPPING_INVALID: no completeness variant matched entity "
            f"'{normalized_entity_name}'"
        )
    if len(matching_variants) > 1:
        variant_ids = ", ".join(variant_id for variant_id, _ in matching_variants)
        raise ValueError(
            f"POOL_DOCUMENT_POLICY_MAPPING_INVALID: completeness variant match for entity "
            f"'{normalized_entity_name}' is ambiguous ({variant_ids})"
        )

    _, variant_requirements = matching_variants[0]
    return _merge_completeness_requirements(
        base_requirements=base_requirements,
        variant_requirements=_build_completeness_requirements_payload(variant_requirements),
    )


def ensure_document_mapping_completeness(
    *,
    document: Mapping[str, Any],
    completeness_requirements: Mapping[str, Any] | None,
    path_prefix: str,
    error_code: str,
) -> dict[str, Any] | None:
    if not isinstance(completeness_requirements, Mapping):
        return None

    entity_name = str(document.get("entity_name") or "").strip()
    field_mapping = (
        dict(document.get("field_mapping"))
        if isinstance(document.get("field_mapping"), Mapping)
        else {}
    )
    table_parts_mapping = (
        dict(document.get("table_parts_mapping"))
        if isinstance(document.get("table_parts_mapping"), Mapping)
        else {}
    )

    normalized_required_fields = _normalized_required_field_tokens(
        completeness_requirements.get("required_fields")
    )
    normalized_required_table_parts = _normalized_required_table_parts_payload(
        completeness_requirements.get("required_table_parts")
    )

    for required_field in normalized_required_fields:
        if not _mapping_contains_value(field_mapping, required_field):
            raise ValueError(
                f"{error_code}: {path_prefix}.field_mapping.{required_field} is required by completeness "
                f"profile for entity '{entity_name}'"
            )

    for table_part_name, requirement in normalized_required_table_parts.items():
        min_rows = max(1, _parse_non_negative_int(requirement.get("min_rows"), default=1))
        raw_rows = table_parts_mapping.get(table_part_name)
        if not isinstance(raw_rows, list) or len(raw_rows) < min_rows:
            raise ValueError(
                f"{error_code}: {path_prefix}.table_parts_mapping.{table_part_name} is required by "
                f"completeness profile for entity '{entity_name}'"
            )
        required_row_fields = _normalized_required_field_tokens(requirement.get("required_fields"))
        for row_index in range(min_rows):
            row = raw_rows[row_index]
            if not isinstance(row, Mapping):
                raise ValueError(
                    f"{error_code}: {path_prefix}.table_parts_mapping.{table_part_name}[{row_index}] is "
                    f"required by completeness profile for entity '{entity_name}'"
                )
            for required_row_field in required_row_fields:
                if not _mapping_contains_value(row, required_row_field):
                    raise ValueError(
                        f"{error_code}: {path_prefix}.table_parts_mapping.{table_part_name}[{row_index}]."
                        f"{required_row_field} is required by completeness profile for entity "
                        f"'{entity_name}'"
                    )

    return {
        "required_fields": normalized_required_fields,
        "required_table_parts": normalized_required_table_parts,
    }


def collect_document_payload_mismatches(
    *,
    database_id: str,
    entity_name: str,
    document_idempotency_key: str,
    payload: Mapping[str, Any],
    completeness_requirements: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(completeness_requirements, Mapping):
        return []

    mismatches: list[dict[str, Any]] = []
    normalized_required_fields = _normalized_required_field_tokens(
        completeness_requirements.get("required_fields")
    )
    normalized_required_table_parts = _normalized_required_table_parts_payload(
        completeness_requirements.get("required_table_parts")
    )
    normalized_database_id = str(database_id or "").strip()
    normalized_entity_name = str(entity_name or "").strip()
    normalized_document_key = str(document_idempotency_key or "").strip()

    for required_field in normalized_required_fields:
        if _payload_mapping_contains_value(payload, required_field):
            continue
        mismatches.append(
            {
                "database_id": normalized_database_id,
                "entity_name": normalized_entity_name,
                "document_idempotency_key": normalized_document_key,
                "field_or_table_path": required_field,
                "kind": "missing_field",
            }
        )

    for table_part_name, requirement in normalized_required_table_parts.items():
        min_rows = max(1, _parse_non_negative_int(requirement.get("min_rows"), default=1))
        rows = payload.get(table_part_name)
        if not isinstance(rows, list) or len(rows) < min_rows:
            mismatches.append(
                {
                    "database_id": normalized_database_id,
                    "entity_name": normalized_entity_name,
                    "document_idempotency_key": normalized_document_key,
                    "field_or_table_path": table_part_name,
                    "kind": "missing_table_part",
                }
            )
            continue

        required_row_fields = _normalized_required_field_tokens(requirement.get("required_fields"))
        for row_index in range(min_rows):
            row = rows[row_index]
            if not isinstance(row, Mapping):
                mismatches.append(
                    {
                        "database_id": normalized_database_id,
                        "entity_name": normalized_entity_name,
                        "document_idempotency_key": normalized_document_key,
                        "field_or_table_path": f"{table_part_name}[{row_index}]",
                        "kind": "missing_table_part",
                    }
                )
                continue
            for required_row_field in required_row_fields:
                if _payload_mapping_contains_value(row, required_row_field):
                    continue
                mismatches.append(
                    {
                        "database_id": normalized_database_id,
                        "entity_name": normalized_entity_name,
                        "document_idempotency_key": normalized_document_key,
                        "field_or_table_path": f"{table_part_name}[{row_index}].{required_row_field}",
                        "kind": "missing_table_part_field",
                    }
                )

    return mismatches


def _normalize_required_fields(
    raw_required_fields: Any,
    *,
    field_name: str,
    error_code: str,
) -> list[str]:
    if raw_required_fields is None:
        return []
    if not isinstance(raw_required_fields, list):
        raise ValueError(f"{error_code}: {field_name} must be an array")
    normalized = [str(item or "").strip() for item in raw_required_fields]
    if any(not token for token in normalized):
        raise ValueError(f"{error_code}: {field_name} must contain non-empty strings")
    return normalized


def _normalize_completeness_requirements_payload(
    raw_requirements: Mapping[str, Any],
    *,
    field_name: str,
    error_code: str,
) -> dict[str, Any]:
    required_fields = _normalize_required_fields(
        raw_requirements.get("required_fields"),
        field_name=f"{field_name}.required_fields",
        error_code=error_code,
    )
    required_table_parts = _normalize_required_table_parts(
        raw_requirements.get("required_table_parts"),
        field_name=f"{field_name}.required_table_parts",
        error_code=error_code,
    )
    normalized: dict[str, Any] = {
        "required_fields": required_fields,
        "required_table_parts": required_table_parts,
    }
    variants = _normalize_completeness_variants(
        raw_requirements.get("variants"),
        field_name=f"{field_name}.variants",
        error_code=error_code,
    )
    if variants:
        normalized["variants"] = variants
    return normalized


def _normalize_completeness_variants(
    raw_variants: Any,
    *,
    field_name: str,
    error_code: str,
) -> dict[str, Any]:
    if raw_variants is None:
        return {}
    if not isinstance(raw_variants, Mapping):
        raise ValueError(f"{error_code}: {field_name} must be an object")

    normalized_variants: dict[str, Any] = {}
    for raw_variant_id, raw_variant_requirements in raw_variants.items():
        variant_id = str(raw_variant_id or "").strip()
        if not variant_id:
            raise ValueError(f"{error_code}: {field_name} keys must be non-empty strings")
        if not isinstance(raw_variant_requirements, Mapping):
            raise ValueError(f"{error_code}: {field_name}.{variant_id} must be an object")
        match = _normalize_variant_match(
            raw_variant_requirements.get("match"),
            field_name=f"{field_name}.{variant_id}.match",
            error_code=error_code,
        )
        normalized_variant = _build_completeness_requirements_payload(raw_variant_requirements)
        normalized_variant["match"] = match
        normalized_variants[variant_id] = normalized_variant
    return normalized_variants


def _normalize_variant_match(
    raw_match: Any,
    *,
    field_name: str,
    error_code: str,
) -> dict[str, Any]:
    if not isinstance(raw_match, Mapping) or not raw_match:
        raise ValueError(f"{error_code}: {field_name} must be a non-empty object")
    normalized: dict[str, Any] = {}
    for raw_field_name, raw_expected_value in raw_match.items():
        match_field_name = str(raw_field_name or "").strip()
        if not match_field_name:
            raise ValueError(f"{error_code}: {field_name} keys must be non-empty strings")
        normalized[match_field_name] = _normalize_variant_match_value(
            raw_expected_value,
            field_name=f"{field_name}.{match_field_name}",
            error_code=error_code,
        )
    return normalized


def _normalize_variant_match_value(
    raw_value: Any,
    *,
    field_name: str,
    error_code: str,
) -> Any:
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if not normalized:
            raise ValueError(f"{error_code}: {field_name} must be a non-empty scalar")
        return normalized
    if isinstance(raw_value, (bool, int, float)) or raw_value is None:
        return raw_value
    raise ValueError(f"{error_code}: {field_name} must be a scalar")


def _build_completeness_requirements_payload(raw_requirements: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "required_fields": _normalized_required_field_tokens(raw_requirements.get("required_fields")),
        "required_table_parts": _normalized_required_table_parts_payload(
            raw_requirements.get("required_table_parts")
        ),
    }


def _merge_completeness_requirements(
    *,
    base_requirements: Mapping[str, Any],
    variant_requirements: Mapping[str, Any],
) -> dict[str, Any]:
    required_fields = _merge_required_fields(
        base_requirements.get("required_fields"),
        variant_requirements.get("required_fields"),
    )
    required_table_parts = _merge_required_table_parts(
        base_requirements.get("required_table_parts"),
        variant_requirements.get("required_table_parts"),
    )
    return {
        "required_fields": required_fields,
        "required_table_parts": required_table_parts,
    }


def _merge_required_fields(*raw_field_sets: Any) -> list[str]:
    merged: list[str] = []
    for raw_fields in raw_field_sets:
        for field_name in _normalized_required_field_tokens(raw_fields):
            if field_name not in merged:
                merged.append(field_name)
    return merged


def _merge_required_table_parts(*raw_table_parts_sets: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for raw_table_parts in raw_table_parts_sets:
        normalized_table_parts = _normalized_required_table_parts_payload(raw_table_parts)
        for table_part_name, requirement in normalized_table_parts.items():
            current = merged.get(table_part_name)
            if current is None:
                merged[table_part_name] = {
                    "min_rows": max(1, _parse_non_negative_int(requirement.get("min_rows"), default=1)),
                    "required_fields": _normalized_required_field_tokens(
                        requirement.get("required_fields")
                    ),
                }
                continue
            merged[table_part_name] = {
                "min_rows": max(
                    _parse_non_negative_int(current.get("min_rows"), default=1),
                    _parse_non_negative_int(requirement.get("min_rows"), default=1),
                    1,
                ),
                "required_fields": _merge_required_fields(
                    current.get("required_fields"),
                    requirement.get("required_fields"),
                ),
            }
    return merged


def _variant_matches_document(
    *,
    variant_requirements: Mapping[str, Any],
    document: Mapping[str, Any],
) -> bool:
    field_mapping = (
        dict(document.get("field_mapping"))
        if isinstance(document.get("field_mapping"), Mapping)
        else {}
    )
    match = variant_requirements.get("match")
    if not isinstance(match, Mapping) or not match:
        return False
    for field_name, expected_value in match.items():
        if _normalize_document_variant_value(field_mapping.get(field_name)) != expected_value:
            return False
    return True


def _normalize_document_variant_value(raw_value: Any) -> Any:
    if isinstance(raw_value, str):
        return raw_value.strip()
    return raw_value


def _normalize_required_table_parts(
    raw_required_table_parts: Any,
    *,
    field_name: str,
    error_code: str,
) -> dict[str, Any]:
    if raw_required_table_parts is None:
        return {}
    if not isinstance(raw_required_table_parts, Mapping):
        raise ValueError(f"{error_code}: {field_name} must be an object")

    normalized: dict[str, Any] = {}
    for raw_table_part_name, raw_requirement in raw_required_table_parts.items():
        table_part_name = str(raw_table_part_name or "").strip()
        if not table_part_name:
            raise ValueError(f"{error_code}: {field_name} keys must be non-empty strings")
        if isinstance(raw_requirement, Mapping):
            normalized[table_part_name] = {
                "min_rows": max(
                    1,
                    _parse_non_negative_int(raw_requirement.get("min_rows"), default=1),
                ),
                "required_fields": _normalize_required_fields(
                    raw_requirement.get("required_fields"),
                    field_name=f"{field_name}.{table_part_name}.required_fields",
                    error_code=error_code,
                ),
            }
            continue
        min_rows = _parse_non_negative_int(raw_requirement, default=1)
        if min_rows < 1:
            raise ValueError(f"{error_code}: {field_name}.{table_part_name} min_rows must be >= 1")
        normalized[table_part_name] = {
            "min_rows": min_rows,
            "required_fields": [],
        }
    return normalized


def _normalized_required_field_tokens(raw_required_fields: Any) -> list[str]:
    if not isinstance(raw_required_fields, list):
        return []
    return [str(item or "").strip() for item in raw_required_fields if str(item or "").strip()]


def _normalized_required_table_parts_payload(raw_required_table_parts: Any) -> dict[str, Any]:
    if not isinstance(raw_required_table_parts, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for raw_table_part_name, raw_requirement in raw_required_table_parts.items():
        table_part_name = str(raw_table_part_name or "").strip()
        if not table_part_name or not isinstance(raw_requirement, Mapping):
            continue
        normalized[table_part_name] = {
            "min_rows": max(
                1,
                _parse_non_negative_int(raw_requirement.get("min_rows"), default=1),
            ),
            "required_fields": _normalized_required_field_tokens(raw_requirement.get("required_fields")),
        }
    return normalized


def _mapping_contains_value(mapping: Mapping[str, Any], field_name: str) -> bool:
    if field_name not in mapping:
        return False
    value = mapping.get(field_name)
    if value is None:
        return False
    if isinstance(value, str):
        if value == "":
            return True
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True


def _payload_mapping_contains_value(mapping: Mapping[str, Any], field_name: str) -> bool:
    if field_name not in mapping:
        return False
    value = mapping.get(field_name)
    if value is None:
        return False
    if isinstance(value, str):
        if value == "":
            return True
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True


def _parse_non_negative_int(raw_value: Any, *, default: int) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if value < 0:
        return default
    return value

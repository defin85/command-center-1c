from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from apps.templates.pool_workflow_artifacts import resolve_odata_compatibility_profile_paths

PROFILE_PATH, PROFILE_SCHEMA_PATH = resolve_odata_compatibility_profile_paths()
_LEGACY_MODE_CUTOFF = (8, 3, 7)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload must be an object: {path}")
    return payload


def _schema_errors(*, schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for item in sorted(validator.iter_errors(payload), key=lambda error: str(error.path)):
        path = ".".join(str(segment) for segment in item.path)
        location = path or "<root>"
        errors.append(f"{location}: {item.message}")
    return errors


def _parse_version_tuple(raw_version: str | None) -> tuple[int, int, int] | None:
    token = str(raw_version or "").strip()
    if not token:
        return None
    segments = token.split(".")
    if len(segments) < 3:
        return None
    try:
        return int(segments[0]), int(segments[1]), int(segments[2])
    except ValueError:
        return None


def _is_legacy_mode_le_8_3_7(raw_version: str | None) -> bool:
    version = _parse_version_tuple(raw_version)
    if version is None:
        return False
    return version <= _LEGACY_MODE_CUTOFF


def run_odata_compatibility_preflight(
    *,
    configuration_id: str,
    compatibility_mode: str | None = None,
    write_content_type: str | None = None,
    release_profile_version: str | None = None,
) -> dict[str, Any]:
    profile = _load_yaml_file(PROFILE_PATH)
    schema = _load_yaml_file(PROFILE_SCHEMA_PATH)
    schema_errors = _schema_errors(schema=schema, payload=profile)

    profile_version = str(profile.get("profile_version") or "")
    rollout_gate = profile.get("rollout_gate") if isinstance(profile.get("rollout_gate"), dict) else {}
    entries_payload = profile.get("entries")
    entries = entries_payload if isinstance(entries_payload, list) else []
    target_entry = next(
        (
            item
            for item in entries
            if isinstance(item, dict)
            and str(item.get("configuration_id") or "") == configuration_id
        ),
        None,
    )

    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "key": "profile_schema",
            "ok": len(schema_errors) == 0,
            "errors": schema_errors,
        }
    )

    checks.append(
        {
            "key": "configuration_entry_exists",
            "ok": target_entry is not None,
            "configuration_id": configuration_id,
        }
    )

    if target_entry is None:
        decision = "no_go"
        return {
            "decision": decision,
            "profile": {
                "path": str(PROFILE_PATH),
                "schema_path": str(PROFILE_SCHEMA_PATH),
                "profile_version": profile_version,
            },
            "checks": checks,
            "summary": {
                "total_checks": len(checks),
                "failed_checks": sum(1 for item in checks if not bool(item.get("ok"))),
            },
        }

    require_approved_entry = bool(rollout_gate.get("require_approved_entry", True))
    verification_status = str(target_entry.get("verification_status") or "").strip().lower()
    checks.append(
        {
            "key": "verification_status",
            "ok": (not require_approved_entry) or verification_status == "approved",
            "required_status": "approved" if require_approved_entry else "any",
            "actual_status": verification_status,
        }
    )

    media_type_policy = (
        target_entry.get("media_type_policy")
        if isinstance(target_entry.get("media_type_policy"), dict)
        else {}
    )
    default_write_content_type = str(media_type_policy.get("default_write_content_type") or "").strip()
    effective_write_content_type = str(write_content_type or default_write_content_type).strip()
    accepts = [
        str(item).strip()
        for item in (media_type_policy.get("accepts") if isinstance(media_type_policy.get("accepts"), list) else [])
        if str(item).strip()
    ]
    rejects = [
        str(item).strip()
        for item in (media_type_policy.get("rejects") if isinstance(media_type_policy.get("rejects"), list) else [])
        if str(item).strip()
    ]

    write_content_type_ok = True
    if effective_write_content_type:
        if effective_write_content_type in rejects:
            write_content_type_ok = False
        elif accepts and effective_write_content_type not in accepts:
            write_content_type_ok = False
    checks.append(
        {
            "key": "media_type_policy",
            "ok": write_content_type_ok,
            "write_content_type": effective_write_content_type,
            "accepts": accepts,
            "rejects": rejects,
        }
    )

    block_on_incompatible_policy = bool(rollout_gate.get("block_on_incompatible_media_type_policy", True))
    legacy_mode_payload = (
        media_type_policy.get("legacy_mode_le_8_3_7")
        if isinstance(media_type_policy.get("legacy_mode_le_8_3_7"), dict)
        else {}
    )
    legacy_supported = bool(legacy_mode_payload.get("supported"))
    is_legacy_target = _is_legacy_mode_le_8_3_7(compatibility_mode)
    legacy_mode_ok = (not is_legacy_target) or legacy_supported
    checks.append(
        {
            "key": "legacy_mode_policy",
            "ok": (not block_on_incompatible_policy) or legacy_mode_ok,
            "compatibility_mode": compatibility_mode,
            "legacy_target": is_legacy_target,
            "legacy_supported": legacy_supported,
            "required_policy_note": legacy_mode_payload.get("required_policy_note"),
        }
    )

    require_release_profile_version = bool(rollout_gate.get("require_profile_version_in_release", True))
    checks.append(
        {
            "key": "release_profile_version",
            "ok": (not require_release_profile_version)
            or (
                bool(release_profile_version)
                and str(release_profile_version).strip() == profile_version
            ),
            "expected_profile_version": profile_version,
            "release_profile_version": release_profile_version,
        }
    )

    decision = "go" if all(bool(item.get("ok")) for item in checks) else "no_go"
    return {
        "decision": decision,
        "profile": {
            "path": str(PROFILE_PATH),
            "schema_path": str(PROFILE_SCHEMA_PATH),
            "profile_version": profile_version,
            "configuration_id": configuration_id,
        },
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "failed_checks": sum(1 for item in checks if not bool(item.get("ok"))),
        },
    }

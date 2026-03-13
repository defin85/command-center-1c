from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator


SCHEMA_VERSION = "workflow_hardening_cutover_evidence.v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "artifacts"
    / "workflow-hardening-rollout-evidence"
)
SCHEMA_PATH = ARTIFACT_ROOT / "workflow-hardening-cutover-evidence.schema.json"
REPOSITORY_EVIDENCE_PATH = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "artifacts"
    / "refactor-14"
    / "repository-acceptance-evidence.md"
).resolve()
REQUIRED_EVIDENCE_KINDS = (
    "binding_preview",
    "create_run",
    "inspect_lineage",
    "migration_outcome",
)
REQUIRED_SIGNOFF_ROLES = ("platform", "security", "operations")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def compute_bundle_digest(payload: dict[str, Any]) -> str:
    canonical_payload = copy.deepcopy(payload)
    canonical_payload.pop("bundle_digest", None)
    encoded = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _resolve_input_path(raw_bundle_path_or_uri: str) -> tuple[Path | None, str | None]:
    token = str(raw_bundle_path_or_uri or "").strip()
    if not token:
        return None, "BUNDLE_SOURCE_REQUIRED"

    parsed = urlparse(token)
    if not parsed.scheme:
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve(), None

    if parsed.scheme != "file":
        return None, f"UNSUPPORTED_BUNDLE_URI_SCHEME:{parsed.scheme}"

    if parsed.netloc not in {"", "localhost"}:
        return None, f"UNSUPPORTED_FILE_URI_HOST:{parsed.netloc}"

    return Path(unquote(parsed.path)).resolve(), None


def _load_schema() -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, ["VERIFIER_SCHEMA_NOT_FOUND"]
    except json.JSONDecodeError:
        return None, ["VERIFIER_SCHEMA_INVALID_JSON"]

    if not isinstance(payload, dict):
        return None, ["VERIFIER_SCHEMA_INVALID_OBJECT"]

    return payload, []


def _schema_errors(*, schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for item in sorted(validator.iter_errors(payload), key=lambda error: list(error.path)):
        path = ".".join(str(segment) for segment in item.path)
        location = path or "<root>"
        errors.append(f"{location}: {item.message}")
    return errors


def _build_base_verdict() -> dict[str, Any]:
    return {
        "status": "failed",
        "go_no_go": "no_go",
        "bundle_digest": None,
        "missing_requirements": [],
        "failed_checks": [],
    }


def verify_workflow_hardening_cutover_evidence(raw_bundle_path_or_uri: str) -> dict[str, Any]:
    verdict = _build_base_verdict()
    bundle_path, resolve_error = _resolve_input_path(raw_bundle_path_or_uri)
    if resolve_error:
        verdict["missing_requirements"] = ["tenant_live_cutover_bundle"]
        verdict["failed_checks"] = [resolve_error]
        return verdict

    if bundle_path == REPOSITORY_EVIDENCE_PATH:
        verdict["missing_requirements"] = ["tenant_live_cutover_bundle"]
        verdict["failed_checks"] = [
            "REPOSITORY_EVIDENCE_DOES_NOT_REPLACE_TENANT_LIVE_BUNDLE",
        ]
        return verdict

    if bundle_path is None or not bundle_path.exists():
        verdict["missing_requirements"] = ["tenant_live_cutover_bundle"]
        verdict["failed_checks"] = ["BUNDLE_PATH_NOT_FOUND"]
        return verdict

    try:
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        verdict["missing_requirements"] = ["tenant_live_cutover_bundle"]
        verdict["failed_checks"] = ["BUNDLE_JSON_INVALID"]
        return verdict

    if not isinstance(payload, dict):
        verdict["missing_requirements"] = ["tenant_live_cutover_bundle"]
        verdict["failed_checks"] = ["BUNDLE_JSON_OBJECT_REQUIRED"]
        return verdict

    return build_bundle_verdict(payload)


def build_bundle_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    verdict = _build_base_verdict()
    verdict["bundle_digest"] = compute_bundle_digest(payload)

    contract_failures: list[str] = []
    gate_blockers: list[str] = []
    missing_requirements: list[str] = []

    schema, schema_load_errors = _load_schema()
    if schema_load_errors:
        contract_failures.extend(schema_load_errors)
    elif schema is not None:
        schema_errors = _schema_errors(schema=schema, payload=payload)
        if schema_errors:
            contract_failures.append("BUNDLE_SCHEMA_INVALID")

    declared_digest = str(payload.get("bundle_digest") or "").strip()
    if not declared_digest:
        missing_requirements.append("bundle.bundle_digest")
    elif not _DIGEST_PATTERN.fullmatch(declared_digest):
        contract_failures.append("BUNDLE_DIGEST_FORMAT_INVALID")
    elif declared_digest != verdict["bundle_digest"]:
        contract_failures.append("BUNDLE_DIGEST_MISMATCH")

    evidence_refs = payload.get("evidence_refs")
    refs_by_kind: dict[str, list[dict[str, Any]]] = {}
    if isinstance(evidence_refs, list):
        for item in evidence_refs:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            if not kind:
                continue
            refs_by_kind.setdefault(kind, []).append(item)

    for kind in REQUIRED_EVIDENCE_KINDS:
        items = refs_by_kind.get(kind) or []
        if not items:
            missing_requirements.append(f"evidence_refs.kind:{kind}")
            continue
        for item in items:
            result = str(item.get("result") or "").strip()
            if kind == "migration_outcome":
                if result == "not_applicable":
                    if not str(item.get("reason") or "").strip():
                        contract_failures.append("MIGRATION_OUTCOME_REASON_REQUIRED")
                    continue
                if result == "failed":
                    gate_blockers.append("EVIDENCE_REF_RESULT_FAILED:migration_outcome")
                    continue
                if result != "passed":
                    contract_failures.append("MIGRATION_OUTCOME_RESULT_INVALID")
                continue
            if result == "failed":
                gate_blockers.append(f"EVIDENCE_REF_RESULT_FAILED:{kind}")
            elif result != "passed":
                contract_failures.append(f"EVIDENCE_REF_RESULT_INVALID:{kind}")

    overall_status = str(payload.get("overall_status") or "").strip()
    if overall_status == "no_go":
        gate_blockers.append("BUNDLE_OVERALL_STATUS_NO_GO")
    elif overall_status != "go":
        contract_failures.append("BUNDLE_OVERALL_STATUS_INVALID")

    sign_off = payload.get("sign_off")
    sign_off_by_role: dict[str, list[dict[str, Any]]] = {}
    if isinstance(sign_off, list):
        for item in sign_off:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            if not role:
                continue
            sign_off_by_role.setdefault(role, []).append(item)

    for role in REQUIRED_SIGNOFF_ROLES:
        entries = sign_off_by_role.get(role) or []
        if not entries:
            missing_requirements.append(f"sign_off.role:{role}")
            continue
        if len(entries) > 1:
            contract_failures.append(f"SIGN_OFF_ROLE_DUPLICATED:{role}")
            continue
        verdict_value = str(entries[0].get("verdict") or "").strip()
        if verdict_value == "no_go":
            gate_blockers.append(f"SIGN_OFF_VERDICT_NO_GO:{role}")
        elif verdict_value != "go":
            contract_failures.append(f"SIGN_OFF_VERDICT_INVALID:{role}")

    if overall_status == "go" and gate_blockers:
        contract_failures.append("BUNDLE_DECLARES_GO_WITH_BLOCKING_CHECKS")

    verdict["missing_requirements"] = missing_requirements
    verdict["failed_checks"] = contract_failures + gate_blockers

    if not missing_requirements and not contract_failures:
        verdict["status"] = "passed"

    if verdict["status"] == "passed" and not gate_blockers:
        verdict["go_no_go"] = "go"

    return verdict

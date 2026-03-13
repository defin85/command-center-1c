from __future__ import annotations

import copy
import hashlib
import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def _bundle_digest(payload: dict[str, object]) -> str:
    canonical_payload = copy.deepcopy(payload)
    canonical_payload.pop("bundle_digest", None)
    encoded = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _build_bundle(
    *,
    overall_status: str = "go",
    security_verdict: str = "go",
    migration_result: str = "not_applicable",
) -> dict[str, object]:
    reason = "legacy import was not required for this tenant"
    payload: dict[str, object] = {
        "schema_version": "workflow_hardening_cutover_evidence.v1",
        "change_id": "tighten-workflow-hardening-canonical-contracts",
        "git_sha": "0123456789abcdef0123456789abcdef01234567",
        "environment": "staging",
        "tenant_id": "stroygrupp",
        "runbook_version": "2026-03-13",
        "captured_at": "2026-03-13T09:00:00Z",
        "bundle_digest": "",
        "evidence_refs": [
            {
                "kind": "binding_preview",
                "uri": "s3://tenant-artifacts/staging/binding-preview.json",
                "digest": "sha256:" + "1" * 64,
                "captured_at": "2026-03-13T08:50:00Z",
                "result": "passed",
            },
            {
                "kind": "create_run",
                "uri": "s3://tenant-artifacts/staging/create-run.json",
                "digest": "sha256:" + "2" * 64,
                "captured_at": "2026-03-13T08:52:00Z",
                "result": "passed",
            },
            {
                "kind": "inspect_lineage",
                "uri": "s3://tenant-artifacts/staging/inspect-lineage.png",
                "digest": "sha256:" + "3" * 64,
                "captured_at": "2026-03-13T08:54:00Z",
                "result": "passed",
            },
            {
                "kind": "migration_outcome",
                "uri": "s3://tenant-artifacts/staging/migration-outcome.json",
                "digest": "sha256:" + "4" * 64,
                "captured_at": "2026-03-13T08:55:00Z",
                "result": migration_result,
                "reason": reason if migration_result == "not_applicable" else None,
            },
        ],
        "overall_status": overall_status,
        "sign_off": [
            {
                "role": "platform",
                "actor": "platform.lead",
                "signed_at": "2026-03-13T08:56:00Z",
                "verdict": "go",
            },
            {
                "role": "security",
                "actor": "security.lead",
                "signed_at": "2026-03-13T08:57:00Z",
                "verdict": security_verdict,
            },
            {
                "role": "operations",
                "actor": "operations.lead",
                "signed_at": "2026-03-13T08:58:00Z",
                "verdict": "go",
            },
        ],
    }
    payload["bundle_digest"] = _bundle_digest(payload)
    return payload


def test_verify_workflow_hardening_cutover_evidence_passes_for_valid_go_bundle(tmp_path) -> None:
    bundle_path = tmp_path / "workflow-hardening-cutover-evidence.json"
    bundle = _build_bundle()
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = io.StringIO()
    call_command(
        "verify_workflow_hardening_cutover_evidence",
        bundle_path.as_uri(),
        stdout=out,
    )

    verdict = json.loads(out.getvalue())
    assert verdict == {
        "status": "passed",
        "go_no_go": "go",
        "bundle_digest": bundle["bundle_digest"],
        "missing_requirements": [],
        "failed_checks": [],
    }


def test_verify_workflow_hardening_cutover_evidence_fails_closed_for_missing_refs_and_signoff(tmp_path) -> None:
    bundle_path = tmp_path / "workflow-hardening-cutover-evidence.json"
    bundle = _build_bundle()
    bundle["bundle_digest"] = ""
    bundle["evidence_refs"] = [
        ref for ref in bundle["evidence_refs"] if ref["kind"] != "migration_outcome"
    ]
    bundle["sign_off"] = [item for item in bundle["sign_off"] if item["role"] != "operations"]
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command(
            "verify_workflow_hardening_cutover_evidence",
            str(bundle_path),
            stdout=out,
        )

    verdict = json.loads(out.getvalue())
    assert verdict["status"] == "failed"
    assert verdict["go_no_go"] == "no_go"
    assert verdict["bundle_digest"] == _bundle_digest(bundle)
    assert verdict["missing_requirements"] == [
        "bundle.bundle_digest",
        "evidence_refs.kind:migration_outcome",
        "sign_off.role:operations",
    ]
    assert "BUNDLE_SCHEMA_INVALID" in verdict["failed_checks"]


def test_verify_workflow_hardening_cutover_evidence_rejects_repository_evidence_as_live_bundle() -> None:
    out = io.StringIO()

    with pytest.raises(CommandError):
        call_command(
            "verify_workflow_hardening_cutover_evidence",
            "docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md",
            stdout=out,
        )

    verdict = json.loads(out.getvalue())
    assert verdict["status"] == "failed"
    assert verdict["go_no_go"] == "no_go"
    assert verdict["bundle_digest"] is None
    assert verdict["missing_requirements"] == ["tenant_live_cutover_bundle"]
    assert verdict["failed_checks"] == [
        "REPOSITORY_EVIDENCE_DOES_NOT_REPLACE_TENANT_LIVE_BUNDLE",
    ]


def test_verify_workflow_hardening_cutover_evidence_returns_valid_no_go_verdict(tmp_path) -> None:
    bundle_path = tmp_path / "workflow-hardening-cutover-evidence.json"
    bundle = _build_bundle(
        overall_status="no_go",
        security_verdict="no_go",
    )
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command(
            "verify_workflow_hardening_cutover_evidence",
            str(bundle_path),
            stdout=out,
        )

    verdict = json.loads(out.getvalue())
    assert verdict["status"] == "passed"
    assert verdict["go_no_go"] == "no_go"
    assert verdict["bundle_digest"] == bundle["bundle_digest"]
    assert verdict["missing_requirements"] == []
    assert verdict["failed_checks"] == [
        "BUNDLE_OVERALL_STATUS_NO_GO",
        "SIGN_OFF_VERDICT_NO_GO:security",
    ]

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates import odata_compatibility_preflight as preflight_module


@pytest.mark.django_db
def test_odata_compatibility_preflight_go_for_approved_configuration() -> None:
    out = StringIO()
    call_command(
        "preflight_odata_compatibility_profile",
        "--configuration-id",
        "1c-accounting-3.0-standard-odata",
        "--compatibility-mode",
        "8.3.23",
        "--write-content-type",
        "application/json;odata=nometadata",
        "--release-profile-version",
        "0.4.2-draft",
        "--json",
        "--strict",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["decision"] == "go"
    checks = {item["key"]: item for item in payload["checks"]}
    assert checks["verification_status"]["ok"] is True
    assert checks["media_type_policy"]["ok"] is True
    assert checks["legacy_mode_policy"]["ok"] is True
    assert "openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml" in payload["profile"]["path"]


@pytest.mark.django_db
def test_odata_compatibility_preflight_release_profile_version_mismatch_fails() -> None:
    out = StringIO()
    call_command(
        "preflight_odata_compatibility_profile",
        "--configuration-id",
        "1c-accounting-3.0-standard-odata",
        "--compatibility-mode",
        "8.3.23",
        "--write-content-type",
        "application/json;odata=nometadata",
        "--release-profile-version",
        "0.0.0-mismatch",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["decision"] == "no_go"
    assert checks["release_profile_version"]["ok"] is False
    assert checks["release_profile_version"]["expected_profile_version"] == "0.4.2-draft"
    assert checks["release_profile_version"]["release_profile_version"] == "0.0.0-mismatch"

    with pytest.raises(CommandError, match="decision=No-Go"):
        call_command(
            "preflight_odata_compatibility_profile",
            "--configuration-id",
            "1c-accounting-3.0-standard-odata",
            "--compatibility-mode",
            "8.3.23",
            "--write-content-type",
            "application/json;odata=nometadata",
            "--release-profile-version",
            "0.0.0-mismatch",
            "--strict",
        )


@pytest.mark.django_db
def test_odata_compatibility_preflight_strict_fails_on_legacy_mode_without_policy() -> None:
    with pytest.raises(CommandError):
        call_command(
            "preflight_odata_compatibility_profile",
            "--configuration-id",
            "1c-accounting-3.0-standard-odata",
            "--compatibility-mode",
            "8.3.7",
            "--write-content-type",
            "application/json;odata=nometadata",
            "--release-profile-version",
            "0.4.2-draft",
            "--strict",
        )


@pytest.mark.django_db
def test_odata_compatibility_preflight_fails_on_rejected_content_type() -> None:
    out = StringIO()
    call_command(
        "preflight_odata_compatibility_profile",
        "--configuration-id",
        "1c-accounting-3.0-standard-odata",
        "--compatibility-mode",
        "8.3.23",
        "--write-content-type",
        "application/json;odata=verbose",
        "--release-profile-version",
        "0.4.2-draft",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}
    assert payload["decision"] == "no_go"
    assert checks["media_type_policy"]["ok"] is False


@pytest.mark.django_db
def test_odata_compatibility_preflight_reports_legacy_mode_policy_block_without_legacy_entry() -> None:
    out = StringIO()
    call_command(
        "preflight_odata_compatibility_profile",
        "--configuration-id",
        "1c-accounting-3.0-standard-odata",
        "--compatibility-mode",
        "8.3.7",
        "--write-content-type",
        "application/json;odata=nometadata",
        "--release-profile-version",
        "0.4.2-draft",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}
    legacy_check = checks["legacy_mode_policy"]

    assert payload["decision"] == "no_go"
    assert legacy_check["ok"] is False
    assert legacy_check["legacy_target"] is True
    assert legacy_check["legacy_supported"] is False


@pytest.mark.django_db
def test_odata_compatibility_preflight_does_not_fallback_to_archived_change_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archived_profiles = sorted(
        Path("openspec/changes/archive").glob(
            "*-refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.yaml"
        )
    )
    assert archived_profiles

    missing_profile = Path("/tmp/missing-odata-compatibility-profile.yaml")
    missing_schema = Path("/tmp/missing-odata-compatibility-profile.schema.yaml")
    monkeypatch.setattr(preflight_module, "PROFILE_PATH", missing_profile)
    monkeypatch.setattr(preflight_module, "PROFILE_SCHEMA_PATH", missing_schema)

    with pytest.raises(CommandError, match="missing-odata-compatibility-profile.yaml"):
        call_command(
            "preflight_odata_compatibility_profile",
            "--configuration-id",
            "1c-accounting-3.0-standard-odata",
            "--compatibility-mode",
            "8.3.23",
        )

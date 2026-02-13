from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


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

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_gate_operation_template_references_passes_for_clean_custom_path(tmp_path):
    file_path = tmp_path / "clean.py"
    file_path.write_text("def ok() -> str:\n    return 'clean'\n", encoding="utf-8")

    out = StringIO()
    call_command(
        "gate_operation_template_references",
        "--path",
        str(file_path),
        "--json",
        "--strict",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["status"] == "pass"
    assert payload["violation_count"] == 0
    assert payload["missing_paths"] == []


@pytest.mark.django_db
def test_gate_operation_template_references_fails_for_forbidden_token(tmp_path):
    file_path = tmp_path / "bad.py"
    file_path.write_text(
        "from apps.templates.models import OperationTemplate\n",
        encoding="utf-8",
    )

    with pytest.raises(CommandError):
        call_command(
            "gate_operation_template_references",
            "--path",
            str(file_path),
            "--strict",
        )


@pytest.mark.django_db
def test_gate_operation_template_references_ignores_safe_serializer_names(tmp_path):
    file_path = tmp_path / "safe_names.py"
    file_path.write_text(
        "GrantOperationTemplatePermissionRequestSerializer = object\n"
        "OperationTemplateGroupPermissionListResponseSerializer = object\n",
        encoding="utf-8",
    )

    out = StringIO()
    call_command(
        "gate_operation_template_references",
        "--path",
        str(file_path),
        "--json",
        "--strict",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    assert payload["status"] == "pass"
    assert payload["violation_count"] == 0

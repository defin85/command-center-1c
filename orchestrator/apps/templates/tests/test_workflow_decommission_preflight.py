from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates import workflow_decommission_preflight as preflight_module
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


def _create_workflow_template(name: str) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=name,
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-test",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )


def _write_registry_with_all_consumers_migrated(tmp_path: Path) -> tuple[Path, str]:
    registry_payload = preflight_module._load_yaml_file(preflight_module.REGISTRY_PATH)
    consumers_payload = registry_payload.get("consumers")
    consumers = consumers_payload if isinstance(consumers_payload, list) else []
    registry_payload["consumers"] = [
        {**item, "migrated": True} if isinstance(item, dict) else item for item in consumers
    ]
    registry_path = tmp_path / "execution-consumers-registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(registry_payload, sort_keys=False),
        encoding="utf-8",
    )
    return registry_path, str(registry_payload.get("registry_version") or "").strip()


@pytest.mark.django_db
def test_workflow_decommission_preflight_returns_no_go_from_registry() -> None:
    out = StringIO()
    call_command("preflight_workflow_decommission_consumers", "--json", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["decision"] == "no_go"
    checks = {item["key"]: item for item in payload["checks"]}
    assert checks["registry_schema"]["ok"] is True
    assert checks["all_consumers_migrated"]["ok"] is False
    assert "pools" in checks["all_consumers_migrated"]["unmigrated_consumers"]
    assert "legacy" in checks["all_consumers_migrated"]["unmigrated_consumers"]
    assert "openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.yaml" in payload["registry"]["path"]


@pytest.mark.django_db
def test_workflow_decommission_preflight_strict_mode_fails_for_no_go() -> None:
    with pytest.raises(CommandError):
        call_command("preflight_workflow_decommission_consumers", "--strict")


@pytest.mark.django_db
def test_workflow_decommission_preflight_release_registry_version_match_can_go(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry_path, registry_version = _write_registry_with_all_consumers_migrated(tmp_path)
    monkeypatch.setattr(preflight_module, "REGISTRY_PATH", registry_path)

    out = StringIO()
    call_command(
        "preflight_workflow_decommission_consumers",
        "--release-registry-version",
        registry_version,
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["decision"] == "go"
    assert checks["release_registry_version"]["ok"] is True
    assert checks["release_registry_version"]["required_in_release"] is True
    assert checks["release_registry_version"]["expected_registry_version"] == registry_version
    assert checks["release_registry_version"]["release_registry_version"] == registry_version


@pytest.mark.django_db
def test_workflow_decommission_preflight_release_registry_version_mismatch_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry_path, registry_version = _write_registry_with_all_consumers_migrated(tmp_path)
    monkeypatch.setattr(preflight_module, "REGISTRY_PATH", registry_path)
    wrong_registry_version = f"{registry_version}-mismatch"

    out = StringIO()
    call_command(
        "preflight_workflow_decommission_consumers",
        "--release-registry-version",
        wrong_registry_version,
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["decision"] == "no_go"
    assert checks["release_registry_version"]["ok"] is False
    assert checks["release_registry_version"]["expected_registry_version"] == registry_version
    assert (
        checks["release_registry_version"]["release_registry_version"]
        == wrong_registry_version
    )

    with pytest.raises(CommandError, match="decision=No-Go"):
        call_command(
            "preflight_workflow_decommission_consumers",
            "--release-registry-version",
            wrong_registry_version,
            "--strict",
        )


@pytest.mark.django_db
def test_workflow_decommission_preflight_missing_release_registry_version_fails_when_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry_path, _ = _write_registry_with_all_consumers_migrated(tmp_path)
    monkeypatch.setattr(preflight_module, "REGISTRY_PATH", registry_path)

    out = StringIO()
    call_command("preflight_workflow_decommission_consumers", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["decision"] == "no_go"
    assert checks["release_registry_version"]["required_in_release"] is True
    assert checks["release_registry_version"]["ok"] is False
    assert checks["release_registry_version"]["release_registry_version"] is None

    with pytest.raises(CommandError, match="decision=No-Go"):
        call_command("preflight_workflow_decommission_consumers", "--strict")


@pytest.mark.django_db
def test_workflow_decommission_preflight_allows_nullable_transition_mode_for_legacy() -> None:
    template = _create_workflow_template("decommission-preflight-legacy")
    template.create_execution(
        {"operation": "legacy-no-tenant"},
        execution_consumer="legacy",
    )

    out = StringIO()
    call_command("preflight_workflow_decommission_consumers", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}
    tenant_mode_check = checks["tenant_mode_requirements"]

    assert tenant_mode_check["ok"] is True
    assert tenant_mode_check["violations"] == []
    assert any(
        item["consumer"] == "legacy" and item["null_tenant_total"] >= 1
        for item in tenant_mode_check["transition_null_tenant_consumers"]
    )


@pytest.mark.django_db
def test_workflow_decommission_preflight_does_not_fallback_to_archived_change_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archived_registries = sorted(
        Path("openspec/changes/archive").glob(
            "*-refactor-unify-pools-workflow-execution-core/execution-consumers-registry.yaml"
        )
    )
    assert archived_registries

    missing_registry = Path("/tmp/missing-execution-consumers-registry.yaml")
    missing_schema = Path("/tmp/missing-execution-consumers-registry.schema.yaml")
    monkeypatch.setattr(preflight_module, "REGISTRY_PATH", missing_registry)
    monkeypatch.setattr(preflight_module, "REGISTRY_SCHEMA_PATH", missing_schema)

    with pytest.raises(CommandError, match="missing-execution-consumers-registry.yaml"):
        call_command("preflight_workflow_decommission_consumers")

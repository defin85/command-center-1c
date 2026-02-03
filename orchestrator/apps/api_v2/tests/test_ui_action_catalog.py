import io
import json
import uuid

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.databases.models import Database, DatabaseExtensionsSnapshot, DatabasePermission, PermissionLevel
from apps.runtime_settings.models import RuntimeSetting
from apps.templates.models import WorkflowTemplatePermission
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


def _seed_ibcmd_catalog(monkeypatch, *, base_catalog: dict, overrides_catalog: dict | None = None):
    suffix = uuid.uuid4().hex[:8]

    base = Artifact.objects.create(
        name="driver_catalog.ibcmd.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "ibcmd", "base"],
    )
    base_version = ArtifactVersion.objects.create(
        artifact=base,
        version=f"v-base-{suffix}",
        filename=f"driver_catalog.ibcmd.base__v-base-{suffix}.json",
        storage_key=f"test/ibcmd/base/{suffix}",
        size=1,
        checksum=f"base-{suffix}",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)

    overrides_version = None
    storage_map = {
        base_version.storage_key: json.dumps(base_catalog).encode("utf-8"),
    }

    if overrides_catalog is not None:
        overrides = Artifact.objects.create(
            name="driver_catalog.ibcmd.overrides",
            kind=ArtifactKind.DRIVER_CATALOG,
            is_versioned=True,
            tags=["driver_catalog", "ibcmd", "overrides"],
        )
        overrides_version = ArtifactVersion.objects.create(
            artifact=overrides,
            version=f"v-override-{suffix}",
            filename=f"driver_catalog.ibcmd.overrides__v-override-{suffix}.json",
            storage_key=f"test/ibcmd/overrides/{suffix}",
            size=1,
            checksum=f"overrides-{suffix}",
            content_type="application/json",
            metadata={},
        )
        ArtifactAlias.objects.create(artifact=overrides, alias="active", version=overrides_version)
        storage_map[overrides_version.storage_key] = json.dumps(overrides_catalog).encode("utf-8")

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_map[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)
    return base_version, overrides_version


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="ui_action_catalog_staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def user():
    return User.objects.create_user(username="ui_action_catalog_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_update_runtime_setting_ui_action_catalog_rejects_invalid_schema(staff_client):
    resp = staff_client.patch(
        "/api/v2/settings/runtime/ui.action_catalog/",
        data={"value": {"catalog_version": 1}},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(payload["error"]["message"], list)
    assert payload["error"]["message"]


@pytest.mark.django_db
def test_update_runtime_setting_ui_action_catalog_rejects_unknown_command_reference(staff_client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    _seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )

    resp = staff_client.patch(
        "/api/v2/settings/runtime/ui.action_catalog/",
        data={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.unknown",
                            "label": "Unknown command",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "unknown.command"},
                        }
                    ]
                },
            }
        },
        format="json",
    )

    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(payload["error"]["message"], list)
    assert any("unknown command_id" in msg for msg in payload["error"]["message"])
    assert any("extensions.actions[0]" in msg for msg in payload["error"]["message"])
    assert any("executor.command_id" in msg for msg in payload["error"]["message"])


@pytest.mark.django_db
def test_update_runtime_setting_ui_action_catalog_rejects_unknown_workflow_reference(staff_client):
    missing_workflow_id = str(uuid.uuid4())
    resp = staff_client.patch(
        "/api/v2/settings/runtime/ui.action_catalog/",
        data={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.workflow",
                            "label": "Workflow",
                            "contexts": ["database_card"],
                            "executor": {"kind": "workflow", "workflow_id": missing_workflow_id},
                        }
                    ]
                },
            }
        },
        format="json",
    )

    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(payload["error"]["message"], list)
    assert any("workflow not found" in msg for msg in payload["error"]["message"])
    assert any("extensions.actions[0]" in msg for msg in payload["error"]["message"])
    assert any("executor.workflow_id" in msg for msg in payload["error"]["message"])


@pytest.mark.django_db
def test_update_runtime_setting_ui_action_catalog_accepts_valid_references(staff_client, staff_user, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    _seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )

    workflow = WorkflowTemplate.objects.create(
        name="Test Workflow",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {"id": "n1", "name": "Node 1", "type": "operation", "template_id": "tpl-test"},
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
        created_by=staff_user,
    )

    resp = staff_client.patch(
        "/api/v2/settings/runtime/ui.action_catalog/",
        data={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.list",
                            "label": "List extensions",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                        {
                            "id": "extensions.workflow",
                            "label": "Workflow",
                            "contexts": ["database_card"],
                            "executor": {"kind": "workflow", "workflow_id": str(workflow.id)},
                        },
                    ]
                },
            }
        },
        format="json",
    )

    assert resp.status_code == 200


@pytest.mark.django_db
def test_update_runtime_setting_ui_action_catalog_rejects_duplicate_reserved_capability(staff_client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    _seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )

    resp = staff_client.patch(
        "/api/v2/settings/runtime/ui.action_catalog/",
        data={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "ListExtension1",
                            "capability": "extensions.list",
                            "label": "List extensions 1",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                        {
                            "id": "ListExtension2",
                            "capability": "extensions.list",
                            "label": "List extensions 2",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                    ]
                },
            }
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert any("duplicate reserved capability" in msg for msg in payload["error"]["message"])
    assert any("extensions.list" in msg for msg in payload["error"]["message"])


@pytest.mark.django_db
def test_update_runtime_setting_ui_action_catalog_accepts_unknown_capability(staff_client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    _seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )

    resp2 = staff_client.patch(
        "/api/v2/settings/runtime/ui.action_catalog/",
        data={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "CustomList",
                            "capability": "custom.extensions.list",
                            "label": "Custom list",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                    ]
                },
            }
        },
        format="json",
    )
    assert resp2.status_code == 200

@pytest.mark.django_db
def test_ui_action_catalog_filters_unknown_and_dangerous_for_non_staff(client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "List extensions",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
            "server.config.drop": {
                "label": "drop config",
                "description": "dangerous",
                "argv": ["server", "config", "drop"],
                "scope": "global",
                "risk_level": "dangerous",
                "params_by_name": {},
            },
        },
    }
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}})

    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.list",
                            "label": "List extensions",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": " infobase.extension.list "},
                        },
                        {
                            "id": "extensions.drop",
                            "label": "Drop config",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "server.config.drop"},
                        },
                        {
                            "id": "extensions.unknown",
                            "label": "Unknown",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "unknown.command"},
                        },
                    ]
                },
            }
        },
    )

    resp = client.get("/api/v2/ui/action-catalog/")
    assert resp.status_code == 200
    payload = resp.json()
    actions = payload["extensions"]["actions"]
    ids = {item["id"] for item in actions}
    assert ids == {"extensions.list"}


@pytest.mark.django_db
def test_ui_action_catalog_filters_workflow_without_permission(client, user):
    ct = ContentType.objects.get(app_label="templates", model="workflowtemplate")
    perm = Permission.objects.get(content_type=ct, codename="execute_workflow_template")
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))

    workflow = WorkflowTemplate.objects.create(
        name="Test Workflow",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {"id": "n1", "name": "Node 1", "type": "operation", "template_id": "tpl-test"},
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
        created_by=user,
    )

    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.workflow",
                            "label": "Workflow",
                            "contexts": ["database_card"],
                            "executor": {"kind": "workflow", "workflow_id": f" {workflow.id} "},
                        },
                    ]
                },
            }
        },
    )

    resp = client.get("/api/v2/ui/action-catalog/")
    assert resp.status_code == 200
    assert resp.json()["extensions"]["actions"] == []

    WorkflowTemplatePermission.objects.create(
        user=user,
        workflow_template=workflow,
        level=PermissionLevel.OPERATE,
        notes="",
    )
    client.force_authenticate(user=User.objects.get(pk=user.pk))

    resp2 = client.get("/api/v2/ui/action-catalog/")
    assert resp2.status_code == 200
    actions = resp2.json()["extensions"]["actions"]
    assert {item["id"] for item in actions} == {"extensions.workflow"}


@pytest.mark.django_db
def test_get_extensions_snapshot_requires_permission_and_returns_empty(client, user):
    db = Database.objects.create(
        name="db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )

    denied = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert denied.status_code == 403

    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="view_database")
    user.user_permissions.add(perm)
    DatabasePermission.objects.create(user=user, database=db, level=PermissionLevel.VIEW)
    client.force_authenticate(user=User.objects.get(pk=user.pk))

    resp = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["database_id"] == str(db.id)
    assert payload["snapshot"] == {}

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db.id,
        defaults={"snapshot": {"stdout": "ok", "exit_code": 0}, "source_operation_id": "op-1"},
    )
    resp2 = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert resp2.status_code == 200
    snapshot = resp2.json()["snapshot"]
    assert snapshot["extensions"] == []
    assert snapshot["raw"] == {"stdout": "ok", "exit_code": 0}
    assert snapshot["parse_error"] is None

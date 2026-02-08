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
from apps.templates.models import OperationExposure, WorkflowTemplatePermission
from apps.templates.operation_catalog_service import resolve_definition, resolve_exposure
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


def _seed_action_catalog_exposures(*, actions: list[dict], tenant_id: str | None = None):
    tenant_scope = f"tenant:{tenant_id}" if tenant_id else "global"
    for index, action in enumerate(actions):
        executor = dict(action.get("executor") or {})
        definition, _ = resolve_definition(
            tenant_scope=tenant_scope,
            executor_kind=str(executor.get("kind") or "").strip(),
            executor_payload=executor,
            contract_version=1,
        )
        resolve_exposure(
            definition=definition,
            surface=OperationExposure.SURFACE_ACTION_CATALOG,
            alias=str(action.get("id") or "").strip(),
            tenant_id=tenant_id,
            label=str(action.get("label") or action.get("id") or "").strip(),
            description=str(action.get("description") or ""),
            is_active=bool(action.get("is_active", True)),
            capability=str(action.get("capability") or "").strip(),
            contexts=[str(v) for v in (action.get("contexts") or []) if isinstance(v, str)],
            display_order=index,
            capability_config={},
            status=OperationExposure.STATUS_PUBLISHED,
        )


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
    _seed_action_catalog_exposures(
        actions=[
            {
                "id": "extensions.list",
                "label": "List extensions",
                "contexts": ["database_card"],
                "capability": "extensions.list",
                "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": " infobase.extension.list "},
            },
            {
                "id": "extensions.drop",
                "label": "Drop config",
                "contexts": ["database_card"],
                "capability": "extensions.drop",
                "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "server.config.drop"},
            },
            {
                "id": "extensions.unknown",
                "label": "Unknown",
                "contexts": ["database_card"],
                "capability": "extensions.unknown",
                "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "unknown.command"},
            },
        ]
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
    _seed_action_catalog_exposures(
        actions=[
            {
                "id": "extensions.workflow",
                "label": "Workflow",
                "contexts": ["database_card"],
                "capability": "extensions.workflow",
                "executor": {"kind": "workflow", "workflow_id": f" {workflow.id} "},
            },
        ]
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
def test_ui_action_catalog_ignores_legacy_runtime_setting_payload(staff_client):
    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "legacy.extensions.list",
                            "label": "Legacy list",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        }
                    ]
                },
            }
        },
    )

    resp = staff_client.get("/api/v2/ui/action-catalog/")
    assert resp.status_code == 200
    assert resp.json()["extensions"]["actions"] == []


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


@pytest.mark.django_db
def test_get_extensions_snapshot_preserves_full_extensions_fields(client, user):
    db = Database.objects.create(
        name="db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )

    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="view_database")
    user.user_permissions.add(perm)
    DatabasePermission.objects.create(user=user, database=db, level=PermissionLevel.VIEW)
    client.force_authenticate(user=User.objects.get(pk=user.pk))

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db.id,
        defaults={
            "snapshot": {
                "raw": {"stdout": "ok", "exit_code": 0},
                "parse_error": None,
                "extensions": [
                    {
                        "name": "ExtA",
                        "purpose": "Accounting",
                        "is_active": True,
                        "safe_mode": False,
                        "unsafe_action_protection": True,
                    },
                    {
                        "name": "ExtB",
                        "purpose": "",
                        "is_active": False,
                        "safe_mode": True,
                        "unsafe_action_protection": False,
                    },
                ],
            },
            "source_operation_id": "op-2",
        },
    )

    resp = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert resp.status_code == 200
    snapshot = resp.json()["snapshot"]
    assert snapshot["parse_error"] is None
    assert snapshot["raw"] == {"stdout": "ok", "exit_code": 0}
    assert snapshot["extensions"] == [
        {
            "name": "ExtA",
            "purpose": "Accounting",
            "is_active": True,
            "safe_mode": False,
            "unsafe_action_protection": True,
        },
        {
            "name": "ExtB",
            "purpose": "",
            "is_active": False,
            "safe_mode": True,
            "unsafe_action_protection": False,
        },
    ]

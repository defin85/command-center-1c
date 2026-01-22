import io
import json
import uuid

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.databases.models import PermissionLevel
from apps.operations.models import BatchOperation, Task
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


def _grant_operation_permission(client: APIClient, user: User, codename: str) -> None:
    ct = ContentType.objects.get(app_label="operations", model="batchoperation")
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="execution_plan_staff", password="pass")
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
    return User.objects.create_user(username="execution_plan_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_preview_execution_plan_staff_only(client):
    resp = client.post("/api/v2/ui/execution-plan/preview/", {"executor": {"kind": "workflow"}}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_preview_execution_plan_workflow_masks_secrets(staff_client, staff_user):
    workflow = WorkflowTemplate.objects.create(
        name="wf",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "operation",
                    "template_id": "noop",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
        version_number=1,
    )
    WorkflowTemplatePermission.objects.create(
        user=staff_user,
        workflow_template=workflow,
        level=PermissionLevel.OPERATE,
        notes="",
    )
    staff_client.force_authenticate(user=User.objects.get(pk=staff_user.pk))

    secret = "s3cr3t"
    resp = staff_client.post(
        "/api/v2/ui/execution-plan/preview/",
        {
            "executor": {
                "kind": "workflow",
                "workflow_id": str(workflow.id),
                "params": {"password": secret, "foo": "bar"},
            },
            "database_ids": [str(uuid.uuid4())],
        },
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["execution_plan"]["kind"] == "workflow"
    assert payload["execution_plan"]["input_context_masked"]["password"] == "***"
    assert secret not in json.dumps(payload)


@pytest.mark.django_db
def test_preview_execution_plan_ibcmd_masks_db_pwd(staff_client, staff_user, monkeypatch):
    _grant_operation_permission(staff_client, staff_user, "execute_safe_operation")

    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.extension.list": {
                "label": "list extensions",
                "description": "list",
                "argv": ["infobase", "config", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    secret = "db-secret"
    resp = staff_client.post(
        "/api/v2/ui/execution-plan/preview/",
        {
            "executor": {"kind": "ibcmd_cli", "command_id": "infobase.extension.list", "mode": "guided"},
            "connection": {
                "offline": {
                    "config": "/tmp/config",
                    "data": "/tmp/data",
                    "dbms": "mssql",
                    "db_server": "srv",
                    "db_name": "db",
                    "db_user": "admin",
                    "db_pwd": secret,
                }
            },
        },
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    argv_masked = payload["execution_plan"]["argv_masked"]
    assert any("--db-pwd=***" in token for token in argv_masked)
    assert secret not in json.dumps(payload)


@pytest.mark.django_db
def test_get_operation_hides_execution_plan_for_non_staff(client, user):
    op_id = uuid.uuid4().hex
    BatchOperation.objects.create(
        id=op_id,
        name="op",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_PENDING,
        payload={},
        config={},
        total_tasks=1,
        created_by=user.username,
        metadata={
            "execution_plan": {"kind": "ibcmd_cli", "argv_masked": ["--db-pwd=***"]},
            "bindings": [{"target_ref": "stdin", "source_ref": "x", "resolve_at": "api", "sensitive": True, "status": "applied"}],
        },
    )
    Task.objects.create(id=uuid.uuid4().hex, batch_operation_id=op_id, database=None, status=Task.STATUS_PENDING)

    resp = client.get("/api/v2/operations/get-operation/", {"operation_id": op_id})
    assert resp.status_code == 200
    payload = resp.json()
    assert "execution_plan" not in payload
    assert "bindings" not in payload
    assert "execution_plan" not in (payload.get("operation", {}).get("metadata") or {})
    assert "bindings" not in (payload.get("operation", {}).get("metadata") or {})


@pytest.mark.django_db
def test_get_operation_includes_execution_plan_for_staff(staff_client, staff_user):
    op_id = uuid.uuid4().hex
    BatchOperation.objects.create(
        id=op_id,
        name="op",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_PENDING,
        payload={},
        config={},
        total_tasks=1,
        created_by=staff_user.username,
        metadata={
            "execution_plan": {"kind": "ibcmd_cli", "argv_masked": ["--db-pwd=***"]},
            "bindings": [{"target_ref": "stdin", "source_ref": "x", "resolve_at": "api", "sensitive": True, "status": "applied"}],
        },
    )
    Task.objects.create(id=uuid.uuid4().hex, batch_operation_id=op_id, database=None, status=Task.STATUS_PENDING)

    resp = staff_client.get("/api/v2/operations/get-operation/", {"operation_id": op_id})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["execution_plan"]["kind"] == "ibcmd_cli"
    assert isinstance(payload["bindings"], list)

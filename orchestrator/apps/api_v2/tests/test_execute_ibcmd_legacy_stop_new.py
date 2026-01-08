import io
import json
import uuid

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.databases.models import Database, DatabasePermission, PermissionLevel
from apps.operations.models import BatchOperation
from apps.operations.services import EnqueueResult, OperationsService


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


def _allow_operate(user, database: Database, *, level: int = PermissionLevel.OPERATE):
    DatabasePermission.objects.create(user=user, database=database, level=level)


@pytest.fixture
def user():
    return User.objects.create_user(username="legacy_ibcmd_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def target_dbs():
    db1 = Database.objects.create(
        name="target_db_1",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    db2 = Database.objects.create(
        name="target_db_2",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    return [db1, db2]


@pytest.mark.django_db
def test_execute_ibcmd_deprecated_requires_catalog(client, user, target_dbs):
    _grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        _allow_operate(user, db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd/",
        {
            "operation_type": "ibcmd_backup",
            "database_ids": [db.id for db in target_dbs],
            "config": {
                "dbms": "PostgreSQL",
                "db_server": "localhost",
                "db_name": "db",
                "db_user": "user",
                "db_password": "secret",
            },
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "CATALOG_NOT_AVAILABLE"
    assert resp.headers.get("Deprecation") == "true"
    assert resp.headers.get("Sunset")
    assert resp.headers.get("X-CC1C-Legacy-Operation-Type") == "ibcmd_backup"
    assert resp.headers.get("X-CC1C-Legacy-Endpoint") == "execute_ibcmd_operation"


@pytest.mark.django_db
def test_execute_ibcmd_deprecated_maps_to_ibcmd_cli(client, user, target_dbs, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.dump": {
                "label": "infobase dump",
                "description": "dump",
                "argv": ["infobase", "dump"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {
                    "dbms": {"kind": "flag", "flag": "--dbms", "expects_value": True, "required": True},
                    "db_server": {"kind": "flag", "flag": "--db-server", "expects_value": True, "required": True},
                    "db_name": {"kind": "flag", "flag": "--db-name", "expects_value": True, "required": True},
                    "db_user": {"kind": "flag", "flag": "--db-user", "expects_value": True, "required": True},
                    "db_pwd": {"kind": "flag", "flag": "--db-pwd", "expects_value": True, "required": True},
                    "arg1": {"kind": "positional", "position": 1, "expects_value": True, "required": False},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        _allow_operate(user, db)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd/",
        {
            "operation_type": "ibcmd_backup",
            "database_ids": [db.id for db in target_dbs],
            "config": {
                "dbms": "PostgreSQL",
                "db_server": "localhost",
                "db_name": "db",
                "db_user": "user",
                "db_password": "secret",
                "output_path": "test.dt",
            },
        },
        format="json",
    )
    assert resp.status_code == 202
    payload = resp.json()
    op_id = payload["operation_id"]

    op = BatchOperation.objects.get(id=op_id)
    assert op.operation_type == BatchOperation.TYPE_IBCMD_CLI
    assert op.metadata.get("legacy_operation_type") == "ibcmd_backup"
    assert op.payload["data"]["command_id"] == "infobase.dump"

    assert resp.headers.get("Deprecation") == "true"
    assert resp.headers.get("Sunset")
    assert resp.headers.get("X-CC1C-Legacy-Operation-Type") == "ibcmd_backup"
    assert resp.headers.get("X-CC1C-Legacy-Endpoint") == "execute_ibcmd_operation"


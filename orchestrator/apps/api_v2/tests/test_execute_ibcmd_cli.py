import io
import json
import uuid

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.databases.models import Database, DatabasePermission, PermissionLevel, DbmsUserMapping
from apps.operations.models import BatchOperation, Task
from apps.operations.redis_client import redis_client
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


@pytest.fixture
def user():
    return User.objects.create_user(username="ibcmd_cli_user", password="pass")


@pytest.fixture
def staff_user():
    u = User.objects.create_user(username="ibcmd_cli_staff", password="pass")
    u.is_staff = True
    u.save(update_fields=["is_staff"])
    return u


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def staff_client(staff_user):
    c = APIClient()
    c.force_authenticate(user=staff_user)
    return c


@pytest.fixture
def auth_db():
    return Database.objects.create(
        name="auth_db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )


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


def _allow_operate(user, database: Database, *, level: int = PermissionLevel.OPERATE):
    DatabasePermission.objects.create(user=user, database=database, level=level)


@pytest.mark.django_db
def test_execute_ibcmd_cli_requires_authentication():
    anon = APIClient()
    resp = anon.post("/api/v2/operations/execute-ibcmd-cli/", {}, format="json")
    assert resp.status_code in [401, 403]


@pytest.mark.django_db
def test_execute_ibcmd_cli_unknown_command_returns_400(client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {},
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "unknown.command", "database_ids": []},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_COMMAND"


@pytest.mark.django_db
def test_execute_ibcmd_cli_safe_requires_capability(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _allow_operate(user, auth_db)
    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
        },
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dangerous_requires_confirm(staff_client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "server.config.drop", "auth_database_id": str(uuid.uuid4())},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DANGEROUS_CONFIRM_REQUIRED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dangerous_hidden_for_non_staff(client, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {"command_id": "server.config.drop", "auth_database_id": str(uuid.uuid4()), "confirm_dangerous": True},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_COMMAND"

@pytest.mark.django_db
def test_execute_ibcmd_cli_per_database_success_creates_tasks(client, user, target_dbs, monkeypatch):
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
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        _allow_operate(user, db)

    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [db.id for db in target_dbs],
            "connection": {"remote": "http://host:1545"},
        },
        format="json",
    )
    assert resp.status_code == 202
    payload = resp.json()
    op_id = payload["operation_id"]

    op = BatchOperation.objects.get(id=op_id)
    assert op.operation_type == BatchOperation.TYPE_IBCMD_CLI
    assert op.total_tasks == len(target_dbs)
    assert op.target_databases.count() == len(target_dbs)

    tasks = list(Task.objects.filter(batch_operation=op))
    assert len(tasks) == len(target_dbs)
    assert all(task.database_id for task in tasks)

    data = op.payload.get("data", {})
    assert data.get("command_id") == "infobase.extension.list"
    assert data.get("argv")
    assert data.get("argv_masked")
    assert all("--user" not in token.lower() for token in data["argv"])
    assert all("--password" not in token.lower() for token in data["argv"])


@pytest.mark.django_db
def test_execute_ibcmd_cli_allows_connection_remote_when_command_has_no_params_schema(client, user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(user, target_db)

    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://localhost:1545"},
        },
        format="json",
    )
    assert resp.status_code == 202
    op_id = resp.json()["operation_id"]

    op = BatchOperation.objects.get(id=op_id)
    argv = op.payload.get("data", {}).get("argv", [])
    assert "--remote=http://localhost:1545" in argv


@pytest.mark.django_db
def test_execute_ibcmd_cli_allows_connection_offline_params_when_command_has_no_params_schema(client, user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(user, target_db)
    target_db.metadata = {"dbms": "PostgreSQL", "db_server": "localhost", "db_name": "testdb"}
    target_db.save(update_fields=["metadata"])
    DbmsUserMapping.objects.create(database=target_db, user=user, db_username="postgres", db_password="secret")

    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"offline": {"dbms": "PostgreSQL"}},
        },
        format="json",
    )
    assert resp.status_code == 202
    op_id = resp.json()["operation_id"]

    op = BatchOperation.objects.get(id=op_id)
    argv = op.payload.get("data", {}).get("argv", [])
    assert "--dbms=PostgreSQL" in argv
    assert all("--db-user" not in token.lower() for token in argv)


@pytest.mark.django_db
def test_execute_ibcmd_cli_rejects_inline_dbms_credentials(client, user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(user, target_db)

    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"offline": {"db_user": "admin"}},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DBMS_CREDS_NOT_ALLOWED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_global_success_creates_global_task(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    _allow_operate(user, auth_db)
    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
        },
        format="json",
    )
    assert resp.status_code == 202
    payload = resp.json()
    op_id = payload["operation_id"]

    op = BatchOperation.objects.get(id=op_id)
    assert op.operation_type == BatchOperation.TYPE_IBCMD_CLI
    assert op.total_tasks == 1
    assert op.target_databases.count() == 0

    tasks = list(Task.objects.filter(batch_operation=op))
    assert len(tasks) == 1
    assert tasks[0].database_id is None

    assert op.payload["options"]["target_scope"] == "global"
    assert isinstance(op.payload["options"]["target_ref"], str) and op.payload["options"]["target_ref"]
    assert op.payload["data"]["auth_database_id"] == auth_db.id


@pytest.mark.django_db
def test_execute_ibcmd_cli_global_locked_returns_409(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    _allow_operate(user, auth_db)
    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: True)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
        },
        format="json",
    )
    assert resp.status_code == 409
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "GLOBAL_TARGET_LOCKED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_pid_in_args_not_allowed(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    _allow_operate(user, auth_db)
    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
            "additional_args": ["--pid=123"],
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PID_IN_ARGS_NOT_ALLOWED"

    resp_short = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
            "additional_args": ["-p123"],
        },
        format="json",
    )
    assert resp_short.status_code == 400
    payload_short = resp_short.json()
    assert payload_short["success"] is False
    assert payload_short["error"]["code"] == "PID_IN_ARGS_NOT_ALLOWED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_remote_conflict_between_connection_and_additional_args_returns_400(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    _allow_operate(user, auth_db)
    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545"},
            "additional_args": ["--remote=http://other:1545"],
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "remote" in payload["error"]["message"].lower()


@pytest.mark.django_db
def test_execute_ibcmd_cli_pid_not_allowed_in_production(client, user, auth_db, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
                    "pid": {"kind": "flag", "flag": "--pid", "expects_value": True, "required": False},
                },
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    _allow_operate(user, auth_db)
    monkeypatch.setenv("APP_ENV", "production")

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "server.config.init",
            "database_ids": [],
            "auth_database_id": auth_db.id,
            "connection": {"remote": "http://host:1545", "pid": 123},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PID_NOT_ALLOWED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_rejects_request_db_pwd_in_guided(client, user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(user, target_db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "additional_args": ["-W"],
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "REQUEST_DB_PWD_NOT_ALLOWED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_service_requires_permission(client, user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(user, target_db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "ib_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_service_allowed_for_staff_on_allowlist(staff_client, staff_user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(staff_client, staff_user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(staff_user, target_db)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "ib_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 202
    op = BatchOperation.objects.get(id=resp.json()["operation_id"])
    assert op.payload["data"]["ib_auth"]["strategy"] == "service"


@pytest.mark.django_db
def test_execute_ibcmd_cli_service_rejected_for_non_allowlist(staff_client, staff_user, target_dbs, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.dump": {
                "label": "dump",
                "description": "Dump",
                "argv": ["infobase", "dump"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(staff_client, staff_user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(staff_user, target_db)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.dump",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "ib_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "IB_AUTH_SERVICE_NOT_ALLOWED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dbms_service_requires_permission(client, user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(user, target_db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "dbms_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dbms_service_allowed_for_staff_on_allowlist(staff_client, staff_user, target_dbs, monkeypatch):
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
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(staff_client, staff_user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(staff_user, target_db)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "dbms_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 202
    op = BatchOperation.objects.get(id=resp.json()["operation_id"])
    assert op.payload["data"]["dbms_auth"]["strategy"] == "service"


@pytest.mark.django_db
def test_execute_ibcmd_cli_dbms_service_rejected_for_non_allowlist(staff_client, staff_user, target_dbs, monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "infobase.dump": {
                "label": "dump",
                "description": "Dump",
                "argv": ["infobase", "dump"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    _grant_operation_permission(staff_client, staff_user, "execute_safe_operation")
    target_db = target_dbs[0]
    _allow_operate(staff_user, target_db)

    resp = staff_client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.dump",
            "database_ids": [target_db.id],
            "connection": {"remote": "http://host:1545"},
            "dbms_auth": {"strategy": "service"},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DBMS_AUTH_SERVICE_NOT_ALLOWED"

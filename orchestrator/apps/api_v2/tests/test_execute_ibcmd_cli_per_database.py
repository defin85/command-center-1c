# ruff: noqa: F811
import pytest

from apps.databases.models import DbmsUserMapping
from apps.operations.models import BatchOperation, Task
from apps.operations.redis_client import redis_client
from apps.operations.services import EnqueueResult, OperationsService

from . import _execute_ibcmd_cli_support as support
from ._execute_ibcmd_cli_support import client, target_dbs, user  # noqa: F401


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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)

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
def test_execute_ibcmd_cli_returns_503_on_redis_enqueue_failure(client, user, target_dbs, monkeypatch):
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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)

    monkeypatch.setattr(redis_client, "check_global_target_lock", lambda _target_ref: False)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        return EnqueueResult(
            success=False,
            operation_id=_operation_id,
            status="error",
            error="redis down",
            error_code="REDIS_ERROR",
        )

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
    assert resp.status_code == 503
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "REDIS_ERROR"


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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(user, target_db)

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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(user, target_db)
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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(user, target_db)

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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    target_db = target_dbs[0]
    support._allow_operate(user, target_db)

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

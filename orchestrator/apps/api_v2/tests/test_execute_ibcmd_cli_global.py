# ruff: noqa: F811
import pytest

from apps.operations.models import BatchOperation, Task
from apps.operations.redis_client import redis_client
from apps.operations.services import EnqueueResult, OperationsService

from . import _execute_ibcmd_cli_support as support
from ._execute_ibcmd_cli_support import auth_db, client, user  # noqa: F401


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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    support._allow_operate(user, auth_db)
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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    support._allow_operate(user, auth_db)
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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    support._allow_operate(user, auth_db)
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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    support._allow_operate(user, auth_db)
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
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    support._allow_operate(user, auth_db)
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

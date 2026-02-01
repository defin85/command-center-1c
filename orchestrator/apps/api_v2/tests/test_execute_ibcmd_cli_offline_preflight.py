# ruff: noqa: F811
import pytest

from apps.databases.models import DbmsUserMapping
from apps.operations.models import BatchOperation
from apps.operations.services import EnqueueResult, OperationsService

from . import _execute_ibcmd_cli_support as support
from ._execute_ibcmd_cli_support import client, target_dbs, user  # noqa: F401


def _seed_simple_per_db_catalog(monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "test.offline.preflight": {
                "label": "test offline preflight",
                "description": "test",
                "argv": ["infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    support._seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)


def _configure_dbms_mapping(user, dbs):
    for db in dbs:
        DbmsUserMapping.objects.create(
            database=db,
            user=user,
            db_username="db_user",
            db_password="db_pwd",
        )


@pytest.mark.django_db
def test_execute_ibcmd_cli_offline_preflight_fails_when_dbms_metadata_missing(client, user, target_dbs, monkeypatch):
    _seed_simple_per_db_catalog(monkeypatch)
    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)
    _configure_dbms_mapping(user, target_dbs)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "test.offline.preflight",
            "database_ids": [db.id for db in target_dbs],
            "connection": {},
            "dbms_auth": {"strategy": "actor"},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "OFFLINE_DB_METADATA_NOT_CONFIGURED"
    details = payload["error"]["details"]
    assert isinstance(details.get("missing"), list)
    assert details.get("missing_total") == len(target_dbs)
    for item in details["missing"]:
        assert set(item["missing_keys"]) == {"dbms", "db_server", "db_name"}


@pytest.mark.django_db
def test_execute_ibcmd_cli_offline_preflight_allows_request_level_dbms_and_per_target_db_name(client, user, target_dbs, monkeypatch):
    _seed_simple_per_db_catalog(monkeypatch)
    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)
        db.metadata = {"db_name": f"name_{db.id}"}
        db.save(update_fields=["metadata", "updated_at"])
    _configure_dbms_mapping(user, target_dbs)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "test.offline.preflight",
            "database_ids": [db.id for db in target_dbs],
            "connection": {"offline": {"dbms": "PostgreSQL", "db_server": "db.example.local"}},
            "dbms_auth": {"strategy": "actor"},
        },
        format="json",
    )
    assert resp.status_code == 202


@pytest.mark.django_db
def test_execute_ibcmd_cli_offline_preflight_allows_request_level_db_name_override(client, user, target_dbs, monkeypatch):
    _seed_simple_per_db_catalog(monkeypatch)
    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)
        db.metadata = {"dbms": "PostgreSQL", "db_server": "db.example.local"}
        db.save(update_fields=["metadata", "updated_at"])
    _configure_dbms_mapping(user, target_dbs)

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "test.offline.preflight",
            "database_ids": [db.id for db in target_dbs],
            "connection": {"offline": {"db_name": "common_db_name"}},
            "dbms_auth": {"strategy": "actor"},
        },
        format="json",
    )
    assert resp.status_code == 202


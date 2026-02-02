# ruff: noqa: F811
import pytest

from apps.databases.models import DbmsUserMapping
from apps.operations.models import BatchOperation, Task
from apps.operations.services import EnqueueResult, OperationsService

from . import _execute_ibcmd_cli_support as support
from ._execute_ibcmd_cli_support import client, target_dbs, user  # noqa: F401


def _seed_minimal_per_database_catalog(monkeypatch):
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


@pytest.mark.django_db
def test_execute_ibcmd_cli_per_database_derived_rejects_missing_profile(client, user, target_dbs, monkeypatch):
    _seed_minimal_per_database_catalog(monkeypatch)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)

    good = target_dbs[0]
    bad = target_dbs[1]
    good.metadata = {"ibcmd_connection": {"mode": "remote", "remote_url": "http://host:1545"}}
    good.save(update_fields=["metadata"])
    bad.metadata = {}
    bad.save(update_fields=["metadata"])

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [db.id for db in target_dbs],
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "IBCMD_CONNECTION_PROFILE_INVALID"
    assert payload["error"]["details"]["missing_total"] == 1
    assert payload["error"]["details"]["missing"][0]["database_id"] == str(bad.id)


@pytest.mark.django_db
def test_execute_ibcmd_cli_per_database_derived_allows_mixed_remote_and_offline(client, user, target_dbs, monkeypatch):
    _seed_minimal_per_database_catalog(monkeypatch)

    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)

    remote_db = target_dbs[0]
    offline_db = target_dbs[1]

    remote_db.metadata = {"ibcmd_connection": {"mode": "remote", "remote_url": "http://host:1545"}}
    remote_db.save(update_fields=["metadata"])

    offline_db.metadata = {
        "ibcmd_connection": {
            "mode": "offline",
            "offline": {"config": "/opt/1c/offline/config", "data": "/opt/1c/offline/data"},
        },
        "dbms": "PostgreSQL",
        "db_server": "localhost",
        "db_name": "testdb",
    }
    offline_db.save(update_fields=["metadata"])
    DbmsUserMapping.objects.create(database=offline_db, user=user, db_username="postgres", db_password="secret")

    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "infobase.extension.list",
            "database_ids": [db.id for db in target_dbs],
        },
        format="json",
    )
    assert resp.status_code == 202
    op_id = resp.json()["operation_id"]

    op = BatchOperation.objects.get(id=op_id)
    assert op.total_tasks == len(target_dbs)
    assert op.payload.get("data", {}).get("connection_source") == "database_profile"

    tasks = list(Task.objects.filter(batch_operation=op))
    assert len(tasks) == len(target_dbs)

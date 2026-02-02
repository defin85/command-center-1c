# ruff: noqa: F811
import pytest

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


def _fake_enqueue(monkeypatch):
    def fake_enqueue(_operation_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=_operation_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=_operation_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", fake_enqueue)


@pytest.mark.django_db
def test_execute_ibcmd_cli_per_database_allows_derived_when_connection_omitted(client, user, target_dbs, monkeypatch):
    _seed_simple_per_db_catalog(monkeypatch)
    _fake_enqueue(monkeypatch)
    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)
        db.metadata = {"ibcmd_connection": {"remote": "ssh://host:1545"}}
        db.save(update_fields=["metadata"])

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "test.offline.preflight",
            "database_ids": [db.id for db in target_dbs],
        },
        format="json",
    )
    assert resp.status_code == 202
    op_id = resp.json()["operation_id"]
    op = BatchOperation.objects.get(id=op_id)
    assert op.payload.get("data", {}).get("connection_source") == "database_profile"


@pytest.mark.django_db
def test_execute_ibcmd_cli_requires_non_empty_connection_object_when_connection_provided(client, user, target_dbs, monkeypatch):
    _seed_simple_per_db_catalog(monkeypatch)
    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "test.offline.preflight",
            "database_ids": [db.id for db in target_dbs],
            "connection": {},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "MISSING_CONNECTION"


@pytest.mark.django_db
def test_execute_ibcmd_cli_explicit_offline_connection_does_not_preflight_dbms_metadata(client, user, target_dbs, monkeypatch):
    _seed_simple_per_db_catalog(monkeypatch)
    _fake_enqueue(monkeypatch)
    support._grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        support._allow_operate(user, db)

    resp = client.post(
        "/api/v2/operations/execute-ibcmd-cli/",
        {
            "command_id": "test.offline.preflight",
            "database_ids": [db.id for db in target_dbs],
            "connection": {"offline": {"config": "/tmp/config"}},
            "dbms_auth": {"strategy": "actor"},
        },
        format="json",
    )
    assert resp.status_code == 202


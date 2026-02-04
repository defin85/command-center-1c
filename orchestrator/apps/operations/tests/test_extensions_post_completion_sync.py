# ruff: noqa: F811
import pytest

from apps.databases.models import Database
from apps.operations.event_subscriber.handlers_worker import WorkerEventHandlersMixin
from apps.operations.models import BatchOperation, Task
from apps.operations.services.operations_service import OperationsService
from apps.operations.services.operations_service.types import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.tenancy.models import Tenant

from apps.api_v2.tests import _execute_ibcmd_cli_support as support


@pytest.mark.django_db
def test_post_completion_extensions_sync_enqueues_follow_up(monkeypatch):
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
    support._seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )

    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    db = Database.objects.create(
        tenant=tenant,
        name="db_post_completion",
        host="localhost",
        port=80,
        base_name="db_post_completion",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "SyncAction",
                            "capability": "extensions.sync",
                            "label": "Sync",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                    ]
                },
            }
        },
    )

    def _fake_enqueue(op_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=op_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=op_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", _fake_enqueue)

    original = BatchOperation.objects.create(
        id="op-original",
        name="set_flags",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_COMPLETED,
        payload={},
        total_tasks=1,
        completed_tasks=1,
        failed_tasks=0,
        created_by="test",
        metadata={
            "post_completion_extensions_sync": True,
            "post_completion_extensions_sync_database_ids": [db.id],
        },
    )
    original.target_databases.set([db])
    Task.objects.create(id="op-original-task", batch_operation=original, database=db, status=Task.STATUS_COMPLETED)

    handler = WorkerEventHandlersMixin()
    handler._enqueue_post_completion_extensions_sync(original, [{"database_id": db.id, "success": True}])

    follow_ups = BatchOperation.objects.filter(metadata__triggered_by_operation_id="op-original")
    assert follow_ups.count() == 1
    follow = follow_ups.first()
    assert follow is not None
    assert (follow.metadata or {}).get("action_capability") == "extensions.sync"
    assert (follow.metadata or {}).get("snapshot_kinds") == ["extensions"]
    assert follow.total_tasks == 1
    assert follow.target_databases.count() == 1
    assert Task.objects.filter(batch_operation=follow).count() == 1
    payload = follow.payload or {}
    argv = ((payload.get("data") or {}).get("argv")) if isinstance(payload.get("data"), dict) else None
    assert isinstance(argv, list)
    assert argv[:2] == ["infobase", "extension"]


@pytest.mark.django_db
def test_post_completion_extensions_sync_uses_executor_from_metadata_when_catalog_missing(monkeypatch):
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
    support._seed_ibcmd_catalog(
        monkeypatch,
        base_catalog=base_catalog,
        overrides_catalog={"catalog_version": 2, "driver": "ibcmd", "overrides": {}},
    )

    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    db = Database.objects.create(
        tenant=tenant,
        name="db_post_completion_meta",
        host="localhost",
        port=80,
        base_name="db_post_completion_meta",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    # Ensure catalog is missing (or invalid) for this test.
    RuntimeSetting.objects.filter(key="ui.action_catalog").delete()

    def _fake_enqueue(op_id: str) -> EnqueueResult:
        BatchOperation.objects.filter(id=op_id).update(status=BatchOperation.STATUS_QUEUED)
        return EnqueueResult(success=True, operation_id=op_id, status="queued")

    monkeypatch.setattr(OperationsService, "enqueue_operation", _fake_enqueue)

    original = BatchOperation.objects.create(
        id="op-original-meta",
        name="set_flags",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase",
        status=BatchOperation.STATUS_COMPLETED,
        payload={},
        total_tasks=1,
        completed_tasks=1,
        failed_tasks=0,
        created_by="test",
        metadata={
            "post_completion_extensions_sync": True,
            "post_completion_extensions_sync_database_ids": [db.id],
            "post_completion_extensions_sync_executor": {
                "kind": "ibcmd_cli",
                "driver": "ibcmd",
                "command_id": "infobase.extension.list",
            },
        },
    )
    original.target_databases.set([db])
    Task.objects.create(id="op-original-meta-task", batch_operation=original, database=db, status=Task.STATUS_COMPLETED)

    handler = WorkerEventHandlersMixin()
    handler._enqueue_post_completion_extensions_sync(original, [{"database_id": db.id, "success": True}])

    follow_ups = BatchOperation.objects.filter(metadata__triggered_by_operation_id="op-original-meta")
    assert follow_ups.count() == 1

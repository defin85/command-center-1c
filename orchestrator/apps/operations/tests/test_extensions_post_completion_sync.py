# ruff: noqa: F811
import pytest

from apps.databases.models import Database
from apps.operations.event_subscriber.handlers_worker import WorkerEventHandlersMixin
from apps.operations.models import BatchOperation, Task
from apps.operations.services.operations_service import OperationsService
from apps.operations.services.operations_service.types import EnqueueResult
from apps.tenancy.models import Tenant
from apps.templates.models import OperationExposure
from apps.templates.operation_catalog_service import resolve_definition, resolve_exposure

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

    definition, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="ibcmd_cli",
        executor_payload={
            "kind": "ibcmd_cli",
            "driver": "ibcmd",
            "command_id": "infobase.extension.list",
        },
        contract_version=1,
    )
    resolve_exposure(
        definition=definition,
        surface=OperationExposure.SURFACE_ACTION_CATALOG,
        alias="SyncAction",
        tenant_id=None,
        label="Sync",
        description="",
        is_active=True,
        capability="extensions.sync",
        contexts=["bulk_page"],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
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

    # Keep catalog missing in unified store for this test.

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

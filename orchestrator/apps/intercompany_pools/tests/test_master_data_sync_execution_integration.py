from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.master_data_sync_dispatcher import (
    MasterDataSyncTransportError,
    dispatch_pending_master_data_sync_outbox as real_dispatch_pending_master_data_sync_outbox,
)
from apps.intercompany_pools.master_data_sync_execution import (
    LegacyInboundRouteDisabledError,
    configure_pool_master_data_sync_inbound_callbacks,
    execute_pool_master_data_sync_dispatch_step,
    execute_pool_master_data_sync_finalize_step,
    execute_pool_master_data_sync_inbound_step,
    reset_pool_master_data_sync_inbound_callbacks,
    run_pool_master_data_sync_legacy_inbound_route,
    trigger_pool_master_data_inbound_sync_job,
    trigger_pool_master_data_outbound_sync_job,
)
from apps.intercompany_pools.master_data_sync_inbound_poller import (
    MasterDataSyncInboundChange,
    MasterDataSyncSelectChangesResult,
)
from apps.intercompany_pools.master_data_sync_launch_execution import (
    execute_pool_master_data_sync_launch_step,
)
from apps.intercompany_pools.master_data_sync_launch_service import (
    create_pool_master_data_sync_launch_request,
    get_pool_master_data_sync_launch_request,
)
from apps.intercompany_pools.master_data_sync_launch_workflow_contract import (
    build_master_data_sync_launch_workflow_input_context,
)
from apps.intercompany_pools.master_data_sync_outbox import (
    build_master_data_mutation_payload_fingerprint,
    enqueue_master_data_sync_outbox_intent,
)
from apps.intercompany_pools.models import (
    PoolMasterContract,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncLaunchItemStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterDataSyncPolicy,
    PoolMasterDataSyncScope,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
)
from apps.operations.services import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-e2e-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_service_mapping(*, database: Database, username: str = "svc-user", password: str = "svc-pass") -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=username,
        ib_password=password,
        is_service=True,
    )


def _set_runtime_settings() -> None:
    RuntimeSetting.objects.create(key="pools.master_data.sync.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.inbound.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.outbound.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.default_policy", value="cc_master")
    RuntimeSetting.objects.create(key="pools.master_data.sync.dispatch_batch_size", value=100)
    RuntimeSetting.objects.create(key="pools.master_data.sync.max_retry_backoff_seconds", value=900)


def _build_input_context(
    *,
    sync_job: PoolMasterDataSyncJob,
    origin_system: str = "cc",
    origin_event_id: str = "evt-sync-e2e",
    correlation_id: str = "corr-sync-e2e",
) -> dict[str, str]:
    return {
        "contract_version": "pool_master_data_sync_workflow.v1",
        "sync_job_id": str(sync_job.id),
        "tenant_id": str(sync_job.tenant_id),
        "database_id": str(sync_job.database_id),
        "entity_type": str(sync_job.entity_type),
        "sync_policy": str(sync_job.policy),
        "sync_direction": str(sync_job.direction),
        "correlation_id": str(correlation_id),
        "origin_system": str(origin_system),
        "origin_event_id": str(origin_event_id),
    }


@pytest.mark.django_db
def test_outbound_sync_path_supports_retry_recovery_and_finalize() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-retry-{uuid4().hex[:6]}", name="Sync E2E Retry")
    database = _create_database(tenant=tenant, suffix="retry")
    _set_runtime_settings()
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    outbox_row = enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-retry-001",
        mutation_kind="item_upsert",
        payload={"canonical_id": "item-retry-001", "name": "Retry Item"},
        origin_system="cc",
        origin_event_id="evt-retry-001",
    )

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        side_effect=_enqueue,
    ):
        trigger_result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-retry-001",
            origin_system="cc",
            origin_event_id="evt-retry-001",
        )
    assert trigger_result.sync_job is not None
    sync_job = trigger_result.sync_job

    dispatch_attempt = {"count": 0}

    def _dispatch_with_retry(**kwargs):
        dispatch_attempt["count"] += 1

        def _transport_apply(_outbox):
            if dispatch_attempt["count"] == 1:
                raise MasterDataSyncTransportError(
                    code="IB_TRANSPORT_DOWN",
                    detail="temporary outage",
                )
            return {"status": "ok"}

        return real_dispatch_pending_master_data_sync_outbox(
            transport_apply=_transport_apply,
            **kwargs,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.dispatch_pending_master_data_sync_outbox",
        side_effect=_dispatch_with_retry,
    ):
        first = execute_pool_master_data_sync_dispatch_step(input_context=_build_input_context(sync_job=sync_job))
        assert first["dispatch"]["failed"] == 1

        outbox_row.refresh_from_db()
        assert outbox_row.status == PoolMasterDataSyncOutboxStatus.FAILED
        assert outbox_row.last_error_code == "IB_TRANSPORT_DOWN"
        outbox_row.available_at = timezone.now() - timedelta(seconds=1)
        outbox_row.save(update_fields=["available_at", "updated_at"])

        second = execute_pool_master_data_sync_dispatch_step(input_context=_build_input_context(sync_job=sync_job))
        assert second["dispatch"]["sent"] == 1

    outbox_row.refresh_from_db()
    assert outbox_row.status == PoolMasterDataSyncOutboxStatus.SENT
    assert outbox_row.attempt_count == 2
    assert dispatch_attempt["count"] == 2

    finalize_output = execute_pool_master_data_sync_finalize_step(
        input_context=_build_input_context(sync_job=sync_job)
    )
    sync_job.refresh_from_db()
    assert finalize_output["status"] == PoolMasterDataSyncJobStatus.SUCCEEDED
    assert sync_job.status == PoolMasterDataSyncJobStatus.SUCCEEDED
    assert sync_job.attempt_count == 2


@pytest.mark.django_db
def test_outbound_sync_path_preserves_dedupe_without_duplicate_side_effects() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-dedupe-{uuid4().hex[:6]}", name="Sync E2E Dedupe")
    database = _create_database(tenant=tenant, suffix="dedupe")
    _set_runtime_settings()
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    payload = {"canonical_id": "item-dedupe-001", "ib_ref_key": "ref-item-dedupe-001"}
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    binding = PoolMasterDataBinding.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-dedupe-001",
        database=database,
        ib_ref_key="ref-item-dedupe-001",
        sync_status="resolved",
        fingerprint=payload_fingerprint,
        metadata={},
    )
    enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-dedupe-001",
        mutation_kind="binding_upsert",
        payload=payload,
        origin_system="cc",
        origin_event_id="evt-dedupe-001",
    )

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        side_effect=_enqueue,
    ):
        trigger_result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-dedupe-001",
            origin_system="cc",
            origin_event_id="evt-dedupe-001",
        )
    assert trigger_result.sync_job is not None

    ib_apply_calls = {"count": 0}

    def _dispatch_with_ib_apply(**kwargs):
        def _ib_apply(_outbox):
            ib_apply_calls["count"] += 1
            return {"status": "applied"}

        return real_dispatch_pending_master_data_sync_outbox(
            ib_apply=_ib_apply,
            **kwargs,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.dispatch_pending_master_data_sync_outbox",
        side_effect=_dispatch_with_ib_apply,
    ):
        result = execute_pool_master_data_sync_dispatch_step(
            input_context=_build_input_context(sync_job=trigger_result.sync_job)
        )

    assert result["dispatch"]["sent"] == 1
    assert ib_apply_calls["count"] == 0

    outbox_row = PoolMasterDataSyncOutbox.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
    )
    assert outbox_row.status == PoolMasterDataSyncOutboxStatus.SENT
    binding.refresh_from_db()
    assert binding.metadata["sync_audit"][-1]["event"] == "idempotent_skip"


@pytest.mark.django_db(transaction=True)
def test_sync_runtime_moves_item_from_source_ib_to_cc_and_then_to_target_ib() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-item-bridge-{uuid4().hex[:6]}", name="Sync E2E Item Bridge")
    source_database = _create_database(tenant=tenant, suffix="source")
    target_database = _create_database(tenant=tenant, suffix="target")
    _set_runtime_settings()
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=source_database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=target_database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )

    source_odata_catalog = {
        "Catalog_Номенклатура": [
            {
                "Ref_Key": "ib-a-item-001",
                "Description": "Imported OData Item",
                "Артикул": "SKU-ODATA-001",
                "ЕдиницаИзмерения": "pcs",
            }
        ]
    }
    target_odata_catalog: dict[str, list[dict[str, str]]] = {
        "Catalog_Номенклатура": [],
    }
    inbound_ack_calls: list[dict[str, str]] = []

    def _select_changes(*, database_id: str, checkpoint_token: str, **kwargs):
        assert database_id == str(source_database.id)
        source_row = source_odata_catalog["Catalog_Номенклатура"][0]
        return MasterDataSyncSelectChangesResult(
            changes=[
                MasterDataSyncInboundChange(
                    origin_system="ib",
                    origin_event_id="evt-odata-item-001",
                    canonical_id="item-odata-001",
                    entity_type=PoolMasterDataEntityType.ITEM,
                    payload={
                        "name": source_row["Description"],
                        "sku": source_row["Артикул"],
                        "unit": source_row["ЕдиницаИзмерения"],
                        "source_ref": source_row["Ref_Key"],
                    },
                    payload_fingerprint="fp-odata-item-001",
                )
            ],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-odata-item-001",
        )

    def _notify_changes_received(*, checkpoint_token: str, next_checkpoint_token: str, **kwargs):
        inbound_ack_calls.append(
            {
                "checkpoint_token": checkpoint_token,
                "next_checkpoint_token": next_checkpoint_token,
            }
        )

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    configure_pool_master_data_sync_inbound_callbacks(
        select_changes=_select_changes,
        apply_change=None,
        notify_changes_received=_notify_changes_received,
    )
    try:
        with patch(
            "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
            side_effect=_enqueue,
        ), patch(
            "apps.intercompany_pools.master_data_sync_launch_workflow_runtime.OperationsService.enqueue_workflow_execution",
            side_effect=_enqueue,
        ):
            inbound_trigger = trigger_pool_master_data_inbound_sync_job(
                tenant_id=str(tenant.id),
                database_id=str(source_database.id),
                entity_type=PoolMasterDataEntityType.ITEM,
                origin_system="ib",
                origin_event_id="evt-odata-item-001",
                correlation_id="corr-odata-item-001",
            )
            assert inbound_trigger.sync_job is not None
            inbound_job = inbound_trigger.sync_job

            inbound_output = execute_pool_master_data_sync_inbound_step(
                input_context=_build_input_context(
                    sync_job=inbound_job,
                    origin_system="ib",
                    origin_event_id="evt-odata-item-001",
                    correlation_id="corr-odata-item-001",
                )
            )
            assert inbound_output["inbound"]["applied"] == 1
            execute_pool_master_data_sync_finalize_step(
                input_context=_build_input_context(
                    sync_job=inbound_job,
                    origin_system="ib",
                    origin_event_id="evt-odata-item-001",
                    correlation_id="corr-odata-item-001",
                )
            )

            imported_item = PoolMasterItem.objects.get(
                tenant=tenant,
                canonical_id="item-odata-001",
            )
            assert imported_item.name == "Imported OData Item"
            assert imported_item.sku == "SKU-ODATA-001"
            assert inbound_ack_calls == [
                {
                    "checkpoint_token": "",
                    "next_checkpoint_token": "cp-odata-item-001",
                }
            ]

            launch_request = create_pool_master_data_sync_launch_request(
                tenant=tenant,
                mode="outbound",
                target_mode="database_set",
                cluster_id=None,
                database_ids=[str(target_database.id)],
                entity_scope=[PoolMasterDataEntityType.ITEM],
                actor_id="",
                actor_username="sync-e2e",
            )

            launch_output = execute_pool_master_data_sync_launch_step(
                input_context=build_master_data_sync_launch_workflow_input_context(
                    launch_request=launch_request,
                    correlation_id=f"corr-sync-launch-{launch_request.id}",
                    origin_system="manual_sync_launch",
                    origin_event_id=f"manual-sync-launch:{launch_request.id}",
                    actor_username="sync-e2e",
                )
            )
            assert launch_output["status"] == "completed"

            refreshed_launch = get_pool_master_data_sync_launch_request(
                tenant_id=str(tenant.id),
                launch_request_id=str(launch_request.id),
            )
            launch_item = refreshed_launch.items.get()
            assert launch_item.status == PoolMasterDataSyncLaunchItemStatus.SCHEDULED
            assert launch_item.child_job is not None
            assert launch_item.metadata["manual_outbound_snapshot"] == {
                "candidates": 1,
                "prepared": 1,
                "blocked": 0,
            }

            outbound_outbox = PoolMasterDataSyncOutbox.objects.get(
                tenant=tenant,
                database=target_database,
                entity_type=PoolMasterDataEntityType.ITEM,
            )
            assert outbound_outbox.status == PoolMasterDataSyncOutboxStatus.PENDING
            assert outbound_outbox.origin_system == "manual_sync_launch"
            assert outbound_outbox.payload["canonical_id"] == str(imported_item.canonical_id)
            assert outbound_outbox.payload["payload"]["name"] == "Imported OData Item"

            def _dispatch_to_target(**kwargs):
                def _ib_apply(outbox):
                    payload = dict((outbox.payload or {}).get("payload") or {})
                    target_odata_catalog["Catalog_Номенклатура"].append(
                        {
                            "Ref_Key": f"target-{payload['canonical_id']}",
                            "Description": str(payload["name"]),
                            "Артикул": str(payload["sku"]),
                            "ЕдиницаИзмерения": str(payload["unit"]),
                        }
                    )
                    return {
                        "status": "applied",
                        "canonical_id": str(payload["canonical_id"]),
                    }

                return real_dispatch_pending_master_data_sync_outbox(
                    ib_apply=_ib_apply,
                    **kwargs,
                )

            with patch(
                "apps.intercompany_pools.master_data_sync_execution.dispatch_pending_master_data_sync_outbox",
                side_effect=_dispatch_to_target,
            ):
                dispatch_output = execute_pool_master_data_sync_dispatch_step(
                    input_context=_build_input_context(
                        sync_job=launch_item.child_job,
                        origin_system="manual_sync_launch",
                        origin_event_id=f"manual-sync-launch:{launch_request.id}",
                        correlation_id=f"corr-sync-launch:{launch_request.id}:{launch_item.id}",
                    )
                )
            assert dispatch_output["dispatch"]["sent"] == 1

            finalize_output = execute_pool_master_data_sync_finalize_step(
                input_context=_build_input_context(
                    sync_job=launch_item.child_job,
                    origin_system="manual_sync_launch",
                    origin_event_id=f"manual-sync-launch:{launch_request.id}",
                    correlation_id=f"corr-sync-launch:{launch_request.id}:{launch_item.id}",
                )
            )
            assert finalize_output["status"] == PoolMasterDataSyncJobStatus.SUCCEEDED

            refreshed_launch = get_pool_master_data_sync_launch_request(
                tenant_id=str(tenant.id),
                launch_request_id=str(launch_request.id),
            )
            assert refreshed_launch.metadata["aggregate_counters"]["completed"] == 1
            assert target_odata_catalog["Catalog_Номенклатура"] == [
                {
                    "Ref_Key": "target-item-odata-001",
                    "Description": "Imported OData Item",
                    "Артикул": "SKU-ODATA-001",
                    "ЕдиницаИзмерения": "pcs",
                }
            ]
    finally:
        reset_pool_master_data_sync_inbound_callbacks()


@pytest.mark.django_db(transaction=True)
def test_sync_runtime_moves_party_tax_profile_and_contract_from_source_ib_to_cc_and_then_to_target_ib() -> None:
    tenant = Tenant.objects.create(
        slug=f"sync-e2e-master-data-bridge-{uuid4().hex[:6]}",
        name="Sync E2E Master Data Bridge",
    )
    source_database = _create_database(tenant=tenant, suffix="source-md")
    target_database = _create_database(tenant=tenant, suffix="target-md")
    _create_service_mapping(database=source_database)
    _create_service_mapping(database=target_database)
    _set_runtime_settings()

    for database in (source_database, target_database):
        for entity_type in (
            PoolMasterDataEntityType.PARTY,
            PoolMasterDataEntityType.TAX_PROFILE,
            PoolMasterDataEntityType.CONTRACT,
        ):
            PoolMasterDataSyncScope.objects.create(
                tenant=tenant,
                database=database,
                entity_type=entity_type,
                policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            )

    source_odata_catalog: dict[str, list[dict[str, object]]] = {
        "Catalog_Контрагенты": [],
        "Catalog_ДоговорыКонтрагентов": [],
    }
    target_odata_catalog: dict[str, list[dict[str, object]]] = {
        "Catalog_Контрагенты": [],
        "Catalog_ДоговорыКонтрагентов": [],
    }

    class _FakeODataClient:
        def __init__(self, *, base_url: str, **kwargs):
            _ = kwargs
            self.catalog = source_odata_catalog if "source-md" in base_url else target_odata_catalog

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_entities(self, entity_name, filter_query=None, select_fields=None, top=None, skip=None):
            _ = (filter_query, select_fields)
            rows = self.catalog.get(entity_name, [])
            start = int(skip or 0)
            size = int(top or len(rows) or 1)
            return [dict(row) for row in rows[start : start + size]]

        def create_entity(self, entity_name, entity_data):
            if entity_name == "Catalog_Контрагенты":
                created = {
                    "Ref_Key": "target-party-001",
                    **dict(entity_data),
                }
                self.catalog[entity_name].append(created)
                return {"Ref_Key": created["Ref_Key"]}
            if entity_name == "Catalog_ДоговорыКонтрагентов":
                created = {
                    "Ref_Key": "target-contract-001",
                    **dict(entity_data),
                }
                self.catalog[entity_name].append(created)
                return {"Ref_Key": created["Ref_Key"]}
            raise AssertionError(f"unexpected create for {entity_name}")

        def update_entity(self, entity_name, entity_id, entity_data):
            raise AssertionError(f"unexpected update for {entity_name} {entity_id} {entity_data}")

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    def _run_inbound(entity_type: str, suffix: str) -> dict[str, object]:
        sync_job = PoolMasterDataSyncJob.objects.create(
            tenant=tenant,
            database=source_database,
            entity_type=entity_type,
            policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            direction="inbound",
            status=PoolMasterDataSyncJobStatus.RUNNING,
        )
        output = execute_pool_master_data_sync_inbound_step(
            input_context=_build_input_context(
                sync_job=sync_job,
                origin_system="ib",
                origin_event_id=f"evt-{entity_type}-{suffix}",
                correlation_id=f"corr-{entity_type}-{suffix}",
            )
        )
        execute_pool_master_data_sync_finalize_step(
            input_context=_build_input_context(
                sync_job=sync_job,
                origin_system="ib",
                origin_event_id=f"evt-{entity_type}-{suffix}",
                correlation_id=f"corr-{entity_type}-{suffix}",
            )
        )
        return output

    reset_pool_master_data_sync_inbound_callbacks()
    try:
        with patch(
            "apps.intercompany_pools.master_data_sync_live_odata_transport.ODataClient",
            _FakeODataClient,
        ), patch(
            "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
            side_effect=_enqueue,
        ), patch(
            "apps.intercompany_pools.master_data_sync_launch_workflow_runtime.OperationsService.enqueue_workflow_execution",
            side_effect=_enqueue,
        ):
            for entity_type in (
                PoolMasterDataEntityType.PARTY,
                PoolMasterDataEntityType.TAX_PROFILE,
                PoolMasterDataEntityType.CONTRACT,
            ):
                baseline_output = _run_inbound(entity_type, "baseline")
                assert baseline_output["inbound"]["polled"] == 0
                assert baseline_output["inbound"]["applied"] == 0

            source_odata_catalog["Catalog_Контрагенты"].append(
                {
                    "Ref_Key": "source-party-001",
                    "DataVersion": "AAAAAAAB",
                    "Code": "00001",
                    "Description": "Bridge Party",
                    "НаименованиеПолное": "Bridge Party LLC",
                    "ИНН": "7701234567",
                    "КПП": "770101001",
                    "DeletionMark": False,
                    "IsFolder": False,
                }
            )
            party_inbound = _run_inbound(PoolMasterDataEntityType.PARTY, "delta-party")
            assert party_inbound["inbound"]["polled"] == 1
            assert party_inbound["inbound"]["applied"] == 1

            source_odata_catalog["Catalog_ДоговорыКонтрагентов"].append(
                {
                    "Ref_Key": "source-contract-001",
                    "DataVersion": "AAAAAAAC",
                    "Description": "Bridge Contract",
                    "Owner_Key": "source-party-001",
                    "Номер": "BR-001",
                    "Дата": "2026-04-13T00:00:00",
                    "ВидДоговора": "СПокупателем",
                    "СтавкаНДС": "НДС20",
                    "СуммаВключаетНДС": True,
                    "DeletionMark": False,
                    "IsFolder": False,
                }
            )
            tax_inbound = _run_inbound(PoolMasterDataEntityType.TAX_PROFILE, "delta-tax")
            contract_inbound = _run_inbound(PoolMasterDataEntityType.CONTRACT, "delta-contract")
            assert tax_inbound["inbound"]["polled"] == 1
            assert tax_inbound["inbound"]["applied"] == 1
            assert contract_inbound["inbound"]["polled"] == 1
            assert contract_inbound["inbound"]["applied"] == 1

            party = PoolMasterParty.objects.get(
                tenant=tenant,
                canonical_id="party:source-party-001",
            )
            tax_profile = PoolMasterTaxProfile.objects.get(
                tenant=tenant,
                canonical_id="vat20",
            )
            contract = PoolMasterContract.objects.get(
                tenant=tenant,
                canonical_id="contract:source-contract-001",
            )
            assert contract.owner_counterparty_id == party.id
            assert party.metadata["ib_ref_keys"][str(source_database.id)]["counterparty"] == "source-party-001"
            assert tax_profile.metadata["ib_ref_keys"][str(source_database.id)] == "НДС20"
            assert contract.metadata["ib_ref_keys"][str(source_database.id)]["party:source-party-001"] == "source-contract-001"

            launch_request = create_pool_master_data_sync_launch_request(
                tenant=tenant,
                mode="outbound",
                target_mode="database_set",
                cluster_id=None,
                database_ids=[str(target_database.id)],
                entity_scope=[
                    PoolMasterDataEntityType.PARTY,
                    PoolMasterDataEntityType.TAX_PROFILE,
                    PoolMasterDataEntityType.CONTRACT,
                ],
                actor_id="",
                actor_username="sync-e2e",
            )

            launch_output = execute_pool_master_data_sync_launch_step(
                input_context=build_master_data_sync_launch_workflow_input_context(
                    launch_request=launch_request,
                    correlation_id=f"corr-sync-launch-{launch_request.id}",
                    origin_system="manual_sync_launch",
                    origin_event_id=f"manual-sync-launch:{launch_request.id}",
                    actor_username="sync-e2e",
                )
            )
            assert launch_output["status"] == "completed"

            refreshed_launch = get_pool_master_data_sync_launch_request(
                tenant_id=str(tenant.id),
                launch_request_id=str(launch_request.id),
            )
            launch_items = sorted(
                list(refreshed_launch.items.select_related("child_job").all()),
                key=lambda item: {
                    PoolMasterDataEntityType.PARTY: 0,
                    PoolMasterDataEntityType.TAX_PROFILE: 1,
                    PoolMasterDataEntityType.CONTRACT: 2,
                }[str(item.entity_type)],
            )
            assert [item.status for item in launch_items] == [
                PoolMasterDataSyncLaunchItemStatus.SCHEDULED,
                PoolMasterDataSyncLaunchItemStatus.SCHEDULED,
                PoolMasterDataSyncLaunchItemStatus.SCHEDULED,
            ]

            for launch_item in launch_items:
                dispatch_output = execute_pool_master_data_sync_dispatch_step(
                    input_context=_build_input_context(
                        sync_job=launch_item.child_job,
                        origin_system="manual_sync_launch",
                        origin_event_id=f"manual-sync-launch:{launch_request.id}",
                        correlation_id=f"corr-sync-launch:{launch_request.id}:{launch_item.id}",
                    )
                )
                assert dispatch_output["dispatch"]["sent"] == 1
                finalize_output = execute_pool_master_data_sync_finalize_step(
                    input_context=_build_input_context(
                        sync_job=launch_item.child_job,
                        origin_system="manual_sync_launch",
                        origin_event_id=f"manual-sync-launch:{launch_request.id}",
                        correlation_id=f"corr-sync-launch:{launch_request.id}:{launch_item.id}",
                    )
                )
                assert finalize_output["status"] == PoolMasterDataSyncJobStatus.SUCCEEDED

            refreshed_launch = get_pool_master_data_sync_launch_request(
                tenant_id=str(tenant.id),
                launch_request_id=str(launch_request.id),
            )
            assert refreshed_launch.metadata["aggregate_counters"]["completed"] == 3
            assert target_odata_catalog["Catalog_Контрагенты"] == [
                {
                    "Ref_Key": "target-party-001",
                    "Description": "Bridge Party",
                    "НаименованиеПолное": "Bridge Party LLC",
                    "Parent_Key": "00000000-0000-0000-0000-000000000000",
                    "IsFolder": False,
                    "DeletionMark": False,
                    "ЮридическоеФизическоеЛицо": "ЮридическоеЛицо",
                    "ИНН": "7701234567",
                    "КПП": "770101001",
                }
            ]
            assert target_odata_catalog["Catalog_ДоговорыКонтрагентов"] == [
                {
                    "Ref_Key": "target-contract-001",
                    "Description": "Bridge Contract",
                    "Owner_Key": "target-party-001",
                    "Parent_Key": "00000000-0000-0000-0000-000000000000",
                    "IsFolder": False,
                    "DeletionMark": False,
                    "ВидДоговора": "СПокупателем",
                    "СуммаВключаетНДС": True,
                    "Номер": "BR-001",
                    "Дата": "2026-04-13T00:00:00",
                    "СтавкаНДС": "НДС20",
                }
            ]

            target_party_binding = PoolMasterDataBinding.objects.get(
                tenant=tenant,
                database=target_database,
                entity_type=PoolMasterDataEntityType.PARTY,
                canonical_id="party:source-party-001",
                ib_catalog_kind="counterparty",
            )
            assert target_party_binding.ib_ref_key == "target-party-001"

            target_tax_binding = PoolMasterDataBinding.objects.get(
                tenant=tenant,
                database=target_database,
                entity_type=PoolMasterDataEntityType.TAX_PROFILE,
                canonical_id="vat20",
            )
            assert target_tax_binding.ib_ref_key == "НДС20"

            target_contract_binding = PoolMasterDataBinding.objects.get(
                tenant=tenant,
                database=target_database,
                entity_type=PoolMasterDataEntityType.CONTRACT,
                canonical_id="contract:source-contract-001",
                owner_counterparty_canonical_id="party:source-party-001",
            )
            assert target_contract_binding.ib_ref_key == "target-contract-001"
    finally:
        reset_pool_master_data_sync_inbound_callbacks()


@pytest.mark.django_db
def test_legacy_inbound_route_is_fail_closed_with_machine_readable_code_and_no_side_effects() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-legacy-{uuid4().hex[:6]}", name="Sync E2E Legacy Disabled")
    database = _create_database(tenant=tenant, suffix="legacy-disabled")

    with pytest.raises(LegacyInboundRouteDisabledError) as exc_info:
        run_pool_master_data_sync_legacy_inbound_route(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
        )

    assert exc_info.value.code == "SYNC_LEGACY_INBOUND_ROUTE_DISABLED"
    assert "Use workflow runtime trigger" in exc_info.value.detail
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant, database=database).count() == 0
    assert PoolMasterDataSyncOutbox.objects.filter(tenant=tenant, database=database).count() == 0
    assert PoolMasterDataSyncCheckpoint.objects.filter(tenant=tenant, database=database).count() == 0
    assert PoolMasterDataSyncConflict.objects.filter(tenant=tenant, database=database).count() == 0

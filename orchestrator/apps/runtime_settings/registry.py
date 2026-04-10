from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class RuntimeSettingDefinition:
    key: str
    value_type: str
    default: Any
    description: str
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    env_default_setting: Optional[str] = None
    tenant_override_allowed: bool = True


RUNTIME_SETTINGS = {
    "ui.operations.max_live_streams": RuntimeSettingDefinition(
        key="ui.operations.max_live_streams",
        value_type="int",
        default=10,
        min_value=1,
        max_value=50,
        description="Maximum live SSE streams for Operations list.",
    ),
    "observability.timeline.queue_size": RuntimeSettingDefinition(
        key="observability.timeline.queue_size",
        value_type="int",
        default=10000,
        min_value=100,
        max_value=100000,
        description="Timeline recorder queue size (bounded buffer).",
    ),
    "observability.timeline.worker_count": RuntimeSettingDefinition(
        key="observability.timeline.worker_count",
        value_type="int",
        default=4,
        min_value=1,
        max_value=64,
        description="Timeline recorder worker pool size.",
    ),
    "observability.timeline.drop_on_full": RuntimeSettingDefinition(
        key="observability.timeline.drop_on_full",
        value_type="bool",
        default=True,
        description="Drop timeline events when the queue is full.",
    ),
    "observability.timeline.reset_token": RuntimeSettingDefinition(
        key="observability.timeline.reset_token",
        value_type="string",
        default="",
        description="Trigger timeline queue reset when value changes.",
    ),
    "observability.operations.max_subscriptions": RuntimeSettingDefinition(
        key="observability.operations.max_subscriptions",
        value_type="int",
        default=200,
        min_value=10,
        max_value=5000,
        description="Maximum operation subscriptions per user for multiplex SSE.",
    ),
    "observability.operations.max_mux_streams": RuntimeSettingDefinition(
        key="observability.operations.max_mux_streams",
        value_type="int",
        default=1,
        min_value=1,
        max_value=5,
        description="Maximum multiplex SSE connections per user.",
    ),
    "workflows.operation_binding.enforce_pinned": RuntimeSettingDefinition(
        key="workflows.operation_binding.enforce_pinned",
        value_type="bool",
        default=False,
        description=(
            "Require operation nodes to use operation_ref.binding_mode='pinned_exposure' "
            "on workflow create/update."
        ),
    ),
    "workflows.authoring.phase": RuntimeSettingDefinition(
        key="workflows.authoring.phase",
        value_type="string",
        default="workflow_centric_prerequisite",
        description=(
            "Controls workflow authoring rollout phase for analyst-facing pool modeling "
            "(legacy_technical_dag, workflow_centric_prerequisite, workflow_centric_active)."
        ),
    ),
    "pools.projection.publication_hardening_cutoff_utc": RuntimeSettingDefinition(
        key="pools.projection.publication_hardening_cutoff_utc",
        value_type="string",
        default="",
        description=(
            "RFC3339 UTC cutoff for staged pool projection hardening. "
            "workflow_core runs with missing publication_step_state before cutoff keep legacy terminal projection."
        ),
    ),
    "pools.master_data.gate_enabled": RuntimeSettingDefinition(
        key="pools.master_data.gate_enabled",
        value_type="bool",
        default=False,
        description=(
            "Enable pool master-data gate in workflow runtime. "
            "When disabled, pool.master_data_gate step is skipped."
        ),
        env_default_setting="POOL_RUNTIME_MASTER_DATA_GATE_ENABLED",
    ),
    "pools.master_data.sync.enabled": RuntimeSettingDefinition(
        key="pools.master_data.sync.enabled",
        value_type="bool",
        default=False,
        description=(
            "Enable pool master-data bidirectional sync runtime for inbound/outbound pipelines."
        ),
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_ENABLED",
    ),
    "pools.master_data.sync.inbound.enabled": RuntimeSettingDefinition(
        key="pools.master_data.sync.inbound.enabled",
        value_type="bool",
        default=True,
        description="Enable inbound (IB -> CC) master-data sync runtime path.",
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_INBOUND_ENABLED",
    ),
    "pools.master_data.sync.outbound.enabled": RuntimeSettingDefinition(
        key="pools.master_data.sync.outbound.enabled",
        value_type="bool",
        default=True,
        description="Enable outbound (CC -> IB) master-data sync runtime path.",
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_OUTBOUND_ENABLED",
    ),
    "pools.master_data.sync.default_policy": RuntimeSettingDefinition(
        key="pools.master_data.sync.default_policy",
        value_type="string",
        default="cc_master",
        description=(
            "Fallback policy for scope without explicit PoolMasterDataSyncScope row "
            "(allowed: cc_master, ib_master, bidirectional)."
        ),
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_DEFAULT_POLICY",
    ),
    "pools.master_data.sync.poll_interval_seconds": RuntimeSettingDefinition(
        key="pools.master_data.sync.poll_interval_seconds",
        value_type="int",
        default=30,
        min_value=1,
        max_value=3600,
        description="Inbound exchange-plan poll interval in seconds.",
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_POLL_INTERVAL_SECONDS",
    ),
    "pools.master_data.sync.dispatch_batch_size": RuntimeSettingDefinition(
        key="pools.master_data.sync.dispatch_batch_size",
        value_type="int",
        default=100,
        min_value=1,
        max_value=1000,
        description="Outbound dispatcher batch size for master-data sync intents.",
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_DISPATCH_BATCH_SIZE",
    ),
    "pools.master_data.sync.max_retry_backoff_seconds": RuntimeSettingDefinition(
        key="pools.master_data.sync.max_retry_backoff_seconds",
        value_type="int",
        default=900,
        min_value=1,
        max_value=7200,
        description="Maximum retry backoff for master-data sync outbox dispatcher.",
        env_default_setting="POOL_RUNTIME_MASTER_DATA_SYNC_MAX_RETRY_BACKOFF_SECONDS",
    ),
    "runtime.scheduler.enabled": RuntimeSettingDefinition(
        key="runtime.scheduler.enabled",
        value_type="bool",
        default=True,
        description="Global operator-facing desired state for the scheduler control plane.",
        tenant_override_allowed=False,
    ),
    "runtime.scheduler.job.pool_factual_active_sync.enabled": RuntimeSettingDefinition(
        key="runtime.scheduler.job.pool_factual_active_sync.enabled",
        value_type="bool",
        default=True,
        description="Enable scheduler launches for the pool factual active sync job.",
        tenant_override_allowed=False,
    ),
    "runtime.scheduler.job.pool_factual_closed_quarter_reconcile.enabled": RuntimeSettingDefinition(
        key="runtime.scheduler.job.pool_factual_closed_quarter_reconcile.enabled",
        value_type="bool",
        default=True,
        description="Enable scheduler launches for the pool factual closed-quarter reconcile job.",
        tenant_override_allowed=False,
    ),
}


def runtime_setting_allows_tenant_override(key: str) -> bool:
    definition = RUNTIME_SETTINGS.get(key)
    if definition is None:
        return True
    return bool(definition.tenant_override_allowed)

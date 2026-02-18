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
    "pools.projection.publication_hardening_cutoff_utc": RuntimeSettingDefinition(
        key="pools.projection.publication_hardening_cutoff_utc",
        value_type="string",
        default="",
        description=(
            "RFC3339 UTC cutoff for staged pool projection hardening. "
            "workflow_core runs with missing publication_step_state before cutoff keep legacy terminal projection."
        ),
    ),
}

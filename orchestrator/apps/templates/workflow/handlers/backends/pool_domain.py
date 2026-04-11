"""
Pool domain backend for Workflow Engine.

Routes system-managed pool runtime steps through a dedicated backend without
falling back to generic CLI/OData handlers.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Set

from apps.intercompany_pools.master_data_sync_execution import (
    execute_pool_master_data_sync_dispatch_step,
    execute_pool_master_data_sync_finalize_step,
    execute_pool_master_data_sync_inbound_step,
)
from apps.intercompany_pools.master_data_sync_launch_execution import (
    execute_pool_master_data_sync_launch_step,
)
from apps.intercompany_pools.pool_domain_steps import execute_pool_runtime_step
from apps.templates.workflow.models import WorkflowExecution

from ..base import NodeExecutionMode, NodeExecutionResult
from .base import AbstractOperationBackend


class PoolDomainBackend(AbstractOperationBackend):
    """Dedicated backend for pool runtime operation aliases."""

    SUPPORTED_TYPES: Set[str] = {
        "pool.prepare_input",
        "pool.distribution_calculation.top_down",
        "pool.distribution_calculation.bottom_up",
        "pool.reconciliation_report",
        "pool.approval_gate",
        "pool.master_data_gate",
        "pool.publication_odata",
        "pool.master_data_sync.inbound",
        "pool.master_data_sync.dispatch",
        "pool.master_data_sync.finalize",
        "pool.master_data_sync.launch",
    }

    BACKEND_NAME = "pool_domain"

    def execute(
        self,
        template: Any,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC,
    ) -> NodeExecutionResult:
        start_time = time.time()
        operation_type = str(getattr(template, "operation_type", "") or "")
        step_id = self._resolve_step_id(operation_type=operation_type, rendered_data=rendered_data)
        try:
            if operation_type == "pool.master_data_sync.inbound":
                step_output = execute_pool_master_data_sync_inbound_step(
                    input_context=execution.input_context if isinstance(execution.input_context, dict) else {},
                )
            elif operation_type == "pool.master_data_sync.dispatch":
                step_output = execute_pool_master_data_sync_dispatch_step(
                    input_context=execution.input_context if isinstance(execution.input_context, dict) else {},
                )
            elif operation_type == "pool.master_data_sync.finalize":
                step_output = execute_pool_master_data_sync_finalize_step(
                    input_context=execution.input_context if isinstance(execution.input_context, dict) else {},
                )
            elif operation_type == "pool.master_data_sync.launch":
                step_output = execute_pool_master_data_sync_launch_step(
                    input_context=execution.input_context if isinstance(execution.input_context, dict) else {},
                )
            else:
                step_output = execute_pool_runtime_step(
                    operation_type=operation_type,
                    rendered_data=rendered_data if isinstance(rendered_data, dict) else {},
                    context=context if isinstance(context, dict) else {},
                    execution=execution,
                )
        except Exception as exc:  # noqa: BLE001
            return NodeExecutionResult(
                success=False,
                output=None,
                error=str(exc),
                mode=mode,
                duration_seconds=time.time() - start_time,
                operation_id=None,
                task_id=None,
            )

        output = {
            "backend": self.BACKEND_NAME,
            "operation_type": operation_type,
            "pool_runtime_step": step_id,
            "target_databases_count": len(target_databases),
            "rendered_data": rendered_data if isinstance(rendered_data, dict) else {},
            "context_summary": {
                "pool_run_id": str(context.get("pool_run_id") or ""),
                "sync_job_id": str(
                    (
                        execution.input_context.get("sync_job_id")
                        if isinstance(getattr(execution, "input_context", None), dict)
                        else ""
                    )
                    or ""
                ),
                "approval_state": str(context.get("approval_state") or ""),
                "publication_step_state": str(context.get("publication_step_state") or ""),
            },
            "step_output": step_output if isinstance(step_output, dict) else {},
        }
        return NodeExecutionResult(
            success=True,
            output=output,
            error=None,
            mode=mode,
            duration_seconds=time.time() - start_time,
            operation_id=None,
            task_id=None,
        )

    def supports_operation_type(self, operation_type: str) -> bool:
        return operation_type in self.SUPPORTED_TYPES

    @classmethod
    def get_supported_types(cls) -> Set[str]:
        return set(cls.SUPPORTED_TYPES)

    @staticmethod
    def _resolve_step_id(*, operation_type: str, rendered_data: Dict[str, Any]) -> str:
        if not isinstance(rendered_data, dict):
            return operation_type
        runtime_data = rendered_data.get("pool_runtime")
        if isinstance(runtime_data, dict):
            step_id = str(runtime_data.get("step_id") or "").strip()
            if step_id:
                return step_id
        return operation_type

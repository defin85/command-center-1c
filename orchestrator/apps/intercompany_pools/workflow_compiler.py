from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from apps.templates.workflow.models import WorkflowCategory, WorkflowTemplate, WorkflowType

from .models import PoolRunDirection, PoolRunMode, PoolSchemaTemplate


PLAN_VERSION = 1

_OP_PREPARE_INPUT = "pool.prepare_input"
_OP_DISTRIBUTION_TOP_DOWN = "pool.distribution_calculation.top_down"
_OP_DISTRIBUTION_BOTTOM_UP = "pool.distribution_calculation.bottom_up"
_OP_RECONCILIATION = "pool.reconciliation_report"
_OP_APPROVAL_GATE = "pool.approval_gate"
_OP_PUBLICATION = "pool.publication_odata"


@dataclass(frozen=True)
class PoolWorkflowRunContext:
    pool_id: str
    period_start: date
    period_end: date | None
    direction: str
    mode: str
    run_input: dict[str, Any]


@dataclass(frozen=True)
class PoolExecutionPlanStep:
    node_id: str
    name: str
    operation_alias: str
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True)
class PoolExecutionPlan:
    plan_key: str
    plan_version: int
    template_version: str
    workflow_binding_hint: str | None
    workflow_template_name: str
    workflow_template_description: str
    workflow_type: str
    workflow_config: dict[str, Any]
    dag_structure: dict[str, Any]
    input_schema: dict[str, Any]
    steps: tuple[PoolExecutionPlanStep, ...]

    def build_workflow_template(self, *, created_by=None) -> WorkflowTemplate:
        template = WorkflowTemplate(
            name=self.workflow_template_name,
            description=self.workflow_template_description,
            workflow_type=self.workflow_type,
            dag_structure=self.dag_structure,
            config=self.workflow_config,
            is_valid=True,
            is_active=True,
            is_template=False,
            category=WorkflowCategory.SYSTEM,
            input_schema=self.input_schema,
            created_by=created_by,
        )
        template.validate()
        return template


class PoolWorkflowCompiler:
    def compile(
        self,
        *,
        schema_template: PoolSchemaTemplate,
        run_context: PoolWorkflowRunContext,
    ) -> PoolExecutionPlan:
        self._validate_context(run_context)

        template_version = self._build_template_version(schema_template)
        steps = self._build_steps(run_context)
        dag_structure = self._build_dag_structure(steps, run_context=run_context)

        plan_seed = {
            "pool_id": str(run_context.pool_id),
            "period_start": run_context.period_start.isoformat(),
            "period_end": run_context.period_end.isoformat() if run_context.period_end else None,
            "direction": run_context.direction,
            "mode": run_context.mode,
            "run_input": run_context.run_input,
            "template_version": template_version,
            "workflow_binding_hint": self._resolve_workflow_binding_hint(schema_template),
            "dag_structure": dag_structure,
        }
        plan_key = self._sha256(self._canonical_json(plan_seed))
        workflow_binding_hint = self._resolve_workflow_binding_hint(schema_template)
        workflow_name = self._build_workflow_name(run_context=run_context, plan_key=plan_key)
        workflow_description = (
            "Compiled pool execution workflow "
            f"(plan_key={plan_key}, template_version={template_version}, mode={run_context.mode})"
        )
        workflow_config = self._build_workflow_config(run_context.mode)

        return PoolExecutionPlan(
            plan_key=plan_key,
            plan_version=PLAN_VERSION,
            template_version=template_version,
            workflow_binding_hint=workflow_binding_hint,
            workflow_template_name=workflow_name,
            workflow_template_description=workflow_description,
            workflow_type=WorkflowType.SEQUENTIAL,
            workflow_config=workflow_config,
            dag_structure=dag_structure,
            input_schema=self._build_input_schema(),
            steps=tuple(steps),
        )

    @staticmethod
    def _validate_context(run_context: PoolWorkflowRunContext) -> None:
        if run_context.direction not in PoolRunDirection.values:
            raise ValueError(f"Unsupported direction '{run_context.direction}'")
        if run_context.mode not in PoolRunMode.values:
            raise ValueError(f"Unsupported mode '{run_context.mode}'")

    def _build_steps(self, run_context: PoolWorkflowRunContext) -> list[PoolExecutionPlanStep]:
        distribution_alias = (
            _OP_DISTRIBUTION_TOP_DOWN
            if run_context.direction == PoolRunDirection.TOP_DOWN
            else _OP_DISTRIBUTION_BOTTOM_UP
        )

        steps = [
            PoolExecutionPlanStep(
                node_id="prepare_input",
                name="Prepare Input",
                operation_alias=_OP_PREPARE_INPUT,
                timeout_seconds=300,
                max_retries=0,
            ),
            PoolExecutionPlanStep(
                node_id="distribution_calculation",
                name="Distribution Calculation",
                operation_alias=distribution_alias,
                timeout_seconds=900,
                max_retries=0,
            ),
            PoolExecutionPlanStep(
                node_id="reconciliation_report",
                name="Reconciliation Report",
                operation_alias=_OP_RECONCILIATION,
                timeout_seconds=300,
                max_retries=0,
            ),
        ]

        if run_context.mode == PoolRunMode.SAFE:
            steps.append(
                PoolExecutionPlanStep(
                    node_id="approval_gate",
                    name="Approval Gate",
                    operation_alias=_OP_APPROVAL_GATE,
                    timeout_seconds=3600,
                    max_retries=0,
                )
            )

        steps.append(
            PoolExecutionPlanStep(
                node_id="publication_odata",
                name="Publication OData",
                operation_alias=_OP_PUBLICATION,
                timeout_seconds=1800,
                max_retries=4,
            )
        )
        return steps

    @staticmethod
    def _build_dag_structure(
        steps: list[PoolExecutionPlanStep],
        *,
        run_context: PoolWorkflowRunContext,
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for idx, step in enumerate(steps):
            nodes.append(
                {
                    "id": step.node_id,
                    "name": step.name,
                    "type": "operation",
                    "template_id": step.operation_alias,
                    "operation_ref": {
                        "alias": step.operation_alias,
                        "binding_mode": "alias_latest",
                    },
                    "io": {
                        "mode": "implicit_legacy",
                        "input_mapping": {},
                        "output_mapping": {},
                    },
                    "config": {
                        "timeout_seconds": step.timeout_seconds,
                        "max_retries": step.max_retries,
                    },
                }
            )
            if idx > 0:
                edge: dict[str, Any] = {
                    "from": steps[idx - 1].node_id,
                    "to": step.node_id,
                }
                if (
                    run_context.mode == PoolRunMode.SAFE
                    and step.node_id == "publication_odata"
                    and steps[idx - 1].node_id == "approval_gate"
                ):
                    edge["condition"] = "{{approved_at}}"
                edges.append(edge)

        return {"nodes": nodes, "edges": edges}

    def _build_template_version(self, schema_template: PoolSchemaTemplate) -> str:
        payload = {
            "id": str(schema_template.id),
            "code": schema_template.code,
            "name": schema_template.name,
            "format": schema_template.format,
            "schema": schema_template.schema if isinstance(schema_template.schema, dict) else {},
            "metadata": schema_template.metadata if isinstance(schema_template.metadata, dict) else {},
            "updated_at": self._iso(schema_template.updated_at),
        }
        return self._sha256(self._canonical_json(payload))

    @staticmethod
    def _resolve_workflow_binding_hint(schema_template: PoolSchemaTemplate) -> str | None:
        metadata = schema_template.metadata if isinstance(schema_template.metadata, dict) else {}
        workflow_binding = str(metadata.get("workflow_binding") or "").strip()
        if workflow_binding:
            return workflow_binding
        workflow_template_id = str(metadata.get("workflow_template_id") or "").strip()
        if workflow_template_id:
            return workflow_template_id
        return None

    @staticmethod
    def _build_workflow_name(*, run_context: PoolWorkflowRunContext, plan_key: str) -> str:
        pool_token = str(run_context.pool_id).replace("-", "")[:12]
        prefix = f"pool-unified-{pool_token}-{run_context.direction}-{run_context.mode}-{plan_key[:16]}"
        return prefix[:200]

    @staticmethod
    def _build_workflow_config(mode: str) -> dict[str, Any]:
        timeout_seconds = 86400 if mode == PoolRunMode.SAFE else 14400
        return {
            "timeout_seconds": timeout_seconds,
            "max_retries": 0,
        }

    @staticmethod
    def _build_input_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pool_run_id": {"type": "string", "format": "uuid"},
                "pool_id": {"type": "string", "format": "uuid"},
                "period_start": {"type": "string", "format": "date"},
                "period_end": {"type": ["string", "null"], "format": "date"},
                "direction": {
                    "type": "string",
                    "enum": [PoolRunDirection.TOP_DOWN, PoolRunDirection.BOTTOM_UP],
                },
                "mode": {
                    "type": "string",
                    "enum": [PoolRunMode.SAFE, PoolRunMode.UNSAFE],
                },
                "run_input": {"type": "object"},
            },
            "required": ["pool_run_id", "pool_id", "period_start", "direction", "mode", "run_input"],
        }

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _sha256(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compile_pool_execution_plan(
    *,
    schema_template: PoolSchemaTemplate,
    run_context: PoolWorkflowRunContext,
) -> PoolExecutionPlan:
    return PoolWorkflowCompiler().compile(schema_template=schema_template, run_context=run_context)

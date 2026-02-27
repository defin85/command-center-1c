from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from apps.templates.models import OperationExposure
from apps.templates.workflow.models import WorkflowCategory, WorkflowTemplate, WorkflowType

from .document_plan_artifact_contract import validate_document_plan_artifact_v1
from .master_data_feature_flags import is_pool_master_data_gate_enabled
from .models import PoolRunDirection, PoolRunMode, PoolSchemaTemplate


PLAN_VERSION = 1

_OP_PREPARE_INPUT = "pool.prepare_input"
_OP_DISTRIBUTION_TOP_DOWN = "pool.distribution_calculation.top_down"
_OP_DISTRIBUTION_BOTTOM_UP = "pool.distribution_calculation.bottom_up"
_OP_RECONCILIATION = "pool.reconciliation_report"
_OP_APPROVAL_GATE = "pool.approval_gate"
_OP_MASTER_DATA_GATE = "pool.master_data_gate"
_OP_PUBLICATION = "pool.publication_odata"
POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING = "POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING"


@dataclass(frozen=True)
class PoolWorkflowRunContext:
    pool_id: str
    period_start: date
    period_end: date | None
    direction: str
    mode: str
    run_input: dict[str, Any]
    document_plan_artifact: dict[str, Any] | None = None


@dataclass(frozen=True)
class PoolExecutionPlanStep:
    node_id: str
    name: str
    operation_alias: str
    template_exposure_id: str
    template_exposure_revision: int
    timeout_seconds: int
    max_retries: int
    provenance: dict[str, Any] | None = None


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
        workflow_binding_hint = self._resolve_workflow_binding_hint(schema_template)

        definition_seed = self._build_definition_seed(
            run_context=run_context,
            template_version=template_version,
            workflow_binding_hint=workflow_binding_hint,
            dag_structure=dag_structure,
        )
        definition_key = self._sha256(self._canonical_json(definition_seed))
        workflow_name = self._build_workflow_name(run_context=run_context, definition_key=definition_key)
        workflow_description = (
            "Compiled pool execution workflow "
            f"(definition_key={definition_key}, template_version={template_version}, mode={run_context.mode})"
        )
        workflow_config = self._build_workflow_config(run_context.mode)

        return PoolExecutionPlan(
            plan_key=definition_key,
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

    @staticmethod
    def _build_definition_seed(
        *,
        run_context: PoolWorkflowRunContext,
        template_version: str,
        workflow_binding_hint: str | None,
        dag_structure: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "pool_id": str(run_context.pool_id),
            "direction": run_context.direction,
            "mode": run_context.mode,
            "template_version": template_version,
            "workflow_binding_hint": workflow_binding_hint,
            "dag_structure": dag_structure,
        }

    def _build_steps(self, run_context: PoolWorkflowRunContext) -> list[PoolExecutionPlanStep]:
        distribution_alias = (
            _OP_DISTRIBUTION_TOP_DOWN
            if run_context.direction == PoolRunDirection.TOP_DOWN
            else _OP_DISTRIBUTION_BOTTOM_UP
        )

        steps = [
            self._make_step(
                node_id="prepare_input",
                name="Prepare Input",
                operation_alias=_OP_PREPARE_INPUT,
                timeout_seconds=300,
                max_retries=0,
            ),
            self._make_step(
                node_id="distribution_calculation",
                name="Distribution Calculation",
                operation_alias=distribution_alias,
                timeout_seconds=900,
                max_retries=0,
            ),
            self._make_step(
                node_id="reconciliation_report",
                name="Reconciliation Report",
                operation_alias=_OP_RECONCILIATION,
                timeout_seconds=300,
                max_retries=0,
            ),
        ]

        if run_context.mode == PoolRunMode.SAFE:
            steps.append(
                self._make_step(
                    node_id="approval_gate",
                    name="Approval Gate",
                    operation_alias=_OP_APPROVAL_GATE,
                    timeout_seconds=3600,
                    max_retries=0,
                )
            )

        if is_pool_master_data_gate_enabled():
            steps.append(
                self._make_step(
                    node_id="master_data_gate",
                    name="Master Data Gate",
                    operation_alias=_OP_MASTER_DATA_GATE,
                    timeout_seconds=900,
                    max_retries=0,
                )
            )

        atomic_publication_steps = self._build_atomic_publication_steps(run_context=run_context)
        if atomic_publication_steps:
            steps.extend(atomic_publication_steps)
        else:
            steps.append(
                self._make_step(
                    node_id="publication_odata",
                    name="Publication OData",
                    operation_alias=_OP_PUBLICATION,
                    timeout_seconds=1800,
                    max_retries=4,
                )
            )
        return steps

    def _build_atomic_publication_steps(
        self,
        *,
        run_context: PoolWorkflowRunContext,
    ) -> list[PoolExecutionPlanStep]:
        artifact_raw = run_context.document_plan_artifact
        if artifact_raw is None:
            return []
        artifact = validate_document_plan_artifact_v1(artifact=artifact_raw)

        targets_raw = artifact.get("targets")
        if not isinstance(targets_raw, list):
            return []

        publication_steps: list[PoolExecutionPlanStep] = []
        targets = sorted(
            (
                dict(target)
                for target in targets_raw
                if isinstance(target, dict)
            ),
            key=lambda item: str(item.get("database_id") or ""),
        )
        for target in targets:
            database_id = str(target.get("database_id") or "").strip()
            if not database_id:
                continue
            chains_raw = target.get("chains")
            if not isinstance(chains_raw, list):
                continue
            chains = sorted(
                (
                    dict(chain)
                    for chain in chains_raw
                    if isinstance(chain, dict)
                ),
                key=lambda item: (
                    str((item.get("edge_ref") or {}).get("parent_node_id") or ""),
                    str((item.get("edge_ref") or {}).get("child_node_id") or ""),
                    str(item.get("chain_id") or ""),
                ),
            )
            for chain in chains:
                chain_id = str(chain.get("chain_id") or "").strip()
                edge_ref = chain.get("edge_ref") if isinstance(chain.get("edge_ref"), dict) else {}
                parent_node_id = str(edge_ref.get("parent_node_id") or "").strip()
                child_node_id = str(edge_ref.get("child_node_id") or "").strip()
                documents_raw = chain.get("documents")
                if not isinstance(documents_raw, list):
                    continue
                requires_invoice_step = any(
                    str(
                        (document_raw.get("invoice_mode") if isinstance(document_raw, dict) else "")
                        or ""
                    ).strip().lower() == "required"
                    for document_raw in documents_raw
                )
                has_invoice_step = any(
                    str(
                        (document_raw.get("document_role") if isinstance(document_raw, dict) else "")
                        or ""
                    ).strip().lower() == "invoice"
                    for document_raw in documents_raw
                )
                if requires_invoice_step and not has_invoice_step:
                    raise ValueError(
                        f"{POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING}: "
                        f"chain_id='{chain_id or '<unknown>'}', database_id='{database_id}'"
                    )
                for document_index, document_raw in enumerate(documents_raw):
                    if not isinstance(document_raw, dict):
                        continue
                    document = dict(document_raw)
                    document_id = str(document.get("document_id") or "").strip()
                    if not document_id:
                        continue
                    document_role = str(document.get("document_role") or "").strip() or "base"
                    node_id = self._build_atomic_publication_node_id(
                        database_id=database_id,
                        parent_node_id=parent_node_id,
                        child_node_id=child_node_id,
                        chain_id=chain_id,
                        document_id=document_id,
                        document_role=document_role,
                        document_index=document_index,
                    )
                    publication_steps.append(
                        self._make_step(
                            node_id=node_id,
                            name=self._build_atomic_publication_name(
                                database_id=database_id,
                                document_role=document_role,
                                document_id=document_id,
                            ),
                            operation_alias=_OP_PUBLICATION,
                            timeout_seconds=1800,
                            max_retries=4,
                            provenance={
                                "kind": "pool_atomic_publication",
                                "database_id": database_id,
                                "edge_ref": {
                                    "parent_node_id": parent_node_id,
                                    "child_node_id": child_node_id,
                                },
                                "chain_id": chain_id,
                                "document_id": document_id,
                                "document_role": document_role,
                                "action_kind": "publish_odata",
                                "attempt_scope": "run_execution",
                            },
                        )
                    )

        return publication_steps

    @classmethod
    def _build_atomic_publication_node_id(
        cls,
        *,
        database_id: str,
        parent_node_id: str,
        child_node_id: str,
        chain_id: str,
        document_id: str,
        document_role: str,
        document_index: int,
    ) -> str:
        payload = {
            "database_id": database_id,
            "parent_node_id": parent_node_id,
            "child_node_id": child_node_id,
            "chain_id": chain_id,
            "document_id": document_id,
            "document_role": document_role,
            "document_index": int(document_index),
        }
        digest = cls._sha256(cls._canonical_json(payload))[:16]
        parent_token = cls._normalize_node_token(parent_node_id)
        child_token = cls._normalize_node_token(child_node_id)
        role_token = cls._normalize_node_token(document_role)
        action_token = "publish_odata"
        prefix = (
            f"publication_odata__edge_{parent_token}_{child_token}"
            f"__doc_{role_token}__{action_token}"
        )
        max_prefix_length = 100 - len(digest) - 2
        normalized_prefix = prefix[:max_prefix_length].rstrip("_")
        return f"{normalized_prefix}__{digest}"

    @staticmethod
    def _normalize_node_token(value: str) -> str:
        token = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower()).strip("_")
        return token[:24] or "na"

    @staticmethod
    def _build_atomic_publication_name(
        *,
        database_id: str,
        document_role: str,
        document_id: str,
    ) -> str:
        role_token = document_role or document_id or "document"
        database_token = database_id[:8] if database_id else "db"
        return f"Publication OData {role_token} ({database_token})"

    def _make_step(
        self,
        *,
        node_id: str,
        name: str,
        operation_alias: str,
        timeout_seconds: int,
        max_retries: int,
        provenance: dict[str, Any] | None = None,
    ) -> PoolExecutionPlanStep:
        exposure_id, exposure_revision = self._resolve_pinned_template_binding(alias=operation_alias)
        return PoolExecutionPlanStep(
            node_id=node_id,
            name=name,
            operation_alias=operation_alias,
            template_exposure_id=exposure_id,
            template_exposure_revision=exposure_revision,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            provenance=dict(provenance) if isinstance(provenance, dict) else None,
        )

    def _resolve_pinned_template_binding(self, *, alias: str) -> tuple[str, int]:
        exposure = (
            OperationExposure.objects.select_related("definition")
            .filter(
                surface=OperationExposure.SURFACE_TEMPLATE,
                alias=alias,
                tenant__isnull=True,
                system_managed=True,
                domain=OperationExposure.DOMAIN_POOL_RUNTIME,
            )
            .first()
        )
        if exposure is None:
            raise ValueError(f"POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED: alias '{alias}' is not configured")
        if not bool(exposure.is_active) or exposure.status != OperationExposure.STATUS_PUBLISHED:
            raise ValueError(f"POOL_RUNTIME_TEMPLATE_INACTIVE: alias '{alias}' is inactive or unpublished")
        return str(exposure.id), self._resolve_exposure_revision(exposure)

    @staticmethod
    def _resolve_exposure_revision(exposure: OperationExposure) -> int:
        try:
            parsed = int(getattr(exposure, "exposure_revision", 0) or 0)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            return parsed
        definition = getattr(exposure, "definition", None)
        try:
            fallback = int(getattr(definition, "contract_version", 1) or 1)
        except (TypeError, ValueError):
            fallback = 1
        return fallback if fallback > 0 else 1

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
                        "binding_mode": "pinned_exposure",
                        "template_exposure_id": step.template_exposure_id,
                        "template_exposure_revision": step.template_exposure_revision,
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
    def _build_workflow_name(*, run_context: PoolWorkflowRunContext, definition_key: str) -> str:
        pool_token = str(run_context.pool_id).replace("-", "")[:12]
        prefix = f"pool-unified-{pool_token}-{run_context.direction}-{run_context.mode}-{definition_key[:16]}"
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
                "publication_auth": {
                    "type": "object",
                    "properties": {
                        "strategy": {"type": "string", "enum": ["actor", "service"]},
                        "actor_username": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["strategy", "source"],
                },
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

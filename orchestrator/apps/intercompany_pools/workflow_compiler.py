from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from apps.templates.models import OperationExposure
from apps.templates.template_runtime import TemplateResolveError, resolve_runtime_template
from apps.templates.workflow.authoring_contract import derive_workflow_definition_key
from apps.templates.workflow.models import DAGStructure, WorkflowCategory, WorkflowTemplate, WorkflowType

from .document_plan_artifact_contract import validate_document_plan_artifact_v1
from .master_data_feature_flags import resolve_pool_master_data_gate_flag
from .models import PoolRunDirection, PoolRunMode, PoolSchemaTemplate
from .workflow_authoring_contract import PoolWorkflowBindingContract


PLAN_VERSION = 1

_OP_PREPARE_INPUT = "pool.prepare_input"
_OP_DISTRIBUTION_TOP_DOWN = "pool.distribution_calculation.top_down"
_OP_DISTRIBUTION_BOTTOM_UP = "pool.distribution_calculation.bottom_up"
_OP_RECONCILIATION = "pool.reconciliation_report"
_OP_APPROVAL_GATE = "pool.approval_gate"
_OP_MASTER_DATA_GATE = "pool.master_data_gate"
_OP_PUBLICATION = "pool.publication_odata"
POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING = "POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING"
_MASTER_DATA_TOKEN_PREFIX = "master_data."
_MASTER_DATA_TOKEN_SUFFIX = ".ref"


@dataclass(frozen=True)
class PoolWorkflowRunContext:
    pool_id: str
    period_start: date
    period_end: date | None
    direction: str
    mode: str
    run_input: dict[str, Any]
    document_plan_artifact: dict[str, Any] | None = None
    workflow_binding: dict[str, Any] | None = None


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
    workflow_binding_snapshot: dict[str, Any] | None
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

        workflow_binding_snapshot = self._build_workflow_binding_snapshot(
            workflow_binding=run_context.workflow_binding,
            workflow_binding_hint=None,
        )
        authored_workflow = self._resolve_bound_workflow_template(
            workflow_binding=run_context.workflow_binding,
        )
        template_version = self._build_template_version(
            schema_template,
            authored_workflow=authored_workflow,
        )
        if authored_workflow is not None:
            steps, dag_structure, workflow_type, workflow_config = self._build_authored_workflow_projection(
                workflow_template=authored_workflow,
                run_context=run_context,
            )
        else:
            steps = self._build_steps(
                run_context,
                tenant_id=str(schema_template.tenant_id),
            )
            dag_structure = self._build_dag_structure(steps, run_context=run_context)
            workflow_type = WorkflowType.SEQUENTIAL
            workflow_config = self._build_workflow_config(run_context.mode)

        definition_seed = self._build_definition_seed(
            run_context=run_context,
            template_version=template_version,
            workflow_binding_snapshot=workflow_binding_snapshot,
            dag_structure=dag_structure,
        )
        definition_key = self._sha256(self._canonical_json(definition_seed))
        workflow_name = self._build_workflow_name(run_context=run_context, definition_key=definition_key)
        workflow_description = (
            "Compiled pool execution workflow "
            f"(definition_key={definition_key}, template_version={template_version}, mode={run_context.mode})"
        )

        return PoolExecutionPlan(
            plan_key=definition_key,
            plan_version=PLAN_VERSION,
            template_version=template_version,
            workflow_binding_hint=None,
            workflow_binding_snapshot=workflow_binding_snapshot,
            workflow_template_name=workflow_name,
            workflow_template_description=workflow_description,
            workflow_type=workflow_type,
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
        workflow_binding_snapshot: dict[str, Any] | None,
        dag_structure: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "pool_id": str(run_context.pool_id),
            "direction": run_context.direction,
            "mode": run_context.mode,
            "template_version": template_version,
            "workflow_binding": workflow_binding_snapshot,
            "dag_structure": dag_structure,
        }

    @staticmethod
    def _build_workflow_binding_snapshot(
        *,
        workflow_binding: dict[str, Any] | None,
        workflow_binding_hint: str | None,
    ) -> dict[str, Any] | None:
        if isinstance(workflow_binding, dict) and workflow_binding:
            binding = PoolWorkflowBindingContract(**workflow_binding)
            return {
                "binding_mode": "pool_workflow_binding",
                "binding_id": binding.binding_id,
                "pool_id": binding.pool_id,
                "workflow_definition_key": binding.workflow.workflow_definition_key,
                "workflow_revision_id": binding.workflow.workflow_revision_id,
                "workflow_revision": binding.workflow.workflow_revision,
                "workflow_name": binding.workflow.workflow_name,
                "decision_refs": [
                    decision.model_dump(mode="json", exclude_none=True)
                    for decision in binding.decisions
                ],
                "selector": binding.selector.model_dump(mode="json"),
                "status": binding.status.value,
            }
        return None

    @staticmethod
    def _resolve_bound_workflow_template(
        *,
        workflow_binding: dict[str, Any] | None,
    ) -> WorkflowTemplate | None:
        if not isinstance(workflow_binding, dict) or not workflow_binding:
            return None
        binding = PoolWorkflowBindingContract(**workflow_binding)
        workflow_revision_id = str(binding.workflow.workflow_revision_id or "").strip()
        workflow = (
            WorkflowTemplate.objects.filter(id=workflow_revision_id, is_active=True, is_valid=True)
            .order_by("-version_number")
            .first()
        )
        if workflow is None:
            raise ValueError(
                "POOL_WORKFLOW_DEFINITION_NOT_FOUND: "
                f"workflow revision '{workflow_revision_id}' was not found or is inactive"
            )
        expected_definition_key = str(binding.workflow.workflow_definition_key or "").strip()
        actual_definition_key = derive_workflow_definition_key(workflow_template=workflow)
        if expected_definition_key and actual_definition_key != expected_definition_key:
            raise ValueError(
                "POOL_WORKFLOW_DEFINITION_MISMATCH: "
                f"workflow revision '{workflow_revision_id}' does not match "
                f"workflow_definition_key '{expected_definition_key}'"
            )
        return workflow

    def _build_authored_workflow_projection(
        self,
        *,
        workflow_template: WorkflowTemplate,
        run_context: PoolWorkflowRunContext,
    ) -> tuple[list[PoolExecutionPlanStep], dict[str, Any], str, dict[str, Any]]:
        source_dag = (
            workflow_template.dag_structure
            if isinstance(workflow_template.dag_structure, DAGStructure)
            else DAGStructure(**workflow_template.dag_structure)
        )
        atomic_publication_steps = self._build_atomic_publication_steps(run_context=run_context)
        publication_nodes = [
            node
            for node in source_dag.nodes
            if node.type == "operation"
            and self._resolve_operation_alias_from_node(node=node) == _OP_PUBLICATION
        ]
        if atomic_publication_steps and len(publication_nodes) > 1:
            raise ValueError(
                "POOL_RUNTIME_PUBLICATION_NODE_AMBIGUOUS: "
                "workflow contains multiple publication nodes and cannot be expanded deterministically"
            )

        expanded_nodes: list[dict[str, Any]] = []
        expanded_edges: list[dict[str, Any]] = []
        steps: list[PoolExecutionPlanStep] = []
        expansion_by_node_id: dict[str, list[str]] = {}

        for node in source_dag.nodes:
            if node.type != "operation":
                expanded_nodes.append(node.model_dump(mode="json", by_alias=True))
                continue

            operation_alias = self._resolve_operation_alias_from_node(node=node)
            if operation_alias == _OP_PUBLICATION and atomic_publication_steps:
                expansion_by_node_id[node.id] = [step.node_id for step in atomic_publication_steps]
                for step in atomic_publication_steps:
                    expanded_nodes.append(
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
                steps.extend(atomic_publication_steps)
                continue

            step = self._build_step_from_workflow_node(node=node)
            steps.append(step)
            expansion_by_node_id[node.id] = [step.node_id]
            expanded_nodes.append(
                self._build_pinned_operation_node_payload(
                    node=node,
                    step=step,
                )
            )

        for edge in source_dag.edges:
            from_candidates = expansion_by_node_id.get(edge.from_node, [edge.from_node])
            to_candidates = expansion_by_node_id.get(edge.to_node, [edge.to_node])
            edge_payload: dict[str, Any] = {
                "from": from_candidates[-1],
                "to": to_candidates[0],
            }
            if edge.condition:
                edge_payload["condition"] = edge.condition
            expanded_edges.append(edge_payload)

        for expanded_node_ids in expansion_by_node_id.values():
            if len(expanded_node_ids) < 2:
                continue
            for from_node_id, to_node_id in zip(expanded_node_ids, expanded_node_ids[1:]):
                expanded_edges.append({"from": from_node_id, "to": to_node_id})

        authored_config = (
            workflow_template.config.model_dump(mode="json")
            if hasattr(workflow_template.config, "model_dump")
            else dict(workflow_template.config or {})
            if isinstance(workflow_template.config, Mapping)
            else {}
        )
        workflow_config = {
            **self._build_workflow_config(run_context.mode),
            **authored_config,
        }
        return (
            steps,
            {"nodes": expanded_nodes, "edges": expanded_edges},
            str(workflow_template.workflow_type or WorkflowType.SEQUENTIAL),
            workflow_config,
        )

    def _build_steps(
        self,
        run_context: PoolWorkflowRunContext,
        *,
        tenant_id: str | None,
    ) -> list[PoolExecutionPlanStep]:
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

        gate_flag_resolution = resolve_pool_master_data_gate_flag(tenant_id=tenant_id)
        requires_master_data_gate = (
            gate_flag_resolution.value is not False
            or self._document_plan_requires_master_data_gate(
                artifact=run_context.document_plan_artifact
            )
        )
        # Invalid gate config must still execute gate-step path and fail-closed at runtime.
        if requires_master_data_gate:
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
    def _document_plan_requires_master_data_gate(
        cls,
        *,
        artifact: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(artifact, dict):
            return False
        validated_artifact = validate_document_plan_artifact_v1(artifact=artifact)
        targets_raw = validated_artifact.get("targets")
        if not isinstance(targets_raw, list):
            return False

        for target in targets_raw:
            if not isinstance(target, dict):
                continue
            chains_raw = target.get("chains")
            if not isinstance(chains_raw, list):
                continue
            for chain in chains_raw:
                if not isinstance(chain, dict):
                    continue
                documents_raw = chain.get("documents")
                if not isinstance(documents_raw, list):
                    continue
                for document in documents_raw:
                    if not isinstance(document, dict):
                        continue
                    if cls._mapping_contains_master_data_token(document.get("field_mapping")):
                        return True
                    if cls._mapping_contains_master_data_token(document.get("table_parts_mapping")):
                        return True
        return False

    @classmethod
    def _mapping_contains_master_data_token(cls, value: Any) -> bool:
        if isinstance(value, str):
            token = value.strip()
            return token.startswith(_MASTER_DATA_TOKEN_PREFIX) and token.endswith(
                _MASTER_DATA_TOKEN_SUFFIX
            )
        if isinstance(value, dict):
            return any(cls._mapping_contains_master_data_token(item) for item in value.values())
        if isinstance(value, list):
            return any(cls._mapping_contains_master_data_token(item) for item in value)
        return False

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

    def _build_step_from_workflow_node(
        self,
        *,
        node,
    ) -> PoolExecutionPlanStep:
        operation_alias = self._resolve_operation_alias_from_node(node=node)
        runtime_template = self._resolve_runtime_template_for_node(node=node, alias=operation_alias)
        return PoolExecutionPlanStep(
            node_id=str(node.id),
            name=str(node.name),
            operation_alias=operation_alias,
            template_exposure_id=runtime_template.exposure_id,
            template_exposure_revision=runtime_template.exposure_revision,
            timeout_seconds=int(getattr(node.config, "timeout_seconds", 300) or 300),
            max_retries=int(getattr(node.config, "max_retries", 0) or 0),
            provenance=None,
        )

    @staticmethod
    def _resolve_operation_alias_from_node(*, node) -> str:
        operation_ref = getattr(node, "operation_ref", None)
        alias = str(getattr(operation_ref, "alias", "") or "").strip()
        if alias:
            return alias
        return str(getattr(node, "template_id", "") or "").strip()

    @staticmethod
    def _resolve_runtime_template_for_node(*, node, alias: str):
        operation_ref = getattr(node, "operation_ref", None)
        binding_mode = str(getattr(operation_ref, "binding_mode", "") or "").strip()
        template_exposure_id = (
            str(getattr(operation_ref, "template_exposure_id", "") or "").strip()
            if binding_mode == "pinned_exposure"
            else None
        )
        expected_exposure_revision = (
            getattr(operation_ref, "template_exposure_revision", None)
            if binding_mode == "pinned_exposure"
            else None
        )
        try:
            return resolve_runtime_template(
                template_alias=alias or None,
                template_exposure_id=template_exposure_id or None,
                expected_exposure_revision=expected_exposure_revision,
                require_active=True,
                require_published=True,
            )
        except TemplateResolveError as exc:
            raise ValueError(f"{exc.code}: {exc.message}") from exc

    @staticmethod
    def _build_pinned_operation_node_payload(
        *,
        node,
        step: PoolExecutionPlanStep,
    ) -> dict[str, Any]:
        payload = node.model_dump(mode="json", by_alias=True)
        payload["template_id"] = step.operation_alias
        payload["operation_ref"] = {
            "alias": step.operation_alias,
            "binding_mode": "pinned_exposure",
            "template_exposure_id": step.template_exposure_id,
            "template_exposure_revision": step.template_exposure_revision,
        }
        return payload

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

    def _build_template_version(
        self,
        schema_template: PoolSchemaTemplate,
        *,
        authored_workflow: WorkflowTemplate | None = None,
    ) -> str:
        payload = {
            "id": str(schema_template.id),
            "code": schema_template.code,
            "name": schema_template.name,
            "format": schema_template.format,
            "schema": schema_template.schema if isinstance(schema_template.schema, dict) else {},
            "metadata": schema_template.metadata if isinstance(schema_template.metadata, dict) else {},
            "updated_at": self._iso(schema_template.updated_at),
            "workflow_revision_id": str(authored_workflow.id) if authored_workflow is not None else None,
            "workflow_revision": (
                int(authored_workflow.version_number)
                if authored_workflow is not None
                else None
            ),
            "workflow_updated_at": self._iso(authored_workflow.updated_at) if authored_workflow is not None else None,
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
                "decisions": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "pool_runtime_document_plan_artifact": {
                    "type": "object",
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

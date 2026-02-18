"""Tests for workflow internal v2 endpoints."""

from copy import deepcopy
from datetime import date
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
    PoolRuntimeStepIdempotencyLog,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant, TenantMember

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class WorkflowInternalEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def _create_template(self) -> WorkflowTemplate:
        return WorkflowTemplate.objects.create(
            name=f"workflow-internal-{uuid4().hex[:8]}",
            description="",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "n1",
                        "name": "Node 1",
                        "type": "operation",
                        "template_id": "tpl-test",
                    }
                ],
                "edges": [],
            },
            is_valid=True,
            is_active=True,
        )

    def _create_pool_runtime_template(self) -> WorkflowTemplate:
        return WorkflowTemplate.objects.create(
            name=f"pool-runtime-{uuid4().hex[:8]}",
            description="",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "n1",
                        "name": "Prepare Input",
                        "type": "operation",
                        "template_id": "pool.prepare_input",
                    }
                ],
                "edges": [],
            },
            is_valid=True,
            is_active=True,
        )

    def _create_pool_runtime_fixture(self):
        tenant = Tenant.objects.create(slug=f"tenant-pool-runtime-{uuid4().hex[:8]}", name="Tenant Pool Runtime")
        pool = OrganizationPool.objects.create(
            tenant=tenant,
            code=f"pool-{uuid4().hex[:8]}",
            name="Pool Runtime",
        )
        run = PoolRun.objects.create(
            tenant=tenant,
            pool=pool,
            mode=PoolRunMode.UNSAFE,
            direction=PoolRunDirection.TOP_DOWN,
            period_start=date(2026, 1, 1),
            run_input={"starting_amount": "100.00"},
        )

        template = self._create_pool_runtime_template()
        execution = template.create_execution(
            {
                "pool_run_id": str(run.id),
                "approval_required": False,
                "approval_state": "not_required",
                "publication_step_state": "queued",
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        run.workflow_execution_id = execution.id
        run.workflow_status = execution.status
        run.execution_backend = "workflow_core"
        run.save(update_fields=["workflow_execution_id", "workflow_status", "execution_backend", "updated_at"])

        return tenant, run, execution, template

    def _build_bridge_request_payload(
        self,
        *,
        tenant_id: str,
        pool_run_id: str,
        workflow_execution_id: str,
        node_id: str = "n1",
        operation_type: str = "pool.prepare_input",
    ) -> dict[str, object]:
        return {
            "tenant_id": tenant_id,
            "pool_run_id": pool_run_id,
            "workflow_execution_id": workflow_execution_id,
            "node_id": node_id,
            "operation_type": operation_type,
            "operation_ref": {
                "alias": operation_type,
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(uuid4()),
                "template_exposure_revision": 1,
            },
            "step_attempt": 1,
            "transport_attempt": 1,
            "idempotency_key": "bridge-key-0001",
            "payload": {"pool_runtime": {"step_id": "prepare_input"}},
        }

    def test_update_workflow_status_advances_pools_approval_state_on_complete(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {
                "approval_required": True,
                "approved_at": None,
                "approval_state": "preparing",
                "publication_step_state": "not_enqueued",
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "completed",
                "result": {"ok": True},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["status"], "completed")

        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertEqual(saved.input_context.get("approval_state"), "awaiting_approval")
        self.assertEqual(saved.input_context.get("publication_step_state"), "not_enqueued")

    def test_update_workflow_status_sets_not_required_for_unsafe_pools_execution_without_synthetic_publication_completion(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {
                "approval_required": False,
                "approved_at": "2026-01-01T00:00:00Z",
                "publication_step_state": "queued",
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "completed",
                "result": {"ok": True},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertEqual(saved.input_context.get("approval_state"), "not_required")
        self.assertEqual(saved.input_context.get("publication_step_state"), "queued")

    def test_update_workflow_status_running_does_not_synthesize_publication_state_started(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {
                "approval_required": False,
                "approved_at": "2026-01-01T00:00:00Z",
                "approval_state": "not_required",
                "publication_step_state": "queued",
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "running",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertEqual(saved.input_context.get("publication_step_state"), "queued")

    def test_update_workflow_status_persists_structured_failure_diagnostics(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {
                "pool_run_id": str(uuid4()),
                "approval_required": False,
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "failed",
                "error_message": "bridge failed",
                "error_code": "POOL_RUNTIME_ROUTE_DISABLED",
                "error_details": {
                    "http_status": 503,
                    "attempts": 3,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["status"], "failed")
        self.assertEqual(response.data["error_code"], "POOL_RUNTIME_ROUTE_DISABLED")

        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertEqual(saved.status, WorkflowExecution.STATUS_FAILED)
        self.assertEqual(saved.error_message, "bridge failed")
        self.assertEqual(saved.error_code, "POOL_RUNTIME_ROUTE_DISABLED")
        self.assertEqual(saved.error_details, {"http_status": 503, "attempts": 3})

    def test_update_workflow_status_failed_idempotent_update_overwrites_structured_diagnostics(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {
                "pool_run_id": str(uuid4()),
                "approval_required": False,
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        first_response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "failed",
                "error_message": "bridge failed",
                "error_code": "POOL_RUNTIME_ROUTE_DISABLED",
                "error_details": {"attempts": 1},
            },
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)

        second_response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "failed",
                "error_message": "bridge retry budget exhausted",
                "error_code": "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED",
                "error_details": {"attempts": 4, "deadline_reached": True},
            },
            format="json",
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(second_response.data["success"])
        self.assertEqual(
            second_response.data["error_code"],
            "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED",
        )

        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertEqual(saved.status, WorkflowExecution.STATUS_FAILED)
        self.assertEqual(saved.error_message, "bridge retry budget exhausted")
        self.assertEqual(saved.error_code, "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED")
        self.assertEqual(saved.error_details, {"attempts": 4, "deadline_reached": True})

    def test_update_workflow_status_sanitizes_error_details_with_allowlist_and_redaction(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {"pool_run_id": str(uuid4()), "approval_required": False},
            tenant=tenant,
            execution_consumer="pools",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "failed",
                "error_message": "bridge failed",
                "error_code": "POOL_RUNTIME_ROUTE_DISABLED",
                "error_details": {
                    "http_status": 503,
                    "attempts": 3,
                    "api_key": "secret-key",
                    "ignored_top_level": "drop-me",
                    "context": {
                        "authorization": "Bearer super-secret",
                        "token": "nested-secret",
                        "retry_after_seconds": 2,
                    },
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertIsInstance(saved.error_details, dict)
        self.assertEqual(saved.error_details.get("http_status"), 503)
        self.assertEqual(saved.error_details.get("attempts"), 3)
        self.assertEqual(saved.error_details.get("api_key"), "***REDACTED***")
        self.assertNotIn("ignored_top_level", saved.error_details)
        self.assertEqual(saved.error_details.get("context", {}).get("authorization"), "***REDACTED***")
        self.assertEqual(saved.error_details.get("context", {}).get("token"), "***REDACTED***")
        self.assertEqual(saved.error_details.get("context", {}).get("retry_after_seconds"), 2)

    def test_update_workflow_status_applies_8k_size_cap_to_error_details(self):
        tenant = Tenant.objects.create(slug=f"tenant-{uuid4().hex[:8]}", name="Tenant")
        template = self._create_template()
        execution = template.create_execution(
            {"pool_run_id": str(uuid4()), "approval_required": False},
            tenant=tenant,
            execution_consumer="pools",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "failed",
                "error_message": "bridge failed",
                "error_code": "POOL_RUNTIME_ROUTE_DISABLED",
                "error_details": {
                    "http_status": 503,
                    "context": {
                        "logs": ["x" * 400 for _ in range(64)],
                    },
                    "message": "x" * 5000,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        saved = WorkflowExecution.objects.get(id=execution.id)
        self.assertIsInstance(saved.error_details, dict)
        encoded = json.dumps(
            saved.error_details,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        self.assertLessEqual(len(encoded), 8 * 1024)
        self.assertTrue(saved.error_details.get("_truncated"))

    def test_update_workflow_status_fail_closed_code_propagates_to_facade_diagnostics(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        username = f"pool-facade-user-{uuid4().hex[:8]}"
        user = User.objects.create_user(username=username, password="pass")
        TenantMember.objects.create(
            tenant=tenant,
            user=user,
            role=TenantMember.ROLE_ADMIN,
        )

        update_response = self.client.post(
            "/api/v2/internal/workflows/update-execution-status",
            {
                "execution_id": str(execution.id),
                "status": "failed",
                "error_message": "pool operation executor is not configured",
                "error_code": "WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED",
                "error_details": {"operation_type": "pool.publication_odata"},
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(update_response.data["success"])
        self.assertEqual(
            update_response.data["error_code"],
            "WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED",
        )

        facade_client = APIClient()
        facade_client.force_authenticate(user=user)
        facade_client.credentials(HTTP_X_CC1C_TENANT_ID=str(tenant.id))
        facade_response = facade_client.get(f"/api/v2/pools/runs/{run.id}/")

        self.assertEqual(facade_response.status_code, status.HTTP_200_OK)
        run_payload = facade_response.data["run"]
        self.assertEqual(run_payload["status"], "failed")
        self.assertEqual(run_payload["workflow_status"], "failed")
        diagnostics = run_payload.get("diagnostics")
        self.assertIsInstance(diagnostics, list)
        workflow_failure_diagnostic = next(
            (
                item
                for item in diagnostics
                if isinstance(item, dict)
                and item.get("code") == "WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED"
            ),
            None,
        )
        self.assertIsNotNone(workflow_failure_diagnostic)
        self.assertEqual(
            workflow_failure_diagnostic.get("error_details"),
            {"operation_type": "pool.publication_odata"},
        )

    def test_execute_pool_runtime_step_returns_completed_for_matching_context(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )

        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["workflow_execution_id"], str(execution.id))
        self.assertEqual(response.data["pool_run_id"], str(run.id))
        self.assertEqual(response.data["node_id"], "n1")
        self.assertEqual(response.data["idempotency_key"], "bridge-key-0001")
        self.assertEqual(response.data["result"]["step"], "prepare_input")

    def test_execute_pool_runtime_step_requires_internal_auth(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )

        unauthenticated = self.get_unauthenticated_client()
        response = unauthenticated.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_execute_pool_runtime_step_returns_bad_request_for_invalid_payload(self):
        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            {"tenant_id": str(uuid4())},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "BAD_REQUEST")

    def test_execute_pool_runtime_step_returns_not_found_for_unknown_execution(self):
        tenant, run, _, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(uuid4()),
        )

        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "NOT_FOUND")

    def test_execute_pool_runtime_step_returns_not_found_for_unknown_run(self):
        tenant, _, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(uuid4()),
            workflow_execution_id=str(execution.id),
        )

        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "NOT_FOUND")

    def test_execute_pool_runtime_step_returns_context_mismatch_for_tenant_mismatch(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(uuid4()),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )

        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "POOL_RUNTIME_CONTEXT_MISMATCH")
        self.assertIn("Bridge context does not match execution scope", response.data["error"])
        self.assertNotEqual(payload["tenant_id"], str(tenant.id))

    def test_execute_pool_runtime_step_returns_context_mismatch_for_run_execution_link_mismatch(self):
        tenant, run, execution, template = self._create_pool_runtime_fixture()
        other_execution = template.create_execution(
            {
                "pool_run_id": str(run.id),
                "approval_required": False,
            },
            tenant=tenant,
            execution_consumer="pools",
        )

        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(other_execution.id),
        )

        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "POOL_RUNTIME_CONTEXT_MISMATCH")
        self.assertNotEqual(str(execution.id), str(other_execution.id))

    def test_execute_pool_runtime_step_returns_context_mismatch_for_unknown_node_id(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
            node_id="unknown-node",
        )

        response = self.client.post(
            "/api/v2/internal/workflows/execute-pool-runtime-step",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "POOL_RUNTIME_CONTEXT_MISMATCH")

    def test_execute_pool_runtime_step_publication_odata_creates_publication_attempt_and_posts_documents(self):
        tenant, run, execution, template = self._create_pool_runtime_fixture()
        database = Database.objects.create(
            tenant=tenant,
            name=f"pool-runtime-db-{uuid4().hex[:8]}",
            host="localhost",
            odata_url="http://localhost/odata/standard.odata",
            username="admin",
            password="secret",
        )
        dag = (
            template.dag_structure.model_dump()
            if hasattr(template.dag_structure, "model_dump")
            else deepcopy(template.dag_structure)
        )
        dag["nodes"][0]["template_id"] = "pool.publication_odata"
        operation_ref = dag["nodes"][0].get("operation_ref")
        if isinstance(operation_ref, dict):
            operation_ref["alias"] = "pool.publication_odata"
        template.dag_structure = dag
        template.save(update_fields=["dag_structure"])

        run.mark_validated(summary={"rows": 1}, diagnostics=[])
        run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])

        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
            operation_type="pool.publication_odata",
        )
        payload["payload"] = {
            "pool_runtime": {
                "step_id": "publication_odata",
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(database.id): [{"Amount": "100.00"}],
                },
            }
        }

        odata_client = MagicMock()
        odata_client.get_entities.return_value = []
        odata_client.create_entity.return_value = {"Ref_Key": "550e8400-e29b-41d4-a716-446655440000"}

        with patch("apps.intercompany_pools.publication.session_manager.get_client", return_value=odata_client):
            response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                payload,
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["result"]["step"], "publication_odata")
        self.assertEqual(response.data["result"]["documents_targets"], 1)
        self.assertEqual(response.data["result"]["succeeded_targets"], 1)
        self.assertEqual(response.data["result"]["failed_targets"], 0)

        run_state = PoolRun.objects.filter(id=run.id).values("status", "publication_summary").get()
        self.assertEqual(run_state["status"], PoolRun.STATUS_PUBLISHED)
        self.assertEqual(run_state["publication_summary"].get("total_targets"), 1)
        self.assertEqual(run_state["publication_summary"].get("succeeded_targets"), 1)

        execution.refresh_from_db(fields=["input_context"])
        self.assertEqual(execution.input_context.get("publication_step_state"), "completed")

        attempt = PoolPublicationAttempt.objects.get(run=run, target_database=database)
        self.assertEqual(attempt.status, PoolPublicationAttemptStatus.SUCCESS)
        self.assertTrue(attempt.posted)
        self.assertEqual(attempt.documents_count, 1)
        self.assertEqual(attempt.request_summary.get("documents_count"), 1)

        odata_client.create_entity.assert_called_once()
        odata_client.update_entity.assert_called_once()

    def test_execute_pool_runtime_step_replays_idempotent_request_without_reapplying_side_effect(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )
        replay_payload_second = deepcopy(payload)
        replay_payload_second["transport_attempt"] = 2
        replay_payload_third = deepcopy(payload)
        replay_payload_third["transport_attempt"] = 3

        with patch(
            "apps.intercompany_pools.pool_domain_steps.execute_pool_runtime_step",
            return_value={"step": "prepare_input", "status": "ok"},
        ) as bridge_step_mock:
            first_response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                payload,
                format="json",
            )
            second_response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                replay_payload_second,
                format="json",
            )
            third_response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                replay_payload_third,
                format="json",
            )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(third_response.status_code, status.HTTP_200_OK)
        self.assertFalse(first_response.data["idempotency_replayed"])
        self.assertTrue(first_response.data["side_effect_applied"])
        self.assertEqual(first_response.data["step_attempt"], 1)
        self.assertEqual(first_response.data["transport_attempt"], 1)
        self.assertTrue(second_response.data["idempotency_replayed"])
        self.assertFalse(second_response.data["side_effect_applied"])
        self.assertEqual(second_response.data["step_attempt"], 1)
        self.assertEqual(second_response.data["transport_attempt"], 2)
        self.assertTrue(third_response.data["idempotency_replayed"])
        self.assertFalse(third_response.data["side_effect_applied"])
        self.assertEqual(third_response.data["step_attempt"], 1)
        self.assertEqual(third_response.data["transport_attempt"], 3)
        self.assertEqual(first_response.data["result"], second_response.data["result"])
        self.assertEqual(first_response.data["result"], third_response.data["result"])
        self.assertEqual(bridge_step_mock.call_count, 1)

        log_entry = PoolRuntimeStepIdempotencyLog.objects.get(
            tenant_id=tenant.id,
            idempotency_key="bridge-key-0001",
        )
        self.assertTrue(log_entry.request_fingerprint)
        self.assertEqual(log_entry.replay_count, 2)
        self.assertIsNotNone(log_entry.last_replayed_at)

    def test_execute_pool_runtime_step_returns_machine_readable_fail_closed_code(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )

        with patch(
            "apps.intercompany_pools.pool_domain_steps.execute_pool_runtime_step",
            side_effect=ValueError("POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED: retry budget exhausted"),
        ):
            response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                payload,
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED")
        self.assertIn("retry budget exhausted", response.data["error"])

    def test_execute_pool_runtime_step_returns_internal_error_for_unhandled_exception(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )

        with patch(
            "apps.intercompany_pools.pool_domain_steps.execute_pool_runtime_step",
            side_effect=RuntimeError("unexpected bridge failure"),
        ):
            response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                payload,
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["code"], "INTERNAL_ERROR")

    def test_execute_pool_runtime_step_returns_idempotency_conflict_for_same_key_different_payload(self):
        tenant, run, execution, _ = self._create_pool_runtime_fixture()
        payload = self._build_bridge_request_payload(
            tenant_id=str(tenant.id),
            pool_run_id=str(run.id),
            workflow_execution_id=str(execution.id),
        )
        conflicting_payload = deepcopy(payload)
        conflicting_payload["payload"] = {
            "pool_runtime": {"step_id": "prepare_input"},
            "target_scope": "conflicting-payload",
        }

        with patch(
            "apps.intercompany_pools.pool_domain_steps.execute_pool_runtime_step",
            return_value={"step": "prepare_input", "status": "ok"},
        ) as bridge_step_mock:
            first_response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                payload,
                format="json",
            )
            conflict_response = self.client.post(
                "/api/v2/internal/workflows/execute-pool-runtime-step",
                conflicting_payload,
                format="json",
            )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(conflict_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(conflict_response.data["code"], "IDEMPOTENCY_KEY_CONFLICT")
        self.assertEqual(bridge_step_mock.call_count, 1)

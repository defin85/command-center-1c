"""Tests for workflow internal v2 endpoints."""

from uuid import uuid4

from rest_framework import status

from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant

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

    def test_update_workflow_status_sets_not_required_for_unsafe_pools_execution(self):
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
        self.assertEqual(saved.input_context.get("publication_step_state"), "completed")

    def test_update_workflow_status_sets_publication_state_started_on_running(self):
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
        self.assertEqual(saved.input_context.get("publication_step_state"), "started")

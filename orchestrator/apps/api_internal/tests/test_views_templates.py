"""Tests for template v2 endpoints (Internal API)."""
from rest_framework import status

from apps.templates.models import OperationDefinition, OperationExposure

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


def _create_template_exposure(
    *,
    template_id: str,
    operation_type: str = "query",
    target_entity: str = "Users",
    template_data: dict | None = None,
    contract_version: int = 1,
    is_active: bool = True,
    status_value: str = OperationExposure.STATUS_PUBLISHED,
) -> OperationExposure:
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": operation_type,
            "target_entity": target_entity,
            "template_data": template_data or {},
        },
        contract_version=contract_version,
        fingerprint=f"fp-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant=None,
        label=f"Template {template_id}",
        description="",
        is_active=is_active,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=status_value,
    )


class TemplateEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def test_get_template_missing_id(self):
        response = self.client.get("/api/v2/internal/get-template")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("template_id", response.data["error"])

    def test_get_template_not_found(self):
        response = self.client.get("/api/v2/internal/get-template?template_id=nonexistent")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_get_template_success_from_exposure(self):
        exposure = _create_template_exposure(
            template_id="tpl_internal_get",
            operation_type="designer_cli",
            target_entity="Infobase",
            template_data={"command": "list"},
        )

        response = self.client.get("/api/v2/internal/get-template?template_id=tpl_internal_get")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["template"]["id"], "tpl_internal_get")
        self.assertEqual(response.data["template"]["operation_type"], "designer_cli")
        self.assertEqual(response.data["template"]["target_entity"], "Infobase")
        self.assertEqual(response.data["template"]["template_data"], {"command": "list"})

        response_by_id = self.client.get(
            f"/api/v2/internal/get-template?template_exposure_id={exposure.id}&template_exposure_revision=1"
        )
        self.assertEqual(response_by_id.status_code, status.HTTP_200_OK)
        self.assertTrue(response_by_id.data["success"])
        self.assertEqual(response_by_id.data["template"]["id"], "tpl_internal_get")

    def test_get_template_invalid_exposure_revision(self):
        _create_template_exposure(template_id="tpl_internal_get_invalid_revision")

        response = self.client.get(
            "/api/v2/internal/get-template"
            "?template_id=tpl_internal_get_invalid_revision&template_exposure_revision=oops"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("template_exposure_revision", response.data["error"])

    def test_get_template_detects_exposure_drift(self):
        exposure = _create_template_exposure(
            template_id="tpl_internal_get_drift",
            contract_version=3,
        )

        response = self.client.get(
            "/api/v2/internal/get-template"
            f"?template_exposure_id={exposure.id}&template_exposure_revision=2"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("TEMPLATE_DRIFT", str(response.data["error"]))

    def test_get_template_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.get("/api/v2/internal/get-template?template_id=test")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_render_template_missing_id(self):
        response = self.client.post(
            "/api/v2/internal/render-template",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("template_id", response.data["error"])

    def test_render_template_not_found(self):
        response = self.client.post(
            "/api/v2/internal/render-template?template_id=nonexistent",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_render_template_success_from_exposure(self):
        exposure = _create_template_exposure(
            template_id="tpl_internal_render",
            template_data={
                "query": "SELECT * FROM {{ table }}",
                "nested": {"limit": "{{ limit }}"},
                "plain": 123,
            },
        )

        response = self.client.post(
            "/api/v2/internal/render-template?template_id=tpl_internal_render",
            {"context": {"table": "users", "limit": 10}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(
            response.data["rendered"],
            {
                "query": "SELECT * FROM users",
                "nested": {"limit": "10"},
                "plain": 123,
            },
        )

        response_by_id = self.client.post(
            f"/api/v2/internal/render-template?template_exposure_id={exposure.id}&template_exposure_revision=1",
            {"context": {"table": "users", "limit": 10}},
            format="json",
        )
        self.assertEqual(response_by_id.status_code, status.HTTP_200_OK)
        self.assertTrue(response_by_id.data["success"])
        self.assertEqual(response_by_id.data["rendered"]["query"], "SELECT * FROM users")

    def test_render_template_detects_exposure_drift(self):
        exposure = _create_template_exposure(
            template_id="tpl_internal_render_drift",
            template_data={"query": "SELECT 1"},
            contract_version=5,
        )

        response = self.client.post(
            "/api/v2/internal/render-template"
            f"?template_exposure_id={exposure.id}&template_exposure_revision=4",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("TEMPLATE_DRIFT", str(response.data["error"]))

    def test_render_template_missing_context(self):
        response = self.client.post(
            "/api/v2/internal/render-template?template_id=test",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_render_template_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/render-template?template_id=test",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

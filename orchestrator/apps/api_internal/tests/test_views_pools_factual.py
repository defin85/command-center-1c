from rest_framework import status
from unittest.mock import patch

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class PoolFactualInternalEndpointsTests(InternalAPIV2BaseTestCase):
    def test_trigger_pool_factual_active_sync_window(self):
        with patch(
            "apps.api_internal.views_pools_factual.trigger_pool_factual_active_sync_window",
            return_value={
                "quarter_start": "2026-04-01",
                "pools_scanned": 2,
                "checkpoints_touched": 3,
                "checkpoints_running": 2,
            },
        ) as runtime_call:
            response = self.client.post(
                "/api/v2/internal/pools/factual/trigger-active-sync-window",
                {},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["pools_scanned"], 2)
        runtime_call.assert_called_once_with(tenant_id=None)

    def test_trigger_pool_factual_closed_quarter_reconcile_window(self):
        with patch(
            "apps.api_internal.views_pools_factual.trigger_pool_factual_closed_quarter_reconcile_window",
            return_value={
                "quarter_cutoff_start": "2026-04-01",
                "read_checkpoints_scanned": 1,
                "reconcile_checkpoints_touched": 1,
                "reconcile_checkpoints_created": 1,
                "reconcile_checkpoints_running": 1,
            },
        ) as runtime_call:
            response = self.client.post(
                "/api/v2/internal/pools/factual/trigger-closed-quarter-reconcile-window",
                {},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["reconcile_checkpoints_created"], 1)
        runtime_call.assert_called_once_with(tenant_id=None)

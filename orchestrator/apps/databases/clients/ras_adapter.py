"""
Thin wrapper for ras_adapter_api_client.
Returns v2 types directly without conversion.

This module provides a simplified interface to RAS Adapter API v2,
using the auto-generated client from OpenAPI specification.
"""
import logging
from typing import Optional, Union
from uuid import UUID

from django.conf import settings
import httpx

from .generated.ras_adapter_api_client import Client
from .generated.ras_adapter_api_client.api.health import get_health
from .generated.ras_adapter_api_client.api.infobases_v2 import list_infobases_v2
from .generated.ras_adapter_api_client.api.clusters_v2 import list_clusters_v2
from .generated.ras_adapter_api_client.models import (
    InfobasesResponse,
    HealthResponse,
    ClustersResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)


class RasAdapterError(Exception):
    """Exception raised when RAS Adapter returns an error response."""

    def __init__(self, message: str, error_response: Optional[ErrorResponse] = None):
        super().__init__(message)
        self.error_response = error_response


class RasAdapterClient:
    """
    Thin wrapper for RAS Adapter API v2.

    Returns v2 types directly (InfobasesResponse, ClustersResponse, etc.)
    without converting to legacy dictionary format.

    Usage:
        # As context manager (recommended)
        with RasAdapterClient() as client:
            if client.health_check():
                response = client.list_infobases(cluster_id)
                for ib in response.infobases:
                    print(ib.name, ib.uuid)

        # Direct usage
        client = RasAdapterClient()
        try:
            response = client.list_clusters(server="localhost:1545")
            for cluster in response.clusters:
                print(cluster.name, cluster.uuid)
        finally:
            client.close()
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize RAS Adapter client.

        Args:
            base_url: RAS Adapter URL (default: from settings.RAS_ADAPTER_URL)
            timeout: Request timeout in seconds (default: from settings.RAS_ADAPTER_TIMEOUT)
        """
        self.base_url = (
            base_url or
            getattr(settings, 'RAS_ADAPTER_URL', 'http://localhost:8088')
        ).rstrip('/')
        self.timeout = timeout or getattr(settings, 'RAS_ADAPTER_TIMEOUT', 180)

        self._client = Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(float(self.timeout))
        )

        logger.debug(
            f"Initialized RasAdapterClient: base_url={self.base_url}, "
            f"timeout={self.timeout}s"
        )

    def health_check(self) -> bool:
        """
        Check if RAS Adapter service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = get_health.sync(client=self._client)
            is_healthy = (
                isinstance(response, HealthResponse) and
                response.status == "healthy"
            )
            logger.debug(f"RAS Adapter health check: {is_healthy}")
            return is_healthy
        except Exception as e:
            logger.warning(f"RAS Adapter health check failed: {e}")
            return False

    def list_infobases(self, cluster_id: Union[str, UUID]) -> InfobasesResponse:
        """
        List infobases for specified cluster.

        Args:
            cluster_id: Cluster UUID (string or UUID object)

        Returns:
            InfobasesResponse with list of Infobase objects

        Raises:
            RasAdapterError: If API returns an error
            httpx.TimeoutException: If request times out
        """
        # Convert string to UUID if needed
        if isinstance(cluster_id, str):
            cluster_uuid = UUID(cluster_id)
        else:
            cluster_uuid = cluster_id

        logger.info(f"Listing infobases for cluster: {cluster_uuid}")

        response = list_infobases_v2.sync(
            client=self._client,
            cluster_id=cluster_uuid
        )

        if isinstance(response, ErrorResponse):
            error_msg = f"RAS Adapter error: {response.error if hasattr(response, 'error') else 'Unknown error'}"
            logger.error(error_msg)
            raise RasAdapterError(error_msg, response)

        if response is None:
            raise RasAdapterError("RAS Adapter returned empty response")

        logger.info(f"Retrieved {response.count} infobases from cluster {cluster_uuid}")
        return response

    def list_clusters(self, server: str) -> ClustersResponse:
        """
        List all clusters from RAS server.

        Args:
            server: RAS server address (e.g., "localhost:1545")

        Returns:
            ClustersResponse with list of Cluster objects

        Raises:
            RasAdapterError: If API returns an error
            httpx.TimeoutException: If request times out
        """
        logger.info(f"Listing clusters from RAS server: {server}")

        response = list_clusters_v2.sync(
            client=self._client,
            server=server
        )

        if isinstance(response, ErrorResponse):
            error_msg = f"RAS Adapter error: {response.error if hasattr(response, 'error') else 'Unknown error'}"
            logger.error(error_msg)
            raise RasAdapterError(error_msg, response)

        if response is None:
            raise RasAdapterError("RAS Adapter returned empty response")

        logger.info(f"Retrieved {response.count} clusters from {server}")
        return response

    def close(self):
        """Close HTTP connection."""
        if self._client is not None:
            # Close the underlying httpx client if it was created
            if hasattr(self._client, '_client') and self._client._client is not None:
                self._client._client.close()
                logger.debug("Closed RasAdapterClient HTTP connection")

    def __enter__(self) -> "RasAdapterClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

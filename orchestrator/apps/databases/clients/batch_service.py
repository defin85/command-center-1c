"""HTTP client for interacting with batch-service (Go microservice)."""

import logging
from typing import Optional
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from django.conf import settings

logger = logging.getLogger(__name__)


class BatchServiceClient:
    """
    HTTP client for interacting with batch-service.

    Batch-service is a Go microservice that provides parallel batch operations
    for 1C:Enterprise databases via OData protocol using goroutine pools.

    Usage:
        with BatchServiceClient(base_url="http://localhost:8087") as client:
            is_healthy = client.health_check()
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = None
    ):
        """
        Initialize batch-service client.

        Args:
            base_url: URL of batch-service (default: from settings.BATCH_SERVICE_URL)
            timeout: HTTP timeout in seconds (default: from settings.BATCH_SERVICE_TIMEOUT)
        """
        self.base_url = (base_url or getattr(
            settings,
            'BATCH_SERVICE_URL',
            'http://localhost:8087'
        )).rstrip('/')
        self.timeout = (
            timeout if timeout is not None
            else getattr(settings, 'BATCH_SERVICE_TIMEOUT', 60)
        )
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        logger.info(
            f"Initialized BatchServiceClient: base_url={self.base_url}, timeout={self.timeout}s"
        )

    def health_check(self) -> bool:
        """
        Check batch-service health.

        Endpoint: GET /health

        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/health"
            logger.info(f"Checking batch-service health: {url}")

            response = self.session.get(
                url,
                timeout=5  # Short timeout for health check
            )

            if response.status_code == 200:
                logger.info(f"Batch-service is healthy: {url}")
                return True
            else:
                logger.warning(
                    f"Batch-service returned status {response.status_code}: {url}"
                )
                return False

        except Timeout:
            logger.error(
                f"Timeout connecting to batch-service: {self.base_url} "
                f"(timeout: {self.timeout}s)"
            )
            return False
        except ConnectionError:
            logger.error(
                f"Connection error to batch-service: {self.base_url}"
            )
            return False
        except RequestException as e:
            logger.error(
                f"HTTP error checking batch-service: {e}",
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error checking batch-service: {type(e).__name__}: {e}",
                exc_info=True
            )
            return False

    def close(self):
        """Close HTTP session."""
        if self.session:
            self.session.close()
            logger.debug("Closed BatchServiceClient session")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

"""HTTP client for interacting with installation-service (Go microservice)."""

import logging
from typing import Dict, Optional
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from django.conf import settings

logger = logging.getLogger(__name__)


class InstallationServiceClient:
    """
    HTTP client for interacting with installation-service.

    Installation-service is a Go microservice that provides administrative
    operations for 1C:Enterprise clusters via RAS/RAC protocol.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: int = 180):
        """
        Initialize installation-service client.

        Args:
            base_url: URL of installation-service (default: from settings)
            timeout: HTTP timeout in seconds (default: 180)
        """
        self.base_url = (base_url or getattr(
            settings,
            'INSTALLATION_SERVICE_URL',
            'http://localhost:8085'
        )).rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        logger.info(f"Initialized InstallationServiceClient with base_url={self.base_url}")

    def health_check(self) -> bool:
        """
        Check if installation-service is available.

        Returns:
            True if service is available, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5  # Short timeout for health check
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def get_infobases(
        self,
        server: str = "localhost:1545",
        cluster_user: Optional[str] = None,
        cluster_pwd: Optional[str] = None,
        detailed: bool = False
    ) -> Dict:
        """
        Get list of information bases from 1C cluster.

        This method calls installation-service's GET /api/v1/infobases endpoint,
        which connects to 1C cluster via RAS protocol and retrieves database list.

        Args:
            server: RAS server address (host:port), default: "localhost:1545"
            cluster_user: Cluster administrator username (optional)
            cluster_pwd: Cluster administrator password (optional)
            detailed: Get detailed information (slower but more complete)

        Returns:
            Dictionary with result:
            {
                "status": "success",
                "cluster_id": "...",
                "cluster_name": "...",
                "total_count": 2,
                "infobases": [
                    {
                        "uuid": "...",
                        "name": "...",
                        "description": "...",
                        "dbms": "PostgreSQL" | "MSSQLServer" | "IBMDB2" | "OracleDatabase",
                        "db_server": "...",
                        "db_name": "...",
                        "db_user": "...",
                        "security_level": 0,
                        "connection_string": "...",
                        "locale": "ru_RU"
                    }
                ],
                "duration_ms": 1250
            }

        Raises:
            RequestException: On HTTP errors
            ValueError: On invalid response format
            Timeout: On request timeout
            ConnectionError: On connection errors
        """
        # Build query parameters for API call
        params = {
            'server': server,
            'detailed': str(detailed).lower()
        }

        if cluster_user:
            params['cluster_user'] = cluster_user

        if cluster_pwd:
            params['cluster_pwd'] = cluster_pwd

        # Build safe params for logging (mask password immediately)
        safe_params = {
            'server': server,
            'detailed': str(detailed).lower()
        }
        if cluster_user:
            safe_params['cluster_user'] = cluster_user
        if cluster_pwd:
            safe_params['cluster_pwd'] = '***'

        endpoint = f"{self.base_url}/api/v1/infobases"
        logger.info(f"Calling installation-service: GET {endpoint} with params={safe_params}")

        try:
            response = self.session.get(
                endpoint,
                params=params,
                timeout=self.timeout
            )

            # Log response status
            logger.info(
                f"Installation-service response: status={response.status_code}, "
                f"duration={response.elapsed.total_seconds():.3f}s"
            )

            # Check HTTP status
            response.raise_for_status()

            # Parse JSON
            data = response.json()

            # Validate response structure
            if 'status' not in data:
                raise ValueError("Response missing 'status' field")

            if data['status'] == 'error':
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"Installation-service returned error: {error_msg}")
                raise ValueError(f"Installation-service error: {error_msg}")

            if data['status'] != 'success':
                raise ValueError(f"Unexpected status: {data['status']}")

            # Validate required fields
            required_fields = ['cluster_id', 'cluster_name', 'total_count', 'infobases']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Response missing '{field}' field")

            # Log success
            logger.info(
                f"Successfully retrieved {data['total_count']} infobases "
                f"from cluster '{data['cluster_name']}' ({data['cluster_id']})"
            )

            return data

        except Timeout as e:
            logger.error(
                f"Timeout calling installation-service after {self.timeout}s: {e}. "
                f"Params: {safe_params}"
            )
            raise

        except ConnectionError as e:
            logger.error(
                f"Connection error to installation-service at {self.base_url}: {e}. "
                f"Params: {safe_params}"
            )
            raise

        except RequestException as e:
            logger.error(
                f"HTTP error calling installation-service: {e}. "
                f"Params: {safe_params}"
            )
            raise

        except ValueError as e:
            logger.error(
                f"Invalid response from installation-service: {e}. "
                f"Params: {safe_params}"
            )
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error calling installation-service: {type(e).__name__}: {e}. "
                f"Params: {safe_params}",
                exc_info=True
            )
            raise

    def close(self):
        """Close HTTP session."""
        if self.session:
            self.session.close()
            logger.debug("Closed InstallationServiceClient session")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

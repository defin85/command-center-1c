from __future__ import annotations

import requests

from .client import ODataClient


class ODataMetadataTransportError(Exception):
    """Transport error while fetching OData $metadata."""


class ODataMetadataAdapter:
    """Thin adapter for OData $metadata fetch using shared OData client stack."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout: int | None = None,
    ) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._username = username
        self._password = password
        read_timeout = timeout if isinstance(timeout, int) and timeout > 0 else ODataClient.READ_TIMEOUT
        self._timeout: tuple[int, int] = (ODataClient.CONNECT_TIMEOUT, read_timeout)

    def fetch_metadata(self) -> requests.Response:
        metadata_url = f"{self._base_url}/$metadata"
        try:
            return requests.get(
                metadata_url,
                headers={"Accept": "application/xml"},
                auth=(self._username, self._password),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise ODataMetadataTransportError(str(exc)) from exc

    def close(self) -> None:
        return None

    def __enter__(self) -> "ODataMetadataAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

from __future__ import annotations

from typing import Optional

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
        timeout: Optional[int] = None,
    ) -> None:
        self._client = ODataClient(
            base_url=base_url,
            username=username,
            password=password,
            timeout=timeout,
        )

    def fetch_metadata(self) -> requests.Response:
        metadata_url = f"{self._client.base_url}/$metadata"
        try:
            return self._client.session.get(
                metadata_url,
                headers={"Accept": "application/xml"},
                timeout=self._client.timeout,
            )
        except requests.RequestException as exc:
            raise ODataMetadataTransportError(str(exc)) from exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ODataMetadataAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

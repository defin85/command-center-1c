from __future__ import annotations

import base64
from urllib.parse import quote

import requests

from .client import ODataClient


class ODataDocumentTransportError(Exception):
    """Transport error while fetching a single OData entity."""


class ODataDocumentAdapter:
    """Thin adapter for single-entity OData fetches."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout: int | None = None,
        verify_tls: bool = True,
    ) -> None:
        self._base_url = str(base_url or "").rstrip("/")
        self._username = username
        self._password = password
        self._verify_tls = verify_tls
        read_timeout = timeout if isinstance(timeout, int) and timeout > 0 else ODataClient.READ_TIMEOUT
        self._timeout: tuple[int, int] = (ODataClient.CONNECT_TIMEOUT, read_timeout)

    def fetch_document(self, *, entity_name: str, entity_id: str) -> requests.Response:
        document_url = f"{self._base_url}/{entity_name}({quote(str(entity_id or ''), safe='')})"
        raw_credentials = f"{self._username}:{self._password}".encode("utf-8")
        basic_credentials = base64.b64encode(raw_credentials).decode("ascii")
        try:
            return requests.get(
                document_url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {basic_credentials}",
                },
                timeout=self._timeout,
                verify=self._verify_tls,
            )
        except requests.RequestException as exc:
            raise ODataDocumentTransportError(str(exc)) from exc

    def close(self) -> None:
        return None

    def __enter__(self) -> "ODataDocumentAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

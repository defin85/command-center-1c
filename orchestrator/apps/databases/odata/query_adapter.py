from __future__ import annotations

import base64

import requests

from .client import ODataClient


class ODataQueryTransportError(Exception):
    """Transport error while fetching OData rows."""


class ODataQueryAdapter:
    """Thin adapter for read-only OData entity/function queries."""

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

    def query(
        self,
        *,
        entity_name: str,
        filter_query: str | None = None,
        order_by: str | None = None,
        top: int | None = None,
        skip: int | None = None,
    ) -> requests.Response:
        entity_url = f"{self._base_url}/{str(entity_name or '').lstrip('/')}"
        raw_credentials = f"{self._username}:{self._password}".encode("utf-8")
        basic_credentials = base64.b64encode(raw_credentials).decode("ascii")
        params: dict[str, object] = {}
        if filter_query:
            params["$filter"] = filter_query
        if order_by:
            params["$orderby"] = order_by
        if top is not None:
            params["$top"] = int(top)
        if skip is not None:
            params["$skip"] = int(skip)
        try:
            return requests.get(
                entity_url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {basic_credentials}",
                },
                params=params,
                timeout=self._timeout,
                verify=self._verify_tls,
            )
        except requests.RequestException as exc:
            raise ODataQueryTransportError(str(exc)) from exc

    def close(self) -> None:
        return None

    def __enter__(self) -> "ODataQueryAdapter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

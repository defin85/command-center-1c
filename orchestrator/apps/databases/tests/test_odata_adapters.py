from __future__ import annotations

import base64

import pytest

from apps.databases.odata.document_adapter import ODataDocumentAdapter
from apps.databases.odata.metadata_adapter import ODataMetadataAdapter


def test_document_adapter_uses_utf8_basic_auth_and_verify_tls_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

    def _fake_get(
        url: str,
        *,
        headers: dict[str, str],
        timeout: tuple[int, int],
        verify: bool,
    ) -> _Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["verify"] = verify
        return _Response()

    monkeypatch.setattr("apps.databases.odata.document_adapter.requests.get", _fake_get)

    with ODataDocumentAdapter(
        base_url="https://odata.example.test/standard.odata/",
        username="ГлавБух",
        password="пароль",
        timeout=17,
        verify_tls=False,
    ) as adapter:
        response = adapter.fetch_document(
            entity_name="Document_РеализацияТоваровУслуг",
            entity_id="guid'abc123'",
        )

    expected_auth = "Basic " + base64.b64encode("ГлавБух:пароль".encode("utf-8")).decode("ascii")
    assert response.status_code == 200
    assert captured["url"] == (
        "https://odata.example.test/standard.odata/"
        "Document_РеализацияТоваровУслуг(guid%27abc123%27)"
    )
    assert captured["headers"] == {
        "Accept": "application/json",
        "Authorization": expected_auth,
    }
    assert captured["timeout"] == (5, 17)
    assert captured["verify"] is False


def test_metadata_adapter_respects_verify_tls_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

    def _fake_get(
        url: str,
        *,
        headers: dict[str, str],
        timeout: tuple[int, int],
        verify: bool,
    ) -> _Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["verify"] = verify
        return _Response()

    monkeypatch.setattr("apps.databases.odata.metadata_adapter.requests.get", _fake_get)

    with ODataMetadataAdapter(
        base_url="https://odata.example.test/standard.odata/",
        username="svc-user",
        password="svc-pass",
        timeout=11,
        verify_tls=False,
    ) as adapter:
        response = adapter.fetch_metadata()

    expected_auth = "Basic " + base64.b64encode("svc-user:svc-pass".encode("utf-8")).decode("ascii")
    assert response.status_code == 200
    assert captured["url"] == "https://odata.example.test/standard.odata/$metadata"
    assert captured["headers"] == {
        "Accept": "application/xml",
        "Authorization": expected_auth,
    }
    assert captured["timeout"] == (5, 11)
    assert captured["verify"] is False

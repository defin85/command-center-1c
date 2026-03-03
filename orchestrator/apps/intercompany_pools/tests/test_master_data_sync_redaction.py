from __future__ import annotations

from apps.intercompany_pools.master_data_sync_redaction import (
    sanitize_master_data_sync_text,
    sanitize_master_data_sync_value,
)


def test_redaction_masks_sensitive_key_value_pairs_and_preserves_checkpoint_tokens() -> None:
    message = (
        "dispatch failed: password=super-secret "
        "checkpoint_token=cp-001 "
        "authorization=Bearer abc.def "
        "url=http://user:pwd123@localhost/api"
    )

    sanitized = sanitize_master_data_sync_text(message)

    assert "password=***" in sanitized
    assert "checkpoint_token=cp-001" in sanitized
    assert "authorization=***" in sanitized or "authorization=Bearer ***" in sanitized
    assert "http://***:***@localhost/api" in sanitized
    assert "super-secret" not in sanitized
    assert "pwd123" not in sanitized


def test_redaction_masks_nested_sensitive_payload_values() -> None:
    payload = {
        "password": "secret",
        "nested": {
            "client_secret": "client-secret",
            "checkpoint_token": "cp-002",
        },
        "list": [{"api_key": "k-1"}, {"note": "safe"}],
    }

    sanitized = sanitize_master_data_sync_value(payload)

    assert sanitized["password"] == "***"
    assert sanitized["nested"]["client_secret"] == "***"
    assert sanitized["nested"]["checkpoint_token"] == "cp-002"
    assert sanitized["list"][0]["api_key"] == "***"
    assert sanitized["list"][1]["note"] == "safe"

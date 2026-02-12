from __future__ import annotations

from apps.api_v2.views.operations.execute_ibcmd_cli_impl import _validate_template_metadata_overrides


def test_validate_template_metadata_overrides_ignores_non_template_payload() -> None:
    assert _validate_template_metadata_overrides({"snapshot_source": "extensions_plan_apply"}) is None


def test_validate_template_metadata_overrides_requires_exposure_id_for_template_operations() -> None:
    response = _validate_template_metadata_overrides(
        {
            "execution_source": "template_manual_operation",
            "template_id": "tpl-sync",
        }
    )
    assert response is not None
    assert response.status_code == 400
    assert response.data["error"]["code"] == "TEMPLATE_METADATA_INVALID"
    assert response.data["error"]["details"]["missing_fields"] == ["template_exposure_id"]


def test_validate_template_metadata_overrides_accepts_full_template_reference() -> None:
    assert (
        _validate_template_metadata_overrides(
            {
                "execution_source": "template_manual_operation",
                "template_id": "tpl-sync",
                "template_exposure_id": "4d9a1ef8-b4b6-45d5-b9ad-f5001085be26",
            }
        )
        is None
    )

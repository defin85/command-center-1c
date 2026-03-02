from __future__ import annotations

import pytest

from apps.intercompany_pools.master_data_sync_origin import (
    MASTER_DATA_SYNC_ORIGIN_CC,
    MASTER_DATA_SYNC_ORIGIN_IB,
    normalize_master_data_sync_origin,
    should_skip_outbound_sync_for_origin,
)


def test_normalize_origin_uses_cc_default() -> None:
    origin = normalize_master_data_sync_origin(origin_system="", origin_event_id="")

    assert origin.origin_system == MASTER_DATA_SYNC_ORIGIN_CC
    assert origin.origin_event_id == ""


def test_normalize_origin_requires_event_id_for_non_cc_origin() -> None:
    with pytest.raises(ValueError, match="origin_event_id is required"):
        normalize_master_data_sync_origin(
            origin_system=MASTER_DATA_SYNC_ORIGIN_IB,
            origin_event_id="",
        )


def test_should_skip_outbound_for_ib_origin_with_event_id() -> None:
    assert (
        should_skip_outbound_sync_for_origin(
            origin_system=MASTER_DATA_SYNC_ORIGIN_IB,
            origin_event_id="evt-ib-001",
        )
        is True
    )


def test_should_not_skip_outbound_for_cc_origin() -> None:
    assert (
        should_skip_outbound_sync_for_origin(
            origin_system=MASTER_DATA_SYNC_ORIGIN_CC,
            origin_event_id="evt-cc-001",
        )
        is False
    )

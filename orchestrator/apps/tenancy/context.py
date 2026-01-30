from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


_state = threading.local()


def set_current_tenant_id(tenant_id: str | None) -> None:
    _state.tenant_id = tenant_id


def get_current_tenant_id() -> str | None:
    return getattr(_state, "tenant_id", None)


def clear_current_tenant_id() -> None:
    if hasattr(_state, "tenant_id"):
        delattr(_state, "tenant_id")


@contextmanager
def tenant_context(tenant_id: str | None) -> Iterator[None]:
    prev = get_current_tenant_id()
    try:
        set_current_tenant_id(tenant_id)
        yield
    finally:
        set_current_tenant_id(prev)


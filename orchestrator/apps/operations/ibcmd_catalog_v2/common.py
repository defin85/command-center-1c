# ruff: noqa: F401
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..driver_catalog_v2 import (
    CATALOG_RISK_DANGEROUS,
    CATALOG_RISK_SAFE,
    CATALOG_SCOPE_GLOBAL,
    CATALOG_SCOPE_PER_DATABASE,
)


_RU_MODE = "\u0420\u0435\u0436\u0438\u043c"
_RU_GROUP_COMMANDS = "\u041a\u043e\u043c\u0430\u043d\u0434\u044b \u0433\u0440\u0443\u043f\u043f\u044b"
_RU_PARAM = "\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440"
_RU_PARAMS = "\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b"
_RU_DESCRIPTION = "\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435"
_RU_GENERAL_INFO = "\u041e\u0431\u0449\u0430\u044f \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f"
_RU_COMMON_PARAMS = "\u041e\u0431\u0449\u0438\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b"
_RU_ALLOWED_VALUES = "\u0414\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0435 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u044f"
_RU_BULLET = "\u25cf"
_RU_NO_INFOBASE_CONNECT = (
    "\u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u0435\u0442 "
    "\u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 "
    "\u043a \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u043e\u043d\u043d\u043e\u0439 \u0431\u0430\u0437\u0435"
)
_RU_DELETE_SUBSTR = "\u0443\u0434\u0430\u043b"
_RU_CLEAR_SUBSTR = "\u043e\u0447\u0438\u0441\u0442"

_TITLE_RE = re.compile(r"^(4\.10(?:\.\d+)*)\.\s*(.+)$")
_MODE_RE = re.compile(rf"^{_RU_MODE}\s+([A-Za-z0-9][A-Za-z0-9-]*)\b")
_GROUP_RE = re.compile(rf"^{_RU_GROUP_COMMANDS}\s+([A-Za-z0-9][A-Za-z0-9-]*)\b")
_COMMAND_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*(?: [a-z0-9-]+)*$")

_PARAM_SECTION_RE = re.compile(rf"^{_RU_PARAM}(?:\u044b)?\b", re.IGNORECASE)
_DESCRIPTION_HEADER_RE = re.compile(rf"^{_RU_DESCRIPTION}\b", re.IGNORECASE)
_GROUP_PARAMS_RE = re.compile(rf"^{_RU_PARAMS}\s+([A-Za-z0-9][A-Za-z0-9-]*)\b")

_FLAG_VARIANT_RE = re.compile(r"^(--?[A-Za-z0-9][A-Za-z0-9-]*)(?:=(<[^>]+>))?$")
_SHORT_FLAG_WITH_VALUE_RE = re.compile(r"^(-[A-Za-z0-9])\s+(<[^>]+>)$")
_POSITIONAL_VARIANT_RE = re.compile(r"^(<[^>]+>)$")

_INFO_TITLES = {
    _RU_GENERAL_INFO,
    _RU_COMMON_PARAMS,
}

_COMMON_PARAMS_SECTION_PREFIX = "4.10.2."

_COMMON_PARAMS_KEY_RENAMES: dict[str, str] = {
    # Keep backward-compatible field names used across API/UI, even if canonical flag is --database-*.
    "database_name": "db_name",
    "database_server": "db_server",
    "database_user": "db_user",
    "database_password": "db_pwd",
    "database_path": "db_path",
    "request_database_password": "request_db_pwd",
}

_CREDENTIAL_SEMANTICS: dict[str, dict[str, Any]] = {
    "db_user": {"credential_kind": "db_user"},
    "db_pwd": {"credential_kind": "db_password"},
    "user": {"credential_kind": "ib_user"},
    "password": {"credential_kind": "ib_password"},
}


@dataclass(frozen=True)
class _TitleEntry:
    kind: str  # mode|group|command|info
    token: str | None = None
    command_tokens: list[str] | None = None

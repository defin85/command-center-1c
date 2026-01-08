from __future__ import annotations

from typing import Any


LEGACY_IBCMD_OPERATION_TO_COMMAND_ID = {
    "ibcmd_backup": "infobase.dump",
    "ibcmd_restore": "infobase.restore",
    "ibcmd_replicate": "infobase.replicate",
    "ibcmd_create": "infobase.create",
    "ibcmd_load_cfg": "infobase.config.load-cfg",
    "ibcmd_extension_update": "infobase.extension.update",
}


def _coerce_yes_no(value: Any, *, name: str) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return "yes" if value != 0 else "no"
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "no"}:
            return lowered
        if lowered in {"true", "1", "on"}:
            return "yes"
        if lowered in {"false", "0", "off"}:
            return "no"
    raise ValueError(f"{name} must be a boolean or yes/no string")


def legacy_ibcmd_config_to_ibcmd_cli_request(operation_type: str, config: dict[str, Any]) -> dict[str, Any]:
    op = str(operation_type or "").strip()
    command_id = LEGACY_IBCMD_OPERATION_TO_COMMAND_ID.get(op)
    if not command_id:
        raise ValueError(f"Unsupported legacy ibcmd operation_type: {op}")

    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError("config must be an object")

    params: dict[str, Any] = {
        "dbms": config.get("dbms"),
        "db_server": config.get("db_server"),
        "db_name": config.get("db_name"),
        "db_user": config.get("db_user"),
        "db_pwd": config.get("db_pwd") if config.get("db_pwd") is not None else config.get("db_password"),
    }

    if op == "ibcmd_backup":
        output_path = config.get("output_path")
        if isinstance(output_path, str) and output_path.strip():
            params["arg1"] = output_path.strip()

    elif op == "ibcmd_restore":
        input_path = config.get("input_path")
        if not input_path:
            input_path = config.get("backup_path")
        if not isinstance(input_path, str) or not input_path.strip():
            raise ValueError("input_path is required")
        params["arg1"] = input_path.strip()

        if config.get("create_database") is True:
            params["create_database"] = True
        if config.get("force") is True:
            params["force"] = True

    elif op == "ibcmd_replicate":
        params["target_dbms"] = config.get("target_dbms")
        params["target_database_server"] = (
            config.get("target_database_server")
            if config.get("target_database_server") is not None
            else config.get("target_db_server")
        )
        params["target_database_name"] = (
            config.get("target_database_name")
            if config.get("target_database_name") is not None
            else config.get("target_db_name")
        )
        params["target_database_user"] = (
            config.get("target_database_user")
            if config.get("target_database_user") is not None
            else config.get("target_db_user")
        )
        params["target_database_password"] = (
            config.get("target_database_password")
            if config.get("target_database_password") is not None
            else config.get("target_db_password")
        )

        if config.get("jobs_count") is not None:
            params["jobs_count"] = config.get("jobs_count")
        if config.get("target_jobs_count") is not None:
            params["target_jobs_count"] = config.get("target_jobs_count")

    elif op == "ibcmd_load_cfg":
        file_path = config.get("file")
        if not file_path:
            file_path = config.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("file is required")
        params["file"] = file_path.strip()

        extension = config.get("extension")
        if isinstance(extension, str) and extension.strip():
            params["extension"] = extension.strip()

    elif op == "ibcmd_extension_update":
        ext_name = config.get("name")
        if not ext_name:
            ext_name = config.get("extension")
        if not isinstance(ext_name, str) or not ext_name.strip():
            raise ValueError("name is required")
        params["name"] = ext_name.strip()

        for key in ("active", "safe_mode", "unsafe_action_protection", "used_in_distributed_infobase"):
            if key not in config or config.get(key) is None:
                continue
            params[key] = _coerce_yes_no(config.get(key), name=key)

        scope = config.get("scope")
        if isinstance(scope, str) and scope.strip():
            params["scope"] = scope.strip()

        profile = config.get("security_profile_name")
        if isinstance(profile, str) and profile.strip():
            params["security_profile_name"] = profile.strip()

    additional_args = config.get("additional_args") or []
    if not isinstance(additional_args, list):
        raise ValueError("additional_args must be an array")
    extra = [str(item).strip() for item in additional_args if item is not None and str(item).strip()]

    stdin = config.get("stdin")
    if stdin is None:
        stdin = ""
    stdin = str(stdin)

    return {
        "command_id": command_id,
        "mode": "guided",
        "params": params,
        "additional_args": extra,
        "stdin": stdin,
        "confirm_dangerous": True,
    }


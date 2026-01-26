import pytest

from apps.operations.ibcmd_catalog_v2 import build_base_catalog_from_its, validate_catalog_v2


def _ru(s: str) -> str:
    return s.encode("utf-8").decode("unicode_escape")


@pytest.mark.parametrize(
    ("marker_param", "marker_desc"),
    [
        (_ru("\\u041f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440"), _ru("\\u041e\\u043f\\u0438\\u0441\\u0430\\u043d\\u0438\\u0435")),
    ],
)
def test_build_base_catalog_from_its_parses_command_section(marker_param, marker_desc):
    payload = {
        "version": "8.3.27",
        "pointer_ti": "TI000001193",
        "sections": [
            {"title": f"4.10.3. {_ru('\\u0420\\u0435\\u0436\\u0438\\u043c')} server", "text": ""},
            {"title": f"4.10.3.2. {_ru('\\u041a\\u043e\\u043c\\u0430\\u043d\\u0434\\u044b \\u0433\\u0440\\u0443\\u043f\\u043f\\u044b')} config", "text": ""},
            {
                "title": "4.10.3.2.1. init",
                "text": "\n".join([
                    "Init standalone server configuration.",
                    "",
                    marker_param,
                    "",
                    marker_desc,
                    "",
                    "--dbms=<kind>",
                    "",
                    "DBMS kind.",
                    "--database-name=<name>",
                    "",
                    "Database name.",
                ]),
            },
        ],
    }

    catalog = build_base_catalog_from_its(payload)
    assert catalog["catalog_version"] == 2
    assert catalog["driver"] == "ibcmd"
    assert catalog["platform_version"] == "8.3.27"

    driver_schema = catalog.get("driver_schema")
    assert isinstance(driver_schema, dict)
    assert "connection" in driver_schema
    assert "timeout_seconds" in driver_schema
    assert driver_schema["timeout_seconds"]["default"] == 900
    assert driver_schema["auth_database_id"]["kind"] == "database_ref"
    assert driver_schema["ui"]["version"] == 1

    cmd = catalog["commands_by_id"]["server.config.init"]
    assert cmd["argv"] == ["server", "config", "init"]
    assert cmd["scope"] == "global"
    assert cmd["risk_level"] == "safe"
    assert "dbms" in (cmd.get("params_by_name") or {})
    assert "database_name" in (cmd.get("params_by_name") or {})

    errors = validate_catalog_v2(catalog)
    assert errors == []


def test_build_base_catalog_from_its_parses_group_section_commands():
    marker_param = _ru("\\u041f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440")
    marker_desc = _ru("\\u041e\\u043f\\u0438\\u0441\\u0430\\u043d\\u0438\\u0435")

    payload = {
        "version": "8.3.27",
        "pointer_ti": "TI000001193",
        "sections": [
            {"title": f"4.10.4. {_ru('\\u0420\\u0435\\u0436\\u0438\\u043c')} infobase", "text": ""},
            {"title": f"4.10.4.7. {_ru('\\u041a\\u043e\\u043c\\u0430\\u043d\\u0434\\u044b \\u0433\\u0440\\u0443\\u043f\\u043f\\u044b')} config", "text": ""},
            {
                "title": f"4.10.4.7.12. {_ru('\\u041a\\u043e\\u043c\\u0430\\u043d\\u0434\\u044b \\u0433\\u0440\\u0443\\u043f\\u043f\\u044b')} extension",
                "text": "\n".join([
                    "create",
                    "",
                    "Create extension.",
                    "",
                    marker_param,
                    "",
                    marker_desc,
                    "",
                    "--name=<name>",
                    "",
                    "Extension name.",
                    "",
                    "list",
                    "",
                    "List extensions.",
                ]),
            },
        ],
    }

    catalog = build_base_catalog_from_its(payload)
    assert "infobase.extension.create" in catalog["commands_by_id"]
    assert "infobase.extension.list" in catalog["commands_by_id"]

    create_cmd = catalog["commands_by_id"]["infobase.extension.create"]
    assert create_cmd["argv"] == ["infobase", "extension", "create"]
    assert create_cmd["scope"] == "per_database"
    assert create_cmd["risk_level"] == "safe"
    assert create_cmd["params_by_name"]["name"]["flag"] == "--name"


def test_build_base_catalog_from_its_parses_flag_variants_with_extra_placeholders():
    marker_param = _ru("\\u041f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440")
    marker_desc = _ru("\\u041e\\u043f\\u0438\\u0441\\u0430\\u043d\\u0438\\u0435")

    payload = {
        "version": "8.3.27",
        "pointer_ti": "TI000001193",
        "sections": [
            {"title": f"4.10.11. {_ru('\\u0420\\u0435\\u0436\\u0438\\u043c')} eventlog", "text": ""},
            {
                "title": "4.10.11.2. export",
                "text": "\n".join(
                    [
                        "Export event log.",
                        "",
                        marker_param,
                        "",
                        marker_desc,
                        "",
                        "--follow=<timeout> <ms>",
                        "",
                        "-F <timeout> <ms>",
                        "",
                        "Polling frequency in ms.",
                    ]
                ),
            },
        ],
    }

    catalog = build_base_catalog_from_its(payload)
    cmd = catalog["commands_by_id"]["eventlog.export"]
    assert cmd["argv"] == ["eventlog", "export"]

    follow = (cmd.get("params_by_name") or {}).get("follow")
    assert follow is not None
    assert follow["kind"] == "flag"
    assert follow["flag"] == "--follow"
    assert follow["expects_value"] is True
    assert follow.get("ui", {}).get("aliases") == ["-F"]

    errors = validate_catalog_v2(catalog)
    assert errors == []


def test_build_base_catalog_from_its_parses_common_params_into_driver_schema():
    payload = {
        "version": "8.3.27",
        "pointer_ti": "TI000001149",
        "sections": [
            {
                "title": f"4.10.2. {_ru('\\u041e\\u0431\\u0449\\u0438\\u0435 \\u043f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440\\u044b')}",
                "blocks": [
                    {
                        "kind": "table",
                        "rows": [
                            [_ru("\\u041f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440"), _ru("\\u041e\\u043f\\u0438\\u0441\\u0430\\u043d\\u0438\\u0435")],
                            ["--database-path=<path> --db-path=<path>", "DB path."],
                            ["--database-password=<password> --db-pwd=<password>", "DB password."],
                            ["--database-user=<name> --db-user=<name>", "DB user."],
                            ["--user=<name> -u <name>", "IB user."],
                            ["--password=<password> -P <password>", "IB password."],
                        ],
                    },
                ],
            },
        ],
    }

    catalog = build_base_catalog_from_its(payload)
    driver_schema = catalog.get("driver_schema")
    assert isinstance(driver_schema, dict)

    offline = driver_schema.get("connection", {}).get("offline", {})
    assert isinstance(offline, dict)
    assert "db_path" in offline
    assert offline["db_path"]["flag"] == "--db-path"
    assert "db_pwd" in offline
    assert offline["db_pwd"]["flag"] == "--db-pwd"
    assert offline["db_pwd"]["sensitive"] is True
    assert offline["db_pwd"]["semantics"]["credential_kind"] == "db_password"
    assert "--database-password" in (offline["db_pwd"].get("ui") or {}).get("aliases", [])

    ib_auth = driver_schema.get("ib_auth")
    assert isinstance(ib_auth, dict)
    assert ib_auth["strategy"]["default"] == "actor"
    assert ib_auth["user"]["flag"] == "--user"
    assert ib_auth["user"]["semantics"]["credential_kind"] == "ib_user"
    assert ib_auth["password"]["flag"] == "--password"
    assert ib_auth["password"]["sensitive"] is True
    assert ib_auth["password"]["semantics"]["credential_kind"] == "ib_password"
    assert "-P" in (ib_auth["password"].get("ui") or {}).get("aliases", [])


def test_build_base_catalog_from_its_parses_enum_values_with_blank_lines_in_text():
    marker_param = _ru("\\u041f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440")
    marker_desc = _ru("\\u041e\\u043f\\u0438\\u0441\\u0430\\u043d\\u0438\\u0435")
    allowed = _ru("\\u0414\\u043e\\u043f\\u0443\\u0441\\u0442\\u0438\\u043c\\u044b\\u0435 \\u0437\\u043d\\u0430\\u0447\\u0435\\u043d\\u0438\\u044f")
    bullet = _ru("\\u25cf")

    payload = {
        "version": "8.3.27",
        "pointer_ti": "TI000001193",
        "sections": [
            {"title": f"4.10.4. {_ru('\\u0420\\u0435\\u0436\\u0438\\u043c')} infobase", "text": ""},
            {
                "title": f"4.10.4.7.12. {_ru('\\u041a\\u043e\\u043c\\u0430\\u043d\\u0434\\u044b \\u0433\\u0440\\u0443\\u043f\\u043f\\u044b')} extension",
                "text": "\n".join(
                    [
                        "update",
                        "",
                        marker_param,
                        "",
                        marker_desc,
                        "",
                        "--active=<flag>",
                        "",
                        "Active flag.",
                        f"{allowed}:",
                        f"{bullet} yes - enable.",
                        "",
                        f"{bullet} no - disable.",
                    ]
                ),
            },
        ],
    }

    catalog = build_base_catalog_from_its(payload)
    cmd = catalog["commands_by_id"]["infobase.extension.update"]
    active = (cmd.get("params_by_name") or {}).get("active")
    assert active is not None
    assert active.get("enum") == ["yes", "no"]

    errors = validate_catalog_v2(catalog)
    assert errors == []


def test_build_base_catalog_from_its_prefers_blocks_for_enum_values():
    marker_param = _ru("\\u041f\\u0430\\u0440\\u0430\\u043c\\u0435\\u0442\\u0440")
    marker_desc = _ru("\\u041e\\u043f\\u0438\\u0441\\u0430\\u043d\\u0438\\u0435")
    allowed = _ru("\\u0414\\u043e\\u043f\\u0443\\u0441\\u0442\\u0438\\u043c\\u044b\\u0435 \\u0437\\u043d\\u0430\\u0447\\u0435\\u043d\\u0438\\u044f")
    bullet = _ru("\\u25cf")

    payload = {
        "version": "8.3.27",
        "pointer_ti": "TI000001193",
        "sections": [
            {"title": f"4.10.4. {_ru('\\u0420\\u0435\\u0436\\u0438\\u043c')} infobase", "text": ""},
            {
                "title": f"4.10.4.7.12. {_ru('\\u041a\\u043e\\u043c\\u0430\\u043d\\u0434\\u044b \\u0433\\u0440\\u0443\\u043f\\u043f\\u044b')} extension",
                # Text simulates current innerText export: blank line between enum items.
                "text": "\n".join(
                    [
                        "update",
                        "",
                        marker_param,
                        "",
                        marker_desc,
                        "",
                        "--active=<flag>",
                        "",
                        "Active flag.",
                        f"{allowed}:",
                        f"{bullet} yes - enable.",
                        "",
                        f"{bullet} no - disable.",
                    ]
                ),
                # Blocks represent DOM paragraphs: no blank line between consecutive bullet items.
                "blocks": [
                    {"kind": "h6", "text": "update"},
                    {"kind": "p", "text": marker_param},
                    {"kind": "p", "text": marker_desc},
                    {"kind": "p", "text": "--active=<flag>"},
                    {"kind": "p", "text": "Active flag."},
                    {"kind": "p", "text": f"{allowed}:"},
                    {"kind": "p", "text": f"{bullet} yes - enable."},
                    {"kind": "p", "text": f"{bullet} no - disable."},
                ],
            },
        ],
    }

    catalog = build_base_catalog_from_its(payload)
    cmd = catalog["commands_by_id"]["infobase.extension.update"]
    active = (cmd.get("params_by_name") or {}).get("active")
    assert active is not None
    assert active.get("enum") == ["yes", "no"]

    errors = validate_catalog_v2(catalog)
    assert errors == []

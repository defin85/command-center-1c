from apps.operations.cli_catalog import build_cli_catalog_from_its


def _ru(s: str) -> str:
    return s.encode("utf-8").decode("unicode_escape")


def test_build_cli_catalog_from_its_prefers_blocks_lang_parameter():
    payload = {
        "version": "8.3.27",
        "doc_url": "https://its.1c.ru/db/v8327doc#bookmark:adm:TI000000493",
        "sections": [
            {
                "id": "TI000000811",
                "title": "7.3.2. Настройка аутентификации",
                "text": "",
                "blocks": [
                    {"kind": "p", "class": "Lang-parameter", "text": "/AccessToken"},
                    {
                        "kind": "p",
                        "class": "MsoNormal",
                        "text": _ru(
                            "\\u041f\\u043e\\u0437\\u0432\\u043e\\u043b\\u044f\\u0435\\u0442 "
                            "\\u0443\\u043a\\u0430\\u0437\\u0430\\u0442\\u044c JWT "
                            "\\u0434\\u043b\\u044f \\u0432\\u044b\\u043f\\u043e\\u043b\\u043d\\u0435\\u043d\\u0438\\u044f "
                            "\\u0430\\u0443\\u0442\\u0435\\u043d\\u0442\\u0438\\u0444\\u0438\\u043a\\u0430\\u0446\\u0438\\u0438 "
                            "\\u043f\\u043e\\u043b\\u044c\\u0437\\u043e\\u0432\\u0430\\u0442\\u0435\\u043b\\u044f."
                        ),
                    },
                ],
            }
        ],
    }

    catalog = build_cli_catalog_from_its(payload)
    by_id = {c["id"]: c for c in catalog["commands"]}

    cmd = by_id["AccessToken"]
    assert cmd["usage"] == "/AccessToken"
    assert cmd["params"] == []
    assert cmd["source_section_id"] == "TI000000811"
    assert cmd["source_section"] == "7.3.2. Настройка аутентификации"


def test_build_cli_catalog_from_its_parses_nested_optional_groups_and_alternations():
    addr_proxy = _ru("\\u0430\\u0434\\u0440\\u0435\\u0441 \\u043f\\u0440\\u043e\\u043a\\u0441\\u0438")
    port = _ru("\\u043f\\u043e\\u0440\\u0442")
    user_proxy = _ru(
        "\\u0438\\u043c\\u044f \\u043f\\u043e\\u043b\\u044c\\u0437\\u043e\\u0432\\u0430\\u0442\\u0435\\u043b\\u044f "
        "\\u043f\\u0440\\u043e\\u043a\\u0441\\u0438"
    )
    password = _ru("\\u043f\\u0430\\u0440\\u043e\\u043b\\u044c")

    payload = {
        "version": "8.3.27",
        "doc_url": "https://its.1c.ru/db/v8327doc#bookmark:adm:TI000000493",
        "sections": [
            {
                "id": "TI000000810",
                "title": "7.3.1. Указание параметров подключения",
                "text": "",
                "blocks": [
                    {
                        "kind": "p",
                        "class": "Lang-parameter",
                        "text": f"/Proxy -PSrv <{addr_proxy}> -PPort <{port}> [-PUser <{user_proxy}> [-PPwd <{password}>]]",
                    },
                    {"kind": "p", "class": "MsoNormal", "text": _ru("\\u0418\\u0441\\u043f\\u043e\\u043b\\u044c\\u0437\\u043e\\u0432\\u0430\\u0442\\u044c \\u0443\\u043a\\u0430\\u0437\\u0430\\u043d\\u043d\\u044b\\u0435 \\u043d\\u0430\\u0441\\u0442\\u0440\\u043e\\u0439\\u043a\\u0438 \\u043f\\u0440\\u043e\\u043a\\u0441\\u0438.")},
                    {"kind": "p", "class": "Lang-parameter", "text": "/AllowExecuteScheduledJobs -Off|-Force"},
                    {"kind": "p", "class": "MsoNormal", "text": _ru("\\u0423\\u043f\\u0440\\u0430\\u0432\\u043b\\u0435\\u043d\\u0438\\u0435 \\u0437\\u0430\\u043f\\u0443\\u0441\\u043a\\u043e\\u043c \\u0440\\u0435\\u0433\\u043b\\u0430\\u043c\\u0435\\u043d\\u0442\\u043d\\u044b\\u0445 \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0439.")},
                ],
            }
        ],
    }

    catalog = build_cli_catalog_from_its(payload)
    by_id = {c["id"]: c for c in catalog["commands"]}

    proxy = by_id["Proxy"]
    assert proxy["usage"].startswith("/Proxy")
    assert proxy["params"] == [
        {"name": "PSrv", "kind": "flag", "flag": "-PSrv", "required": True, "label": addr_proxy, "expects_value": True},
        {"name": "PPort", "kind": "flag", "flag": "-PPort", "required": True, "label": port, "expects_value": True},
        {
            "name": "PUser",
            "kind": "flag",
            "flag": "-PUser",
            "required": False,
            "label": user_proxy,
            "expects_value": True,
        },
        {"name": "PPwd", "kind": "flag", "flag": "-PPwd", "required": False, "label": password, "expects_value": True},
    ]

    jobs = by_id["AllowExecuteScheduledJobs"]
    assert jobs["usage"] == "/AllowExecuteScheduledJobs -Off|-Force"
    # We can't model "one-of" requirement in CLI v1 schema; keep both flags non-required.
    assert jobs["params"] == [
        {"name": "Off", "kind": "flag", "flag": "-Off", "required": False, "label": "-Off", "expects_value": False},
        {"name": "Force", "kind": "flag", "flag": "-Force", "required": False, "label": "-Force", "expects_value": False},
    ]

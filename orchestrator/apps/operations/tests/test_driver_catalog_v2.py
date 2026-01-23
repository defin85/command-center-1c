from apps.operations.driver_catalog_v2 import cli_catalog_v1_to_v2


def test_cli_catalog_v1_to_v2_includes_default_driver_schema():
    legacy = {
        "version": "8.3.27",
        "source": "its_import",
        "generated_at": "2026-01-23T00:00:00Z",
        "commands": [
            {
                "id": "Proxy",
                "label": "Proxy",
                "description": "Set proxy options.",
                "params": [
                    {"name": "PSrv", "kind": "flag", "flag": "-PSrv", "expects_value": True, "required": True},
                ],
            },
        ],
    }

    catalog = cli_catalog_v1_to_v2(legacy)
    assert catalog["catalog_version"] == 2
    assert catalog["driver"] == "cli"
    assert catalog["platform_version"] == "8.3.27"

    driver_schema = catalog.get("driver_schema")
    assert isinstance(driver_schema, dict)
    assert "cli_options" in driver_schema
    assert "ui" in driver_schema
    assert driver_schema["ui"]["version"] == 1


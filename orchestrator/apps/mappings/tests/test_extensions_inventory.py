from apps.mappings.extensions_inventory import build_canonical_extensions_inventory


def test_build_canonical_extensions_inventory_includes_optional_fields():
    payload = {
        "extensions": [
            {
                "name": " A ",
                "version": " 1.0 ",
                "is_active": True,
                "purpose": " patch ",
                "safe_mode": False,
                "unsafe_action_protection": True,
            },
            {
                "name": "B",
                "purpose": None,
                "safe_mode": "no",
                "unsafe_action_protection": 0,
            },
            {"name": ""},
            "not-an-object",
        ]
    }

    canonical = build_canonical_extensions_inventory(payload, spec={})
    assert canonical == {
        "extensions": [
            {
                "name": "A",
                "purpose": "patch",
                "version": "1.0",
                "is_active": True,
                "safe_mode": False,
                "unsafe_action_protection": True,
            },
            {"name": "B"},
        ]
    }


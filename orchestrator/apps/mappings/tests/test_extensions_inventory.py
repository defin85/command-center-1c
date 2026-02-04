from apps.mappings.extensions_inventory import build_canonical_extensions_inventory, validate_extensions_inventory


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


def test_validate_extensions_inventory_accepts_canonical_shape():
    payload = {
        "extensions": [
            {"name": "A", "purpose": "patch", "version": "1.0", "is_active": True, "safe_mode": False, "unsafe_action_protection": True},
            {"name": "B"},
        ]
    }
    assert validate_extensions_inventory(payload) == []


def test_validate_extensions_inventory_rejects_unknown_fields_and_types():
    payload = {
        "extensions": [
            {"name": "A", "unknown": 123},
            {"name": "B", "safe_mode": "no"},
        ],
        "extra": True,
    }
    errors = validate_extensions_inventory(payload)
    assert "unexpected top-level key: extra" in errors
    assert "extensions[0].unknown is not allowed" in errors
    assert "extensions[1].safe_mode must be a boolean" in errors

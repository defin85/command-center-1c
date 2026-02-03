from apps.databases.extensions_snapshot import (
    build_extensions_snapshot_from_worker_result,
    parse_extensions_stdout,
)


def test_parse_extensions_stdout_kv_format():
    stdout = 'name : "test" version : "1.2.3" active : yes purpose : add-on'
    items = parse_extensions_stdout(stdout)
    assert items == [{"name": "test", "version": "1.2.3", "is_active": True, "purpose": "add-on"}]


def test_parse_extensions_stdout_kv_format_parses_extended_fields():
    stdout = "\n".join([
        'name : "EF_10236744_4"',
        "version :",
        "active : yes",
        "purpose : patch",
        "safe-mode : no",
        "security-profile-name :",
        "unsafe-action-protection : no",
        "used-in-distributed-infobase : yes",
        "scope : infobase",
        'hash-sum : "56pD01LTf43r4q+f7HKWxkeqJwE="',
        "",
    ])
    items = parse_extensions_stdout(stdout)
    assert items == [{
        "name": "EF_10236744_4",
        "is_active": True,
        "purpose": "patch",
        "safe_mode": False,
        "unsafe_action_protection": False,
        "used_in_distributed_infobase": True,
        "scope": "infobase",
        "hash_sum": "56pD01LTf43r4q+f7HKWxkeqJwE=",
    }]


def test_parse_extensions_stdout_table_format_pipe():
    stdout = "\n".join([
        "name | version | active",
        "ExtA | 1.0 | yes",
        "ExtB | 2.0 | no",
    ])
    items = parse_extensions_stdout(stdout)
    assert items == [
        {"name": "ExtA", "version": "1.0", "is_active": True},
        {"name": "ExtB", "version": "2.0", "is_active": False},
    ]


def test_parse_extensions_stdout_json_format():
    stdout = '[{"name":"ExtA","version":"1.0","active":"yes"}]'
    items = parse_extensions_stdout(stdout)
    assert items == [{"name": "ExtA", "version": "1.0", "is_active": True}]


def test_build_extensions_snapshot_from_worker_result_parses_stdout():
    stdout = 'name : "test" version : "1.2.3" active : yes'
    snapshot = build_extensions_snapshot_from_worker_result({"stdout": stdout})
    assert snapshot["extensions"] == [{"name": "test", "version": "1.2.3", "is_active": True}]
    assert snapshot["parse_error"] is None
    assert snapshot["raw"] == {"stdout": stdout}


def test_build_extensions_snapshot_from_worker_result_missing_stdout_sets_parse_error():
    snapshot = build_extensions_snapshot_from_worker_result({"stderr": "no stdout"})
    assert snapshot["extensions"] == []
    assert snapshot["parse_error"]
    assert snapshot["raw"] == {"stderr": "no stdout"}

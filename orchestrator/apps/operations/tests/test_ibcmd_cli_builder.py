import pytest

from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    mask_argv,
)


def test_mask_argv_masks_sensitive_flags():
    masked = mask_argv([
        "--db-pwd=secret",
        "--password=secret",
        "--token=abc",
        "--api-key=xyz",
        "--normal=value",
    ])

    assert masked[0] == "--db-pwd=***"
    assert masked[1] == "--password=***"
    assert masked[2] == "--token=***"
    assert masked[3] == "--api-key=***"
    assert masked[4] == "--normal=value"


def test_build_ibcmd_cli_argv_builds_flags_and_masks_sensitive_values():
    command = {
        "argv": ["server", "config", "init"],
        "params_by_name": {
            "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
            "db_pwd": {"kind": "flag", "flag": "--db-pwd", "expects_value": True, "required": True},
            "verbose": {"kind": "flag", "flag": "--verbose", "expects_value": False, "required": False},
        },
    }
    argv, masked = build_ibcmd_cli_argv(
        command=command,
        params={
            "remote": "http://host:1545",
            "db_pwd": "secret",
            "verbose": True,
            "user": "should_be_stripped",
            "password": "should_be_stripped",
        },
        additional_args=["--password=from_args", "--foo=bar"],
    )

    assert argv[:3] == ["server", "config", "init"]
    assert "--remote=http://host:1545" in argv
    assert "--db-pwd=secret" in argv
    assert "--verbose" in argv
    assert "--foo=bar" in argv
    assert not any(token.lower().startswith("--password") for token in argv)
    assert not any(token.lower().startswith("--user") for token in argv)

    assert "--db-pwd=***" in masked
    assert "--remote=http://host:1545" in masked


def test_build_ibcmd_cli_argv_rejects_unknown_params():
    command = {
        "argv": ["server", "config", "init"],
        "params_by_name": {
            "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
        },
    }

    with pytest.raises(ValueError, match=r"unknown params: extra"):
        build_ibcmd_cli_argv(
            command=command,
            params={"remote": "http://host:1545", "extra": "1"},
            additional_args=[],
        )


def test_build_ibcmd_cli_argv_requires_required_param():
    command = {
        "argv": ["server", "config", "init"],
        "params_by_name": {
            "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
        },
    }

    with pytest.raises(ValueError, match=r"missing required param: remote"):
        build_ibcmd_cli_argv(command=command, params={}, additional_args=[])


def test_build_ibcmd_cli_argv_builds_positionals_in_order():
    command = {
        "argv": ["infobase", "extension", "update"],
        "params_by_name": {
            "first": {"kind": "positional", "position": 2, "required": True},
            "second": {"kind": "positional", "position": 1, "required": True},
        },
    }

    argv, _ = build_ibcmd_cli_argv(
        command=command,
        params={"first": "A", "second": "B"},
        additional_args=[],
    )

    assert argv == ["infobase", "extension", "update", "B", "A"]


def test_build_ibcmd_cli_argv_validates_enum_values():
    command = {
        "argv": ["server", "config", "init"],
        "params_by_name": {
            "safe_mode": {
                "kind": "flag",
                "flag": "--safe-mode",
                "expects_value": True,
                "required": True,
                "enum": ["yes", "no"],
            },
        },
    }

    with pytest.raises(ValueError, match=r"invalid safe_mode"):
        build_ibcmd_cli_argv(command=command, params={"safe_mode": "maybe"}, additional_args=[])


def test_build_ibcmd_cli_argv_manual_ignores_unknown_params_and_required_constraints():
    command = {
        "argv": ["server", "config", "init"],
        "params_by_name": {
            "remote": {"kind": "flag", "flag": "--remote", "expects_value": True, "required": True},
        },
    }

    argv, masked = build_ibcmd_cli_argv_manual(
        command=command,
        params={"unknown": "1"},
        additional_args=["--password=secret", "--bar=baz"],
    )

    assert argv == ["server", "config", "init", "--bar=baz"]
    assert masked == ["server", "config", "init", "--bar=baz"]

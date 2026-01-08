"""Tests for IBCMD backend support helpers."""

from apps.templates.workflow.handlers.backends.ibcmd import IBCMDBackend


def test_ibcmd_backend_supports_types():
    backend = IBCMDBackend()

    assert backend.supports_operation_type('ibcmd_cli') is True
    assert backend.supports_operation_type('create') is False


def test_ibcmd_backend_get_supported_types():
    supported = IBCMDBackend.get_supported_types()
    assert 'ibcmd_cli' in supported

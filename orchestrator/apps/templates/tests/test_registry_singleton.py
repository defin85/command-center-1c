# orchestrator/apps/templates/tests/test_registry_singleton.py
"""
Tests for OperationTypeRegistry singleton behavior.
"""

import pytest

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
    OperationTypeRegistry,
)


class TestOperationTypeRegistrySingleton:
    """Tests for OperationTypeRegistry singleton pattern."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Clean registry before and after each test."""
        registry = get_registry()
        registry.clear()
        yield
        registry.clear()

    def test_singleton_instance(self):
        """Test that OperationTypeRegistry is a singleton."""
        r1 = OperationTypeRegistry()
        r2 = OperationTypeRegistry()

        assert r1 is r2

    def test_get_registry_returns_singleton(self):
        """Test get_registry() returns singleton."""
        r1 = get_registry()
        r2 = get_registry()

        assert r1 is r2

    def test_get_registry_same_as_direct_instantiation(self):
        """Test get_registry() returns same as direct instantiation."""
        r1 = get_registry()
        r2 = OperationTypeRegistry()

        assert r1 is r2

    def test_singleton_preserves_state(self):
        """Test singleton preserves registered operations across calls."""
        registry = get_registry()

        op = OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        registry.register(op)

        # Get new reference
        r2 = OperationTypeRegistry()
        assert r2.is_valid('test_op')


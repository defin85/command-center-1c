# orchestrator/apps/templates/tests/test_registry_registration.py
"""
Tests for registry registration operations.
"""

import pytest

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)


class TestOperationTypeRegistryRegistration:
    """Tests for registry registration operations."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Clean registry before and after each test."""
        registry = get_registry()
        registry.clear()
        yield
        registry.clear()

    def test_register_single_operation(self):
        """Test registering a single operation."""
        registry = get_registry()

        op = OperationType(
            id='test_op',
            name='Test Operation',
            description='Test',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        registry.register(op)

        assert registry.is_valid('test_op')
        assert registry.get('test_op') == op

    def test_register_multiple_operations(self):
        """Test registering multiple operations."""
        registry = get_registry()

        op1 = OperationType(
            id='op1',
            name='Op 1',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )
        op2 = OperationType(
            id='op2',
            name='Op 2',
            description='',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
        )

        registry.register(op1)
        registry.register(op2)

        assert registry.is_valid('op1')
        assert registry.is_valid('op2')
        assert len(registry.get_all()) == 2

    def test_register_many(self):
        """Test register_many() method."""
        registry = get_registry()

        ops = [
            OperationType(
                id=f'op{i}',
                name=f'Op {i}',
                description='',
                backend=BackendType.RAS if i % 2 == 0 else BackendType.ODATA,
                target_entity=TargetEntity.INFOBASE if i % 2 == 0 else TargetEntity.ENTITY,
            )
            for i in range(5)
        ]

        registry.register_many(ops)

        assert len(registry.get_all()) == 5
        for op in ops:
            assert registry.is_valid(op.id)

    def test_register_duplicate_same_backend_idempotent(self):
        """Test registering same operation twice is idempotent."""
        registry = get_registry()

        op = OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        registry.register(op)
        registry.register(op)  # Should not raise

        assert len(registry.get_all()) == 1

    def test_register_duplicate_different_backend_raises(self):
        """Test registering same ID with different backend raises error."""
        registry = get_registry()

        op1 = OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )
        op2 = OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
        )

        registry.register(op1)

        with pytest.raises(ValueError) as exc_info:
            registry.register(op2)

        assert 'already registered' in str(exc_info.value)
        assert 'test_op' in str(exc_info.value)

    def test_register_updated_metadata_same_backend_silent(self):
        """Test re-registering with updated metadata is silent."""
        registry = get_registry()

        op1 = OperationType(
            id='test_op',
            name='Old Name',
            description='Old description',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        op2 = OperationType(
            id='test_op',
            name='New Name',
            description='New description',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        registry.register(op1)
        registry.register(op2)  # Should not raise

        # First one stays in registry (idempotent behavior)
        stored = registry.get('test_op')
        assert stored.name == 'Old Name'


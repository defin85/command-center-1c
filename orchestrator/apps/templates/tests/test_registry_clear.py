# orchestrator/apps/templates/tests/test_registry_clear.py
"""
Tests for registry cleanup.
"""

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)


class TestOperationTypeRegistryClear:
    """Tests for registry cleanup."""

    def test_clear_empties_registry(self):
        """Test clear() removes all operations."""
        registry = get_registry()

        registry.register(
            OperationType(
                id='test_op',
                name='Test',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )

        assert len(registry.get_all()) == 1

        registry.clear()

        assert len(registry.get_all()) == 0
        assert registry.is_valid('test_op') is False

    def test_clear_resets_by_backend(self):
        """Test clear() resets by_backend tracking."""
        registry = get_registry()

        registry.register(
            OperationType(
                id='ras_op',
                name='RAS Op',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )

        assert len(registry.get_by_backend(BackendType.RAS)) == 1

        registry.clear()

        assert len(registry.get_by_backend(BackendType.RAS)) == 0

    def test_clear_allows_reregistration(self):
        """Test operations can be re-registered after clear."""
        registry = get_registry()

        op = OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        registry.register(op)
        registry.clear()
        registry.register(op)  # Should not raise

        assert registry.is_valid('test_op')


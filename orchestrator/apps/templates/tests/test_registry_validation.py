# orchestrator/apps/templates/tests/test_registry_validation.py
"""
Tests for registry validation operations.
"""

import pytest

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)


class TestOperationTypeRegistryValidation:
    """Tests for registry validation operations."""

    @pytest.fixture(autouse=True)
    def setup_operations(self):
        """Setup test operations."""
        registry = get_registry()
        registry.clear()

        registry.register(
            OperationType(
                id='test_op',
                name='Test',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )

        yield

        registry.clear()

    def test_validate_valid_operation(self):
        """Test validate() doesn't raise for valid operation."""
        registry = get_registry()

        # Should not raise
        registry.validate('test_op')

    def test_validate_invalid_operation_raises(self):
        """Test validate() raises ValueError for invalid operation."""
        registry = get_registry()

        with pytest.raises(ValueError) as exc_info:
            registry.validate('nonexistent')

        assert 'Unknown operation type' in str(exc_info.value)
        assert 'nonexistent' in str(exc_info.value)

    def test_validate_error_lists_valid_types(self):
        """Test validate() error message lists valid types."""
        registry = get_registry()

        with pytest.raises(ValueError) as exc_info:
            registry.validate('invalid')

        error_msg = str(exc_info.value)
        assert 'test_op' in error_msg
        assert 'Valid types' in error_msg


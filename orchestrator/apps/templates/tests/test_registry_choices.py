# orchestrator/apps/templates/tests/test_registry_choices.py
"""
Tests for registry choice generation.
"""

import pytest

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)


class TestOperationTypeRegistryChoices:
    """Tests for registry choice generation."""

    @pytest.fixture(autouse=True)
    def setup_operations(self):
        """Setup test operations with specific IDs for sorting."""
        registry = get_registry()
        registry.clear()

        registry.register(
            OperationType(
                id='z_operation',
                name='Z Operation',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )
        registry.register(
            OperationType(
                id='a_operation',
                name='A Operation',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )
        registry.register(
            OperationType(
                id='m_operation',
                name='M Operation',
                description='',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
            )
        )

        yield

        registry.clear()

    def test_get_choices_returns_list(self):
        """Test get_choices returns a list."""
        registry = get_registry()
        choices = registry.get_choices()

        assert isinstance(choices, list)

    def test_get_choices_format(self):
        """Test get_choices returns tuples of (id, name)."""
        registry = get_registry()
        choices = registry.get_choices()

        for choice in choices:
            assert isinstance(choice, tuple)
            assert len(choice) == 2
            assert isinstance(choice[0], str)
            assert isinstance(choice[1], str)

    def test_get_choices_sorted(self):
        """Test get_choices returns sorted by operation ID."""
        registry = get_registry()
        choices = registry.get_choices()

        assert len(choices) == 3
        assert choices[0][0] == 'a_operation'
        assert choices[1][0] == 'm_operation'
        assert choices[2][0] == 'z_operation'

    def test_get_choices_empty_registry(self):
        """Test get_choices on empty registry."""
        registry = get_registry()
        registry.clear()

        choices = registry.get_choices()

        assert choices == []


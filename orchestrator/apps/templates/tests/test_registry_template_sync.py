# orchestrator/apps/templates/tests/test_registry_template_sync.py
"""
Tests for template synchronization data format.
"""

import pytest

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)


class TestOperationTypeRegistryTemplateSyncData:
    """Tests for template synchronization data format."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Clean registry before and after each test."""
        registry = get_registry()
        registry.clear()
        yield
        registry.clear()

    def test_get_for_template_sync_format(self):
        """Test get_for_template_sync returns correct data format."""
        registry = get_registry()

        registry.register(
            OperationType(
                id='test_operation',
                name='Test Operation',
                description='Test description',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )

        data = registry.get_for_template_sync()

        assert len(data) == 1
        item = data[0]

        assert 'id' in item
        assert 'name' in item
        assert 'description' in item
        assert 'operation_type' in item
        assert 'target_entity' in item
        assert 'template_data' in item
        assert 'is_active' in item

    def test_get_for_template_sync_id_conversion(self):
        """Test ID conversion from operation_id to template ID."""
        registry = get_registry()

        registry.register(
            OperationType(
                id='lock_scheduled_jobs',
                name='Lock Scheduled Jobs',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
        )

        data = registry.get_for_template_sync()

        item = data[0]
        assert item['id'] == 'tpl-lock-scheduled-jobs'
        assert item['operation_type'] == 'lock_scheduled_jobs'

    def test_get_for_template_sync_values(self):
        """Test correct values in sync data."""
        registry = get_registry()

        op = OperationType(
            id='test_op',
            name='Test Op',
            description='Test description',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
        )

        registry.register(op)

        data = registry.get_for_template_sync()
        item = data[0]

        assert item['name'] == 'Test Op'
        assert item['description'] == 'Test description'
        assert item['operation_type'] == 'test_op'
        assert item['target_entity'] == 'entity'
        assert item['is_active'] is True

    def test_get_for_template_sync_includes_template_data(self):
        """Test that template_data is included in sync data."""
        registry = get_registry()

        registry.register(
            OperationType(
                id='test_op',
                name='Test Op',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
                timeout_seconds=600,
            )
        )

        data = registry.get_for_template_sync()
        item = data[0]

        assert 'template_data' in item
        template_data = item['template_data']
        assert template_data['backend'] == 'ras'
        assert template_data['timeout_seconds'] == 600

    def test_get_for_template_sync_multiple_operations(self):
        """Test sync data for multiple operations."""
        registry = get_registry()

        for i in range(3):
            registry.register(
                OperationType(
                    id=f'op_{i}',
                    name=f'Operation {i}',
                    description='',
                    backend=BackendType.RAS,
                    target_entity=TargetEntity.INFOBASE,
                )
            )

        data = registry.get_for_template_sync()

        assert len(data) == 3
        ids = {item['operation_type'] for item in data}
        assert ids == {'op_0', 'op_1', 'op_2'}


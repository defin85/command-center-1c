# orchestrator/apps/templates/tests/test_registry_retrieval.py
"""
Tests for registry retrieval operations.
"""

import pytest

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
)


class TestOperationTypeRegistryRetrieval:
    """Tests for registry retrieval operations."""

    @pytest.fixture(autouse=True)
    def setup_operations(self):
        """Setup test operations in registry."""
        registry = get_registry()
        registry.clear()

        ops = [
            OperationType(
                id='lock_jobs',
                name='Lock Jobs',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            ),
            OperationType(
                id='unlock_jobs',
                name='Unlock Jobs',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            ),
            OperationType(
                id='create',
                name='Create Entity',
                description='',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
            ),
            OperationType(
                id='update',
                name='Update Entity',
                description='',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
            ),
            OperationType(
                id='delete',
                name='Delete Entity',
                description='',
                backend=BackendType.ODATA,
                target_entity=TargetEntity.ENTITY,
            ),
        ]

        registry.register_many(ops)

        yield

        registry.clear()

    def test_get_operation_exists(self):
        """Test getting existing operation."""
        registry = get_registry()
        op = registry.get('lock_jobs')

        assert op is not None
        assert op.id == 'lock_jobs'
        assert op.name == 'Lock Jobs'

    def test_get_operation_not_exists(self):
        """Test getting non-existent operation returns None."""
        registry = get_registry()
        op = registry.get('nonexistent')

        assert op is None

    def test_get_all_operations(self):
        """Test getting all operations."""
        registry = get_registry()
        all_ops = registry.get_all()

        assert len(all_ops) == 5
        ids = {op.id for op in all_ops}
        assert 'lock_jobs' in ids
        assert 'create' in ids

    def test_get_by_backend_ras(self):
        """Test filtering operations by RAS backend."""
        registry = get_registry()
        ras_ops = registry.get_by_backend(BackendType.RAS)

        assert len(ras_ops) == 2
        ids = {op.id for op in ras_ops}
        assert 'lock_jobs' in ids
        assert 'unlock_jobs' in ids

    def test_get_by_backend_odata(self):
        """Test filtering operations by OData backend."""
        registry = get_registry()
        odata_ops = registry.get_by_backend(BackendType.ODATA)

        assert len(odata_ops) == 3
        ids = {op.id for op in odata_ops}
        assert 'create' in ids
        assert 'update' in ids
        assert 'delete' in ids

    def test_get_by_backend_empty(self):
        """Test get_by_backend returns empty list for unknown backend."""
        registry = get_registry()
        registry.clear()

        ras_ops = registry.get_by_backend(BackendType.RAS)
        assert len(ras_ops) == 0

    def test_get_ids(self):
        """Test get_ids returns set of all operation IDs."""
        registry = get_registry()
        ids = registry.get_ids()

        assert isinstance(ids, set)
        assert len(ids) == 5
        assert 'lock_jobs' in ids
        assert 'create' in ids

    def test_is_valid_true(self):
        """Test is_valid returns True for registered operation."""
        registry = get_registry()

        assert registry.is_valid('lock_jobs') is True
        assert registry.is_valid('create') is True

    def test_is_valid_false(self):
        """Test is_valid returns False for unregistered operation."""
        registry = get_registry()

        assert registry.is_valid('nonexistent') is False
        assert registry.is_valid('') is False


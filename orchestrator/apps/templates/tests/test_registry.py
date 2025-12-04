# orchestrator/apps/templates/tests/test_registry.py
"""
Comprehensive tests for OperationType Registry.

Tests cover:
- OperationType dataclass functionality
- ParameterSchema validation
- OperationTypeRegistry singleton pattern
- Thread-safe registration
- Registry operations (get, filter, validate)
- Choice generation for Django forms
- Template synchronization data format
"""

import pytest
from threading import Thread, Lock
from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
    ParameterSchema,
    OperationTypeRegistry,
)


class TestParameterSchema:
    """Tests for ParameterSchema dataclass."""

    def test_required_parameter(self):
        """Test creating required parameter schema."""
        param = ParameterSchema(
            name='database_id',
            type='string',
            required=True,
            description='Database identifier',
        )

        assert param.name == 'database_id'
        assert param.type == 'string'
        assert param.required is True
        assert param.description == 'Database identifier'
        assert param.default is None

    def test_optional_parameter_with_default(self):
        """Test creating optional parameter with default value."""
        param = ParameterSchema(
            name='timeout',
            type='integer',
            required=False,
            description='Operation timeout in seconds',
            default=300,
        )

        assert param.name == 'timeout'
        assert param.type == 'integer'
        assert param.required is False
        assert param.default == 300

    def test_parameter_types(self):
        """Test various parameter types."""
        valid_types = ['string', 'integer', 'boolean', 'uuid', 'json']

        for ptype in valid_types:
            param = ParameterSchema(name='test', type=ptype)
            assert param.type == ptype

    def test_parameter_with_json_default(self):
        """Test parameter with JSON default value."""
        param = ParameterSchema(
            name='metadata',
            type='json',
            required=False,
            default={'key': 'value'},
        )

        assert param.default == {'key': 'value'}

    def test_parameter_equality(self):
        """Test parameter schema equality."""
        param1 = ParameterSchema(name='test', type='string')
        param2 = ParameterSchema(name='test', type='string')

        assert param1 == param2

    def test_parameter_inequality_different_names(self):
        """Test parameter inequality when names differ."""
        param1 = ParameterSchema(name='test1', type='string')
        param2 = ParameterSchema(name='test2', type='string')

        assert param1 != param2


class TestOperationType:
    """Tests for OperationType dataclass."""

    def test_minimal_operation_type(self):
        """Test creating operation type with minimal required fields."""
        op = OperationType(
            id='test_op',
            name='Test Operation',
            description='Test description',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        assert op.id == 'test_op'
        assert op.name == 'Test Operation'
        assert op.description == 'Test description'
        assert op.backend == BackendType.RAS
        assert op.target_entity == TargetEntity.INFOBASE
        assert op.required_parameters == []
        assert op.optional_parameters == []
        assert op.is_async is False
        assert op.timeout_seconds == 300
        assert op.max_retries == 3
        assert op.category == 'general'
        assert op.tags == []

    def test_full_operation_type(self):
        """Test creating operation type with all fields."""
        required_params = [
            ParameterSchema('cluster_id', 'string', description='Cluster ID'),
            ParameterSchema('username', 'string', description='Username'),
        ]
        optional_params = [
            ParameterSchema('password', 'string', required=False),
            ParameterSchema('timeout', 'integer', required=False, default=60),
        ]

        op = OperationType(
            id='lock_scheduled_jobs',
            name='Lock Scheduled Jobs',
            description='Disable all scheduled jobs on infobase',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=required_params,
            optional_parameters=optional_params,
            is_async=True,
            timeout_seconds=600,
            max_retries=5,
            category='admin',
            tags=['jobs', 'cluster', 'safety'],
        )

        assert op.id == 'lock_scheduled_jobs'
        assert op.name == 'Lock Scheduled Jobs'
        assert len(op.required_parameters) == 2
        assert len(op.optional_parameters) == 2
        assert op.is_async is True
        assert op.timeout_seconds == 600
        assert op.max_retries == 5
        assert op.category == 'admin'
        assert 'jobs' in op.tags

    def test_to_choice(self):
        """Test conversion to Django choices format."""
        op = OperationType(
            id='test_op',
            name='Test Operation',
            description='Test',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        choice = op.to_choice()

        assert isinstance(choice, tuple)
        assert len(choice) == 2
        assert choice == ('test_op', 'Test Operation')

    def test_to_template_data_minimal(self):
        """Test conversion to template_data with minimal fields."""
        op = OperationType(
            id='test_op',
            name='Test Op',
            description='Test',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        data = op.to_template_data()

        assert 'backend' in data
        assert data['backend'] == 'ras'
        assert 'is_async' in data
        assert data['is_async'] is False
        assert 'timeout_seconds' in data
        assert data['timeout_seconds'] == 300
        assert 'max_retries' in data
        assert data['max_retries'] == 3
        assert 'required_parameters' in data
        assert data['required_parameters'] == []
        assert 'optional_parameters' in data
        assert data['optional_parameters'] == []
        assert 'parameter_schemas' in data
        assert data['parameter_schemas'] == {}
        assert data['category'] == 'general'
        assert data['tags'] == []

    def test_to_template_data_with_parameters(self):
        """Test template_data conversion with parameters."""
        op = OperationType(
            id='test_op',
            name='Test Op',
            description='Test',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
            required_parameters=[
                ParameterSchema('entity_id', 'uuid', description='Entity UUID'),
                ParameterSchema('data', 'json', description='Entity data'),
            ],
            optional_parameters=[
                ParameterSchema('metadata', 'json', required=False, default={}),
            ],
        )

        data = op.to_template_data()

        assert 'entity_id' in data['required_parameters']
        assert 'data' in data['required_parameters']
        assert 'metadata' in data['optional_parameters']

        assert 'entity_id' in data['parameter_schemas']
        assert data['parameter_schemas']['entity_id']['type'] == 'uuid'
        assert data['parameter_schemas']['entity_id']['required'] is True
        assert 'Entity UUID' in data['parameter_schemas']['entity_id']['description']

        assert 'metadata' in data['parameter_schemas']
        assert data['parameter_schemas']['metadata']['required'] is False

    def test_backend_values(self):
        """Test operation types with both backend values."""
        ras_op = OperationType(
            id='ras_op',
            name='RAS Op',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        odata_op = OperationType(
            id='odata_op',
            name='OData Op',
            description='',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
        )

        assert ras_op.to_template_data()['backend'] == 'ras'
        assert odata_op.to_template_data()['backend'] == 'odata'

    def test_target_entity_values(self):
        """Test operation types with various target entities."""
        infobase_op = OperationType(
            id='op1',
            name='Op 1',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        )

        cluster_op = OperationType(
            id='op2',
            name='Op 2',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.CLUSTER,
        )

        entity_op = OperationType(
            id='op3',
            name='Op 3',
            description='',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
        )

        assert infobase_op.target_entity == TargetEntity.INFOBASE
        assert cluster_op.target_entity == TargetEntity.CLUSTER
        assert entity_op.target_entity == TargetEntity.ENTITY


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


class TestOperationTypeRegistryValidation:
    """Tests for registry validation operations."""

    @pytest.fixture(autouse=True)
    def setup_operations(self):
        """Setup test operations."""
        registry = get_registry()
        registry.clear()

        registry.register(OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

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


class TestOperationTypeRegistryChoices:
    """Tests for registry choice generation."""

    @pytest.fixture(autouse=True)
    def setup_operations(self):
        """Setup test operations with specific IDs for sorting."""
        registry = get_registry()
        registry.clear()

        registry.register(OperationType(
            id='z_operation',
            name='Z Operation',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))
        registry.register(OperationType(
            id='a_operation',
            name='A Operation',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))
        registry.register(OperationType(
            id='m_operation',
            name='M Operation',
            description='',
            backend=BackendType.ODATA,
            target_entity=TargetEntity.ENTITY,
        ))

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

        registry.register(OperationType(
            id='test_operation',
            name='Test Operation',
            description='Test description',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

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

        registry.register(OperationType(
            id='lock_scheduled_jobs',
            name='Lock Scheduled Jobs',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

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

        registry.register(OperationType(
            id='test_op',
            name='Test Op',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            timeout_seconds=600,
        ))

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
            registry.register(OperationType(
                id=f'op_{i}',
                name=f'Operation {i}',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            ))

        data = registry.get_for_template_sync()

        assert len(data) == 3
        ids = {item['operation_type'] for item in data}
        assert ids == {'op_0', 'op_1', 'op_2'}


class TestOperationTypeRegistryClear:
    """Tests for registry cleanup."""

    def test_clear_empties_registry(self):
        """Test clear() removes all operations."""
        registry = get_registry()

        registry.register(OperationType(
            id='test_op',
            name='Test',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

        assert len(registry.get_all()) == 1

        registry.clear()

        assert len(registry.get_all()) == 0
        assert registry.is_valid('test_op') is False

    def test_clear_resets_by_backend(self):
        """Test clear() resets by_backend tracking."""
        registry = get_registry()

        registry.register(OperationType(
            id='ras_op',
            name='RAS Op',
            description='',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
        ))

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


class TestOperationTypeRegistryThreadSafety:
    """Tests for thread-safe singleton access."""

    def test_concurrent_singleton_access(self):
        """Test concurrent access to singleton returns same instance."""
        instances = []
        lock = Lock()

        def get_instance():
            instance = OperationTypeRegistry()
            with lock:
                instances.append(instance)

        threads = [Thread(target=get_instance) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(instances) == 10
        for instance in instances[1:]:
            assert instance is instances[0]

    def test_concurrent_get_registry(self):
        """Test concurrent access via get_registry()."""
        instances = []
        lock = Lock()

        def get_registry_instance():
            instance = get_registry()
            with lock:
                instances.append(instance)

        threads = [Thread(target=get_registry_instance) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(instances) == 10
        for instance in instances[1:]:
            assert instance is instances[0]

    def test_concurrent_registration(self):
        """Test concurrent registration of operations."""
        registry = get_registry()
        registry.clear()

        def register_operation(op_id):
            op = OperationType(
                id=op_id,
                name=f'Op {op_id}',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
            registry.register(op)

        threads = [
            Thread(target=register_operation, args=(f'op_{i}',))
            for i in range(10)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should be registered
        assert len(registry.get_all()) == 10

        registry.clear()

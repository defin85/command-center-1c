# orchestrator/apps/templates/tests/test_registry_operation_type.py
"""
Tests for OperationType dataclass.
"""

from apps.templates.registry import (
    OperationType,
    BackendType,
    TargetEntity,
    ParameterSchema,
)


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

    def test_to_template_data_full(self):
        """Test conversion to template_data includes all fields."""
        required_params = [
            ParameterSchema('cluster_id', 'string', description='Cluster ID'),
        ]
        optional_params = [
            ParameterSchema('timeout', 'integer', required=False, default=60),
        ]

        op = OperationType(
            id='test_op',
            name='Test Op',
            description='Test',
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            required_parameters=required_params,
            optional_parameters=optional_params,
            is_async=True,
            timeout_seconds=600,
            max_retries=5,
            category='admin',
            tags=['tag1', 'tag2'],
        )

        data = op.to_template_data()

        assert data['backend'] == 'ras'
        assert data['is_async'] is True
        assert data['timeout_seconds'] == 600
        assert data['max_retries'] == 5
        assert len(data['required_parameters']) == 1
        assert len(data['optional_parameters']) == 1
        assert data['category'] == 'admin'
        assert data['tags'] == ['tag1', 'tag2']
        assert 'parameter_schemas' in data
        assert 'cluster_id' in data['parameter_schemas']
        assert 'timeout' in data['parameter_schemas']

    def test_backend_values(self):
        """Test operation types with different backends."""
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


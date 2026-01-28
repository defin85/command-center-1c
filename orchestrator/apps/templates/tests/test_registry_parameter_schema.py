# orchestrator/apps/templates/tests/test_registry_parameter_schema.py
"""
Tests for ParameterSchema dataclass.
"""

from apps.templates.registry import ParameterSchema


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


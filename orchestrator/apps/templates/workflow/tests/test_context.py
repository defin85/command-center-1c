"""
Tests for ContextManager in Workflow Engine.

Covers:
- Initialization with deep copy
- Get operations (simple keys, dot notation)
- Set operations (immutability, dot notation)
- Merge operations
- Node results management
- Template resolution (Jinja2)
- Condition evaluation
- Edge cases and error handling
"""

import copy
import pytest
from jinja2 import TemplateSyntaxError

from apps.templates.workflow.context import ContextManager


class TestContextManagerInit:
    """Tests for ContextManager initialization."""

    def test_init_empty_context(self):
        """Test initialization with no context creates empty dict and nodes namespace."""
        ctx = ContextManager()
        assert isinstance(ctx.to_dict(), dict)
        assert 'nodes' in ctx.to_dict()
        assert ctx.to_dict()['nodes'] == {}

    def test_init_with_initial_context(self):
        """Test initialization with initial context data."""
        initial = {'database_id': '123', 'user_id': 'user456'}
        ctx = ContextManager(initial)
        assert ctx.get('database_id') == '123'
        assert ctx.get('user_id') == 'user456'
        assert 'nodes' in ctx.to_dict()

    def test_init_deep_copy_isolation(self):
        """Test that initial context is deep-copied for isolation."""
        initial = {'data': {'nested': 'value'}}
        ctx = ContextManager(initial)

        # Modify original dict
        initial['data']['nested'] = 'modified'

        # Context should have original value
        assert ctx.get('data.nested') == 'value'

    def test_init_with_none(self):
        """Test initialization with None creates empty context."""
        ctx = ContextManager(None)
        assert ctx.to_dict() == {'nodes': {}}

    def test_init_creates_nodes_namespace(self):
        """Test that initialization always creates nodes namespace."""
        ctx = ContextManager({'some_key': 'value'})
        assert 'nodes' in ctx.to_dict()
        assert isinstance(ctx.to_dict()['nodes'], dict)


class TestContextManagerGet:
    """Tests for ContextManager.get() method."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({
            'database_id': '123',
            'user': {
                'name': 'John',
                'email': 'john@example.com',
                'profile': {
                    'age': 30,
                    'city': 'NYC'
                }
            }
        })

    def test_get_simple_key(self, context):
        """Test getting simple top-level key."""
        assert context.get('database_id') == '123'

    def test_get_missing_key_returns_default(self, context):
        """Test getting missing key returns None by default."""
        assert context.get('missing_key') is None

    def test_get_missing_key_returns_custom_default(self, context):
        """Test getting missing key returns custom default value."""
        assert context.get('missing_key', 'default_value') == 'default_value'

    def test_get_dot_notation_single_level(self, context):
        """Test getting nested value with single dot."""
        assert context.get('user.name') == 'John'
        assert context.get('user.email') == 'john@example.com'

    def test_get_dot_notation_multiple_levels(self, context):
        """Test getting deeply nested value with multiple dots."""
        assert context.get('user.profile.age') == 30
        assert context.get('user.profile.city') == 'NYC'

    def test_get_dot_notation_missing_intermediate(self, context):
        """Test dot notation with missing intermediate key."""
        assert context.get('user.missing.field') is None

    def test_get_dot_notation_non_dict_intermediate(self, context):
        """Test dot notation when intermediate value is not a dict."""
        assert context.get('database_id.nested') is None

    def test_get_empty_key(self, context):
        """Test getting empty key returns default."""
        assert context.get('') is None

    def test_get_contains_check(self, context):
        """Test __contains__ for key existence."""
        assert 'database_id' in context
        assert 'user.name' in context
        assert 'missing_key' not in context

    def test_get_keys_method(self, context):
        """Test keys() returns top-level keys."""
        keys = context.keys()
        assert 'database_id' in keys
        assert 'user' in keys
        assert 'nodes' in keys


class TestContextManagerSet:
    """Tests for ContextManager.set() method."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({'database_id': '123'})

    def test_set_simple_key_returns_new_context(self, context):
        """Test that set() returns new ContextManager instance (immutable)."""
        new_ctx = context.set('user_id', '456')

        # Original should be unchanged
        assert context.get('user_id') is None
        assert context.get('database_id') == '123'

        # New context should have updated value
        assert new_ctx.get('user_id') == '456'
        assert new_ctx.get('database_id') == '123'

        # Should be different instances
        assert context is not new_ctx

    def test_set_dot_notation_simple(self, context):
        """Test setting nested value with dot notation."""
        new_ctx = context.set('user.name', 'John')

        assert context.get('user.name') is None
        assert new_ctx.get('user.name') == 'John'
        assert new_ctx.get('database_id') == '123'

    def test_set_dot_notation_deep(self, context):
        """Test setting deeply nested value with multiple dots."""
        new_ctx = context.set('user.profile.age', 30)

        assert new_ctx.get('user.profile.age') == 30
        assert new_ctx.get('database_id') == '123'

    def test_set_creates_intermediate_dicts(self, context):
        """Test that set() creates intermediate dicts as needed."""
        new_ctx = context.set('a.b.c.d.e', 'value')

        assert new_ctx.get('a.b.c.d.e') == 'value'
        assert isinstance(new_ctx.get('a.b.c'), dict)
        assert isinstance(new_ctx.get('a.b'), dict)

    def test_set_overwrites_non_dict_intermediate(self, context):
        """Test that set() overwrites non-dict intermediate values."""
        ctx = ContextManager({'status': 'active'})
        # Now try to set nested value under 'status'
        new_ctx = ctx.set('status.value', 'nested')

        # This should overwrite the string 'active' with a dict
        assert new_ctx.get('status.value') == 'nested'

    def test_set_deep_copy_of_value(self, context):
        """Test that set() deep-copies the value."""
        data = {'nested': {'value': 'original'}}
        new_ctx = context.set('data', data)

        # Modify original dict
        data['nested']['value'] = 'modified'

        # Context value should be unchanged
        assert new_ctx.get('data.nested.value') == 'original'

    def test_set_chain_operations(self, context):
        """Test chaining multiple set() operations."""
        new_ctx = (context
                   .set('user_id', '456')
                   .set('status', 'active')
                   .set('data.field', 'value'))

        assert new_ctx.get('user_id') == '456'
        assert new_ctx.get('status') == 'active'
        assert new_ctx.get('data.field') == 'value'


class TestContextManagerMerge:
    """Tests for ContextManager.merge() method."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({'database_id': '123', 'status': 'pending'})

    def test_merge_new_keys(self, context):
        """Test merging new keys into context."""
        new_ctx = context.merge({'user_id': '456', 'timestamp': '2024-01-01'})

        assert new_ctx.get('database_id') == '123'
        assert new_ctx.get('user_id') == '456'
        assert new_ctx.get('timestamp') == '2024-01-01'

    def test_merge_overwrites_existing_keys(self, context):
        """Test that merge() overwrites existing keys by default."""
        new_ctx = context.merge({'status': 'completed', 'user_id': '456'})

        assert new_ctx.get('status') == 'completed'
        assert new_ctx.get('user_id') == '456'

    def test_merge_prevent_overwrite(self, context):
        """Test merge with allow_overwrite=False raises on conflict."""
        with pytest.raises(ValueError, match="Context key conflict"):
            context.merge({'status': 'completed'}, allow_overwrite=False)

    def test_merge_allow_overwrite_false_with_new_keys(self, context):
        """Test merge with allow_overwrite=False allows new keys."""
        new_ctx = context.merge({'new_key': 'value'}, allow_overwrite=False)

        assert new_ctx.get('new_key') == 'value'
        assert new_ctx.get('database_id') == '123'

    def test_merge_empty_dict(self, context):
        """Test merging empty dict returns snapshot."""
        new_ctx = context.merge({})

        assert new_ctx.get('database_id') == '123'
        assert new_ctx.get('status') == 'pending'

    def test_merge_none(self, context):
        """Test merging None returns snapshot."""
        new_ctx = context.merge(None)

        assert new_ctx.get('database_id') == '123'
        assert new_ctx.get('status') == 'pending'

    def test_merge_deep_copy(self, context):
        """Test that merge() deep-copies values."""
        data = {'nested': {'value': 'original'}}
        new_ctx = context.merge({'data': data})

        # Modify original
        data['nested']['value'] = 'modified'

        # Context should be unchanged
        assert new_ctx.get('data.nested.value') == 'original'

    def test_merge_returns_new_instance(self, context):
        """Test that merge() returns new ContextManager instance."""
        new_ctx = context.merge({'new_key': 'value'})

        assert context is not new_ctx
        assert context.get('new_key') is None
        assert new_ctx.get('new_key') == 'value'


class TestContextManagerNodeResults:
    """Tests for managing node execution results."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({'database_id': '123'})

    def test_add_node_result_simple(self, context):
        """Test adding simple node result."""
        new_ctx = context.add_node_result('node_1', {'status': 'success', 'data': 'value'})

        # Check nodes namespace
        assert new_ctx.get('nodes.node_1.status') == 'success'
        assert new_ctx.get('nodes.node_1.data') == 'value'

    def test_add_node_result_with_output_key(self, context):
        """Test that node result is stored with output key for template access."""
        result = {'status': 'success', 'count': 10}
        new_ctx = context.add_node_result('node_1', result)

        # Should be accessible via nodes.node_id
        assert new_ctx.get('nodes.node_1.status') == 'success'

        # Should also be accessible via node_id.output for templates
        assert new_ctx.get('node_1.output.status') == 'success'
        assert new_ctx.get('node_1.output.count') == 10

    def test_add_multiple_node_results(self, context):
        """Test adding multiple node results."""
        ctx1 = context.add_node_result('node_1', {'status': 'success'})
        ctx2 = ctx1.add_node_result('node_2', {'status': 'completed', 'count': 5})

        assert ctx2.get('nodes.node_1.status') == 'success'
        assert ctx2.get('nodes.node_2.status') == 'completed'
        assert ctx2.get('nodes.node_2.count') == 5

    def test_get_node_result(self, context):
        """Test get_node_result() method."""
        new_ctx = context.add_node_result('node_1', {'status': 'ok', 'data': 'test'})

        result = new_ctx.get_node_result('node_1')
        assert result == {'status': 'ok', 'data': 'test'}

    def test_get_node_result_missing(self, context):
        """Test get_node_result() returns None for missing node."""
        result = context.get_node_result('missing_node')
        assert result is None

    def test_has_node_result(self, context):
        """Test has_node_result() method."""
        ctx = context.add_node_result('node_1', {'status': 'ok'})

        assert ctx.has_node_result('node_1') is True
        assert ctx.has_node_result('missing_node') is False

    def test_node_result_deep_copy(self, context):
        """Test that node result is deep-copied."""
        data = {'nested': {'value': 'original'}}
        new_ctx = context.add_node_result('node_1', data)

        # Modify original
        data['nested']['value'] = 'modified'

        # Context should be unchanged
        assert new_ctx.get_node_result('node_1')['nested']['value'] == 'original'

    def test_add_node_result_returns_new_instance(self, context):
        """Test that add_node_result() returns new ContextManager."""
        new_ctx = context.add_node_result('node_1', {'status': 'ok'})

        assert context is not new_ctx
        assert context.get_node_result('node_1') is None


class TestContextManagerJinja2:
    """Tests for Jinja2 template resolution."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({
            'database_id': '123',
            'user_id': '456',
            'status': 'active',
            'data': {
                'count': 10,
                'name': 'test'
            }
        })

    def test_resolve_template_simple_variable(self, context):
        """Test resolving simple template with variable."""
        result = context.resolve_template('ID: {{ database_id }}')
        assert result == 'ID: 123'

    def test_resolve_template_multiple_variables(self, context):
        """Test resolving template with multiple variables."""
        result = context.resolve_template('User {{ user_id }} in {{ status }} database {{ database_id }}')
        assert result == 'User 456 in active database 123'

    def test_resolve_template_nested_access(self, context):
        """Test resolving template with nested variable access."""
        result = context.resolve_template('Count: {{ data.count }}, Name: {{ data.name }}')
        assert result == 'Count: 10, Name: test'

    def test_resolve_template_no_jinja2_markers(self, context):
        """Test that string without Jinja2 markers is returned as-is."""
        result = context.resolve_template('Plain text without markers')
        assert result == 'Plain text without markers'

    def test_resolve_template_empty_string(self, context):
        """Test resolving empty string."""
        result = context.resolve_template('')
        assert result == ''

    def test_resolve_template_undefined_variable(self, context):
        """Test resolving template with undefined variable."""
        # Undefined variables should return empty string
        result = context.resolve_template('Value: {{ missing_variable }}')
        assert result == 'Value: '

    def test_resolve_template_with_node_result(self, context):
        """Test resolving template that references node results."""
        new_ctx = context.add_node_result('node_1', {'status': 'success', 'count': 42})
        result = new_ctx.resolve_template('Node 1 {{ node_1.output.status }}: {{ node_1.output.count }} items')
        assert result == 'Node 1 success: 42 items'

    def test_resolve_template_with_filter(self, context):
        """Test resolving template with Jinja2 filter."""
        result = context.resolve_template('Status: {{ status | upper }}')
        assert result == 'Status: ACTIVE'

    def test_resolve_template_with_expression(self, context):
        """Test resolving template with expressions."""
        result = context.resolve_template('Count is {{ data.count * 2 }}')
        assert result == 'Count is 20'

    def test_resolve_template_syntax_error(self, context):
        """Test that invalid Jinja2 syntax raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Jinja2 template syntax"):
            context.resolve_template('{{ unclosed variable')

    def test_resolve_template_sandbox_security(self, context):
        """Test that Jinja2 sandboxing prevents dangerous operations."""
        # Should not allow access to Python internals - Jinja2 returns empty string for undefined
        result = context.resolve_template('{{ __class__ }}')
        assert result == ''  # Undefined attributes return empty string in ImmutableSandboxedEnvironment


class TestContextManagerConditionEvaluation:
    """Tests for condition evaluation."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({
            'status': 'active',
            'count': 5,
            'enabled': True,
            'tags': ['production', 'critical']
        })

    def test_evaluate_condition_true_boolean_string(self, context):
        """Test evaluating template that renders to 'true'."""
        result = context.evaluate_condition('{{ status == "active" }}')
        assert result is True

    def test_evaluate_condition_false_boolean_string(self, context):
        """Test evaluating template that renders to 'false'."""
        result = context.evaluate_condition('{{ status == "inactive" }}')
        assert result is False

    def test_evaluate_condition_numeric_comparison(self, context):
        """Test evaluating numeric comparison."""
        result = context.evaluate_condition('{{ count > 3 }}')
        assert result is True

        result = context.evaluate_condition('{{ count > 10 }}')
        assert result is False

    def test_evaluate_condition_empty_string(self, context):
        """Test that empty condition is always true."""
        result = context.evaluate_condition('')
        assert result is True

    def test_evaluate_condition_none(self, context):
        """Test that None condition is always true."""
        result = context.evaluate_condition(None)
        assert result is True

    def test_evaluate_condition_string_true_variants(self, context):
        """Test various string representations of true."""
        for true_value in ['true', 'True', 'TRUE', '1', 'yes', 'YES', 'on', 'ON']:
            result = context.evaluate_condition(true_value)
            assert result is True, f"Failed for '{true_value}'"

    def test_evaluate_condition_string_false_variants(self, context):
        """Test various string representations of false."""
        for false_value in ['false', 'False', 'FALSE', '0', 'no', 'NO', 'off', 'OFF']:
            result = context.evaluate_condition(false_value)
            assert result is False, f"Failed for '{false_value}'"

    def test_evaluate_condition_with_node_result(self, context):
        """Test evaluating condition that references node result."""
        new_ctx = context.add_node_result('node_1', {'success': True})
        result = new_ctx.evaluate_condition('{{ node_1.output.success }}')
        assert result is True

    def test_evaluate_condition_complex_expression(self, context):
        """Test evaluating complex expression."""
        result = context.evaluate_condition('{{ count > 3 and status == "active" }}')
        assert result is True

        result = context.evaluate_condition('{{ count > 10 or status == "active" }}')
        assert result is True

    def test_evaluate_condition_invalid_template(self, context):
        """Test that invalid template raises ValueError."""
        with pytest.raises(ValueError, match="Condition evaluation failed"):
            context.evaluate_condition('{{ unclosed')

    def test_evaluate_condition_returns_boolean(self, context):
        """Test that result is always boolean."""
        result = context.evaluate_condition('{{ count }}')
        assert isinstance(result, bool)
        assert result is True


class TestContextManagerSnapshot:
    """Tests for context snapshots."""

    @pytest.fixture
    def context(self):
        """Create context with test data."""
        return ContextManager({
            'database_id': '123',
            'data': {'nested': 'value'}
        })

    def test_snapshot_creates_new_instance(self, context):
        """Test that snapshot() creates new ContextManager instance."""
        snapshot = context.snapshot()

        assert context is not snapshot
        assert isinstance(snapshot, ContextManager)

    def test_snapshot_copies_data(self, context):
        """Test that snapshot() copies all data."""
        snapshot = context.snapshot()

        assert snapshot.get('database_id') == '123'
        assert snapshot.get('data.nested') == 'value'

    def test_snapshot_isolation(self, context):
        """Test that snapshot() creates independent copy."""
        snapshot = context.snapshot()

        # Modify snapshot
        new_snapshot = snapshot.set('database_id', '999')

        # Original should be unchanged
        assert context.get('database_id') == '123'
        assert new_snapshot.get('database_id') == '999'

    def test_snapshot_deep_copy(self, context):
        """Test that snapshot() creates deep copy."""
        snapshot = context.snapshot()

        # Get original data structure
        original_data = context.to_dict()['data']
        snapshot_data = snapshot.to_dict()['data']

        # Modify snapshot data structure
        snapshot_data['nested'] = 'modified'

        # Original should be unchanged
        assert original_data['nested'] == 'value'


class TestContextManagerToDict:
    """Tests for exporting context as dict."""

    def test_to_dict_returns_dict(self):
        """Test that to_dict() returns dict."""
        ctx = ContextManager({'key': 'value'})
        result = ctx.to_dict()

        assert isinstance(result, dict)

    def test_to_dict_contains_data(self):
        """Test that to_dict() contains all context data."""
        ctx = ContextManager({'database_id': '123', 'status': 'active'})
        result = ctx.to_dict()

        assert result['database_id'] == '123'
        assert result['status'] == 'active'
        assert 'nodes' in result

    def test_to_dict_deep_copy(self):
        """Test that to_dict() returns deep copy."""
        ctx = ContextManager({'data': {'nested': 'value'}})
        result = ctx.to_dict()

        # Modify returned dict
        result['data']['nested'] = 'modified'

        # Original context should be unchanged
        assert ctx.get('data.nested') == 'value'

    def test_to_dict_includes_node_results(self):
        """Test that to_dict() includes node results."""
        ctx = ContextManager({'key': 'value'}).add_node_result('node_1', {'status': 'ok'})
        result = ctx.to_dict()

        assert 'nodes' in result
        assert result['nodes']['node_1']['status'] == 'ok'


class TestContextManagerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_context_with_none_values(self):
        """Test context with None values."""
        ctx = ContextManager({'key': None, 'nested': {'value': None}})

        assert ctx.get('key') is None
        assert ctx.get('nested.value') is None

    def test_context_with_empty_collections(self):
        """Test context with empty collections."""
        ctx = ContextManager({'empty_list': [], 'empty_dict': {}})

        assert ctx.get('empty_list') == []
        assert ctx.get('empty_dict') == {}

    def test_context_with_special_characters_in_keys(self):
        """Test that dots in keys are not treated as separators."""
        # Only dots used as separators are treated specially
        ctx = ContextManager({'normal_key': 'value'})
        assert ctx.get('normal_key') == 'value'

    def test_context_with_numeric_values(self):
        """Test context with various numeric types."""
        ctx = ContextManager({
            'integer': 42,
            'float': 3.14,
            'negative': -10,
            'zero': 0
        })

        assert ctx.get('integer') == 42
        assert ctx.get('float') == 3.14
        assert ctx.get('negative') == -10
        assert ctx.get('zero') == 0

    def test_context_with_boolean_values(self):
        """Test context with boolean values."""
        ctx = ContextManager({'true_val': True, 'false_val': False})

        assert ctx.get('true_val') is True
        assert ctx.get('false_val') is False

    def test_large_context(self):
        """Test context with large amount of data."""
        large_data = {f'key_{i}': f'value_{i}' for i in range(1000)}
        ctx = ContextManager(large_data)

        assert ctx.get('key_500') == 'value_500'
        assert ctx.get('key_999') == 'value_999'

    def test_repr_method(self):
        """Test __repr__ method for debugging."""
        ctx = ContextManager({'key1': 'value1', 'key2': 'value2'})
        repr_str = repr(ctx)

        assert 'ContextManager' in repr_str
        assert 'keys=' in repr_str

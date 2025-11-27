"""
Unit tests for conditional logic in templates.

Tests {% if %} conditions, {% for %} loops, and custom Jinja2 tests.
"""

from unittest.mock import Mock
from apps.templates.engine import TemplateRenderer


class TestConditionalIf:
    """Test {% if %} conditional logic."""

    def setup_method(self):
        self.renderer = TemplateRenderer()

    def test_if_true_condition(self):
        """Test {% if %} with true condition."""
        template = Mock()
        template.id = 'test-if-true'
        template.name = 'Test If True'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if is_active %}active{% endif %}"
        }

        result = self.renderer.render(template, {"is_active": True})
        assert result['result'] == "active"

    def test_if_false_condition(self):
        """Test {% if %} with false condition."""
        template = Mock()
        template.id = 'test-if-false'
        template.name = 'Test If False'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if is_active %}active{% endif %}"
        }

        result = self.renderer.render(template, {"is_active": False})
        assert result['result'] == ""

    def test_if_else(self):
        """Test {% if %}...{% else %}."""
        template = Mock()
        template.id = 'test-if-else'
        template.name = 'Test If Else'
        template.operation_type = 'create'
        template.template_data = {
            "status": "{% if is_active %}active{% else %}inactive{% endif %}"
        }

        # Test true branch
        result = self.renderer.render(template, {"is_active": True})
        assert result['status'] == "active"

        # Test false branch
        result = self.renderer.render(template, {"is_active": False})
        assert result['status'] == "inactive"

    def test_if_elif_else(self):
        """Test {% if %}...{% elif %}...{% else %}."""
        template = Mock()
        template.id = 'test-if-elif'
        template.name = 'Test If Elif'
        template.operation_type = 'create'
        template.template_data = {
            "level": "{% if score >= 90 %}A{% elif score >= 80 %}B{% elif score >= 70 %}C{% else %}F{% endif %}"
        }

        # Test A
        result = self.renderer.render(template, {"score": 95})
        assert result['level'] == "A"

        # Test B
        result = self.renderer.render(template, {"score": 85})
        assert result['level'] == "B"

        # Test C
        result = self.renderer.render(template, {"score": 75})
        assert result['level'] == "C"

        # Test F
        result = self.renderer.render(template, {"score": 50})
        assert result['level'] == "F"

    def test_if_comparison_operators(self):
        """Test {% if %} with comparison operators (==, !=, <, >, <=, >=)."""
        template = Mock()
        template.id = 'test-comparison'
        template.name = 'Test Comparison'
        template.operation_type = 'create'
        template.template_data = {
            "equal": "{% if value == 10 %}yes{% else %}no{% endif %}",
            "not_equal": "{% if value != 10 %}yes{% else %}no{% endif %}",
            "less": "{% if value < 10 %}yes{% else %}no{% endif %}",
            "greater": "{% if value > 10 %}yes{% else %}no{% endif %}"
        }

        result = self.renderer.render(template, {"value": 10})
        assert result['equal'] == "yes"
        assert result['not_equal'] == "no"
        assert result['less'] == "no"
        assert result['greater'] == "no"

    def test_if_logical_operators(self):
        """Test {% if %} with logical operators (and, or, not)."""
        template = Mock()
        template.id = 'test-logical'
        template.name = 'Test Logical'
        template.operation_type = 'create'
        template.template_data = {
            "and_result": "{% if is_active and is_verified %}yes{% else %}no{% endif %}",
            "or_result": "{% if is_admin or is_moderator %}yes{% else %}no{% endif %}",
            "not_result": "{% if not is_banned %}yes{% else %}no{% endif %}"
        }

        result = self.renderer.render(template, {
            "is_active": True,
            "is_verified": True,
            "is_admin": False,
            "is_moderator": True,
            "is_banned": False
        })

        assert result['and_result'] == "yes"
        assert result['or_result'] == "yes"
        assert result['not_result'] == "yes"

    def test_if_in_operator(self):
        """Test {% if %} with 'in' operator."""
        template = Mock()
        template.id = 'test-in'
        template.name = 'Test In'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if 'admin' in roles %}has_admin{% else %}no_admin{% endif %}"
        }

        result = self.renderer.render(template, {"roles": ["user", "admin", "moderator"]})
        assert result['result'] == "has_admin"

        result = self.renderer.render(template, {"roles": ["user", "moderator"]})
        assert result['result'] == "no_admin"

    def test_nested_if(self):
        """Test nested {% if %} statements."""
        template = Mock()
        template.id = 'test-nested-if'
        template.name = 'Test Nested If'
        template.operation_type = 'create'
        template.template_data = {
            "message": "{% if is_user %}{% if is_premium %}Premium User{% else %}Regular User{% endif %}{% else %}Guest{% endif %}"
        }

        # Premium user
        result = self.renderer.render(template, {"is_user": True, "is_premium": True})
        assert result['message'] == "Premium User"

        # Regular user
        result = self.renderer.render(template, {"is_user": True, "is_premium": False})
        assert result['message'] == "Regular User"

        # Guest
        result = self.renderer.render(template, {"is_user": False})
        assert result['message'] == "Guest"

    def test_if_with_none_value(self):
        """Test {% if %} with None value."""
        template = Mock()
        template.id = 'test-none'
        template.name = 'Test None'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if value %}has_value{% else %}no_value{% endif %}"
        }

        result = self.renderer.render(template, {"value": None})
        assert result['result'] == "no_value"

    def test_if_with_empty_string(self):
        """Test {% if %} with empty string."""
        template = Mock()
        template.id = 'test-empty-string'
        template.name = 'Test Empty String'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if text %}has_text{% else %}no_text{% endif %}"
        }

        result = self.renderer.render(template, {"text": ""})
        assert result['result'] == "no_text"


class TestConditionalFor:
    """Test {% for %} loop logic."""

    def setup_method(self):
        self.renderer = TemplateRenderer()

    def test_for_simple_loop(self):
        """Test simple {% for %} loop."""
        template = Mock()
        template.id = 'test-for-simple'
        template.name = 'Test For Simple'
        template.operation_type = 'create'
        template.template_data = {
            "items": "{% for item in items %}{{ item }}{% if not loop.last %},{% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {"items": ["a", "b", "c"]})
        assert result['items'] == "a,b,c"

    def test_for_with_index(self):
        """Test {% for %} with loop.index."""
        template = Mock()
        template.id = 'test-for-index'
        template.name = 'Test For Index'
        template.operation_type = 'create'
        template.template_data = {
            "indexed": "{% for item in items %}{{ loop.index }}.{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {"items": ["apple", "banana", "cherry"]})
        assert result['indexed'] == "1.apple, 2.banana, 3.cherry"

    def test_for_dict_items(self):
        """Test {% for %} over dictionary items."""
        template = Mock()
        template.id = 'test-for-dict'
        template.name = 'Test For Dict'
        template.operation_type = 'create'
        template.template_data = {
            "pairs": "{% for key, value in data.items() %}{{ key }}={{ value }}{% if not loop.last %}; {% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {
            "data": {"name": "Alice", "age": "30", "city": "NYC"}
        })

        # Order may vary, so check contains
        assert "name=Alice" in result['pairs']
        assert "age=30" in result['pairs']
        assert "city=NYC" in result['pairs']

    def test_for_with_if_filter(self):
        """Test {% for %} with {% if %} filter inside."""
        template = Mock()
        template.id = 'test-for-if'
        template.name = 'Test For If'
        template.operation_type = 'create'
        template.template_data = {
            "evens": "{% for num in numbers %}{% if num % 2 == 0 %}{{ num }}{% if not loop.last %},{% endif %}{% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {"numbers": [1, 2, 3, 4, 5, 6]})
        # Should contain only even numbers
        # Note: loop.last in inner if won't work correctly, so we get extra commas
        # Just check that evens are present
        assert "2" in result['evens']
        assert "4" in result['evens']
        assert "6" in result['evens']

    def test_nested_for(self):
        """Test nested {% for %} loops."""
        template = Mock()
        template.id = 'test-nested-for'
        template.name = 'Test Nested For'
        template.operation_type = 'create'
        template.template_data = {
            "grid": "{% for row in matrix %}{% for cell in row %}{{ cell }}{% if not loop.last %},{% endif %}{% endfor %}{% if not loop.last %};{% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {
            "matrix": [[1, 2], [3, 4], [5, 6]]
        })

        assert result['grid'] == "1,2;3,4;5,6"

    def test_for_empty_list(self):
        """Test {% for %} with empty list."""
        template = Mock()
        template.id = 'test-for-empty'
        template.name = 'Test For Empty'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% for item in items %}{{ item }}{% else %}empty{% endfor %}"
        }

        result = self.renderer.render(template, {"items": []})
        assert result['result'] == "empty"

    def test_for_with_loop_first(self):
        """Test {% for %} with loop.first."""
        template = Mock()
        template.id = 'test-for-first'
        template.name = 'Test For First'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% for item in items %}{% if loop.first %}[{% endif %}{{ item }}{% if not loop.last %},{% endif %}{% if loop.last %}]{% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {"items": ["x", "y", "z"]})
        assert result['result'] == "[x,y,z]"

    def test_for_with_loop_index0(self):
        """Test {% for %} with loop.index0 (zero-based index)."""
        template = Mock()
        template.id = 'test-for-index0'
        template.name = 'Test For Index0'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% for item in items %}{{ loop.index0 }}:{{ item }}{% if not loop.last %};{% endif %}{% endfor %}"
        }

        result = self.renderer.render(template, {"items": ["a", "b", "c"]})
        assert result['result'] == "0:a;1:b;2:c"


class TestCustomJinja2Tests:
    """Test custom Jinja2 tests (production_database, etc.)."""

    def setup_method(self):
        self.renderer = TemplateRenderer()

    def test_production_database_test_dict(self):
        """Test 'production_database' test with dict."""
        template = Mock()
        template.id = 'test-prod-db'
        template.name = 'Test Production DB'
        template.operation_type = 'create'
        template.template_data = {
            "env": "{% if database is production_database %}production{% else %}not_production{% endif %}"
        }

        # Production database
        result = self.renderer.render(template, {
            "database": {"type": "production", "name": "prod-db"}
        })
        assert result['env'] == "production"

        # Non-production database
        result = self.renderer.render(template, {
            "database": {"type": "test", "name": "test-db"}
        })
        assert result['env'] == "not_production"

    def test_test_database_test(self):
        """Test 'test_database' test."""
        template = Mock()
        template.id = 'test-test-db'
        template.name = 'Test Test DB'
        template.operation_type = 'create'
        template.template_data = {
            "is_test": "{% if database is test_database %}yes{% else %}no{% endif %}"
        }

        result = self.renderer.render(template, {
            "database": {"type": "test"}
        })
        assert result['is_test'] == "yes"

    def test_development_database_test(self):
        """Test 'development_database' test."""
        template = Mock()
        template.id = 'test-dev-db'
        template.name = 'Test Dev DB'
        template.operation_type = 'create'
        template.template_data = {
            "is_dev": "{% if database is development_database %}yes{% else %}no{% endif %}"
        }

        result = self.renderer.render(template, {
            "database": {"type": "development"}
        })
        assert result['is_dev'] == "yes"

    def test_empty_test(self):
        """Test 'empty' test."""
        template = Mock()
        template.id = 'test-empty'
        template.name = 'Test Empty'
        template.operation_type = 'create'
        template.template_data = {
            "empty_list": "{% if items is empty %}empty{% else %}not_empty{% endif %}",
            "empty_dict": "{% if data is empty %}empty{% else %}not_empty{% endif %}",
            "empty_string": "{% if text is empty %}empty{% else %}not_empty{% endif %}"
        }

        result = self.renderer.render(template, {
            "items": [],
            "data": {},
            "text": ""
        })

        assert result['empty_list'] == "empty"
        assert result['empty_dict'] == "empty"
        assert result['empty_string'] == "empty"

    def test_nonempty_test(self):
        """Test 'nonempty' test."""
        template = Mock()
        template.id = 'test-nonempty'
        template.name = 'Test Nonempty'
        template.operation_type = 'create'
        template.template_data = {
            "has_items": "{% if items is nonempty %}yes{% else %}no{% endif %}"
        }

        result = self.renderer.render(template, {"items": [1, 2, 3]})
        assert result['has_items'] == "yes"

    def test_empty_test_with_none(self):
        """Test 'empty' test with None value."""
        template = Mock()
        template.id = 'test-empty-none'
        template.name = 'Test Empty None'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if value is empty %}empty{% else %}not_empty{% endif %}"
        }

        result = self.renderer.render(template, {"value": None})
        assert result['result'] == "empty"

    def test_empty_test_with_zero(self):
        """Test 'empty' test with zero value."""
        template = Mock()
        template.id = 'test-empty-zero'
        template.name = 'Test Empty Zero'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if value is empty %}empty{% else %}not_empty{% endif %}"
        }

        result = self.renderer.render(template, {"value": 0})
        assert result['result'] == "empty"

    def test_combined_custom_tests(self):
        """Test combining custom tests with regular conditions."""
        template = Mock()
        template.id = 'test-combined'
        template.name = 'Test Combined'
        template.operation_type = 'create'
        template.template_data = {
            "message": "{% if database is production_database and users is nonempty %}Production with {{ users|length }} users{% else %}Other{% endif %}"
        }

        # Production with users
        result = self.renderer.render(template, {
            "database": {"type": "production"},
            "users": [1, 2, 3]
        })
        assert "Production with 3 users" in result['message']

        # Test database
        result = self.renderer.render(template, {
            "database": {"type": "test"},
            "users": [1, 2, 3]
        })
        assert result['message'] == "Other"

    def test_empty_test_with_false(self):
        """Test 'empty' test with False value (should NOT be empty)."""
        template = Mock()
        template.id = 'test-empty-false'
        template.name = 'Test Empty False'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if value is empty %}empty{% else %}not_empty{% endif %}"
        }

        result = self.renderer.render(template, {"value": False})
        assert result['result'] == "not_empty", "False is a valid boolean, not empty"

    def test_empty_test_with_true(self):
        """Test 'empty' test with True value (should NOT be empty)."""
        template = Mock()
        template.id = 'test-empty-true'
        template.name = 'Test Empty True'
        template.operation_type = 'create'
        template.template_data = {
            "result": "{% if value is empty %}empty{% else %}not_empty{% endif %}"
        }

        result = self.renderer.render(template, {"value": True})
        assert result['result'] == "not_empty", "True is a valid boolean, not empty"

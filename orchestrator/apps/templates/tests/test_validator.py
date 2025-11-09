import pytest
from unittest.mock import Mock
from apps.templates.engine import TemplateValidator, TemplateValidationError


class TestTemplateValidatorRequiredFields:
    """Test required fields validation."""

    def setup_method(self):
        self.validator = TemplateValidator()

    def test_valid_template_passes(self):
        """Test that valid template passes validation."""
        template = Mock()
        template.id = 'test-001'
        template.name = 'Valid Template'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {"Name": "{{user_name}}"}

        # Should not raise
        self.validator.validate_template(template)

    def test_missing_name_fails(self):
        """Test that missing name fails validation."""
        template = Mock()
        template.name = None  # ← Missing
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {"Name": "test"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "name is required" in str(exc_info.value)

    def test_empty_name_fails(self):
        """Test that empty name fails validation."""
        template = Mock()
        template.name = ''  # ← Empty
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {"Name": "test"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "name is required" in str(exc_info.value)

    def test_missing_operation_type_fails(self):
        """Test that missing operation_type fails validation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = None  # ← Missing
        template.target_entity = 'Catalog_Users'
        template.template_data = {"Name": "test"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "operation_type is required" in str(exc_info.value)

    def test_missing_template_data_fails(self):
        """Test that missing template_data fails validation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = None  # ← Missing

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "template_data is required" in str(exc_info.value)

    def test_empty_template_data_fails(self):
        """Test that empty template_data fails validation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {}  # ← Empty

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "template_data is required" in str(exc_info.value)


class TestTemplateValidatorJSONSyntax:
    """Test JSON syntax validation."""

    def setup_method(self):
        self.validator = TemplateValidator()

    def test_valid_json_dict_passes(self):
        """Test that valid JSON dict passes."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {"Name": "{{user_name}}"}  # Valid dict

        # Should not raise
        self.validator.validate_template(template)

    def test_valid_json_string_passes(self):
        """Test that valid JSON string passes."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = '{"Name": "{{user_name}}"}'  # Valid JSON string

        # Should not raise
        self.validator.validate_template(template)

    def test_invalid_json_string_fails(self):
        """Test that invalid JSON string fails."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = '{"Name": invalid json}'  # Invalid JSON

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "Invalid JSON" in str(exc_info.value)


class TestTemplateValidatorSecurity:
    """Test security validation (dangerous patterns)."""

    def setup_method(self):
        self.validator = TemplateValidator()

    @pytest.mark.parametrize("dangerous_template,pattern_hint", [
        ({"attack": "{{ ''.__class__ }}"}, "__class__"),
        ({"attack": "{{ obj.__globals__ }}"}, "__globals__"),
        ({"attack": "{{ obj.__init__ }}"}, "__init__"),
        ({"attack": "{{ exec('evil') }}"}, "exec"),
        ({"attack": "{{ eval('1+1') }}"}, "eval"),
        ({"attack": "{{ import os }}"}, "import"),
        ({"attack": "{{ __import__('os') }}"}, "__import__"),
        ({"attack": "{{ compile('code', 'file', 'exec') }}"}, "compile"),
        ({"attack": "{{ open('/etc/passwd') }}"}, "open"),
        ({"attack": "{{ file('/etc/passwd') }}"}, "file"),
        ({"attack": "{{ input('prompt') }}"}, "input"),
    ])
    def test_dangerous_patterns_blocked(self, dangerous_template, pattern_hint):
        """Test that dangerous patterns are blocked."""
        template = Mock()
        template.name = 'Malicious'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = dangerous_template

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "Security violation" in str(exc_info.value)
        assert "dangerous pattern" in str(exc_info.value).lower()

    def test_safe_template_passes(self):
        """Test that safe template passes security validation."""
        template = Mock()
        template.name = 'Safe'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {
            "Name": "{{user_name}}",
            "Email": "{{email}}",
            "IsActive": "{% if is_active %}true{% else %}false{% endif %}"
        }

        # Should not raise
        self.validator.validate_template(template)

    def test_safe_underscores_in_variable_names_pass(self):
        """Test that single underscores in variable names are safe."""
        template = Mock()
        template.name = 'Safe'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {
            "Name": "{{user_name}}",  # Single underscores OK
            "Email": "{{user_email}}",
        }

        # Should not raise
        self.validator.validate_template(template)


class TestTemplateValidatorJinja2Syntax:
    """Test Jinja2 syntax validation."""

    def setup_method(self):
        self.validator = TemplateValidator()

    def test_valid_jinja2_syntax_passes(self):
        """Test that valid Jinja2 syntax passes."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {
            "var": "{{name}}",
            "cond": "{% if x %}yes{% endif %}",
            "loop": "{% for i in list %}{{i}}{% endfor %}"
        }

        # Should not raise
        self.validator.validate_template(template)

    def test_unclosed_variable_fails(self):
        """Test that unclosed variable fails."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {"bad": "{{ unclosed_var"}  # Missing }}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "Invalid Jinja2 syntax" in str(exc_info.value)

    def test_unclosed_if_fails(self):
        """Test that unclosed {% if %} fails."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {"bad": "{% if condition %}yes"}  # Missing {% endif %}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "Invalid Jinja2 syntax" in str(exc_info.value)

    def test_unclosed_for_fails(self):
        """Test that unclosed {% for %} fails."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {"bad": "{% for i in items %}{{i}}"}  # Missing {% endfor %}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "Invalid Jinja2 syntax" in str(exc_info.value)


class TestTemplateValidatorBusinessLogic:
    """Test business logic validation."""

    def setup_method(self):
        self.validator = TemplateValidator()

    def test_valid_operation_type_passes(self):
        """Test that valid operation_type passes."""
        for op_type in ['create', 'update', 'delete', 'batch_create', 'batch_update', 'batch_delete', 'query']:
            template = Mock()
            template.name = 'Test'
            template.operation_type = op_type
            template.target_entity = 'Test' if op_type in ['create', 'update', 'delete'] else None
            template.template_data = {"test": "data"}

            # Should not raise
            self.validator.validate_template(template)

    def test_invalid_operation_type_fails(self):
        """Test that invalid operation_type fails."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'invalid_op'  # Not in whitelist
        template.target_entity = 'Test'
        template.template_data = {"test": "data"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "Invalid operation_type" in str(exc_info.value)
        assert "invalid_op" in str(exc_info.value)

    def test_missing_target_entity_for_create_fails(self):
        """Test that missing target_entity fails for 'create' operation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = None  # ← Missing
        template.template_data = {"test": "data"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "target_entity is required" in str(exc_info.value)

    def test_missing_target_entity_for_update_fails(self):
        """Test that missing target_entity fails for 'update' operation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'update'
        template.target_entity = None  # ← Missing
        template.template_data = {"test": "data"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "target_entity is required" in str(exc_info.value)

    def test_missing_target_entity_for_delete_fails(self):
        """Test that missing target_entity fails for 'delete' operation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'delete'
        template.target_entity = None  # ← Missing
        template.template_data = {"test": "data"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "target_entity is required" in str(exc_info.value)

    def test_empty_target_entity_for_create_fails(self):
        """Test that empty target_entity fails for 'create' operation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'create'
        template.target_entity = ''  # ← Empty
        template.template_data = {"test": "data"}

        with pytest.raises(TemplateValidationError) as exc_info:
            self.validator.validate_template(template)

        assert "target_entity is required" in str(exc_info.value)

    def test_target_entity_not_required_for_query(self):
        """Test that target_entity is not required for 'query' operation."""
        template = Mock()
        template.name = 'Test'
        template.operation_type = 'query'
        template.target_entity = None  # OK for query
        template.template_data = {"test": "data"}

        # Should not raise
        self.validator.validate_template(template)


class TestTemplateValidatorDataOnly:
    """Test validate_template_data_only method."""

    def setup_method(self):
        self.validator = TemplateValidator()

    def test_valid_template_data_returns_empty_errors(self):
        """Test that valid template_data returns no errors."""
        template_data = {
            "Name": "{{user_name}}",
            "Email": "{{email}}"
        }

        errors = self.validator.validate_template_data_only(template_data)
        assert errors == []

    def test_dangerous_pattern_returns_error(self):
        """Test that dangerous pattern returns error."""
        template_data = {
            "attack": "{{ obj.__class__ }}"
        }

        errors = self.validator.validate_template_data_only(template_data)
        assert len(errors) > 0
        assert any("Security violation" in err for err in errors)

    def test_invalid_jinja2_returns_error(self):
        """Test that invalid Jinja2 syntax returns error."""
        template_data = {
            "bad": "{{ unclosed"
        }

        errors = self.validator.validate_template_data_only(template_data)
        assert len(errors) > 0
        assert any("Jinja2 syntax" in err for err in errors)

    def test_multiple_errors_returned(self):
        """Test that multiple errors are collected."""
        template_data = {
            "attack": "{{ obj.__class__ }}",  # Security violation
            "bad": "{{ unclosed"  # Syntax error
        }

        errors = self.validator.validate_template_data_only(template_data)
        assert len(errors) >= 2  # At least 2 errors


class TestTemplateValidatorIntegration:
    """Test validator with realistic templates."""

    def setup_method(self):
        self.validator = TemplateValidator()

    def test_realistic_create_user_template(self):
        """Test realistic 'create user' template."""
        template = Mock()
        template.name = 'Create User'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {
            "Code": "{{user_code}}",
            "Description": "{{user_name}}",
            "Email": "{{email}}",
            "IsActive": "{% if is_active %}true{% else %}false{% endif %}",
            "Department": "{{department|default('IT')}}"
        }

        # Should not raise
        self.validator.validate_template(template)

    def test_realistic_batch_update_template(self):
        """Test realistic 'batch update' template."""
        template = Mock()
        template.name = 'Batch Update Prices'
        template.operation_type = 'batch_update'
        template.target_entity = None  # Not required for batch operations
        template.template_data = {
            "updates": [
                {
                    "entity": "Catalog_Products",
                    "filter": {"Code": "{{product_code}}"},
                    "data": {
                        "Price": "{{new_price}}",
                        "UpdatedAt": "{{timestamp}}"
                    }
                }
            ]
        }

        # Should not raise
        self.validator.validate_template(template)

    def test_realistic_query_template(self):
        """Test realistic 'query' template."""
        template = Mock()
        template.name = 'Query Active Users'
        template.operation_type = 'query'
        template.target_entity = None  # Not required for query
        template.template_data = {
            "$select": "Code,Description,Email",
            "$filter": "IsActive eq true{% if department %} and Department eq '{{department}}'{% endif %}",
            "$top": "{{limit|default(100)}}"
        }

        # Should not raise
        self.validator.validate_template(template)

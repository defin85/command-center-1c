"""
Tests for TemplateRenderer.
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock
from apps.templates.engine import (
    TemplateRenderer,
    TemplateRenderError,
)


class TestTemplateRenderer:
    """Test suite for TemplateRenderer."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return TemplateRenderer()

    @pytest.fixture
    def mock_template(self):
        """Create a mock OperationTemplate."""
        template = Mock()
        template.id = "test-template-001"
        template.name = "Test Template"
        template.operation_type = "create"
        return template

    def test_simple_variable_substitution(self, renderer, mock_template):
        """Test simple variable substitution."""
        # Arrange
        mock_template.template_data = {"name": "{{user_name}}"}
        context_data = {"user_name": "Alice"}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"name": "Alice"}

    def test_multiple_variables(self, renderer, mock_template):
        """Test multiple variables substitution."""
        # Arrange
        mock_template.template_data = {
            "name": "{{user_name}}",
            "age": "{{user_age}}",
            "active": "{{is_active}}"
        }
        context_data = {
            "user_name": "Bob",
            "user_age": 30,
            "is_active": True
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        # Note: Variables without filters are rendered as strings (Jinja2 behavior)
        assert result == {
            "name": "Bob",
            "age": "30",
            "active": "True"
        }

    def test_system_variables_current_timestamp(self, renderer, mock_template):
        """Test system variable: current_timestamp."""
        # Arrange
        mock_template.template_data = {
            "timestamp": "{{current_timestamp|datetime1c}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert "timestamp" in result
        # Format: datetime'2025-11-09T15:30:00.123456'
        assert result["timestamp"].startswith("datetime'")
        assert result["timestamp"].endswith("'")

    def test_system_variables_template_info(self, renderer, mock_template):
        """Test system variables: template_id, template_name, operation_type."""
        # Arrange
        mock_template.template_data = {
            "id": "{{template_id}}",
            "name": "{{template_name}}",
            "type": "{{operation_type}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert result == {
            "id": "test-template-001",
            "name": "Test Template",
            "type": "create"
        }

    def test_custom_filter_guid1c(self, renderer, mock_template):
        """Test custom filter: guid1c."""
        # Arrange
        user_id = "12345678-1234-1234-1234-123456789012"
        mock_template.template_data = {"user_id": "{{user_id|guid1c}}"}
        context_data = {"user_id": user_id}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"user_id": f"guid'{user_id}'"}

    def test_custom_filter_datetime1c_with_datetime_object(self, renderer, mock_template):
        """Test custom filter: datetime1c with datetime object."""
        # Arrange
        dt = datetime(2025, 1, 1, 12, 0, 0)
        mock_template.template_data = {"created": "{{created_at|datetime1c}}"}
        context_data = {"created_at": dt}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"created": "datetime'2025-01-01T12:00:00'"}

    def test_custom_filter_datetime1c_with_string(self, renderer, mock_template):
        """Test custom filter: datetime1c with string."""
        # Arrange
        mock_template.template_data = {"created": "{{created_str|datetime1c}}"}
        context_data = {"created_str": "2025-01-01T12:00:00"}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"created": "datetime'2025-01-01T12:00:00'"}

    def test_custom_filter_date1c_with_date_object(self, renderer, mock_template):
        """Test custom filter: date1c with date object."""
        # Arrange
        dt = date(2025, 1, 1)
        mock_template.template_data = {"date": "{{created_date|date1c}}"}
        context_data = {"created_date": dt}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"date": "datetime'2025-01-01T00:00:00'"}

    def test_custom_filter_date1c_with_string(self, renderer, mock_template):
        """Test custom filter: date1c with string."""
        # Arrange
        mock_template.template_data = {"date": "{{date_str|date1c}}"}
        context_data = {"date_str": "2025-01-01"}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"date": "datetime'2025-01-01T00:00:00'"}

    def test_custom_filter_bool1c_true(self, renderer, mock_template):
        """Test custom filter: bool1c with True value."""
        # Arrange
        mock_template.template_data = {"active": "{{is_active|bool1c}}"}
        context_data = {"is_active": True}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"active": "true"}

    def test_custom_filter_bool1c_false(self, renderer, mock_template):
        """Test custom filter: bool1c with False value."""
        # Arrange
        mock_template.template_data = {"active": "{{is_active|bool1c}}"}
        context_data = {"is_active": False}

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"active": "false"}

    def test_context_sanitization_removes_builtins(self, renderer, mock_template):
        """Test that __builtins__ is removed from context."""
        # Arrange
        mock_template.template_data = {"name": "{{user_name}}"}
        context_data = {
            "user_name": "Alice",
            "__builtins__": "evil"
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert - should work normally, __builtins__ filtered out
        assert result == {"name": "Alice"}

    def test_context_sanitization_removes_globals(self, renderer, mock_template):
        """Test that __globals__ is removed from context."""
        # Arrange
        mock_template.template_data = {"name": "{{user_name}}"}
        context_data = {
            "user_name": "Bob",
            "__globals__": "evil"
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"name": "Bob"}

    def test_context_sanitization_removes_private_attributes(self, renderer, mock_template):
        """Test that private attributes (starting with _) are removed."""
        # Arrange
        mock_template.template_data = {"name": "{{user_name}}"}
        context_data = {
            "user_name": "Charlie",
            "_private": "should be removed"
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {"name": "Charlie"}

    def test_nested_object_rendering(self, renderer, mock_template):
        """Test rendering of nested objects."""
        # Arrange
        mock_template.template_data = {
            "user": {
                "name": "{{user.name}}",
                "email": "{{user.email}}"
            }
        }
        context_data = {
            "user": {
                "name": "Alice",
                "email": "alice@example.com"
            }
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {
            "user": {
                "name": "Alice",
                "email": "alice@example.com"
            }
        }

    def test_list_rendering(self, renderer, mock_template):
        """Test rendering of lists."""
        # Arrange
        mock_template.template_data = {
            "users": [
                "{{user1}}",
                "{{user2}}"
            ]
        }
        context_data = {
            "user1": "Alice",
            "user2": "Bob"
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result == {
            "users": ["Alice", "Bob"]
        }

    def test_complex_template(self, renderer, mock_template):
        """Test complex template with multiple features."""
        # Arrange
        mock_template.template_data = {
            "filter": "Ref_Key eq {{user_id|guid1c}}",
            "created_at": "{{timestamp|datetime1c}}",
            "is_active": "{{active|bool1c}}",
            "metadata": {
                "template": "{{template_name}}",
                "type": "{{operation_type}}"
            }
        }
        context_data = {
            "user_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T12:00:00",
            "active": True
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        assert result["filter"] == "Ref_Key eq guid'12345678-1234-1234-1234-123456789012'"
        assert result["created_at"] == "datetime'2025-01-01T12:00:00'"
        assert result["is_active"] == "true"
        assert result["metadata"]["template"] == "Test Template"
        assert result["metadata"]["type"] == "create"

    def test_missing_variable_raises_error(self, renderer, mock_template):
        """Test that missing variable raises TemplateRenderError."""
        # Arrange
        mock_template.template_data = {"name": "{{missing_var}}"}
        context_data = {}

        # Act & Assert
        with pytest.raises(TemplateRenderError):
            renderer.render(mock_template, context_data)

    def test_invalid_json_in_template_data_raises_error(self, renderer, mock_template):
        """Test that invalid template_data raises TemplateRenderError."""
        # Arrange - this will cause json.dumps to fail if template_data is not serializable
        # But in our case, template_data is already a dict from JSONField
        # So we test invalid template syntax instead
        mock_template.template_data = {"name": "{{user_name"}  # Missing closing }}

        context_data = {"user_name": "Alice"}

        # Act & Assert
        with pytest.raises(TemplateRenderError):
            renderer.render(mock_template, context_data)

    def test_whitelisted_functions_available(self, renderer, mock_template):
        """Test that whitelisted functions (len, str, int) are available."""
        # Arrange
        mock_template.template_data = {
            "length": "{{items|length}}",
            "string": "{{num|string}}",
            "integer": "{{str_num|int}}"
        }
        context_data = {
            "items": [1, 2, 3],
            "num": 42,
            "str_num": "123"
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert
        # Note: Variables are rendered as strings (Jinja2 behavior)
        assert result["length"] == "3"
        assert result["string"] == "42"
        assert result["integer"] == "123"

    def test_uuid4_helper_function(self, renderer, mock_template):
        """Test uuid4 helper function generates valid UUID."""
        # Arrange
        mock_template.template_data = {"id": "{{uuid4()}}"}

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert "id" in result
        # Check it's a valid UUID format (36 chars with hyphens)
        assert len(result["id"]) == 36
        assert result["id"].count("-") == 4

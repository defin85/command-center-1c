"""
Edge coverage tests for Template Engine.

These tests cover edge cases for uncovered lines:
- None handling in filters
- CustomJSONEncoder usage
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock
import json

from apps.templates.engine import (
    TemplateRenderer,
)
from apps.templates.engine.renderer import CustomJSONEncoder
from apps.templates.engine.filters import (
    filter_guid1c,
    filter_datetime1c,
    filter_date1c,
    filter_bool1c,
)


class TestFilterEdgeCases:
    """Test edge cases in filter functions."""

    def test_guid1c_with_none(self):
        """Test guid1c filter with None value."""
        result = filter_guid1c(None)
        assert result is None

    def test_guid1c_with_empty_string(self):
        """Test guid1c filter with empty string."""
        result = filter_guid1c("")
        assert result is None

    def test_datetime1c_with_none(self):
        """Test datetime1c filter with None value."""
        result = filter_datetime1c(None)
        assert result is None

    def test_datetime1c_with_string_value(self):
        """Test datetime1c filter with plain string."""
        result = filter_datetime1c("2025-01-01")
        assert result == "datetime'2025-01-01'"

    def test_date1c_with_datetime_object(self):
        """Test date1c filter extracting date part from datetime."""
        dt = datetime(2025, 1, 15, 14, 30, 0)
        result = filter_date1c(dt)
        assert result == "datetime'2025-01-15T00:00:00'"

    def test_date1c_with_none(self):
        """Test date1c filter with None value."""
        result = filter_date1c(None)
        assert result is None

    def test_date1c_with_datetime_string_with_time(self):
        """Test date1c filter with ISO format datetime string."""
        result = filter_date1c("2025-01-01T14:30:00")
        assert result == "datetime'2025-01-01T00:00:00'"

    def test_bool1c_with_zero(self):
        """Test bool1c filter with zero (falsy)."""
        result = filter_bool1c(0)
        assert result == "false"

    def test_bool1c_with_empty_list(self):
        """Test bool1c filter with empty list (falsy)."""
        result = filter_bool1c([])
        assert result == "false"

    def test_bool1c_with_nonempty_list(self):
        """Test bool1c filter with non-empty list (truthy)."""
        result = filter_bool1c([1, 2, 3])
        assert result == "true"

    def test_bool1c_with_nonempty_string(self):
        """Test bool1c filter with non-empty string."""
        result = filter_bool1c("hello")
        assert result == "true"

    def test_bool1c_with_empty_string(self):
        """Test bool1c filter with empty string (falsy)."""
        result = filter_bool1c("")
        assert result == "false"

    def test_datetime1c_with_numeric_timestamp(self):
        """Test datetime1c filter with numeric timestamp."""
        result = filter_datetime1c(123456789)
        assert result == "datetime'123456789'"


class TestCustomJSONEncoder:
    """Test CustomJSONEncoder for datetime serialization."""

    def test_encode_datetime_object(self):
        """Test encoding datetime object."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        CustomJSONEncoder()
        result = json.dumps({"timestamp": dt}, cls=CustomJSONEncoder)
        assert "2025-01-01T12:00:00" in result

    def test_encode_date_object(self):
        """Test encoding date object."""
        d = date(2025, 1, 1)
        CustomJSONEncoder()
        result = json.dumps({"date": d}, cls=CustomJSONEncoder)
        assert "2025-01-01" in result

    def test_encode_datetime_in_list(self):
        """Test encoding datetime in list."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = json.dumps([dt], cls=CustomJSONEncoder)
        assert "2025-01-01T12:00:00" in result

    def test_encode_mixed_types(self):
        """Test encoding mixed types."""
        data = {
            "timestamp": datetime(2025, 1, 1, 12, 0, 0),
            "date": date(2025, 1, 1),
            "string": "hello",
            "number": 42,
            "bool": True
        }
        result = json.dumps(data, cls=CustomJSONEncoder)
        assert "2025-01-01T12:00:00" in result
        assert "2025-01-01" in result
        assert "hello" in result
        assert "42" in result

    def test_encode_non_datetime_object(self):
        """Test encoding non-datetime objects uses parent encoder."""
        data = {"value": 123}
        result = json.dumps(data, cls=CustomJSONEncoder)
        assert result == '{"value": 123}'


class TestRendererEdgeCases:
    """Test edge cases in TemplateRenderer."""

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

    def test_rendering_with_datetime_system_variable(self, renderer, mock_template):
        """Test rendering that uses datetime system variables."""
        # Arrange
        mock_template.template_data = {
            "current_timestamp": "{{current_timestamp}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert - should contain the datetime object rendered as string
        assert "current_timestamp" in result
        # The datetime will be rendered as string by Jinja2

    def test_rendering_with_current_date_system_variable(self, renderer, mock_template):
        """Test rendering that uses current_date system variable."""
        # Arrange
        mock_template.template_data = {
            "current_date": "{{current_date}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert "current_date" in result

    def test_rendering_datetime_through_filter(self, renderer, mock_template):
        """Test that datetime through filter works correctly."""
        # Arrange
        mock_template.template_data = {
            "timestamp": "{{current_timestamp|datetime1c}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert result["timestamp"].startswith("datetime'")
        assert result["timestamp"].endswith("'")


class TestIntegrationWithDjangoModels:
    """Test integration with Django models (using mocks)."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return TemplateRenderer()

    def test_rendering_with_real_django_model_structure(self, renderer):
        """Test rendering with realistic Django model mock."""
        # Arrange
        template = Mock()
        template.id = "tpl-users-create-12345"
        template.name = "User Creation Template"
        template.operation_type = "create"
        template.target_entity = "Catalog_Users"
        template.template_data = {
            "Code": "{{user_code}}",
            "Description": "{{user_name}}",
            "DataVersion": "{{version|int}}",
            "_IDRRef": "{{user_guid|guid1c}}",
            "Metadata": {
                "Created": "{{timestamp|datetime1c}}",
                "IsActive": "{{is_active|bool1c}}"
            }
        }

        context_data = {
            "user_code": "USR-001",
            "user_name": "Alice Johnson",
            "version": 1,
            "user_guid": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2025-01-01T12:00:00",
            "is_active": True
        }

        # Act
        result = renderer.render(template, context_data)

        # Assert
        assert result["Code"] == "USR-001"
        assert result["Description"] == "Alice Johnson"
        assert result["DataVersion"] == "1"
        assert result["_IDRRef"] == "guid'550e8400-e29b-41d4-a716-446655440000'"
        assert result["Metadata"]["Created"] == "datetime'2025-01-01T12:00:00'"
        assert result["Metadata"]["IsActive"] == "true"

    def test_rendering_with_complex_odata_filter(self, renderer):
        """Test rendering of complex OData filter expression."""
        # Arrange
        template = Mock()
        template.id = "tpl-filter-001"
        template.name = "OData Filter Template"
        template.operation_type = "read"
        template.template_data = {
            "filter": "Code eq '{{code}}' and Owner_Key eq {{owner_guid|guid1c}} and IsActive eq {{is_active|bool1c}} and CreatedDate gt {{created_date|date1c}}"
        }

        context_data = {
            "code": "ABC123",
            "owner_guid": "550e8400-e29b-41d4-a716-446655440000",
            "is_active": True,
            "created_date": "2024-01-01"
        }

        # Act - skip validation as 'read' is not in operation_type whitelist (use 'query' instead)
        result = renderer.render(template, context_data, validate=False)

        # Assert
        expected = "Code eq 'ABC123' and Owner_Key eq guid'550e8400-e29b-41d4-a716-446655440000' and IsActive eq true and CreatedDate gt datetime'2024-01-01T00:00:00'"
        assert result["filter"] == expected


class TestPerformanceEdgeCases:
    """Test performance with various edge cases."""

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

    def test_rendering_with_none_values(self, renderer, mock_template):
        """Test rendering with multiple None values (no performance degradation)."""
        # Arrange
        mock_template.template_data = {
            "field1": "{{val1}}",
            "field2": "{{val2}}",
            "field3": "{{val3}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "val1": None,
            "val2": None,
            "val3": None
        })

        # Assert
        assert result["field1"] == "None"
        assert result["field2"] == "None"
        assert result["field3"] == "None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

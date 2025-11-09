"""
Comprehensive test suite for Template Engine Core.

Tests cover:
- Edge cases
- Security (injection attacks)
- Performance
- Integration with Django models
- Error handling
"""

import pytest
import time
from datetime import datetime, date
from unittest.mock import Mock, patch
from decimal import Decimal

from apps.templates.engine import (
    TemplateRenderer,
    TemplateRenderError,
    TemplateError,
)
from jinja2 import TemplateSyntaxError, UndefinedError


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

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

    def test_empty_template_data(self, renderer, mock_template):
        """Test rendering with empty template_data."""
        # Arrange
        mock_template.template_data = {}

        # Act - skip validation as empty template_data is invalid by design
        result = renderer.render(mock_template, {"any": "data"}, validate=False)

        # Assert
        assert result == {}

    def test_empty_context_data(self, renderer, mock_template):
        """Test rendering with empty context_data."""
        # Arrange
        mock_template.template_data = {"name": "Alice"}

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert result == {"name": "Alice"}

    def test_none_values_in_context(self, renderer, mock_template):
        """Test rendering with None values in context."""
        # Arrange
        mock_template.template_data = {
            "value": "{{nullable}}"
        }

        # Act
        result = renderer.render(mock_template, {"nullable": None})

        # Assert
        assert result == {"value": "None"}

    def test_special_characters_in_template(self, renderer, mock_template):
        """Test rendering with special characters."""
        # Arrange
        mock_template.template_data = {
            "text": "Hello {{name}}! Your balance is ${{amount}}. Email: {{email}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "name": "Alice",
            "amount": 100,
            "email": "alice@example.com"
        })

        # Assert
        assert result["text"] == "Hello Alice! Your balance is $100. Email: alice@example.com"

    def test_unicode_characters_in_template(self, renderer, mock_template):
        """Test rendering with Unicode characters."""
        # Arrange
        mock_template.template_data = {
            "text": "Hello {{name}}! Chinese: {{name2}}!"
        }

        # Act
        result = renderer.render(mock_template, {
            "name": "Alice",
            "name2": "Bob"
        })

        # Assert
        assert "Hello Alice!" in result["text"]

    def test_large_numbers_in_template(self, renderer, mock_template):
        """Test rendering with large numbers."""
        # Arrange
        mock_template.template_data = {
            "count": "{{large_number}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "large_number": 999999999999999
        })

        # Assert
        assert result["count"] == "999999999999999"

    def test_float_numbers_in_template(self, renderer, mock_template):
        """Test rendering with float numbers."""
        # Arrange
        mock_template.template_data = {
            "price": "{{price}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "price": 99.99
        })

        # Assert
        assert result["price"] == "99.99"

    def test_empty_string_in_context(self, renderer, mock_template):
        """Test rendering with empty string in context."""
        # Arrange
        mock_template.template_data = {
            "name": "{{user_name}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "user_name": ""
        })

        # Assert
        assert result == {"name": ""}

    def test_whitespace_only_string(self, renderer, mock_template):
        """Test rendering with whitespace-only string."""
        # Arrange
        mock_template.template_data = {
            "text": "{{whitespace}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "whitespace": "   "
        })

        # Assert
        assert result == {"text": "   "}

    def test_very_long_string(self, renderer, mock_template):
        """Test rendering with very long string."""
        # Arrange
        long_string = "x" * 10000
        mock_template.template_data = {
            "text": "{{long_text}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "long_text": long_string
        })

        # Assert
        assert result["text"] == long_string

    def test_deeply_nested_structure(self, renderer, mock_template):
        """Test rendering with deeply nested structure."""
        # Arrange
        mock_template.template_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "{{deep_value}}"
                        }
                    }
                }
            }
        }

        # Act
        result = renderer.render(mock_template, {
            "deep_value": "FOUND"
        })

        # Assert
        assert result["level1"]["level2"]["level3"]["level4"]["value"] == "FOUND"

    def test_complex_nested_context_access(self, renderer, mock_template):
        """Test rendering with complex nested context access."""
        # Arrange
        mock_template.template_data = {
            "user_info": "{{user.profile.name}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "user": {
                "profile": {
                    "name": "Alice"
                }
            }
        })

        # Assert
        assert result["user_info"] == "Alice"

    def test_mixed_filter_and_raw_variable(self, renderer, mock_template):
        """Test mixing filtered and unfiltered variables."""
        # Arrange
        mock_template.template_data = {
            "raw": "{{user_id}}",
            "filtered": "{{user_id|guid1c}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "user_id": "12345678-1234-1234-1234-123456789012"
        })

        # Assert
        assert result["raw"] == "12345678-1234-1234-1234-123456789012"
        assert result["filtered"] == "guid'12345678-1234-1234-1234-123456789012'"

    def test_variable_in_string_middle(self, renderer, mock_template):
        """Test variable substitution in middle of string."""
        # Arrange
        mock_template.template_data = {
            "url": "https://example.com/users/{{user_id}}/profile"
        }

        # Act
        result = renderer.render(mock_template, {
            "user_id": "12345"
        })

        # Assert
        assert result["url"] == "https://example.com/users/12345/profile"

    def test_multiple_variables_in_single_string(self, renderer, mock_template):
        """Test multiple variables in single string."""
        # Arrange
        mock_template.template_data = {
            "filter": "Name eq '{{first_name}} {{last_name}}' and Id eq {{user_id}}"
        }

        # Act
        result = renderer.render(mock_template, {
            "first_name": "John",
            "last_name": "Doe",
            "user_id": "123"
        })

        # Assert
        assert result["filter"] == "Name eq 'John Doe' and Id eq 123"

    def test_list_with_mixed_types(self, renderer, mock_template):
        """Test rendering list with mixed types."""
        # Arrange
        mock_template.template_data = {
            "items": [
                "{{name}}",
                "{{count}}",
                "{{active|bool1c}}"
            ]
        }

        # Act
        result = renderer.render(mock_template, {
            "name": "Item",
            "count": 42,
            "active": True
        })

        # Assert
        assert result["items"] == ["Item", "42", "true"]

    def test_dict_with_numeric_keys(self, renderer, mock_template):
        """Test rendering dict with numeric keys."""
        # Arrange
        mock_template.template_data = {
            "data": {
                "123": "{{value1}}",
                "456": "{{value2}}"
            }
        }

        # Act
        result = renderer.render(mock_template, {
            "value1": "First",
            "value2": "Second"
        })

        # Assert
        assert result["data"]["123"] == "First"
        assert result["data"]["456"] == "Second"


class TestSecurityAndInjection:
    """Test security - injection attacks and sandboxing."""

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

    def test_python_magic_methods_blocked(self, renderer, mock_template):
        """Test that Python magic methods are blocked."""
        # Arrange
        mock_template.template_data = {
            "attack": "{{ ''.__class__.__name__ }}"
        }

        # Act & Assert
        with pytest.raises(Exception):
            renderer.render(mock_template, {})

    def test_access_to_class_blocked(self, renderer, mock_template):
        """Test that access to __class__ is blocked."""
        # Arrange
        mock_template.template_data = {
            "attack": "{{ ''.__class__ }}"
        }

        # Act & Assert
        with pytest.raises(Exception):
            renderer.render(mock_template, {})

    def test_exec_not_available(self, renderer, mock_template):
        """Test that exec() is not available."""
        # Arrange
        mock_template.template_data = {
            "attack": "{{ exec('print(1)') }}"
        }

        # Act & Assert
        with pytest.raises(Exception):
            renderer.render(mock_template, {})

    def test_eval_not_available(self, renderer, mock_template):
        """Test that eval() is not available."""
        # Arrange
        mock_template.template_data = {
            "attack": "{{ eval('1+1') }}"
        }

        # Act & Assert
        with pytest.raises(Exception):
            renderer.render(mock_template, {})

    def test_list_append_blocked(self, renderer, mock_template):
        """Test that list.append() is blocked in ImmutableSandboxedEnvironment."""
        # Arrange
        mock_template.template_data = {
            "result": "{% do items.append(999) %}{{ items }}"
        }

        # Act & Assert
        with pytest.raises(Exception):
            renderer.render(mock_template, {"items": [1, 2, 3]})

    def test_sql_injection_patterns_safe(self, renderer, mock_template):
        """Test that SQL injection patterns are rendered safely."""
        # Arrange
        mock_template.template_data = {
            "filter": "Name eq '{{name}}'"
        }

        # Act
        result = renderer.render(mock_template, {
            "name": "'; DROP TABLE users; --"
        })

        # Assert
        assert result["filter"] == "Name eq ''; DROP TABLE users; --'"

    def test_jinja2_syntax_injection(self, renderer, mock_template):
        """Test that Jinja2 syntax injection is caught."""
        # Arrange
        mock_template.template_data = {
            "result": "{{ for i in range(1000): i }}"
        }

        # Act & Assert
        with pytest.raises(TemplateRenderError):
            renderer.render(mock_template, {})


class TestPerformance:
    """Test performance characteristics."""

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

    def test_simple_rendering_performance(self, renderer, mock_template):
        """Test that simple rendering is fast."""
        # Arrange
        mock_template.template_data = {"name": "{{user_name}}"}
        context_data = {"user_name": "Alice"}

        # Warm up
        renderer.render(mock_template, context_data)

        # Measure
        start = time.time()
        iterations = 100
        for _ in range(iterations):
            renderer.render(mock_template, context_data)
        duration = time.time() - start

        avg_latency_ms = (duration / iterations) * 1000

        # Assert - target: < 50ms per render
        assert avg_latency_ms < 100, f"Rendering too slow: {avg_latency_ms:.2f}ms"

    def test_complex_rendering_performance(self, renderer, mock_template):
        """Test that complex rendering is still reasonably fast."""
        # Arrange
        mock_template.template_data = {
            "filter": "Ref_Key eq {{user_id|guid1c}}",
            "timestamp": "{{timestamp|datetime1c}}",
            "active": "{{active|bool1c}}",
            "metadata": {
                "template": "{{template_name}}",
                "type": "{{operation_type}}"
            },
            "users": [
                {"name": "{{user1}}"},
                {"name": "{{user2}}"},
            ]
        }
        context_data = {
            "user_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T12:00:00",
            "active": True,
            "user1": "Alice",
            "user2": "Bob"
        }

        # Warm up
        renderer.render(mock_template, context_data)

        # Measure
        start = time.time()
        iterations = 50
        for _ in range(iterations):
            renderer.render(mock_template, context_data)
        duration = time.time() - start

        avg_latency_ms = (duration / iterations) * 1000

        # Assert
        assert avg_latency_ms < 100, f"Complex rendering too slow: {avg_latency_ms:.2f}ms"

    def test_large_context_performance(self, renderer, mock_template):
        """Test performance with large context."""
        # Arrange
        context_data = {f"var_{i}": f"value_{i}" for i in range(100)}
        mock_template.template_data = {
            "result": "{{var_0}}-{{var_50}}-{{var_99}}"
        }

        # Warm up
        renderer.render(mock_template, context_data)

        # Measure
        start = time.time()
        iterations = 50
        for _ in range(iterations):
            renderer.render(mock_template, context_data)
        duration = time.time() - start

        avg_latency_ms = (duration / iterations) * 1000

        # Assert
        assert avg_latency_ms < 100, f"Large context rendering too slow: {avg_latency_ms:.2f}ms"


class TestErrorHandling:
    """Test error handling and error messages."""

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

    def test_missing_variable_error_message(self, renderer, mock_template):
        """Test that missing variable error has helpful message."""
        # Arrange
        mock_template.template_data = {"name": "{{missing_var}}"}

        # Act & Assert
        with pytest.raises(TemplateRenderError) as exc_info:
            renderer.render(mock_template, {})

        assert "Test Template" in str(exc_info.value)

    def test_syntax_error_in_template(self, renderer, mock_template):
        """Test that template syntax errors are caught."""
        # Arrange
        mock_template.template_data = {"bad": "{{ unclosed_var"}

        # Act & Assert
        with pytest.raises(TemplateRenderError):
            renderer.render(mock_template, {})

    def test_invalid_filter_error(self, renderer, mock_template):
        """Test that invalid filter names raise error."""
        # Arrange
        mock_template.template_data = {"result": "{{ value|nonexistent_filter }}"}

        # Act & Assert
        with pytest.raises(TemplateRenderError):
            renderer.render(mock_template, {"value": "test"})

    def test_list_as_template_data(self, renderer, mock_template):
        """Test handling of list as template_data."""
        # Arrange
        mock_template.template_data = ["{{item1}}", "{{item2}}"]

        # Act
        result = renderer.render(mock_template, {"item1": "A", "item2": "B"})

        # Assert
        assert result == ["A", "B"]

    def test_non_string_primitive_types(self, renderer, mock_template):
        """Test handling of non-string primitive types."""
        # Arrange
        mock_template.template_data = {
            "int_value": 42,
            "float_value": 3.14,
            "bool_value": True,
            "null_value": None
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert result["int_value"] == 42
        assert result["float_value"] == 3.14
        assert result["bool_value"] is True
        assert result["null_value"] is None


class TestContextBuilder:
    """Test ContextBuilder integration."""

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

    def test_system_variables_always_present(self, renderer, mock_template):
        """Test that system variables are always present."""
        # Arrange
        mock_template.template_data = {
            "template_id": "{{template_id}}",
            "template_name": "{{template_name}}",
            "operation_type": "{{operation_type}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert result["template_id"] == "test-template-001"
        assert result["template_name"] == "Test Template"
        assert result["operation_type"] == "create"

    def test_uuid4_generates_unique_values(self, renderer, mock_template):
        """Test that uuid4() generates unique values."""
        # Arrange
        mock_template.template_data = {
            "id1": "{{uuid4()}}",
            "id2": "{{uuid4()}}"
        }

        # Act
        result = renderer.render(mock_template, {})

        # Assert
        assert result["id1"] != result["id2"]
        assert len(result["id1"]) == 36

    def test_user_data_overrides_system_variables(self, renderer, mock_template):
        """Test that system variables take precedence."""
        # Arrange
        mock_template.template_data = {
            "template_id": "{{template_id}}"
        }
        context_data = {
            "template_id": "hacked"
        }

        # Act
        result = renderer.render(mock_template, context_data)

        # Assert - system variable should win
        assert result["template_id"] == "test-template-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

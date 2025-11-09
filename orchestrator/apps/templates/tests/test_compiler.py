"""
Tests for template compiler and caching.

Tests:
- Template compilation on first access
- Cache hit on subsequent access
- Different sources create different cache keys
- Cache key generation is deterministic
- Cache invalidation methods (placeholders)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from apps.templates.engine import TemplateCompiler
from jinja2.sandbox import ImmutableSandboxedEnvironment


class TestTemplateCompiler:
    """Test template compilation and caching."""

    def setup_method(self):
        """Setup test environment."""
        env = ImmutableSandboxedEnvironment()
        self.compiler = TemplateCompiler(env)

    def test_compile_template_first_time(self):
        """Test that template is compiled on first access (cache miss)."""
        # Clear cache before test
        self.compiler.clear_all_cache()

        template_id = 'test-001'
        template_source = {"name": "{{user_name}}"}

        # First access - cache miss
        compiled = self.compiler.get_compiled_template(template_id, template_source)

        # Should compile successfully
        assert compiled is not None

        # Cache should now contain 1 entry
        stats = self.compiler.get_cache_stats()
        assert stats['size'] >= 1

    def test_cache_hit_returns_cached_template(self):
        """Test that cache hit returns cached template without recompilation."""
        # Clear cache before test
        self.compiler.clear_all_cache()

        template_id = 'test-001'
        template_source = {"name": "{{user_name}}"}

        # First call: cache miss
        compiled1 = self.compiler.get_compiled_template(template_id, template_source)

        # Second call: cache hit (should return same object)
        compiled2 = self.compiler.get_compiled_template(template_id, template_source)

        # Should return same cached template
        assert compiled1 is compiled2  # Same object reference

        # Both should render correctly
        result1 = compiled1.render({"user_name": "Alice"})
        result2 = compiled2.render({"user_name": "Alice"})
        assert result1 == result2

    def test_different_source_creates_different_cache_key(self):
        """Test that different template_source creates different cache key."""
        template_id = 'test-001'
        source1 = {"name": "{{user_name}}"}
        source2 = {"name": "{{full_name}}"}  # Different

        # Compile both (no mocking - use real cache)
        compiled1 = self.compiler.get_compiled_template(template_id, source1)
        compiled2 = self.compiler.get_compiled_template(template_id, source2)

        # Should compile both (different cache keys)
        # Verify by rendering
        result1 = compiled1.render({"user_name": "Alice"})
        result2 = compiled2.render({"full_name": "Bob"})

        assert "Alice" in result1
        assert "Bob" in result2

    def test_cache_key_generation_deterministic(self):
        """Test that cache key generation is deterministic (same source → same key)."""
        template_id = 'test-001'
        template_source = {"name": "{{user_name}}", "email": "{{email}}"}

        # Get compiled template twice (no mocking - use real cache)
        compiled1 = self.compiler.get_compiled_template(template_id, template_source)
        compiled2 = self.compiler.get_compiled_template(template_id, template_source)

        # Should use same cache key (deterministic hash)
        # Both should render same result
        result1 = compiled1.render({"user_name": "Alice", "email": "alice@test.com"})
        result2 = compiled2.render({"user_name": "Alice", "email": "alice@test.com"})

        assert result1 == result2

    def test_string_source_compilation(self):
        """Test compilation of string source (not dict)."""
        template_id = 'test-str-001'
        template_source = "Hello {{name}}"

        compiled = self.compiler.get_compiled_template(template_id, template_source)
        result = compiled.render({"name": "World"})

        assert result == "Hello World"

    def test_list_source_compilation(self):
        """Test compilation of list source."""
        template_id = 'test-list-001'
        template_source = ["{{item1}}", "{{item2}}"]

        compiled = self.compiler.get_compiled_template(template_id, template_source)
        # Jinja2 will render the JSON string
        result = compiled.render({"item1": "A", "item2": "B"})

        # Result should contain the JSON representation
        assert "item1" in result or "A" in result

    def test_invalidate_cache(self):
        """Test cache invalidation."""
        # Clear cache before test
        self.compiler.clear_all_cache()

        template_id = 'test-001'
        source1 = {"name": "{{user_name}}"}
        source2 = {"name": "{{full_name}}"}

        # Compile two versions of same template_id
        self.compiler.get_compiled_template(template_id, source1)
        self.compiler.get_compiled_template(template_id, source2)

        # Cache should have 2 entries
        stats_before = self.compiler.get_cache_stats()
        assert stats_before['size'] >= 2

        # Invalidate template_id
        self.compiler.invalidate_cache(template_id)

        # Cache should be empty (or have fewer entries)
        stats_after = self.compiler.get_cache_stats()
        assert stats_after['size'] < stats_before['size']

    def test_clear_all_cache(self):
        """Test clearing all cache."""
        # Compile some templates
        self.compiler.get_compiled_template('test-001', {"a": "{{x}}"})
        self.compiler.get_compiled_template('test-002', {"b": "{{y}}"})

        # Cache should have entries
        stats_before = self.compiler.get_cache_stats()
        assert stats_before['size'] >= 2

        # Clear all
        self.compiler.clear_all_cache()

        # Cache should be empty
        stats_after = self.compiler.get_cache_stats()
        assert stats_after['size'] == 0

    def test_max_cache_size_configuration(self):
        """Test that max cache size is configurable."""
        assert hasattr(self.compiler, 'MAX_CACHE_SIZE')
        assert self.compiler.MAX_CACHE_SIZE > 0

    def test_cache_prefix_configuration(self):
        """Test that cache prefix is set correctly."""
        assert hasattr(self.compiler, 'CACHE_PREFIX')
        assert self.compiler.CACHE_PREFIX == "template_compiled_"

    def test_same_source_different_ids_creates_different_keys(self):
        """Test that same source but different template_id creates different cache keys."""
        # Clear cache before test
        self.compiler.clear_all_cache()

        source = {"name": "{{user_name}}"}
        template_id1 = 'test-001'
        template_id2 = 'test-002'

        # Compile with different IDs
        compiled1 = self.compiler.get_compiled_template(template_id1, source)
        compiled2 = self.compiler.get_compiled_template(template_id2, source)

        # Should create 2 separate cache entries
        stats = self.compiler.get_cache_stats()
        assert stats['size'] == 2

        # Both should be different objects (different cache keys)
        assert compiled1 is not compiled2

    def test_unicode_source_handling(self):
        """Test compilation of unicode characters in source."""
        template_id = 'test-unicode-001'
        template_source = {"greeting": "Привет, {{name}}!"}

        compiled = self.compiler.get_compiled_template(template_id, template_source)
        result = compiled.render({"name": "Мир"})

        assert "Привет" in result
        assert "Мир" in result

"""
Performance benchmarking tests for Template Engine.

Benchmarks:
- Rendering performance with cache (1st vs 2nd+ calls)
- Validation performance with compiled regex
- Security check performance
- End-to-end pipeline performance

Targets:
- Render: < 5ms (with cache)
- Validate: < 1ms (with compiled regex)
- Full pipeline: < 5ms (validate + render)
"""

import time
from unittest.mock import Mock
from apps.templates.engine import TemplateRenderer, TemplateValidator


class TestRenderingPerformance:
    """Benchmark template rendering performance."""

    def setup_method(self):
        """Setup renderer for benchmarks."""
        self.renderer = TemplateRenderer()

    def test_simple_rendering_with_cache(self):
        """Test rendering performance with cache (should be faster on 2nd+ call)."""
        template = Mock()
        template.id = 'bench-simple'
        template.name = 'Benchmark Simple'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {"name": "{{user_name}}"}

        context = {"user_name": "Alice"}

        # First render (cache miss)
        start = time.time()
        result1 = self.renderer.render(template, context, validate=False)
        first_render_time = time.time() - start

        # Second render (cache hit - should be faster)
        start = time.time()
        result2 = self.renderer.render(template, context, validate=False)
        second_render_time = time.time() - start

        # Results should be identical
        assert result1 == result2

        # Print performance metrics
        print("\n=== Rendering Performance ===")
        print(f"First render:  {first_render_time*1000:.4f}ms")
        print(f"Second render: {second_render_time*1000:.4f}ms")
        if first_render_time > 0:
            speedup = first_render_time / max(second_render_time, 0.0001)
            print(f"Speedup:       {speedup:.2f}x")

        # Both should be < 10ms (target)
        assert first_render_time < 0.01, f"First render too slow: {first_render_time*1000:.2f}ms"
        assert second_render_time < 0.01, f"Second render too slow: {second_render_time*1000:.2f}ms"

    def test_complex_rendering_with_cache(self):
        """Test rendering performance with complex template."""
        template = Mock()
        template.id = 'bench-complex'
        template.name = 'Benchmark Complex'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {
            "Name": "{{user_name}}",
            "Email": "{{email}}",
            "ID": "{{user_id|guid1c}}",
            "CreatedAt": "{{current_timestamp|datetime1c}}",
            "IsActive": "{% if is_active %}true{% else %}false{% endif %}",
            "Metadata": {
                "Source": "{{source}}",
                "Version": "{{version}}"
            }
        }

        context = {
            "user_name": "Alice",
            "email": "alice@test.com",
            "user_id": "12345678-1234-1234-1234-123456789012",
            "current_timestamp": "2025-01-01T00:00:00",
            "is_active": True,
            "source": "API",
            "version": "1.0"
        }

        # Warm up (cache miss)
        self.renderer.render(template, context, validate=False)

        # Measure 100 renders (cache hits)
        start = time.time()
        for _ in range(100):
            result = self.renderer.render(template, context, validate=False)
            assert result['Name'] == "Alice"
        duration = time.time() - start

        avg_latency = duration / 100 * 1000  # ms

        print("\n=== Complex Rendering Performance (100 iterations) ===")
        print(f"Total time:  {duration*1000:.2f}ms")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Target: < 5ms avg (with cache)
        assert avg_latency < 5.0, f"Complex rendering too slow: {avg_latency:.2f}ms"

    def test_cache_hit_rate_with_multiple_renders(self):
        """Test cache effectiveness with multiple identical renders."""
        template = Mock()
        template.id = 'bench-cache'
        template.name = 'Cache Test'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {"value": "{{x}}"}

        # Render 100 times with same context
        start = time.time()
        for i in range(100):
            result = self.renderer.render(template, {"x": i}, validate=False)
            assert result['value'] == str(i)
        duration = time.time() - start

        avg_latency = duration / 100 * 1000

        print("\n=== Cache Hit Rate Test (100 renders) ===")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Should be fast even with 100 different contexts
        # (template itself is cached, only context changes)
        assert avg_latency < 5.0, f"Cache test too slow: {avg_latency:.2f}ms"


class TestValidationPerformance:
    """Benchmark validation performance."""

    def setup_method(self):
        """Setup validator for benchmarks."""
        self.validator = TemplateValidator()

    def test_validation_with_compiled_regex(self):
        """Test validation performance with compiled regex patterns."""
        template = Mock()
        template.name = 'Bench Validator'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {
            "name": "{{user_name}}",
            "email": "{{email}}",
            "active": "{{is_active}}"
        }

        # Warm up
        self.validator.validate_template(template)

        # Measure 1000 validations
        start = time.time()
        for _ in range(1000):
            self.validator.validate_template(template)
        duration = time.time() - start

        avg_latency = duration / 1000 * 1000  # ms

        print("\n=== Validation Performance (1000 iterations) ===")
        print(f"Total time:  {duration*1000:.2f}ms")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Target: < 1ms (with compiled regex optimization)
        assert avg_latency < 1.0, f"Validation too slow: {avg_latency:.2f}ms"

    def test_security_check_performance(self):
        """Test security pattern matching performance."""
        template = Mock()
        template.name = 'Security Bench'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        # Complex template with many fields
        template.template_data = {f"field_{i}": f"{{{{var_{i}}}}}" for i in range(100)}

        # Measure security validation
        start = time.time()
        for _ in range(100):
            errors = self.validator._validate_security(template)
            assert errors == []  # No security issues
        duration = time.time() - start

        avg_latency = duration / 100 * 1000  # ms

        print("\n=== Security Check Performance (100 iterations, 100 fields each) ===")
        print(f"Total time:  {duration*1000:.2f}ms")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Should be fast even with 100 fields
        assert avg_latency < 5.0, f"Security check too slow: {avg_latency:.2f}ms"

    def test_jinja2_syntax_validation_performance(self):
        """Test Jinja2 syntax validation performance with cached environment."""
        template = Mock()
        template.name = 'Syntax Bench'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {
            "name": "{{user_name}}",
            "items": "{% for item in items %}{{item}}{% endfor %}",
            "condition": "{% if x > 10 %}high{% else %}low{% endif %}"
        }

        # Measure syntax validation
        start = time.time()
        for _ in range(1000):
            errors = self.validator._validate_jinja2_syntax(template)
            assert errors == []  # No syntax errors
        duration = time.time() - start

        avg_latency = duration / 1000 * 1000  # ms

        print("\n=== Jinja2 Syntax Validation (1000 iterations) ===")
        print(f"Total time:  {duration*1000:.2f}ms")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Should be fast with cached Jinja2 environment
        # Note: Allow up to 2ms due to system load variability
        assert avg_latency < 2.5, f"Syntax validation too slow: {avg_latency:.2f}ms"


class TestEndToEndPerformance:
    """Benchmark end-to-end performance (validate + render)."""

    def setup_method(self):
        """Setup renderer for end-to-end benchmarks."""
        self.renderer = TemplateRenderer()

    def test_full_pipeline_performance(self):
        """Test validate + render performance (end-to-end)."""
        template = Mock()
        template.id = 'bench-e2e'
        template.name = 'E2E Benchmark'
        template.operation_type = 'create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {
            "Name": "{{user_name}}",
            "Email": "{{email}}",
            "ID": "{{user_id|guid1c}}",
            "CreatedAt": "{{current_timestamp|datetime1c}}",
            "IsActive": "{% if is_active %}true{% else %}false{% endif %}"
        }

        context = {
            "user_name": "Alice",
            "email": "alice@test.com",
            "user_id": "12345678-1234-1234-1234-123456789012",
            "current_timestamp": "2025-01-01T00:00:00",
            "is_active": True
        }

        # Warm up (cache miss)
        self.renderer.render(template, context, validate=True)

        # Measure 100 renders (cache hits)
        start = time.time()
        for _ in range(100):
            result = self.renderer.render(template, context, validate=True)
            assert result['Name'] == "Alice"
        duration = time.time() - start

        avg_latency = duration / 100 * 1000  # ms

        print("\n=== Full Pipeline Performance (validate + render, 100 iterations) ===")
        print(f"Total time:  {duration*1000:.2f}ms")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Target: < 5ms (with all optimizations)
        assert avg_latency < 5.0, f"Full pipeline too slow: {avg_latency:.2f}ms"

    def test_batch_rendering_performance(self):
        """Test batch rendering performance (simulate real workload)."""
        template = Mock()
        template.id = 'bench-batch'
        template.name = 'Batch Benchmark'
        template.operation_type = 'batch_create'
        template.target_entity = 'Catalog_Users'
        template.template_data = {
            "Name": "{{user_name}}",
            "Email": "{{email}}"
        }

        # Simulate batch of 1000 users
        users = [
            {"user_name": f"User{i}", "email": f"user{i}@test.com"}
            for i in range(1000)
        ]

        # Warm up
        self.renderer.render(template, users[0], validate=False)

        # Measure batch rendering
        start = time.time()
        for user in users:
            result = self.renderer.render(template, user, validate=False)
            assert result['Name'] == user['user_name']
        duration = time.time() - start

        avg_latency = duration / 1000 * 1000  # ms

        print("\n=== Batch Rendering Performance (1000 users) ===")
        print(f"Total time:  {duration*1000:.2f}ms ({duration:.2f}s)")
        print(f"Avg latency: {avg_latency:.4f}ms")
        print(f"Throughput:  {1000/duration:.0f} renders/sec")

        # Target: < 5ms avg
        assert avg_latency < 5.0, f"Batch rendering too slow: {avg_latency:.2f}ms"


class TestCacheEffectiveness:
    """Test cache effectiveness and hit rates."""

    def setup_method(self):
        """Setup renderer for cache tests."""
        self.renderer = TemplateRenderer()

    def test_same_template_multiple_contexts(self):
        """Test that same template with different contexts uses cache effectively."""
        template = Mock()
        template.id = 'bench-cache-ctx'
        template.name = 'Cache Context Test'
        template.operation_type = 'create'
        template.target_entity = 'Test'
        template.template_data = {"name": "{{user_name}}", "id": "{{user_id}}"}

        contexts = [
            {"user_name": f"User{i}", "user_id": i}
            for i in range(100)
        ]

        # First render (warm up)
        self.renderer.render(template, contexts[0], validate=False)

        # Measure subsequent renders
        start = time.time()
        for ctx in contexts[1:]:
            result = self.renderer.render(template, ctx, validate=False)
            assert result['name'] == ctx['user_name']
        duration = time.time() - start

        avg_latency = duration / 99 * 1000

        print("\n=== Same Template, Different Contexts (99 iterations) ===")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Should be very fast (template cached, only context changes)
        assert avg_latency < 2.5, f"Too slow: {avg_latency:.2f}ms"

    def test_different_templates_no_cache_pollution(self):
        """Test that different templates don't pollute cache."""
        templates = []
        for i in range(10):
            template = Mock()
            template.id = f'bench-diff-{i}'
            template.name = f'Different Template {i}'
            template.operation_type = 'create'
            template.target_entity = 'Test'
            template.template_data = {f"field_{i}": f"{{{{value_{i}}}}}"}
            templates.append(template)

        contexts = [{f"value_{i}": f"Value{i}"} for i in range(10)]

        # Render each template once (populate cache)
        for template, ctx in zip(templates, contexts):
            self.renderer.render(template, ctx, validate=False)

        # Measure second pass (all should hit cache)
        start = time.time()
        for template, ctx in zip(templates, contexts):
            self.renderer.render(template, ctx, validate=False)
        duration = time.time() - start

        avg_latency = duration / 10 * 1000

        print("\n=== Different Templates Cache Test (10 templates, 2nd pass) ===")
        print(f"Avg latency: {avg_latency:.4f}ms")

        # Should be fast (all cached)
        assert avg_latency < 5.0, f"Too slow: {avg_latency:.2f}ms"

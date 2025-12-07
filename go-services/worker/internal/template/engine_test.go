package template

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

func TestEngine_Render(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	ctx := context.Background()

	t.Run("simple variable substitution", func(t *testing.T) {
		result, err := engine.Render(ctx, "Hello, {{ name }}!", map[string]interface{}{
			"name": "World",
		})
		require.NoError(t, err)
		assert.Equal(t, "Hello, World!", result)
	})

	t.Run("with filter", func(t *testing.T) {
		result, err := engine.Render(ctx, "{{ id|guid1c }}", map[string]interface{}{
			"id": "12345678-1234-1234-1234-123456789abc",
		})
		require.NoError(t, err)
		assert.Equal(t, "guid'12345678-1234-1234-1234-123456789abc'", result)
	})

	t.Run("conditional", func(t *testing.T) {
		result, err := engine.Render(ctx, "{% if active %}ON{% else %}OFF{% endif %}", map[string]interface{}{
			"active": true,
		})
		require.NoError(t, err)
		assert.Equal(t, "ON", result)
	})

	t.Run("loop", func(t *testing.T) {
		result, err := engine.Render(ctx, "{% for item in items %}{{ item }},{% endfor %}", map[string]interface{}{
			"items": []string{"a", "b", "c"},
		})
		require.NoError(t, err)
		assert.Equal(t, "a,b,c,", result)
	})

	t.Run("template caching", func(t *testing.T) {
		template := "{{ value }}"

		// First render
		result1, err := engine.Render(ctx, template, map[string]interface{}{"value": "first"})
		require.NoError(t, err)
		assert.Equal(t, "first", result1)

		// Second render with same template
		result2, err := engine.Render(ctx, template, map[string]interface{}{"value": "second"})
		require.NoError(t, err)
		assert.Equal(t, "second", result2)
	})

	t.Run("context cancellation", func(t *testing.T) {
		cancelCtx, cancel := context.WithCancel(ctx)
		cancel()

		_, err := engine.Render(cancelCtx, "{{ name }}", map[string]interface{}{"name": "test"})
		assert.Error(t, err)
		assert.Equal(t, context.Canceled, err)
	})

	t.Run("compilation error", func(t *testing.T) {
		_, err := engine.Render(ctx, "{% if %}", nil)
		assert.Error(t, err)
		assert.True(t, IsCompilationError(err))
	})
}

func TestEngine_RenderRecursive(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	ctx := context.Background()

	t.Run("nested map", func(t *testing.T) {
		data := map[string]interface{}{
			"outer": map[string]interface{}{
				"inner": "{{ value }}",
			},
		}
		templateContext := map[string]interface{}{
			"value": "rendered",
		}

		result, err := engine.RenderRecursive(ctx, data, templateContext)
		require.NoError(t, err)

		resultMap, ok := result.(map[string]interface{})
		require.True(t, ok)

		outerMap, ok := resultMap["outer"].(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, "rendered", outerMap["inner"])
	})

	t.Run("array of templates", func(t *testing.T) {
		data := []interface{}{
			"{{ a }}",
			"{{ b }}",
			"static",
		}
		templateContext := map[string]interface{}{
			"a": "first",
			"b": "second",
		}

		result, err := engine.RenderRecursive(ctx, data, templateContext)
		require.NoError(t, err)

		resultArr, ok := result.([]interface{})
		require.True(t, ok)
		assert.Equal(t, "first", resultArr[0])
		assert.Equal(t, "second", resultArr[1])
		assert.Equal(t, "static", resultArr[2])
	})

	t.Run("non-template values", func(t *testing.T) {
		data := map[string]interface{}{
			"string":  "static",
			"number":  42,
			"boolean": true,
			"null":    nil,
		}

		result, err := engine.RenderRecursive(ctx, data, nil)
		require.NoError(t, err)

		resultMap, ok := result.(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, "static", resultMap["string"])
		assert.Equal(t, 42, resultMap["number"])
		assert.Equal(t, true, resultMap["boolean"])
		assert.Nil(t, resultMap["null"])
	})
}

func TestEngine_RenderJSON(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	ctx := context.Background()

	t.Run("operation payload template", func(t *testing.T) {
		templateJSON := map[string]interface{}{
			"filter": "Ref eq {{ database_ref|guid1c }}",
			"database": map[string]interface{}{
				"name":    "{{ database_name }}",
				"cluster": "{{ cluster_id }}",
			},
			"options": map[string]interface{}{
				"timeout": 30,
				"enabled": "{{ is_enabled|bool1c }}",
			},
		}
		data := map[string]interface{}{
			"database_ref":  "12345678-1234-1234-1234-123456789abc",
			"database_name": "ERP_Production",
			"cluster_id":    "cluster-01",
			"is_enabled":    true,
		}

		result, err := engine.RenderJSON(ctx, templateJSON, data)
		require.NoError(t, err)

		assert.Equal(t, "Ref eq guid'12345678-1234-1234-1234-123456789abc'", result["filter"])

		dbMap, ok := result["database"].(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, "ERP_Production", dbMap["name"])
		assert.Equal(t, "cluster-01", dbMap["cluster"])

		optMap, ok := result["options"].(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, 30, optMap["timeout"])
		assert.Equal(t, "true", optMap["enabled"])
	})
}

func TestEngine_Validate(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)

	t.Run("valid template", func(t *testing.T) {
		err := engine.Validate("{{ name }}")
		assert.NoError(t, err)
	})

	t.Run("valid template with filter", func(t *testing.T) {
		err := engine.Validate("{{ id|guid1c }}")
		assert.NoError(t, err)
	})

	t.Run("valid template with conditionals", func(t *testing.T) {
		err := engine.Validate("{% if active %}yes{% endif %}")
		assert.NoError(t, err)
	})

	t.Run("invalid template - unclosed tag", func(t *testing.T) {
		err := engine.Validate("{% if active %}")
		assert.Error(t, err)
		assert.True(t, IsValidationError(err))
	})

	t.Run("invalid template - syntax error", func(t *testing.T) {
		err := engine.Validate("{{ }}")
		assert.Error(t, err)
	})
}

func TestEngine_ClearCache(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	ctx := context.Background()

	// Pre-populate cache
	_, err := engine.Render(ctx, "{{ a }}", map[string]interface{}{"a": "1"})
	require.NoError(t, err)

	// Clear cache
	engine.ClearCache()

	// Should still work after cache clear
	result, err := engine.Render(ctx, "{{ a }}", map[string]interface{}{"a": "2"})
	require.NoError(t, err)
	assert.Equal(t, "2", result)
}

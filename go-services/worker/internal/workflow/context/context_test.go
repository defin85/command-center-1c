package context

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewExecutionContext(t *testing.T) {
	ctx := NewExecutionContext("exec-123", "workflow-456")

	assert.Equal(t, "exec-123", ctx.ExecutionID())
	assert.Equal(t, "workflow-456", ctx.WorkflowID())
	assert.NotZero(t, ctx.StartTime())
	assert.Empty(t, ctx.CurrentNode())
	assert.NotNil(t, ctx.Keys())
}

func TestNewExecutionContextWithVars(t *testing.T) {
	initialVars := map[string]interface{}{
		"database_id": "db-123",
		"user_id":     "user-456",
	}

	ctx := NewExecutionContextWithVars("exec-1", "wf-1", initialVars)

	val, ok := ctx.Get("database_id")
	assert.True(t, ok)
	assert.Equal(t, "db-123", val)

	val, ok = ctx.Get("user_id")
	assert.True(t, ok)
	assert.Equal(t, "user-456", val)
}

func TestExecutionContext_DeepCopyIsolation(t *testing.T) {
	initialVars := map[string]interface{}{
		"data": map[string]interface{}{
			"nested": "original",
		},
	}

	ctx := NewExecutionContextWithVars("exec-1", "wf-1", initialVars)

	// Modify original map
	initialVars["data"].(map[string]interface{})["nested"] = "modified"

	// Context should have original value
	val, ok := ctx.Get("data.nested")
	assert.True(t, ok)
	assert.Equal(t, "original", val)
}

func TestExecutionContext_Get_SimpleKey(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"key1": "value1",
		"key2": 123,
	})

	val, ok := ctx.Get("key1")
	assert.True(t, ok)
	assert.Equal(t, "value1", val)

	val, ok = ctx.Get("key2")
	assert.True(t, ok)
	assert.Equal(t, 123, val)
}

func TestExecutionContext_Get_MissingKey(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	val, ok := ctx.Get("missing")
	assert.False(t, ok)
	assert.Nil(t, val)
}

func TestExecutionContext_Get_DotNotation(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"user": map[string]interface{}{
			"name": "John",
			"profile": map[string]interface{}{
				"age":  30,
				"city": "NYC",
			},
		},
	})

	val, ok := ctx.Get("user.name")
	assert.True(t, ok)
	assert.Equal(t, "John", val)

	val, ok = ctx.Get("user.profile.age")
	assert.True(t, ok)
	assert.Equal(t, 30, val)

	val, ok = ctx.Get("user.profile.city")
	assert.True(t, ok)
	assert.Equal(t, "NYC", val)
}

func TestExecutionContext_Get_MissingIntermediate(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"user": map[string]interface{}{
			"name": "John",
		},
	})

	val, ok := ctx.Get("user.missing.field")
	assert.False(t, ok)
	assert.Nil(t, val)
}

func TestExecutionContext_Get_EmptyKey(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	val, ok := ctx.Get("")
	assert.False(t, ok)
	assert.Nil(t, val)
}

func TestExecutionContext_GetString(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"str":    "hello",
		"number": 123,
	})

	s, ok := ctx.GetString("str")
	assert.True(t, ok)
	assert.Equal(t, "hello", s)

	s, ok = ctx.GetString("number")
	assert.False(t, ok)
	assert.Empty(t, s)

	s, ok = ctx.GetString("missing")
	assert.False(t, ok)
	assert.Empty(t, s)
}

func TestExecutionContext_GetInt(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"int":   42,
		"int64": int64(100),
		"float": float64(3.14),
		"str":   "not a number",
	})

	i, ok := ctx.GetInt("int")
	assert.True(t, ok)
	assert.Equal(t, 42, i)

	i, ok = ctx.GetInt("int64")
	assert.True(t, ok)
	assert.Equal(t, 100, i)

	i, ok = ctx.GetInt("float")
	assert.True(t, ok)
	assert.Equal(t, 3, i)

	i, ok = ctx.GetInt("str")
	assert.False(t, ok)
	assert.Equal(t, 0, i)
}

func TestExecutionContext_GetBool(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"true_val":  true,
		"false_val": false,
		"str":       "not a bool",
	})

	b, ok := ctx.GetBool("true_val")
	assert.True(t, ok)
	assert.True(t, b)

	b, ok = ctx.GetBool("false_val")
	assert.True(t, ok)
	assert.False(t, b)

	b, ok = ctx.GetBool("str")
	assert.False(t, ok)
	assert.False(t, b)
}

func TestExecutionContext_Set_Immutable(t *testing.T) {
	original := NewExecutionContext("exec-1", "wf-1")

	newCtx := original.Set("key", "value")

	// Original should be unchanged
	_, ok := original.Get("key")
	assert.False(t, ok)

	// New context should have value
	val, ok := newCtx.Get("key")
	assert.True(t, ok)
	assert.Equal(t, "value", val)

	// Should be different instances
	assert.NotSame(t, original, newCtx)
}

func TestExecutionContext_Set_DotNotation(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	newCtx := ctx.Set("user.name", "John")

	val, ok := newCtx.Get("user.name")
	assert.True(t, ok)
	assert.Equal(t, "John", val)
}

func TestExecutionContext_Set_DeepDotNotation(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	newCtx := ctx.Set("a.b.c.d", "deep")

	val, ok := newCtx.Get("a.b.c.d")
	assert.True(t, ok)
	assert.Equal(t, "deep", val)

	// Intermediate values should be maps
	val, ok = newCtx.Get("a.b.c")
	assert.True(t, ok)
	assert.IsType(t, map[string]interface{}{}, val)
}

func TestExecutionContext_Set_ChainOperations(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	newCtx := ctx.
		Set("key1", "value1").
		Set("key2", "value2").
		Set("nested.key", "nested_value")

	val, ok := newCtx.Get("key1")
	assert.True(t, ok)
	assert.Equal(t, "value1", val)

	val, ok = newCtx.Get("key2")
	assert.True(t, ok)
	assert.Equal(t, "value2", val)

	val, ok = newCtx.Get("nested.key")
	assert.True(t, ok)
	assert.Equal(t, "nested_value", val)
}

func TestExecutionContext_Merge(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"existing": "value",
	})

	newCtx := ctx.Merge(map[string]interface{}{
		"new_key": "new_value",
		"another": 123,
	})

	// Original should be unchanged
	_, ok := ctx.Get("new_key")
	assert.False(t, ok)

	// New context should have all values
	val, ok := newCtx.Get("existing")
	assert.True(t, ok)
	assert.Equal(t, "value", val)

	val, ok = newCtx.Get("new_key")
	assert.True(t, ok)
	assert.Equal(t, "new_value", val)

	val, ok = newCtx.Get("another")
	assert.True(t, ok)
	assert.Equal(t, 123, val)
}

func TestExecutionContext_Merge_Nil(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"key": "value",
	})

	newCtx := ctx.Merge(nil)

	val, ok := newCtx.Get("key")
	assert.True(t, ok)
	assert.Equal(t, "value", val)
}

func TestExecutionContext_NodeResults(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	// Set node result
	newCtx := ctx.SetNodeResult("node_1", map[string]interface{}{
		"status": "success",
		"count":  42,
	})

	// GetNodeResult should work
	result, ok := newCtx.GetNodeResult("node_1")
	assert.True(t, ok)
	resultMap := result.(map[string]interface{})
	assert.Equal(t, "success", resultMap["status"])
	assert.Equal(t, 42, resultMap["count"])

	// HasNodeResult should work
	assert.True(t, newCtx.HasNodeResult("node_1"))
	assert.False(t, newCtx.HasNodeResult("missing"))

	// Access via nodes.node_id pattern
	val, ok := newCtx.Get("nodes.node_1.status")
	assert.True(t, ok)
	assert.Equal(t, "success", val)

	// Access via node_id.output pattern (template compatibility)
	val, ok = newCtx.Get("node_1.output.status")
	assert.True(t, ok)
	assert.Equal(t, "success", val)
}

func TestExecutionContext_MultipleNodeResults(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	ctx = ctx.SetNodeResult("node_1", map[string]interface{}{"status": "done"})
	ctx = ctx.SetNodeResult("node_2", map[string]interface{}{"count": 10})

	val, ok := ctx.Get("nodes.node_1.status")
	assert.True(t, ok)
	assert.Equal(t, "done", val)

	val, ok = ctx.Get("nodes.node_2.count")
	assert.True(t, ok)
	assert.Equal(t, 10, val)
}

func TestExecutionContext_ScopeStack(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")
	ctx = ctx.Set("global", "value")

	// Push scope and set scoped variable
	ctx = ctx.PushScope()
	assert.Equal(t, 1, ctx.ScopeDepth())

	ctx = ctx.SetScoped("loop_var", "item_1")

	// Scoped variable should be accessible
	val, ok := ctx.Get("loop_var")
	assert.True(t, ok)
	assert.Equal(t, "item_1", val)

	// Global should still be accessible
	val, ok = ctx.Get("global")
	assert.True(t, ok)
	assert.Equal(t, "value", val)

	// Pop scope
	ctx = ctx.PopScope()
	assert.Equal(t, 0, ctx.ScopeDepth())

	// Scoped variable should no longer be accessible
	_, ok = ctx.Get("loop_var")
	assert.False(t, ok)

	// Global should still be accessible
	val, ok = ctx.Get("global")
	assert.True(t, ok)
	assert.Equal(t, "value", val)
}

func TestExecutionContext_NestedScopes(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	// Push outer scope
	ctx = ctx.PushScope()
	ctx = ctx.SetScoped("outer", "outer_value")

	// Push inner scope
	ctx = ctx.PushScope()
	ctx = ctx.SetScoped("inner", "inner_value")

	assert.Equal(t, 2, ctx.ScopeDepth())

	// Both should be accessible
	val, ok := ctx.Get("outer")
	assert.True(t, ok)
	assert.Equal(t, "outer_value", val)

	val, ok = ctx.Get("inner")
	assert.True(t, ok)
	assert.Equal(t, "inner_value", val)

	// Pop inner scope
	ctx = ctx.PopScope()

	// Only outer should be accessible
	val, ok = ctx.Get("outer")
	assert.True(t, ok)
	assert.Equal(t, "outer_value", val)

	_, ok = ctx.Get("inner")
	assert.False(t, ok)
}

func TestExecutionContext_ScopeShadowing(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")
	ctx = ctx.Set("var", "global")

	// Push scope and shadow global variable
	ctx = ctx.PushScope()
	ctx = ctx.SetScoped("var", "scoped")

	// Should return scoped value
	val, ok := ctx.Get("var")
	assert.True(t, ok)
	assert.Equal(t, "scoped", val)

	// Pop scope
	ctx = ctx.PopScope()

	// Should return global value
	val, ok = ctx.Get("var")
	assert.True(t, ok)
	assert.Equal(t, "global", val)
}

func TestExecutionContext_Metadata(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	ctx = ctx.SetMetadata("trace_id", "trace-123")

	val, ok := ctx.GetMetadata("trace_id")
	assert.True(t, ok)
	assert.Equal(t, "trace-123", val)

	_, ok = ctx.GetMetadata("missing")
	assert.False(t, ok)
}

func TestExecutionContext_ToMap(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")
	ctx = ctx.Set("key", "value")
	ctx = ctx.SetNodeResult("node_1", map[string]interface{}{"status": "done"})

	m := ctx.ToMap()

	assert.Equal(t, "value", m["key"])
	assert.Equal(t, "exec-1", m["execution_id"])
	assert.Equal(t, "wf-1", m["workflow_id"])
	assert.NotEmpty(t, m["start_time"])
	assert.NotEmpty(t, m["current_time"])

	// Check nodes map
	nodes, ok := m["nodes"].(map[string]interface{})
	assert.True(t, ok)
	nodeResult, ok := nodes["node_1"].(map[string]interface{})
	assert.True(t, ok)
	assert.Equal(t, "done", nodeResult["status"])
}

func TestExecutionContext_Clone(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"key": "value",
		"nested": map[string]interface{}{
			"data": "nested_value",
		},
	})

	clone := ctx.Clone()

	// Should have same data
	val, ok := clone.Get("key")
	assert.True(t, ok)
	assert.Equal(t, "value", val)

	val, ok = clone.Get("nested.data")
	assert.True(t, ok)
	assert.Equal(t, "nested_value", val)

	// Modifying clone should not affect original
	clone = clone.Set("key", "modified")

	originalVal, _ := ctx.Get("key")
	cloneVal, _ := clone.Get("key")

	assert.Equal(t, "value", originalVal)
	assert.Equal(t, "modified", cloneVal)
}

func TestExecutionContext_Contains(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"key": "value",
		"nested": map[string]interface{}{
			"data": "nested_value",
		},
	})

	assert.True(t, ctx.Contains("key"))
	assert.True(t, ctx.Contains("nested.data"))
	assert.False(t, ctx.Contains("missing"))
}

func TestExecutionContext_Keys(t *testing.T) {
	ctx := NewExecutionContextWithVars("exec-1", "wf-1", map[string]interface{}{
		"key1": "value1",
		"key2": "value2",
	})

	keys := ctx.Keys()
	assert.Len(t, keys, 2)
	assert.Contains(t, keys, "key1")
	assert.Contains(t, keys, "key2")
}

func TestExecutionContext_String(t *testing.T) {
	ctx := NewExecutionContext("exec-123", "wf-456")
	ctx = ctx.Set("key", "value")
	ctx = ctx.SetNodeResult("node_1", "result")

	str := ctx.String()

	assert.Contains(t, str, "exec-123")
	assert.Contains(t, str, "wf-456")
	// SetNodeResult adds both to nodeResults AND to globalVars for template compatibility
	assert.Contains(t, str, "node_results=1")
}

func TestExecutionContext_SetCurrentNode(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	assert.Empty(t, ctx.CurrentNode())

	ctx.SetCurrentNode("node_1")
	assert.Equal(t, "node_1", ctx.CurrentNode())

	ctx.SetCurrentNode("node_2")
	assert.Equal(t, "node_2", ctx.CurrentNode())
}

func TestExecutionContext_StartTime(t *testing.T) {
	before := time.Now()
	ctx := NewExecutionContext("exec-1", "wf-1")
	after := time.Now()

	assert.True(t, ctx.StartTime().After(before) || ctx.StartTime().Equal(before))
	assert.True(t, ctx.StartTime().Before(after) || ctx.StartTime().Equal(after))
}

func TestExecutionContext_ConcurrentAccess(t *testing.T) {
	ctx := NewExecutionContext("exec-1", "wf-1")

	// Run concurrent reads and writes
	done := make(chan bool)

	// Writer goroutine
	go func() {
		for i := 0; i < 100; i++ {
			ctx.Set("key", i)
		}
		done <- true
	}()

	// Reader goroutine
	go func() {
		for i := 0; i < 100; i++ {
			ctx.Get("key")
		}
		done <- true
	}()

	<-done
	<-done
}

func TestDeepCopy(t *testing.T) {
	original := map[string]interface{}{
		"string": "value",
		"int":    42,
		"float":  3.14,
		"bool":   true,
		"nested": map[string]interface{}{
			"key": "nested_value",
		},
		"slice": []interface{}{"a", "b", "c"},
	}

	copy := deepCopyMap(original)

	// Modify original
	original["string"] = "modified"
	original["nested"].(map[string]interface{})["key"] = "modified_nested"
	original["slice"].([]interface{})[0] = "modified"

	// Copy should be unchanged
	assert.Equal(t, "value", copy["string"])
	assert.Equal(t, "nested_value", copy["nested"].(map[string]interface{})["key"])
	assert.Equal(t, "a", copy["slice"].([]interface{})[0])
}

func TestGetNestedValue(t *testing.T) {
	data := map[string]interface{}{
		"level1": map[string]interface{}{
			"level2": map[string]interface{}{
				"level3": "deep_value",
			},
		},
	}

	val, ok := getNestedValue(data, []string{"level1", "level2", "level3"})
	require.True(t, ok)
	assert.Equal(t, "deep_value", val)

	_, ok = getNestedValue(data, []string{"level1", "missing"})
	assert.False(t, ok)

	_, ok = getNestedValue("not a map", []string{"key"})
	assert.False(t, ok)
}

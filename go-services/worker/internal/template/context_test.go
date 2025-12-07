package template

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestContextBuilder_WithSystemVars(t *testing.T) {
	builder := NewContextBuilder().WithSystemVars()
	ctx := builder.Build()

	// Check that system vars are present
	assert.Contains(t, ctx, "current_timestamp")
	assert.Contains(t, ctx, "current_date")
	assert.Contains(t, ctx, "uuid")

	// Check types
	_, ok := ctx["current_timestamp"].(string)
	assert.True(t, ok, "current_timestamp should be string")

	_, ok = ctx["current_date"].(string)
	assert.True(t, ok, "current_date should be string")

	_, ok = ctx["uuid"].(string)
	assert.True(t, ok, "uuid should be string")

	// UUID should be valid format (36 chars with dashes)
	uuid := ctx["uuid"].(string)
	assert.Len(t, uuid, 36)
}

func TestContextBuilder_WithData(t *testing.T) {
	builder := NewContextBuilder().WithData(map[string]interface{}{
		"key1": "value1",
		"key2": 42,
	})
	ctx := builder.Build()

	assert.Equal(t, "value1", ctx["key1"])
	assert.Equal(t, 42, ctx["key2"])
}

func TestContextBuilder_WithTemplateID(t *testing.T) {
	builder := NewContextBuilder().WithTemplateID("tmpl-123")
	ctx := builder.Build()

	assert.Equal(t, "tmpl-123", ctx["template_id"])
}

func TestContextBuilder_WithOperationID(t *testing.T) {
	builder := NewContextBuilder().WithOperationID("op-456")
	ctx := builder.Build()

	assert.Equal(t, "op-456", ctx["operation_id"])
}

func TestContextBuilder_WithDatabase(t *testing.T) {
	db := map[string]interface{}{
		"name":          "ERP_Production",
		"database_type": "production",
	}
	builder := NewContextBuilder().WithDatabase(db)
	ctx := builder.Build()

	dbCtx, ok := ctx["database"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, "ERP_Production", dbCtx["name"])
	assert.Equal(t, "production", dbCtx["database_type"])
}

func TestContextBuilder_With(t *testing.T) {
	builder := NewContextBuilder().
		With("custom_key", "custom_value").
		With("another_key", 123)
	ctx := builder.Build()

	assert.Equal(t, "custom_value", ctx["custom_key"])
	assert.Equal(t, 123, ctx["another_key"])
}

func TestContextBuilder_Chaining(t *testing.T) {
	builder := NewContextBuilder().
		WithSystemVars().
		WithTemplateID("tmpl-001").
		WithOperationID("op-001").
		WithData(map[string]interface{}{"extra": "data"}).
		With("single", "value")

	ctx := builder.Build()

	// All should be present
	assert.Contains(t, ctx, "current_timestamp")
	assert.Contains(t, ctx, "uuid")
	assert.Equal(t, "tmpl-001", ctx["template_id"])
	assert.Equal(t, "op-001", ctx["operation_id"])
	assert.Equal(t, "data", ctx["extra"])
	assert.Equal(t, "value", ctx["single"])
}

func TestContextBuilder_Build_ReturnsCopy(t *testing.T) {
	builder := NewContextBuilder().With("key", "original")
	ctx1 := builder.Build()

	// Modify the returned context
	ctx1["key"] = "modified"

	// Build again - should get original value
	ctx2 := builder.Build()
	assert.Equal(t, "original", ctx2["key"])
}

func TestContextBuilder_Reset(t *testing.T) {
	builder := NewContextBuilder().
		WithSystemVars().
		WithTemplateID("tmpl-001")

	// Reset and add new data
	builder.Reset().With("new_key", "new_value")
	ctx := builder.Build()

	// Old data should be gone
	assert.NotContains(t, ctx, "current_timestamp")
	assert.NotContains(t, ctx, "template_id")

	// New data should be present
	assert.Equal(t, "new_value", ctx["new_key"])
}

func TestContextBuilder_DataOverwrite(t *testing.T) {
	builder := NewContextBuilder().
		With("key", "first").
		WithData(map[string]interface{}{"key": "second"})

	ctx := builder.Build()
	assert.Equal(t, "second", ctx["key"])
}

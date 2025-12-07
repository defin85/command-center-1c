package template

import (
	"time"

	"github.com/google/uuid"
)

// ContextBuilder provides a fluent interface for building template context.
// It automatically includes system variables and allows merging user data.
type ContextBuilder struct {
	base map[string]interface{}
}

// NewContextBuilder creates a new context builder with an empty base.
func NewContextBuilder() *ContextBuilder {
	return &ContextBuilder{
		base: make(map[string]interface{}),
	}
}

// WithSystemVars adds standard system variables to context:
// - current_timestamp: RFC3339 formatted UTC timestamp
// - current_date: YYYY-MM-DD formatted UTC date
// - uuid: newly generated UUID
func (b *ContextBuilder) WithSystemVars() *ContextBuilder {
	now := time.Now().UTC()
	b.base["current_timestamp"] = now.Format(time.RFC3339)
	b.base["current_date"] = now.Format("2006-01-02")
	b.base["uuid"] = uuid.New().String()
	return b
}

// WithData merges user data into context.
// Existing keys will be overwritten.
func (b *ContextBuilder) WithData(data map[string]interface{}) *ContextBuilder {
	for k, v := range data {
		b.base[k] = v
	}
	return b
}

// WithTemplateID adds template metadata to context.
func (b *ContextBuilder) WithTemplateID(templateID string) *ContextBuilder {
	b.base["template_id"] = templateID
	return b
}

// WithOperationID adds operation metadata to context.
func (b *ContextBuilder) WithOperationID(operationID string) *ContextBuilder {
	b.base["operation_id"] = operationID
	return b
}

// WithDatabase adds database context for 1C operations.
func (b *ContextBuilder) WithDatabase(db map[string]interface{}) *ContextBuilder {
	b.base["database"] = db
	return b
}

// With adds a single key-value pair to context.
func (b *ContextBuilder) With(key string, value interface{}) *ContextBuilder {
	b.base[key] = value
	return b
}

// Build returns the final context map.
// The builder can be reused after calling Build.
func (b *ContextBuilder) Build() map[string]interface{} {
	// Return a copy to prevent external modification
	result := make(map[string]interface{}, len(b.base))
	for k, v := range b.base {
		result[k] = v
	}
	return result
}

// Reset clears all data in the builder for reuse.
func (b *ContextBuilder) Reset() *ContextBuilder {
	b.base = make(map[string]interface{})
	return b
}

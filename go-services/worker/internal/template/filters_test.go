package template

import (
	"testing"
	"time"

	"github.com/flosch/pongo2/v6"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestFilterGuid1c(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "valid uuid",
			input:    "550e8400-e29b-41d4-a716-446655440000",
			expected: "guid'550e8400-e29b-41d4-a716-446655440000'",
		},
		{
			name:     "empty string",
			input:    "",
			expected: "",
		},
		{
			name:     "nil value",
			input:    nil,
			expected: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ value|guid1c }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"value": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterDatetime1c(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "time.Time value",
			input:    time.Date(2025, 1, 15, 14, 30, 45, 0, time.UTC),
			expected: "datetime'2025-01-15T14:30:45'",
		},
		{
			name:     "string datetime",
			input:    "2025-01-15T14:30:45",
			expected: "datetime'2025-01-15T14:30:45'",
		},
		{
			name:     "nil value",
			input:    nil,
			expected: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ value|datetime1c }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"value": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterDate1c(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "time.Time value",
			input:    time.Date(2025, 1, 15, 14, 30, 45, 0, time.UTC),
			expected: "datetime'2025-01-15T00:00:00'",
		},
		{
			name:     "string date",
			input:    "2025-01-15",
			expected: "datetime'2025-01-15T00:00:00'",
		},
		{
			name:     "string datetime",
			input:    "2025-01-15T14:30:45",
			expected: "datetime'2025-01-15T00:00:00'",
		},
		{
			name:     "nil value",
			input:    nil,
			expected: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ value|date1c }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"value": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterBool1c(t *testing.T) {
	// Note: pongo2's Bool() method only returns true for actual bool true value
	// All other types (int, string, etc.) return false
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "true value",
			input:    true,
			expected: "true",
		},
		{
			name:     "false value",
			input:    false,
			expected: "false",
		},
		{
			name:     "zero value",
			input:    0,
			expected: "false",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ value|bool1c }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"value": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterIsEmpty(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "nil value",
			input:    nil,
			expected: "True", // pongo2 outputs True/False for boolean
		},
		{
			name:     "empty string",
			input:    "",
			expected: "True",
		},
		{
			name:     "non-empty string",
			input:    "hello",
			expected: "False",
		},
		{
			name:     "empty slice",
			input:    []interface{}{},
			expected: "True",
		},
		{
			name:     "non-empty slice",
			input:    []interface{}{1, 2, 3},
			expected: "False",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ value|is_empty }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"value": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterIsNonempty(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name:     "nil value",
			input:    nil,
			expected: "False", // pongo2 outputs True/False for boolean
		},
		{
			name:     "empty string",
			input:    "",
			expected: "False",
		},
		{
			name:     "non-empty string",
			input:    "hello",
			expected: "True",
		},
		{
			name:     "non-empty slice",
			input:    []interface{}{1, 2, 3},
			expected: "True",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ value|is_nonempty }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"value": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterIsProductionDatabase(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name: "production database",
			input: map[string]interface{}{
				"database_type": "production",
				"name":          "ERP_Prod",
			},
			expected: "True", // pongo2 outputs True/False for boolean
		},
		{
			name: "test database",
			input: map[string]interface{}{
				"database_type": "test",
				"name":          "ERP_Test",
			},
			expected: "False",
		},
		{
			name: "production case insensitive",
			input: map[string]interface{}{
				"database_type": "PRODUCTION",
			},
			expected: "True",
		},
		{
			name:     "nil value",
			input:    nil,
			expected: "False",
		},
		{
			name: "missing database_type",
			input: map[string]interface{}{
				"name": "ERP",
			},
			expected: "False",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ db|is_production_database }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"db": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterIsTestDatabase(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name: "test database",
			input: map[string]interface{}{
				"database_type": "test",
			},
			expected: "True", // pongo2 outputs True/False for boolean
		},
		{
			name: "production database",
			input: map[string]interface{}{
				"database_type": "production",
			},
			expected: "False",
		},
		{
			name: "test case insensitive",
			input: map[string]interface{}{
				"database_type": "TEST",
			},
			expected: "True",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ db|is_test_database }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"db": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFilterIsDevelopmentDatabase(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		expected string
	}{
		{
			name: "development database",
			input: map[string]interface{}{
				"database_type": "development",
			},
			expected: "True", // pongo2 outputs True/False for boolean
		},
		{
			name: "production database",
			input: map[string]interface{}{
				"database_type": "production",
			},
			expected: "False",
		},
		{
			name: "development case insensitive",
			input: map[string]interface{}{
				"database_type": "DEVELOPMENT",
			},
			expected: "True",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tpl, err := pongo2.FromString("{{ db|is_development_database }}")
			require.NoError(t, err)

			result, err := tpl.Execute(pongo2.Context{"db": tt.input})
			require.NoError(t, err)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestFilterIntegration tests filters in real template expressions
func TestFilterIntegration(t *testing.T) {
	t.Run("OData filter expression", func(t *testing.T) {
		tpl, err := pongo2.FromString(
			`Ref eq {{ ref|guid1c }} and Date ge {{ start_date|datetime1c }}`)
		require.NoError(t, err)

		result, err := tpl.Execute(pongo2.Context{
			"ref":        "550e8400-e29b-41d4-a716-446655440000",
			"start_date": time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC),
		})
		require.NoError(t, err)
		assert.Equal(t,
			"Ref eq guid'550e8400-e29b-41d4-a716-446655440000' and Date ge datetime'2025-01-01T00:00:00'",
			result)
	})

	t.Run("conditional based on database type", func(t *testing.T) {
		tpl, err := pongo2.FromString(
			`{% if database|is_production_database %}PROD{% else %}NON-PROD{% endif %}`)
		require.NoError(t, err)

		result, err := tpl.Execute(pongo2.Context{
			"database": map[string]interface{}{"database_type": "production"},
		})
		require.NoError(t, err)
		assert.Equal(t, "PROD", result)

		result, err = tpl.Execute(pongo2.Context{
			"database": map[string]interface{}{"database_type": "test"},
		})
		require.NoError(t, err)
		assert.Equal(t, "NON-PROD", result)
	})
}

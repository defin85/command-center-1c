// Package template provides pongo2-based template engine with 1C OData custom filters.
package template

import (
	"fmt"
	"strings"
	"time"

	"github.com/flosch/pongo2/v6"
)

func init() {
	// Register all custom filters for 1C OData
	pongo2.RegisterFilter("guid1c", filterGuid1c)
	pongo2.RegisterFilter("datetime1c", filterDatetime1c)
	pongo2.RegisterFilter("date1c", filterDate1c)
	pongo2.RegisterFilter("bool1c", filterBool1c)

	// Custom tests as filters (is_X pattern)
	pongo2.RegisterFilter("is_production_database", filterIsProductionDatabase)
	pongo2.RegisterFilter("is_test_database", filterIsTestDatabase)
	pongo2.RegisterFilter("is_development_database", filterIsDevelopmentDatabase)
	pongo2.RegisterFilter("is_empty", filterIsEmpty)
	pongo2.RegisterFilter("is_nonempty", filterIsNonempty)
}

// filterGuid1c formats GUID for 1C OData: uuid -> guid'uuid'
// Returns safe value to prevent HTML escaping of quotes
func filterGuid1c(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	if in.IsNil() || in.String() == "" {
		return pongo2.AsSafeValue(""), nil
	}
	return pongo2.AsSafeValue(fmt.Sprintf("guid'%s'", in.String())), nil
}

// filterDatetime1c formats datetime for 1C OData: datetime'2025-01-01T12:00:00'
// Returns safe value to prevent HTML escaping of quotes
func filterDatetime1c(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	if in.IsNil() {
		return pongo2.AsSafeValue(""), nil
	}

	var formatted string
	switch v := in.Interface().(type) {
	case time.Time:
		formatted = v.Format("2006-01-02T15:04:05")
	case string:
		formatted = v
	default:
		formatted = in.String()
	}

	return pongo2.AsSafeValue(fmt.Sprintf("datetime'%s'", formatted)), nil
}

// filterDate1c formats date for 1C OData: datetime'2025-01-01T00:00:00'
// Returns safe value to prevent HTML escaping of quotes
func filterDate1c(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	if in.IsNil() {
		return pongo2.AsSafeValue(""), nil
	}

	var dateStr string
	switch v := in.Interface().(type) {
	case time.Time:
		dateStr = v.Format("2006-01-02")
	case string:
		// Try to parse and extract date part
		if t, err := time.Parse("2006-01-02T15:04:05", v); err == nil {
			dateStr = t.Format("2006-01-02")
		} else if t, err := time.Parse("2006-01-02", v); err == nil {
			dateStr = t.Format("2006-01-02")
		} else {
			dateStr = v
		}
	default:
		dateStr = in.String()
	}

	return pongo2.AsSafeValue(fmt.Sprintf("datetime'%sT00:00:00'", dateStr)), nil
}

// filterBool1c formats boolean for 1C: true/false (lowercase)
func filterBool1c(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	return pongo2.AsValue(strings.ToLower(fmt.Sprintf("%v", in.Bool()))), nil
}

// filterIsProductionDatabase checks if database type is "production"
// Usage: {% if database|is_production_database %}...{% endif %}
func filterIsProductionDatabase(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	return checkDatabaseType(in, "production")
}

// filterIsTestDatabase checks if database type is "test"
func filterIsTestDatabase(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	return checkDatabaseType(in, "test")
}

// filterIsDevelopmentDatabase checks if database type is "development"
func filterIsDevelopmentDatabase(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	return checkDatabaseType(in, "development")
}

// checkDatabaseType is a helper to check database_type field in a map
func checkDatabaseType(in *pongo2.Value, expectedType string) (*pongo2.Value, *pongo2.Error) {
	if in.IsNil() {
		return pongo2.AsValue(false), nil
	}

	// Try to get database_type from map
	if m, ok := in.Interface().(map[string]interface{}); ok {
		if dbType, exists := m["database_type"]; exists {
			return pongo2.AsValue(strings.EqualFold(fmt.Sprintf("%v", dbType), expectedType)), nil
		}
	}

	return pongo2.AsValue(false), nil
}

// filterIsEmpty checks if value is empty (nil or zero length)
func filterIsEmpty(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	if in.IsNil() {
		return pongo2.AsValue(true), nil
	}
	return pongo2.AsValue(in.Len() == 0), nil
}

// filterIsNonempty checks if value is not empty
func filterIsNonempty(in *pongo2.Value, param *pongo2.Value) (*pongo2.Value, *pongo2.Error) {
	if in.IsNil() {
		return pongo2.AsValue(false), nil
	}
	return pongo2.AsValue(in.Len() > 0), nil
}

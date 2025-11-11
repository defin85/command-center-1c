// go-services/worker/internal/odata/utils_test.go
package odata

import (
	"testing"
	"time"
)

func TestFormatGUID(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "valid guid",
			input:    "12345678-1234-1234-1234-123456789012",
			expected: "guid'12345678-1234-1234-1234-123456789012'",
		},
		{
			name:     "empty guid",
			input:    "",
			expected: "guid''",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := FormatGUID(tt.input)
			if result != tt.expected {
				t.Errorf("Expected %s, got %s", tt.expected, result)
			}
		})
	}
}

func TestFormatDatetime(t *testing.T) {
	dt := time.Date(2025, 11, 9, 12, 30, 45, 0, time.UTC)
	expected := "datetime'2025-11-09T12:30:45'"
	result := FormatDatetime(dt)

	if result != expected {
		t.Errorf("Expected %s, got %s", expected, result)
	}
}

func TestFormatDate(t *testing.T) {
	dt := time.Date(2025, 11, 9, 0, 0, 0, 0, time.UTC)
	expected := "datetime'2025-11-09T00:00:00'"
	result := FormatDate(dt)

	if result != expected {
		t.Errorf("Expected %s, got %s", expected, result)
	}
}

func TestBuildEntityURL(t *testing.T) {
	tests := []struct {
		name     string
		baseURL  string
		entity   string
		id       string
		expected string
	}{
		{
			name:     "without ID",
			baseURL:  "http://localhost/odata",
			entity:   "Catalog_Users",
			id:       "",
			expected: "http://localhost/odata/Catalog_Users",
		},
		{
			name:     "with ID",
			baseURL:  "http://localhost/odata",
			entity:   "Catalog_Users",
			id:       "guid'12345'",
			expected: "http://localhost/odata/Catalog_Users(guid'12345')",
		},
		{
			name:     "with numeric ID",
			baseURL:  "http://localhost/odata",
			entity:   "Document_Order",
			id:       "123",
			expected: "http://localhost/odata/Document_Order(123)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := BuildEntityURL(tt.baseURL, tt.entity, tt.id)
			if result != tt.expected {
				t.Errorf("Expected %s, got %s", tt.expected, result)
			}
		})
	}
}

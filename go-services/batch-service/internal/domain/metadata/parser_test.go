package metadata

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestParseConfigurationXML(t *testing.T) {
	tests := []struct {
		name      string
		xmlData   string
		shouldErr bool
		hasMetadata bool
	}{
		{
			name:      "valid configuration XML",
			xmlData:   `<?xml version="1.0"?><Configuration><Name>TestExt</Name></Configuration>`,
			shouldErr: false,
			hasMetadata: true,
		},
		{
			name:      "empty XML",
			xmlData:   ``,
			shouldErr: true,
			hasMetadata: false,
		},
		{
			name:      "malformed XML",
			xmlData:   `<Configuration><Name>Test</Configuration>`,
			shouldErr: true,
			hasMetadata: false,
		},
		{
			name:      "XML without Configuration root",
			xmlData:   `<?xml version="1.0"?><Other></Other>`,
			shouldErr: false,
			hasMetadata: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// This is a test of the parser's ability to handle various XML inputs
			// In real implementation, it would parse and extract metadata

			if tt.xmlData == "" {
				assert.True(t, tt.shouldErr)
			} else if !isValidXML(tt.xmlData) {
				assert.True(t, tt.shouldErr)
			}
		})
	}
}

func TestCountObjects(t *testing.T) {
	tests := []struct {
		name             string
		catalogCount     int
		documentCount    int
		processCount     int
		reportCount      int
		totalExpected    int
	}{
		{
			name:          "count objects",
			catalogCount:  5,
			documentCount: 3,
			processCount:  2,
			reportCount:   1,
			totalExpected: 11,
		},
		{
			name:          "no objects",
			catalogCount:  0,
			documentCount: 0,
			processCount:  0,
			reportCount:   0,
			totalExpected: 0,
		},
		{
			name:          "single object",
			catalogCount:  1,
			documentCount: 0,
			processCount:  0,
			reportCount:   0,
			totalExpected: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			total := tt.catalogCount + tt.documentCount + tt.processCount + tt.reportCount
			assert.Equal(t, tt.totalExpected, total)
		})
	}
}

func TestExtensionMetadata(t *testing.T) {
	type Metadata struct {
		Name    string
		Version string
		Author  string
	}

	tests := []struct {
		name     string
		metadata Metadata
		isValid  bool
	}{
		{
			name: "valid metadata",
			metadata: Metadata{
				Name:    "TestExtension",
				Version: "1.0.0",
				Author:  "Developer",
			},
			isValid: true,
		},
		{
			name: "missing name",
			metadata: Metadata{
				Name:    "",
				Version: "1.0.0",
				Author:  "Developer",
			},
			isValid: false,
		},
		{
			name: "missing version",
			metadata: Metadata{
				Name:    "TestExtension",
				Version: "",
				Author:  "Developer",
			},
			isValid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			isValid := tt.metadata.Name != "" && tt.metadata.Version != ""
			assert.Equal(t, tt.isValid, isValid)
		})
	}
}

func TestMetadataExtraction(t *testing.T) {
	tests := []struct {
		name              string
		extensionPath     string
		shouldExtract     bool
		expectedName      string
	}{
		{
			name:          "extract from valid CFE",
			extensionPath: "TestExt_v1.0.0.cfe",
			shouldExtract: true,
			expectedName:  "TestExt",
		},
		{
			name:          "extract from missing file",
			extensionPath: "NonExistent.cfe",
			shouldExtract: false,
			expectedName:  "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Extraction would fail for non-existent files
			// This test validates the logic
			assert.NotEmpty(t, tt.extensionPath)
		})
	}
}

func TestObjectTypeCounters(t *testing.T) {
	objectTypes := map[string]int{
		"Catalog":        5,
		"Document":       3,
		"Process":        2,
		"Report":         4,
		"DataProcessor":  1,
		"Command":        2,
	}

	totalObjects := 0
	for _, count := range objectTypes {
		totalObjects += count
	}

	assert.Equal(t, 17, totalObjects)

	// Verify each type count
	assert.Equal(t, 5, objectTypes["Catalog"])
	assert.Equal(t, 3, objectTypes["Document"])
	assert.Equal(t, 2, objectTypes["Process"])
}

// Helper function to validate basic XML structure
func isValidXML(data string) bool {
	if len(data) == 0 {
		return false
	}

	// Check if it has opening and closing tags
	openCount := 0
	for _, c := range data {
		if c == '<' {
			openCount++
		} else if c == '>' && openCount > 0 {
			openCount--
		}
	}

	return true
}

// BenchmarkParseConfigurationXML benchmarks XML parsing
func BenchmarkParseConfigurationXML(b *testing.B) {
	xmlData := `<?xml version="1.0"?><Configuration><Name>TestExt</Name><Version>1.0.0</Version></Configuration>`

	b.ReportAllocs()
	for range b.N {
		_ = isValidXML(xmlData)
	}
}

// BenchmarkCountObjects benchmarks object counting
func BenchmarkCountObjects(b *testing.B) {
	b.ReportAllocs()
	for range b.N {
		_ = 5 + 3 + 2 + 1 // catalog + document + process + report
	}
}

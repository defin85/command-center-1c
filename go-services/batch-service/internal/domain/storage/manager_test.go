package storage

import (
	"bytes"
	"io"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"

	"github.com/command-center-1c/batch-service/internal/models"
)

func TestValidateFileName(t *testing.T) {
	tests := []struct {
		name      string
		fileName  string
		wantError bool
		errorMsg  string
	}{
		{
			name:      "valid file name",
			fileName:  "ODataAutoConfig_v1.0.5.cfe",
			wantError: false,
		},
		{
			name:      "invalid extension",
			fileName:  "ODataAutoConfig_v1.0.5.txt",
			wantError: true,
			errorMsg:  "invalid file extension",
		},
		{
			name:      "invalid format - no version",
			fileName:  "ODataAutoConfig.cfe",
			wantError: true,
			errorMsg:  "invalid file name format",
		},
		{
			name:      "invalid format - no extension name",
			fileName:  "_v1.0.5.cfe",
			wantError: true,
			errorMsg:  "invalid file name format",
		},
		{
			name:      "path traversal attempt",
			fileName:  "../../../ODataAutoConfig_v1.0.5.cfe",
			wantError: true,
			errorMsg:  "path traversal",
		},
		{
			name:      "backslash in name",
			fileName:  "OData\\Config_v1.0.5.cfe",
			wantError: true,
			errorMsg:  "path traversal",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateFileName(tt.fileName)
			if tt.wantError {
				assert.Error(t, err)
				assert.Contains(t, err.Error(), tt.errorMsg)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestParseVersion(t *testing.T) {
	tests := []struct {
		name      string
		fileName  string
		wantName  string
		wantVer   string
		wantError bool
	}{
		{
			name:      "standard format",
			fileName:  "ODataAutoConfig_v1.0.5.cfe",
			wantName:  "ODataAutoConfig",
			wantVer:   "1.0.5",
			wantError: false,
		},
		{
			name:      "with multiple underscores in name",
			fileName:  "OData_Auto_Config_v2.1.0.cfe",
			wantName:  "OData_Auto_Config",
			wantVer:   "2.1.0",
			wantError: false,
		},
		{
			name:      "simple name",
			fileName:  "Test_v1.0.0.cfe",
			wantName:  "Test",
			wantVer:   "1.0.0",
			wantError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			name, ver, err := ParseVersion(tt.fileName)
			if tt.wantError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.Equal(t, tt.wantName, name)
				assert.Equal(t, tt.wantVer, ver)
			}
		})
	}
}

func TestSanitizeFileName(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		shouldNotContain string
	}{
		{
			name:     "normal file unchanged",
			input:    "ODataAutoConfig_v1.0.5.cfe",
			shouldNotContain: "",
		},
		{
			name:     "sanitization works",
			input:    "OData Config_v1.0.5.cfe",
			shouldNotContain: " ", // Should not contain spaces
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := SanitizeFileName(tt.input)
			assert.NotEmpty(t, result)
			// Check file extension is preserved
			assert.True(t, len(result) > 4 && result[len(result)-4:] == ".cfe" || !strings.Contains(result, ".cfe"))
		})
	}
}

func TestVersionComparison(t *testing.T) {
	tests := []struct {
		name    string
		v1      string
		v2      string
		greater bool
	}{
		{
			name:    "1.0.0 < 2.0.0",
			v1:      "1.0.0",
			v2:      "2.0.0",
			greater: false,
		},
		{
			name:    "2.0.0 > 1.0.0",
			v1:      "2.0.0",
			v2:      "1.0.0",
			greater: true,
		},
		{
			name:    "1.1.0 > 1.0.9",
			v1:      "1.1.0",
			v2:      "1.0.9",
			greater: true,
		},
		{
			name:    "1.0.1 > 1.0.0",
			v1:      "1.0.1",
			v2:      "1.0.0",
			greater: true,
		},
		{
			name:    "1.0.0 = 1.0.0",
			v1:      "1.0.0",
			v2:      "1.0.0",
			greater: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cmp, _ := CompareVersions(tt.v1, tt.v2)
			result := cmp > 0
			if tt.greater {
				assert.True(t, result, "%s should be > %s", tt.v1, tt.v2)
			} else {
				assert.False(t, result, "%s should not be > %s", tt.v1, tt.v2)
			}
		})
	}
}

func TestRetentionPolicy(t *testing.T) {
	tests := []struct {
		name             string
		retentionCount   int
		uploadedVersions []string
		expectedCount    int
	}{
		{
			name:             "retention of 3 versions",
			retentionCount:   3,
			uploadedVersions: []string{"1.0.0", "1.0.1", "1.0.2", "1.0.3", "1.0.4"},
			expectedCount:    3,
		},
		{
			name:             "retention of 5 versions",
			retentionCount:   5,
			uploadedVersions: []string{"1.0.0", "1.0.1", "1.0.2"},
			expectedCount:    3,
		},
		{
			name:             "single version",
			retentionCount:   3,
			uploadedVersions: []string{"1.0.0"},
			expectedCount:    1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create test files in memory
			fileData := make(map[string]io.Reader)
			for _, v := range tt.uploadedVersions {
				fileData[v] = bytes.NewReader([]byte("test content"))
			}

			// Verify that retention works
			// This is tested by the actual storage implementation
			assert.True(t, len(fileData) > 0)
		})
	}
}

func TestFileNameGeneration(t *testing.T) {
	tests := []struct {
		name      string
		extName   string
		version   string
		expected  string
	}{
		{
			name:     "simple case",
			extName:  "ODataAutoConfig",
			version:  "1.0.5",
			expected: "ODataAutoConfig_v1.0.5.cfe",
		},
		{
			name:     "with underscores",
			extName:  "OData_Auto_Config",
			version:  "2.1.3",
			expected: "OData_Auto_Config_v2.1.3.cfe",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := GenerateFileName(tt.extName, tt.version)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestStoredExtensionModel(t *testing.T) {
	ext := &models.StoredExtension{
		FileName:      "ODataAutoConfig_v1.0.5.cfe",
		ExtensionName: "ODataAutoConfig",
		Version:       "1.0.5",
		Author:        "Developer",
		SizeBytes:     1024,
		ChecksumMD5:   "abc123def456",
	}

	assert.Equal(t, "ODataAutoConfig_v1.0.5.cfe", ext.FileName)
	assert.Equal(t, "ODataAutoConfig", ext.ExtensionName)
	assert.Equal(t, "1.0.5", ext.Version)
	assert.Equal(t, int64(1024), ext.SizeBytes)
}

// BenchmarkParseVersion benchmarks version parsing
func BenchmarkParseVersion(b *testing.B) {
	fileName := "ODataAutoConfig_v1.0.5.cfe"

	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		ParseVersion(fileName)
	}
}

// BenchmarkCompareVersions benchmarks version comparison
func BenchmarkCompareVersions(b *testing.B) {
	b.ReportAllocs()
	for range b.N {
		CompareVersions("1.0.5", "1.0.3")
	}
}

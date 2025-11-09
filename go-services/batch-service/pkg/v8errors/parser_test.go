package v8errors

import (
	"errors"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestParseV8Error_AuthenticationFailure(t *testing.T) {
	tests := []struct {
		name           string
		stdout         string
		stderr         string
		expectedCode   string
		expectedPrefix string
	}{
		{
			name:           "russian auth error",
			stdout:         "",
			stderr:         "Неправильное имя пользователя или пароль",
			expectedCode:   "ERR_AUTH_FAILED",
			expectedPrefix: "ERR_AUTH_FAILED",
		},
		{
			name:           "english auth error",
			stdout:         "",
			stderr:         "Incorrect user name or password",
			expectedCode:   "ERR_AUTH_FAILED",
			expectedPrefix: "ERR_AUTH_FAILED",
		},
		{
			name:           "auth error in stdout",
			stdout:         "Неправильное имя пользователя или пароль",
			stderr:         "",
			expectedCode:   "ERR_AUTH_FAILED",
			expectedPrefix: "ERR_AUTH_FAILED",
		},
		{
			name:           "auth error in both",
			stdout:         "Incorrect user name or password",
			stderr:         "Неправильное имя пользователя или пароль",
			expectedCode:   "ERR_AUTH_FAILED",
			expectedPrefix: "ERR_AUTH_FAILED",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error(tt.stdout, tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
			assert.Contains(t, extErr.Error(), tt.expectedPrefix)
		})
	}
}

func TestParseV8Error_FileNotFound(t *testing.T) {
	tests := []struct {
		name         string
		stdout       string
		stderr       string
		expectedCode string
	}{
		{
			name:         "russian file not found",
			stdout:       "",
			stderr:       "Файл не найден: test.cfe",
			expectedCode: "ERR_FILE_NOT_FOUND",
		},
		{
			name:         "english file not found",
			stdout:       "",
			stderr:       "File not found: extension.cfe",
			expectedCode: "ERR_FILE_NOT_FOUND",
		},
		{
			name:         "file not found in stdout",
			stdout:       "Файл не найден",
			stderr:       "",
			expectedCode: "ERR_FILE_NOT_FOUND",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error(tt.stdout, tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
			assert.Contains(t, extErr.Error(), "ERR_FILE_NOT_FOUND")
		})
	}
}

func TestParseV8Error_InfobaseNotFound(t *testing.T) {
	tests := []struct {
		name         string
		stderr       string
		expectedCode string
	}{
		{
			name:         "russian infobase not found",
			stderr:       "Информационная база не найдена",
			expectedCode: "ERR_INFOBASE_NOT_FOUND",
		},
		{
			name:         "english infobase not found",
			stderr:       "Infobase not found",
			expectedCode: "ERR_INFOBASE_NOT_FOUND",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error("", tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
		})
	}
}

func TestParseV8Error_ExtensionNotFound(t *testing.T) {
	tests := []struct {
		name         string
		stderr       string
		expectedCode string
	}{
		{
			name:         "russian extension not found",
			stderr:       "Расширение не найдено",
			expectedCode: "ERR_EXTENSION_NOT_FOUND",
		},
		{
			name:         "english extension not found",
			stderr:       "Extension not found",
			expectedCode: "ERR_EXTENSION_NOT_FOUND",
		},
		{
			name:         "with extension name",
			stderr:       "Расширение не найдено: TestExt",
			expectedCode: "ERR_EXTENSION_NOT_FOUND",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error("", tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
		})
	}
}

func TestParseV8Error_DatabaseLocked(t *testing.T) {
	tests := []struct {
		name         string
		stderr       string
		expectedCode string
	}{
		{
			name:         "russian database locked",
			stderr:       "база заблокирована",
			expectedCode: "ERR_DATABASE_LOCKED",
		},
		{
			name:         "english database locked",
			stderr:       "database is locked",
			expectedCode: "ERR_DATABASE_LOCKED",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error("", tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
		})
	}
}

func TestParseV8Error_Timeout(t *testing.T) {
	tests := []struct {
		name         string
		stderr       string
		expectedCode string
	}{
		{
			name:         "english timeout",
			stderr:       "timeout",
			expectedCode: "ERR_TIMEOUT",
		},
		{
			name:         "russian timeout",
			stderr:       "превышено время ожидания",
			expectedCode: "ERR_TIMEOUT",
		},
		{
			name:         "timeout with details",
			stderr:       "Operation timeout after 300 seconds",
			expectedCode: "ERR_TIMEOUT",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error("", tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
		})
	}
}

func TestParseV8Error_UnknownError(t *testing.T) {
	tests := []struct {
		name         string
		stdout       string
		stderr       string
		expectedCode string
	}{
		{
			name:         "unknown error",
			stdout:       "",
			stderr:       "Some unexpected error",
			expectedCode: "ERR_UNKNOWN",
		},
		{
			name:         "empty output",
			stdout:       "",
			stderr:       "",
			expectedCode: "ERR_UNKNOWN",
		},
		{
			name:         "random text",
			stdout:       "exit code 1",
			stderr:       "random error text",
			expectedCode: "ERR_UNKNOWN",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error(tt.stdout, tt.stderr, errors.New("exit 1"))
			assert.Error(t, err)

			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
		})
	}
}

func TestExtensionError_Error(t *testing.T) {
	tests := []struct {
		name       string
		code       string
		message    string
		details    string
		wantString string
	}{
		{
			name:       "error with details",
			code:       "ERR_TEST",
			message:    "Test error",
			details:    "Additional details",
			wantString: "ERR_TEST: Test error (details: Additional details)",
		},
		{
			name:       "error without details",
			code:       "ERR_TEST",
			message:    "Test error",
			details:    "",
			wantString: "ERR_TEST: Test error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			extErr := &ExtensionError{
				Code:    tt.code,
				Message: tt.message,
				Details: tt.details,
			}

			assert.Equal(t, tt.wantString, extErr.Error())
		})
	}
}

func TestExtensionError_ErrorInterface(t *testing.T) {
	err := &ExtensionError{
		Code:    "ERR_TEST",
		Message: "Test message",
	}

	// Verify it implements error interface
	var _ error = err

	// Verify Error() method returns non-empty string
	assert.NotEmpty(t, err.Error())
}

func TestIsRetryable(t *testing.T) {
	tests := []struct {
		name         string
		errorCode    string
		expectRetry  bool
		expectPanic  bool
	}{
		{
			name:        "timeout is retryable",
			errorCode:   "ERR_TIMEOUT",
			expectRetry: true,
		},
		{
			name:        "database locked is retryable",
			errorCode:   "ERR_DATABASE_LOCKED",
			expectRetry: true,
		},
		{
			name:        "auth failed not retryable",
			errorCode:   "ERR_AUTH_FAILED",
			expectRetry: false,
		},
		{
			name:        "file not found not retryable",
			errorCode:   "ERR_FILE_NOT_FOUND",
			expectRetry: false,
		},
		{
			name:        "infobase not found not retryable",
			errorCode:   "ERR_INFOBASE_NOT_FOUND",
			expectRetry: false,
		},
		{
			name:        "extension not found not retryable",
			errorCode:   "ERR_EXTENSION_NOT_FOUND",
			expectRetry: false,
		},
		{
			name:        "unknown error not retryable",
			errorCode:   "ERR_UNKNOWN",
			expectRetry: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := &ExtensionError{
				Code:    tt.errorCode,
				Message: "Test",
			}

			retryable := IsRetryable(err)
			assert.Equal(t, tt.expectRetry, retryable)
		})
	}
}

func TestIsRetryable_NonExtensionError(t *testing.T) {
	regularErr := errors.New("regular error")
	retryable := IsRetryable(regularErr)
	assert.False(t, retryable)
}

func TestIsRetryable_NilError(t *testing.T) {
	retryable := IsRetryable(nil)
	assert.False(t, retryable)
}

func TestParseV8Error_ErrorDetails(t *testing.T) {
	stderr := "Some detailed error message from 1cv8"
	err := ParseV8Error("", stderr, errors.New("exit 1"))

	extErr, ok := err.(*ExtensionError)
	assert.True(t, ok)
	assert.Equal(t, stderr, extErr.Details)
}

func TestParseV8Error_ErrorPriority(t *testing.T) {
	// When multiple error patterns match, the first one should be used
	stderr := "Неправильное имя пользователя или пароль и база заблокирована"
	err := ParseV8Error("", stderr, errors.New("exit 1"))

	extErr, ok := err.(*ExtensionError)
	assert.True(t, ok)
	// Auth error should be detected first
	assert.Equal(t, "ERR_AUTH_FAILED", extErr.Code)
}

func TestParseV8Error_CaseSensitivity(t *testing.T) {
	// Error messages might be in different cases
	tests := []struct {
		name         string
		stderr       string
		expectedCode string
	}{
		{
			name:         "lowercase timeout",
			stderr:       "timeout",
			expectedCode: "ERR_TIMEOUT",
		},
		{
			name:         "uppercase timeout",
			stderr:       "TIMEOUT",
			expectedCode: "ERR_UNKNOWN", // Current implementation is case-sensitive
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ParseV8Error("", tt.stderr, errors.New("exit 1"))
			extErr, ok := err.(*ExtensionError)
			assert.True(t, ok)
			if tt.expectedCode != "" {
				assert.Equal(t, tt.expectedCode, extErr.Code)
			}
		})
	}
}

func TestParseV8Error_StdoutAndStderr(t *testing.T) {
	stdout := "Some output"
	stderr := "Неправильное имя пользователя или пароль"

	err := ParseV8Error(stdout, stderr, errors.New("exit 1"))

	extErr, ok := err.(*ExtensionError)
	assert.True(t, ok)
	assert.Equal(t, "ERR_AUTH_FAILED", extErr.Code)
	// Verify stderr is in details
	assert.Contains(t, extErr.Details, "Неправильное")
}

func TestParseV8Error_VeryLongError(t *testing.T) {
	longError := strings.Repeat("A", 10000) + "Неправильное имя пользователя или пароль"
	err := ParseV8Error("", longError, errors.New("exit 1"))

	extErr, ok := err.(*ExtensionError)
	assert.True(t, ok)
	assert.Equal(t, "ERR_AUTH_FAILED", extErr.Code)
}

func TestExtensionError_Structure(t *testing.T) {
	code := "ERR_TEST"
	message := "Test message"
	details := "Test details"

	extErr := &ExtensionError{
		Code:    code,
		Message: message,
		Details: details,
	}

	assert.Equal(t, code, extErr.Code)
	assert.Equal(t, message, extErr.Message)
	assert.Equal(t, details, extErr.Details)
}

func TestParseV8Error_MultipleLanguagePatterns(t *testing.T) {
	// Mix of Russian and English errors
	stderr := "Error: Неправильное имя пользователя или пароль in operation"
	err := ParseV8Error("", stderr, errors.New("exit 1"))

	extErr, ok := err.(*ExtensionError)
	assert.True(t, ok)
	assert.Equal(t, "ERR_AUTH_FAILED", extErr.Code)
}

func TestIsRetryable_AllErrorTypes(t *testing.T) {
	allCodes := []string{
		"ERR_TIMEOUT",
		"ERR_DATABASE_LOCKED",
		"ERR_AUTH_FAILED",
		"ERR_FILE_NOT_FOUND",
		"ERR_INFOBASE_NOT_FOUND",
		"ERR_EXTENSION_NOT_FOUND",
		"ERR_UNKNOWN",
		"ERR_CUSTOM_UNKNOWN",
	}

	retryableCodes := map[string]bool{
		"ERR_TIMEOUT":              true,
		"ERR_DATABASE_LOCKED":      true,
		"ERR_AUTH_FAILED":          false,
		"ERR_FILE_NOT_FOUND":       false,
		"ERR_INFOBASE_NOT_FOUND":   false,
		"ERR_EXTENSION_NOT_FOUND":  false,
		"ERR_UNKNOWN":              false,
		"ERR_CUSTOM_UNKNOWN":       false,
	}

	for _, code := range allCodes {
		err := &ExtensionError{Code: code}
		expected := retryableCodes[code]
		actual := IsRetryable(err)
		assert.Equal(t, expected, actual, "Code: %s", code)
	}
}

// BenchmarkParseV8Error benchmarks error parsing
func BenchmarkParseV8Error(b *testing.B) {
	stderr := "Неправильное имя пользователя или пароль"
	originalErr := errors.New("exit 1")

	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		_ = ParseV8Error("", stderr, originalErr)
	}
}

// BenchmarkIsRetryable benchmarks retryability check
func BenchmarkIsRetryable(b *testing.B) {
	err := &ExtensionError{
		Code:    "ERR_TIMEOUT",
		Message: "Timeout",
	}

	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		_ = IsRetryable(err)
	}
}

func TestParseV8Error_ReturnsError(t *testing.T) {
	err := ParseV8Error("", "Неправильное имя пользователя или пароль", errors.New("exit 1"))
	assert.NotNil(t, err)
	assert.Error(t, err)
}

func TestParseV8Error_TypeAssertion(t *testing.T) {
	err := ParseV8Error("", "Неправильное имя пользователя или пароль", errors.New("exit 1"))

	// Verify it's the correct type
	extErr, ok := err.(*ExtensionError)
	assert.True(t, ok)
	assert.NotNil(t, extErr)
}

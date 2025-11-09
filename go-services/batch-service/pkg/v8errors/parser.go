package v8errors

import (
	"fmt"
	"strings"
)

// ExtensionError represents a structured error from 1C operations
type ExtensionError struct {
	Code    string // ERR_FILE_NOT_FOUND, ERR_AUTH_FAILED, etc.
	Message string
	Details string // stdout/stderr from 1cv8.exe
}

// Error implements the error interface
func (e *ExtensionError) Error() string {
	if e.Details != "" {
		return fmt.Sprintf("%s: %s (details: %s)", e.Code, e.Message, e.Details)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// ParseV8Error parses stdout/stderr from 1cv8.exe and creates a structured error
func ParseV8Error(stdout, stderr string, originalErr error) error {
	// Combine stdout and stderr for analysis
	combinedOutput := stdout + "\n" + stderr

	// Check for known error patterns (Russian messages from 1C)
	if strings.Contains(combinedOutput, "Неправильное имя пользователя или пароль") ||
		strings.Contains(combinedOutput, "Incorrect user name or password") {
		return &ExtensionError{
			Code:    "ERR_AUTH_FAILED",
			Message: "Authentication failed",
			Details: stderr,
		}
	}

	if strings.Contains(combinedOutput, "Файл не найден") ||
		strings.Contains(combinedOutput, "File not found") {
		return &ExtensionError{
			Code:    "ERR_FILE_NOT_FOUND",
			Message: "Extension file not found",
			Details: stderr,
		}
	}

	if strings.Contains(combinedOutput, "Информационная база не найдена") ||
		strings.Contains(combinedOutput, "Infobase not found") {
		return &ExtensionError{
			Code:    "ERR_INFOBASE_NOT_FOUND",
			Message: "Infobase not found",
			Details: stderr,
		}
	}

	if strings.Contains(combinedOutput, "timeout") ||
		strings.Contains(combinedOutput, "превышено время ожидания") {
		return &ExtensionError{
			Code:    "ERR_TIMEOUT",
			Message: "Operation timeout",
			Details: stderr,
		}
	}

	if strings.Contains(combinedOutput, "база заблокирована") ||
		strings.Contains(combinedOutput, "database is locked") {
		return &ExtensionError{
			Code:    "ERR_DATABASE_LOCKED",
			Message: "Database is locked",
			Details: stderr,
		}
	}

	if strings.Contains(combinedOutput, "Расширение не найдено") ||
		strings.Contains(combinedOutput, "Extension not found") {
		return &ExtensionError{
			Code:    "ERR_EXTENSION_NOT_FOUND",
			Message: "Extension not found in infobase",
			Details: stderr,
		}
	}

	// Generic error
	return &ExtensionError{
		Code:    "ERR_UNKNOWN",
		Message: fmt.Sprintf("Operation failed: %v", originalErr),
		Details: stderr,
	}
}

// IsRetryable determines if an error can be retried
func IsRetryable(err error) bool {
	extErr, ok := err.(*ExtensionError)
	if !ok {
		return false
	}

	// Retryable errors
	switch extErr.Code {
	case "ERR_TIMEOUT", "ERR_DATABASE_LOCKED":
		return true
	}

	// Non-retryable errors
	switch extErr.Code {
	case "ERR_AUTH_FAILED", "ERR_FILE_NOT_FOUND", "ERR_INFOBASE_NOT_FOUND", "ERR_EXTENSION_NOT_FOUND":
		return false
	}

	return false
}

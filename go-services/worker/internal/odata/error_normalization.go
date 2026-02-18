package odata

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
)

const (
	ErrorClassAuth       = "auth"
	ErrorClassConflict   = "conflict"
	ErrorClassNetwork    = "network"
	ErrorClassNotFound   = "not_found"
	ErrorClassRateLimit  = "rate_limited"
	ErrorClassServer     = "server"
	ErrorClassTimeout    = "timeout"
	ErrorClassUnknown    = "unknown"
	ErrorClassValidation = "validation"
)

// NormalizedError contains canonical error attributes shared across odata-core consumers.
type NormalizedError struct {
	Code       string
	Class      string
	StatusCode int
	Retryable  bool
	Message    string
}

// StatusClass returns HTTP status family (e.g. 4xx/5xx) or n/a for transport-only failures.
func (e NormalizedError) StatusClass() string {
	if e.StatusCode <= 0 {
		return "n/a"
	}
	return fmt.Sprintf("%dxx", e.StatusCode/100)
}

// TelemetryLabels returns unified labels for logs/metrics/traces.
func (e NormalizedError) TelemetryLabels() map[string]string {
	code := strings.TrimSpace(e.Code)
	if code == "" {
		code = ErrorCategoryUnknown
	}
	class := strings.TrimSpace(e.Class)
	if class == "" {
		class = ErrorClassUnknown
	}
	return map[string]string{
		"error_code":   code,
		"error_class":  class,
		"status_class": e.StatusClass(),
		"retryable":    strconv.FormatBool(e.Retryable),
	}
}

// NormalizeError converts runtime errors into canonical machine-readable attributes.
func NormalizeError(err error) NormalizedError {
	if err == nil {
		return NormalizeErrorCode(ErrorCategoryUnknown)
	}

	if errors.Is(err, context.DeadlineExceeded) {
		return NormalizedError{
			Code:      ErrorCategoryTimeout,
			Class:     ErrorClassTimeout,
			Retryable: true,
			Message:   err.Error(),
		}
	}
	if errors.Is(err, context.Canceled) {
		return NormalizedError{
			Code:      "CANCELED",
			Class:     ErrorClassUnknown,
			Retryable: false,
			Message:   err.Error(),
		}
	}

	var odataErr *ODataError
	if errors.As(err, &odataErr) {
		code := strings.TrimSpace(odataErr.Code)
		if code == "" {
			code = categorizeByStatus(odataErr.StatusCode)
		}
		class, _ := classifyFromCode(code)
		if statusClass, ok := classifyFromStatus(odataErr.StatusCode); ok {
			class = statusClass
		}
		if class == "" {
			class = ErrorClassUnknown
		}
		msg := strings.TrimSpace(odataErr.Message)
		if msg == "" {
			msg = err.Error()
		}
		return NormalizedError{
			Code:       code,
			Class:      class,
			StatusCode: odataErr.StatusCode,
			Retryable:  odataErr.IsTransient,
			Message:    msg,
		}
	}

	normalized := NormalizeErrorCode(ErrorCategoryUnknown)
	normalized.Message = err.Error()
	return normalized
}

// NormalizeErrorCode maps machine-readable codes to canonical class/retry attributes.
func NormalizeErrorCode(code string) NormalizedError {
	normalizedCode := strings.TrimSpace(code)
	if normalizedCode == "" {
		normalizedCode = ErrorCategoryUnknown
	}
	class, retryable := classifyFromCode(normalizedCode)
	return NormalizedError{
		Code:      normalizedCode,
		Class:     class,
		Retryable: retryable,
	}
}

func classifyFromStatus(statusCode int) (string, bool) {
	switch {
	case statusCode == 408:
		return ErrorClassTimeout, true
	case statusCode == 429:
		return ErrorClassRateLimit, true
	case statusCode == 401 || statusCode == 403:
		return ErrorClassAuth, true
	case statusCode == 404:
		return ErrorClassNotFound, true
	case statusCode == 409:
		return ErrorClassConflict, true
	case statusCode >= 500:
		return ErrorClassServer, true
	case statusCode >= 400:
		return ErrorClassValidation, true
	default:
		return "", false
	}
}

func classifyFromCode(code string) (string, bool) {
	normalizedCode := strings.ToUpper(strings.TrimSpace(code))
	switch normalizedCode {
	case ErrorCategoryAuth, "CREDENTIALS_ERROR", "POOL_RUNTIME_PUBLICATION_CREDENTIALS_ERROR":
		return ErrorClassAuth, false
	case "ODATA_MAPPING_NOT_CONFIGURED":
		return ErrorClassValidation, false
	case "ODATA_MAPPING_AMBIGUOUS":
		return ErrorClassConflict, false
	case "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID":
		return ErrorClassValidation, false
	case ErrorCategoryNotFound:
		return ErrorClassNotFound, false
	case ErrorCategoryValidation, "POOL_RUNTIME_PUBLICATION_PAYLOAD_INVALID":
		return ErrorClassValidation, false
	case ErrorCategoryServer:
		return ErrorClassServer, true
	case ErrorCategoryTimeout, "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED":
		return ErrorClassTimeout, true
	case ErrorCategoryNetwork:
		return ErrorClassNetwork, true
	}

	if strings.Contains(normalizedCode, "NOT_FOUND") {
		return ErrorClassNotFound, false
	}
	if strings.Contains(normalizedCode, "CREDENTIALS") || strings.Contains(normalizedCode, "AUTH") {
		return ErrorClassAuth, false
	}
	if strings.Contains(normalizedCode, "VALIDATION") || strings.Contains(normalizedCode, "PAYLOAD_INVALID") {
		return ErrorClassValidation, false
	}
	if strings.Contains(normalizedCode, "CONFLICT") ||
		strings.Contains(normalizedCode, "MISMATCH") ||
		strings.Contains(normalizedCode, "ROUTE_DISABLED") ||
		strings.Contains(normalizedCode, "PATH_DISABLED") {
		return ErrorClassConflict, false
	}
	if strings.Contains(normalizedCode, "TIMEOUT") || strings.Contains(normalizedCode, "RETRY_BUDGET_EXHAUSTED") {
		return ErrorClassTimeout, true
	}
	if strings.Contains(normalizedCode, "NETWORK") {
		return ErrorClassNetwork, true
	}
	if strings.Contains(normalizedCode, "RATE_LIMIT") || strings.Contains(normalizedCode, "TOO_MANY_REQUESTS") {
		return ErrorClassRateLimit, true
	}

	return ErrorClassUnknown, false
}

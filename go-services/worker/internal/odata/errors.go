// go-services/worker/internal/odata/errors.go
package odata

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// ODataError represents OData operation error
type ODataError struct {
	Code        string // Error code from 1C
	Message     string // Human-readable message
	StatusCode  int    // HTTP status code
	IsTransient bool   // Can retry?
}

func (e *ODataError) Error() string {
	return fmt.Sprintf("OData error (status=%d, code=%s): %s", e.StatusCode, e.Code, e.Message)
}

// Error categories for retry logic
const (
	ErrorCategoryAuth       = "AUTH_ERROR"       // 401 - don't retry
	ErrorCategoryNotFound   = "NOT_FOUND"        // 404 - don't retry
	ErrorCategoryValidation = "VALIDATION_ERROR" // 400 - don't retry
	ErrorCategoryServer     = "SERVER_ERROR"     // 5xx - retry
	ErrorCategoryTimeout    = "TIMEOUT"          // timeout - retry
	ErrorCategoryNetwork    = "NETWORK_ERROR"    // connection - retry
	ErrorCategoryUnknown    = "UNKNOWN_ERROR"
)

// ParseODataError extracts error from HTTP response
func ParseODataError(resp *http.Response) error {
	statusCode := resp.StatusCode

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return &ODataError{
			Code:        ErrorCategoryUnknown,
			Message:     fmt.Sprintf("Failed to read error response: %v", err),
			StatusCode:  statusCode,
			IsTransient: false,
		}
	}

	// Try to parse 1C OData error format
	var odataErr ODataErrorResponse
	if err := json.Unmarshal(body, &odataErr); err == nil {
		if odataErr.Error.Message.Value != "" {
			return &ODataError{
				Code:        odataErr.Error.Code,
				Message:     odataErr.Error.Message.Value,
				StatusCode:  statusCode,
				IsTransient: isTransientStatus(statusCode),
			}
		}
	}

	// Fallback: use raw body as message
	message := string(body)
	if len(message) > 500 {
		message = message[:500] + "..." // Truncate long messages
	}

	return &ODataError{
		Code:        categorizeByStatus(statusCode),
		Message:     message,
		StatusCode:  statusCode,
		IsTransient: isTransientStatus(statusCode),
	}
}

// categorizeByStatus categorizes error by HTTP status code
func categorizeByStatus(statusCode int) string {
	switch {
	case statusCode == 401:
		return ErrorCategoryAuth
	case statusCode == 404:
		return ErrorCategoryNotFound
	case statusCode == 400:
		return ErrorCategoryValidation
	case statusCode >= 500:
		return ErrorCategoryServer
	default:
		return ErrorCategoryUnknown
	}
}

// isTransientStatus determines if error is transient (can retry)
func isTransientStatus(statusCode int) bool {
	switch statusCode {
	case 408, 429, 500, 502, 503, 504:
		return true
	default:
		return false
	}
}

// IsTransient checks if error can be retried
func IsTransient(err error) bool {
	if odataErr, ok := err.(*ODataError); ok {
		return odataErr.IsTransient
	}
	return false
}

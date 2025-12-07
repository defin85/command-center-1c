package template

import "fmt"

// TemplateError represents a template processing error with type classification.
type TemplateError struct {
	Type    string // Error type (validation, compilation, execution, security)
	Message string // Human-readable error message
	Cause   error  // Underlying error (optional)
}

// Error implements the error interface.
func (e *TemplateError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("%s: %s: %v", e.Type, e.Message, e.Cause)
	}
	return fmt.Sprintf("%s: %s", e.Type, e.Message)
}

// Unwrap returns the underlying error for errors.Is/As support.
func (e *TemplateError) Unwrap() error {
	return e.Cause
}

// Error type constants
const (
	// ErrTypeValidation indicates invalid template input (e.g., wrong data type)
	ErrTypeValidation = "validation_error"

	// ErrTypeCompilation indicates template syntax error
	ErrTypeCompilation = "compilation_error"

	// ErrTypeExecution indicates runtime error during template rendering
	ErrTypeExecution = "execution_error"

	// ErrTypeSecurity indicates security violation (e.g., forbidden function call)
	ErrTypeSecurity = "security_error"
)

// NewValidationError creates a validation error.
func NewValidationError(message string, cause error) *TemplateError {
	return &TemplateError{
		Type:    ErrTypeValidation,
		Message: message,
		Cause:   cause,
	}
}

// NewCompilationError creates a compilation error.
func NewCompilationError(message string, cause error) *TemplateError {
	return &TemplateError{
		Type:    ErrTypeCompilation,
		Message: message,
		Cause:   cause,
	}
}

// NewExecutionError creates an execution error.
func NewExecutionError(message string, cause error) *TemplateError {
	return &TemplateError{
		Type:    ErrTypeExecution,
		Message: message,
		Cause:   cause,
	}
}

// NewSecurityError creates a security error.
func NewSecurityError(message string) *TemplateError {
	return &TemplateError{
		Type:    ErrTypeSecurity,
		Message: message,
	}
}

// IsValidationError checks if error is a validation error.
func IsValidationError(err error) bool {
	if te, ok := err.(*TemplateError); ok {
		return te.Type == ErrTypeValidation
	}
	return false
}

// IsCompilationError checks if error is a compilation error.
func IsCompilationError(err error) bool {
	if te, ok := err.(*TemplateError); ok {
		return te.Type == ErrTypeCompilation
	}
	return false
}

// IsExecutionError checks if error is an execution error.
func IsExecutionError(err error) bool {
	if te, ok := err.(*TemplateError); ok {
		return te.Type == ErrTypeExecution
	}
	return false
}

// IsSecurityError checks if error is a security error.
func IsSecurityError(err error) bool {
	if te, ok := err.(*TemplateError); ok {
		return te.Type == ErrTypeSecurity
	}
	return false
}

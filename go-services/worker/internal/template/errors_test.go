package template

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestTemplateError_Error(t *testing.T) {
	t.Run("with cause", func(t *testing.T) {
		cause := errors.New("underlying error")
		err := NewValidationError("invalid input", cause)

		assert.Contains(t, err.Error(), "validation_error")
		assert.Contains(t, err.Error(), "invalid input")
		assert.Contains(t, err.Error(), "underlying error")
	})

	t.Run("without cause", func(t *testing.T) {
		err := NewSecurityError("forbidden operation")

		assert.Contains(t, err.Error(), "security_error")
		assert.Contains(t, err.Error(), "forbidden operation")
	})
}

func TestTemplateError_Unwrap(t *testing.T) {
	cause := errors.New("root cause")
	err := NewCompilationError("syntax error", cause)

	unwrapped := errors.Unwrap(err)
	assert.Equal(t, cause, unwrapped)
}

func TestNewValidationError(t *testing.T) {
	err := NewValidationError("test message", nil)

	assert.Equal(t, ErrTypeValidation, err.Type)
	assert.Equal(t, "test message", err.Message)
	assert.Nil(t, err.Cause)
}

func TestNewCompilationError(t *testing.T) {
	cause := errors.New("parse error")
	err := NewCompilationError("failed to compile", cause)

	assert.Equal(t, ErrTypeCompilation, err.Type)
	assert.Equal(t, "failed to compile", err.Message)
	assert.Equal(t, cause, err.Cause)
}

func TestNewExecutionError(t *testing.T) {
	err := NewExecutionError("runtime failure", nil)

	assert.Equal(t, ErrTypeExecution, err.Type)
	assert.Equal(t, "runtime failure", err.Message)
}

func TestNewSecurityError(t *testing.T) {
	err := NewSecurityError("access denied")

	assert.Equal(t, ErrTypeSecurity, err.Type)
	assert.Equal(t, "access denied", err.Message)
	assert.Nil(t, err.Cause)
}

func TestIsValidationError(t *testing.T) {
	validationErr := NewValidationError("test", nil)
	compilationErr := NewCompilationError("test", nil)
	regularErr := errors.New("regular error")

	assert.True(t, IsValidationError(validationErr))
	assert.False(t, IsValidationError(compilationErr))
	assert.False(t, IsValidationError(regularErr))
}

func TestIsCompilationError(t *testing.T) {
	validationErr := NewValidationError("test", nil)
	compilationErr := NewCompilationError("test", nil)
	regularErr := errors.New("regular error")

	assert.False(t, IsCompilationError(validationErr))
	assert.True(t, IsCompilationError(compilationErr))
	assert.False(t, IsCompilationError(regularErr))
}

func TestIsExecutionError(t *testing.T) {
	executionErr := NewExecutionError("test", nil)
	validationErr := NewValidationError("test", nil)
	regularErr := errors.New("regular error")

	assert.True(t, IsExecutionError(executionErr))
	assert.False(t, IsExecutionError(validationErr))
	assert.False(t, IsExecutionError(regularErr))
}

func TestIsSecurityError(t *testing.T) {
	securityErr := NewSecurityError("test")
	validationErr := NewValidationError("test", nil)
	regularErr := errors.New("regular error")

	assert.True(t, IsSecurityError(securityErr))
	assert.False(t, IsSecurityError(validationErr))
	assert.False(t, IsSecurityError(regularErr))
}

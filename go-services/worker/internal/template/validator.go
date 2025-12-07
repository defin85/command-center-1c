package template

import (
	"fmt"
	"regexp"
	"strings"
)

// Validator validates templates for security and syntax.
// It blocks dangerous patterns that could lead to code injection
// or unauthorized access to system resources.
type Validator struct {
	dangerousPatterns []*regexp.Regexp
	maxTemplateSize   int
}

// NewValidator creates a new validator with default security rules.
func NewValidator() *Validator {
	return &Validator{
		dangerousPatterns: []*regexp.Regexp{
			// Python dunder attributes (code execution)
			regexp.MustCompile(`__\w+__`),
			// Dangerous functions
			regexp.MustCompile(`\b(exec|eval|compile|open|import|__import__)\s*\(`),
			// OS/system access
			regexp.MustCompile(`\b(os|sys|subprocess|commands)\b`),
			// File operations
			regexp.MustCompile(`\b(file|read|write|delete|remove)\s*\(`),
			// Globals/builtins access
			regexp.MustCompile(`\b(__globals__|__builtins__|__class__|__mro__|__subclasses__)\b`),
			// Network operations
			regexp.MustCompile(`\b(request|requests|urllib|socket|http)\b`),
			// Code objects
			regexp.MustCompile(`\b(code|func_code|gi_code|co_code)\b`),
			// pongo2-specific dangerous patterns (Go reflection abuse)
			regexp.MustCompile(`\.Call\s*\(`),      // Method invocation via reflection
			regexp.MustCompile(`\.Interface\s*\(`), // Type assertion bypass
			regexp.MustCompile(`\.Elem\s*\(`),      // Dereference pointer via reflection
			regexp.MustCompile(`reflect\.`),        // Direct reflect package access
		},
		maxTemplateSize: 100 * 1024, // 100KB max
	}
}

// ValidatorOption is a functional option for configuring Validator.
type ValidatorOption func(*Validator)

// WithMaxTemplateSize sets the maximum template size.
func WithMaxTemplateSize(size int) ValidatorOption {
	return func(v *Validator) {
		v.maxTemplateSize = size
	}
}

// WithAdditionalPatterns adds additional dangerous patterns to check.
func WithAdditionalPatterns(patterns ...*regexp.Regexp) ValidatorOption {
	return func(v *Validator) {
		v.dangerousPatterns = append(v.dangerousPatterns, patterns...)
	}
}

// NewValidatorWithOptions creates a new validator with custom options.
func NewValidatorWithOptions(opts ...ValidatorOption) *Validator {
	v := NewValidator()
	for _, opt := range opts {
		opt(v)
	}
	return v
}

// Validate checks template for security issues.
// Returns a SecurityError if a dangerous pattern is detected
// or the template exceeds the maximum size.
func (v *Validator) Validate(template string) error {
	// Check size
	if len(template) > v.maxTemplateSize {
		return NewSecurityError(fmt.Sprintf("template exceeds maximum size of %d bytes", v.maxTemplateSize))
	}

	// Check for dangerous patterns
	for _, pattern := range v.dangerousPatterns {
		if pattern.MatchString(template) {
			return NewSecurityError(fmt.Sprintf("dangerous pattern detected: %s", pattern.String()))
		}
	}

	return nil
}

// ValidateRecursive validates all string values in nested structure.
// Useful for validating entire payload structures before rendering.
func (v *Validator) ValidateRecursive(data interface{}) error {
	switch val := data.(type) {
	case string:
		return v.Validate(val)
	case map[string]interface{}:
		for key, value := range val {
			if err := v.ValidateRecursive(value); err != nil {
				return fmt.Errorf("validation failed at key %q: %w", key, err)
			}
		}
	case []interface{}:
		for i, item := range val {
			if err := v.ValidateRecursive(item); err != nil {
				return fmt.Errorf("validation failed at index %d: %w", i, err)
			}
		}
	}
	return nil
}

// IsSafeContext checks if context data is safe.
// Rejects keys starting with underscore (private keys).
func (v *Validator) IsSafeContext(ctx map[string]interface{}) error {
	for key := range ctx {
		if strings.HasPrefix(key, "_") {
			return NewSecurityError(fmt.Sprintf("private key %q not allowed in context", key))
		}
	}
	return nil
}

// ValidateAll performs full validation: template, context, and recursive data.
func (v *Validator) ValidateAll(templateStr string, ctx map[string]interface{}, data interface{}) error {
	if err := v.Validate(templateStr); err != nil {
		return err
	}
	if err := v.IsSafeContext(ctx); err != nil {
		return err
	}
	if data != nil {
		if err := v.ValidateRecursive(data); err != nil {
			return err
		}
	}
	return nil
}

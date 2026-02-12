package template

import (
	"context"
	"errors"
	"testing"

	"go.uber.org/zap"
)

// mockFallbackClient is a mock implementation of FallbackClient for testing.
type mockFallbackClient struct {
	renderFunc func(
		ctx context.Context,
		templateID string,
		templateExposureID string,
		templateExposureRevision int,
		context map[string]interface{},
	) (map[string]interface{}, error)
	callCount int
}

func (m *mockFallbackClient) RenderTemplate(
	ctx context.Context,
	templateID string,
	templateExposureID string,
	templateExposureRevision int,
	context map[string]interface{},
) (map[string]interface{}, error) {
	m.callCount++
	if m.renderFunc != nil {
		return m.renderFunc(ctx, templateID, templateExposureID, templateExposureRevision, context)
	}
	return map[string]interface{}{"fallback": "result"}, nil
}

func TestEngineWithFallback_RenderWithFallback_Success(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	fallback := &mockFallbackClient{}

	ewf := NewEngineWithFallback(engine, fallback, logger)

	templateData := map[string]interface{}{
		"field": "{{ value }}",
	}
	templateContext := map[string]interface{}{
		"value": "hello",
	}

	result, err := ewf.RenderWithFallback(context.Background(), "test-template", "", 0, templateData, templateContext)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if result["field"] != "hello" {
		t.Errorf("expected field='hello', got %v", result["field"])
	}

	// Fallback should not be called on success
	if fallback.callCount != 0 {
		t.Errorf("expected fallback not to be called, got %d calls", fallback.callCount)
	}
}

func TestEngineWithFallback_RenderWithFallback_FallbackOnCompatError(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)

	fallback := &mockFallbackClient{
		renderFunc: func(
			ctx context.Context,
			templateID string,
			templateExposureID string,
			templateExposureRevision int,
			context map[string]interface{},
		) (map[string]interface{}, error) {
			if templateID != "test-template" {
				t.Fatalf("expected templateID=test-template, got %s", templateID)
			}
			if templateExposureID != "exp-1" {
				t.Fatalf("expected templateExposureID=exp-1, got %s", templateExposureID)
			}
			if templateExposureRevision != 7 {
				t.Fatalf("expected templateExposureRevision=7, got %d", templateExposureRevision)
			}
			return map[string]interface{}{
				"field": "fallback-value",
			}, nil
		},
	}

	ewf := NewEngineWithFallback(engine, fallback, logger)

	// Template with unknown filter that pongo2 doesn't have
	templateData := map[string]interface{}{
		"field": "{{ value | unknownfilter }}",
	}
	templateContext := map[string]interface{}{
		"value": "hello",
	}

	result, err := ewf.RenderWithFallback(context.Background(), "test-template", "exp-1", 7, templateData, templateContext)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Should get fallback result
	if result["field"] != "fallback-value" {
		t.Errorf("expected field='fallback-value', got %v", result["field"])
	}

	// Fallback should be called
	if fallback.callCount != 1 {
		t.Errorf("expected fallback to be called once, got %d calls", fallback.callCount)
	}
}

func TestEngineWithFallback_RenderWithFallback_NoFallbackOnOtherError(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	fallback := &mockFallbackClient{}

	ewf := NewEngineWithFallback(engine, fallback, logger)

	// Template with syntax error (not a compatibility issue)
	templateData := map[string]interface{}{
		"field": "{{ value", // Missing closing braces
	}
	templateContext := map[string]interface{}{
		"value": "hello",
	}

	_, err := ewf.RenderWithFallback(context.Background(), "test-template", "", 0, templateData, templateContext)
	if err == nil {
		t.Fatal("expected error for syntax error")
	}

	// Fallback should not be called for syntax errors
	if fallback.callCount != 0 {
		t.Errorf("expected fallback not to be called for syntax error, got %d calls", fallback.callCount)
	}
}

func TestEngineWithFallback_NoFallbackConfigured(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)

	// Create engine without fallback
	ewf := NewEngineWithFallback(engine, nil, logger)

	if ewf.HasFallback() {
		t.Error("expected HasFallback() to return false")
	}

	// Template with unknown filter
	templateData := map[string]interface{}{
		"field": "{{ value | unknownfilter }}",
	}
	templateContext := map[string]interface{}{
		"value": "hello",
	}

	_, err := ewf.RenderWithFallback(context.Background(), "test-template", "", 0, templateData, templateContext)
	if err == nil {
		t.Error("expected error when fallback not configured")
	}
}

func TestIsCompatibilityError(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected bool
	}{
		{
			name:     "nil error",
			err:      nil,
			expected: false,
		},
		{
			name:     "unknown filter error",
			err:      errors.New("unknown filter 'tojson'"),
			expected: true,
		},
		{
			name:     "filter does not exist",
			err:      errors.New("filter does not exist: customfilter"),
			expected: true,
		},
		{
			name:     "unknown tag",
			err:      errors.New("unknown tag 'macro'"),
			expected: true,
		},
		{
			name:     "items method",
			err:      errors.New("cannot call items() on map"),
			expected: true,
		},
		{
			name:     "keys method",
			err:      errors.New("cannot call keys() on object"),
			expected: true,
		},
		{
			name:     "values method",
			err:      errors.New("cannot call values() on dict"),
			expected: true,
		},
		{
			name:     "has no attribute",
			err:      errors.New("object has no attribute 'custom'"),
			expected: true,
		},
		{
			name:     "is not callable",
			err:      errors.New("string is not callable"),
			expected: true,
		},
		{
			name:     "syntax error - not compatibility",
			err:      errors.New("syntax error: unexpected token"),
			expected: false,
		},
		{
			name:     "other error - not compatibility",
			err:      errors.New("connection refused"),
			expected: false,
		},
		{
			name:     "case insensitive - Unknown Filter",
			err:      errors.New("Unknown Filter 'tojson'"),
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isCompatibilityError(tt.err)
			if result != tt.expected {
				t.Errorf("isCompatibilityError(%v) = %v, want %v", tt.err, result, tt.expected)
			}
		})
	}
}

func TestSetFallback(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)

	ewf := NewEngineWithFallback(engine, nil, logger)

	if ewf.HasFallback() {
		t.Error("expected HasFallback() to return false initially")
	}

	fallback := &mockFallbackClient{}
	ewf.SetFallback(fallback)

	if !ewf.HasFallback() {
		t.Error("expected HasFallback() to return true after SetFallback")
	}
}

func TestRenderStringWithFallback(t *testing.T) {
	logger := zap.NewNop()
	engine := NewEngine(logger)
	fallback := &mockFallbackClient{}

	ewf := NewEngineWithFallback(engine, fallback, logger)

	// Test successful render
	result, err := ewf.RenderStringWithFallback(context.Background(), "Hello {{ name }}", map[string]interface{}{
		"name": "World",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "Hello World" {
		t.Errorf("expected 'Hello World', got %q", result)
	}

	// Test with error (fallback cannot be used for string templates)
	_, err = ewf.RenderStringWithFallback(context.Background(), "{{ value | unknownfilter }}", map[string]interface{}{
		"value": "test",
	})
	if err == nil {
		t.Error("expected error for unknown filter")
	}

	// Fallback should not be called for string templates
	if fallback.callCount != 0 {
		t.Errorf("expected fallback not to be called for string templates, got %d calls", fallback.callCount)
	}
}

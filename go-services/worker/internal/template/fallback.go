package template

import (
	"context"
	"strings"

	"go.uber.org/zap"
)

// FallbackClient interface for Python fallback rendering.
// This is implemented by orchestrator.FallbackRenderer.
type FallbackClient interface {
	RenderTemplate(ctx context.Context, templateID string, context map[string]interface{}) (map[string]interface{}, error)
}

// EngineWithFallback wraps Engine with Python fallback capability.
// When pongo2 encounters incompatible Jinja2 syntax, it falls back
// to the Python Jinja2 renderer via HTTP API.
type EngineWithFallback struct {
	*Engine
	fallback FallbackClient
	logger   *zap.Logger
}

// NewEngineWithFallback creates engine with fallback support.
func NewEngineWithFallback(engine *Engine, fallback FallbackClient, logger *zap.Logger) *EngineWithFallback {
	return &EngineWithFallback{
		Engine:   engine,
		fallback: fallback,
		logger:   logger,
	}
}

// RenderWithFallback tries Go pongo2 first, falls back to Python on compatibility errors.
// The templateID is required for the fallback API call.
func (e *EngineWithFallback) RenderWithFallback(ctx context.Context, templateID string, templateData map[string]interface{}, templateContext map[string]interface{}) (map[string]interface{}, error) {
	// Try Go pongo2 first
	result, err := e.RenderJSON(ctx, templateData, templateContext)
	if err == nil {
		return result, nil
	}

	// Check if error is compatibility issue
	if isCompatibilityError(err) {
		e.logger.Warn("pongo2 compatibility issue, falling back to Python",
			zap.String("template_id", templateID),
			zap.Error(err))

		// Fallback to Python
		if e.fallback != nil {
			return e.fallback.RenderTemplate(ctx, templateID, templateContext)
		}

		e.logger.Error("fallback client not configured",
			zap.String("template_id", templateID))
	}

	return nil, err
}

// RenderStringWithFallback renders a single template string with fallback.
// Note: This cannot use the HTTP fallback since we don't have a template ID.
// It only tries pongo2 and returns the error if it fails.
func (e *EngineWithFallback) RenderStringWithFallback(ctx context.Context, templateStr string, templateContext map[string]interface{}) (string, error) {
	result, err := e.Render(ctx, templateStr, templateContext)
	if err != nil {
		if isCompatibilityError(err) {
			e.logger.Warn("pongo2 compatibility issue in string template",
				zap.Error(err))
			// Cannot fallback for string templates without template ID
		}
		return "", err
	}
	return result, nil
}

// isCompatibilityError checks if error indicates pongo2/Jinja2 incompatibility.
// These patterns indicate features that work in Jinja2 but not in pongo2.
func isCompatibilityError(err error) bool {
	if err == nil {
		return false
	}

	errStr := err.Error()

	// Patterns that indicate compatibility issues between pongo2 and Jinja2
	compatPatterns := []string{
		// Unknown filters (pongo2 doesn't have all Jinja2 filters)
		"unknown filter",
		"filter does not exist",      // e.g. "filter does not exist: customfilter"
		"does not exist",             // e.g. "Filter 'x' does not exist."

		// Unknown tags
		"unknown tag",
		"tag does not exist",

		// Dict method calls that work in Jinja2 but not pongo2
		"items()",
		"keys()",
		"values()",

		// Jinja2-specific features
		"namespace",
		"loop.cycle",

		// Method calls on objects
		"has no attribute",
		"is not callable",

		// Slice operations
		"cannot slice",
		"invalid slice",
	}

	for _, pattern := range compatPatterns {
		if strings.Contains(strings.ToLower(errStr), strings.ToLower(pattern)) {
			return true
		}
	}

	return false
}

// SetFallback allows setting or replacing the fallback client.
func (e *EngineWithFallback) SetFallback(fallback FallbackClient) {
	e.fallback = fallback
}

// HasFallback returns true if a fallback client is configured.
func (e *EngineWithFallback) HasFallback() bool {
	return e.fallback != nil
}

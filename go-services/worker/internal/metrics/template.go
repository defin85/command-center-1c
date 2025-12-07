package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Template Engine Metrics for monitoring Go pongo2 vs Python Jinja2 fallback performance
// Used for A/B comparison and rollout decisions

var (
	// TemplateRenderTotal - counter of template renders
	// Labels: status (success, error), engine (go, python_fallback)
	TemplateRenderTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_template_render_total",
			Help: "Total template renders",
		},
		[]string{"status", "engine"},
	)

	// TemplateRenderDuration - histogram of template render duration
	// Labels: engine (go, python_fallback)
	// Buckets optimized for template rendering (1ms to 10s)
	TemplateRenderDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "cc1c_template_render_duration_seconds",
			Help:    "Template render duration",
			Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
		},
		[]string{"engine"},
	)

	// TemplateFallbackTotal - counter of Python fallback invocations
	// Labels: reason (compatibility, error, disabled)
	TemplateFallbackTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_template_fallback_total",
			Help: "Total Python fallback invocations",
		},
		[]string{"reason"},
	)

	// TemplateRenderErrors - counter of template render errors by type
	// Labels: error_type (validation, compilation, execution, timeout, network)
	TemplateRenderErrors = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_template_render_errors_total",
			Help: "Template render errors by type",
		},
		[]string{"error_type"},
	)

	// TemplateCacheHits - counter of template cache hits/misses
	// Labels: hit (true, false)
	TemplateCacheHits = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_template_cache_total",
			Help: "Template cache hits and misses",
		},
		[]string{"hit"},
	)
)

// validateEngine ensures engine is one of expected values
func validateEngine(engine string) string {
	switch engine {
	case "go", "python_fallback":
		return engine
	default:
		return "unknown"
	}
}

// validateRenderStatus ensures status is valid
func validateRenderStatus(status string) string {
	switch status {
	case "success", "error":
		return status
	default:
		return "unknown"
	}
}

// validateFallbackReason ensures reason is valid
func validateFallbackReason(reason string) string {
	switch reason {
	case "compatibility", "error", "disabled":
		return reason
	default:
		return "unknown"
	}
}

// validateErrorType ensures error type is valid
func validateErrorType(errorType string) string {
	switch errorType {
	case "validation", "compilation", "execution", "timeout", "network":
		return errorType
	default:
		return "unknown"
	}
}

// RecordTemplateRender records a template render operation
func RecordTemplateRender(status, engine string, durationSeconds float64) {
	validStatus := validateRenderStatus(status)
	validEngine := validateEngine(engine)

	TemplateRenderTotal.WithLabelValues(validStatus, validEngine).Inc()
	TemplateRenderDuration.WithLabelValues(validEngine).Observe(durationSeconds)
}

// RecordTemplateRenderSuccess records a successful template render
func RecordTemplateRenderSuccess(engine string, durationSeconds float64) {
	RecordTemplateRender("success", engine, durationSeconds)
}

// RecordTemplateRenderError records a failed template render
func RecordTemplateRenderError(engine string, durationSeconds float64, errorType string) {
	RecordTemplateRender("error", engine, durationSeconds)
	validErrorType := validateErrorType(errorType)
	TemplateRenderErrors.WithLabelValues(validErrorType).Inc()
}

// RecordTemplateFallback records a Python fallback invocation
func RecordTemplateFallback(reason string) {
	validReason := validateFallbackReason(reason)
	TemplateFallbackTotal.WithLabelValues(validReason).Inc()
}

// RecordTemplateCacheHit records a template cache hit
func RecordTemplateCacheHit() {
	TemplateCacheHits.WithLabelValues("true").Inc()
}

// RecordTemplateCacheMiss records a template cache miss
func RecordTemplateCacheMiss() {
	TemplateCacheHits.WithLabelValues("false").Inc()
}

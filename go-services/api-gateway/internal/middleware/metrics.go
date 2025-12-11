package middleware

import (
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/metrics"
	"github.com/gin-gonic/gin"
)

// Known API path patterns for normalization (prevents high cardinality)
// Maps regex pattern -> normalized path template
var knownPathPatterns = []struct {
	pattern    *regexp.Regexp
	normalized string
}{
	// UUID patterns (standard format: 8-4-4-4-12 hex digits)
	{regexp.MustCompile(`/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})`), "/:id"},

	// Numeric IDs
	{regexp.MustCompile(`/(\d+)(/|$)`), "/:id$2"},

	// File IDs in paths like /files/download/:file_id/
	{regexp.MustCompile(`/files/(download|delete)/[^/]+/`), "/files/$1/:file_id/"},

	// WebSocket execution IDs
	{regexp.MustCompile(`/ws/workflow/[^/]+/`), "/ws/workflow/:execution_id/"},
}

// allowedPaths contains known API paths that should be tracked with exact path
// Used for high cardinality protection - unknown paths are grouped
var allowedPaths = map[string]bool{
	// Health and metrics
	"/health":  true,
	"/metrics": true,

	// Auth
	"/api/token":          true,
	"/api/token/":         true,
	"/api/token/refresh":  true,
	"/api/token/refresh/": true,

	// WebSocket (normalized)
	"/ws/workflow/:execution_id/": true,
	"/ws/service-mesh/":           true,
}

// init populates allowedPaths from generated routes
func init() {
	// API v2 base paths - these will be populated dynamically
	// Common patterns that are always allowed
	apiV2Prefixes := []string{
		"/api/v2/audit/",
		"/api/v2/clusters/",
		"/api/v2/databases/",
		"/api/v2/events/",
		"/api/v2/extensions/",
		"/api/v2/files/",
		"/api/v2/operations/",
		"/api/v2/service-mesh/",
		"/api/v2/system/",
		"/api/v2/templates/",
		"/api/v2/workflows/",
		"/api/v2/tracing/",
		"/api/v2/ras/",
	}

	for _, prefix := range apiV2Prefixes {
		allowedPaths[prefix] = true
	}
}

// MetricsMiddleware creates Prometheus metrics middleware for Gin
func MetricsMiddleware(m *metrics.Metrics) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Skip metrics endpoint to avoid recursion
		if c.Request.URL.Path == "/metrics" {
			c.Next()
			return
		}

		start := time.Now()

		// Process request
		c.Next()

		// Calculate duration
		duration := time.Since(start).Seconds()

		// Get normalized path and method
		path := normalizePath(c)
		method := c.Request.Method
		status := strconv.Itoa(c.Writer.Status())

		// Record metrics
		m.RequestsTotal.WithLabelValues(method, path, status).Inc()
		m.RequestDuration.WithLabelValues(method, path).Observe(duration)
	}
}

// normalizePath returns a normalized path suitable for metrics labels
// Replaces dynamic segments (UUIDs, IDs) with placeholders to prevent high cardinality
func normalizePath(c *gin.Context) string {
	// First, try to use Gin's matched route pattern (best option)
	if fullPath := c.FullPath(); fullPath != "" {
		return fullPath
	}

	// Fallback: manually normalize the path
	path := c.Request.URL.Path

	// Apply known patterns for normalization
	for _, p := range knownPathPatterns {
		path = p.pattern.ReplaceAllString(path, p.normalized)
	}

	// High cardinality protection: check if path is known
	if isAllowedPath(path) {
		return path
	}

	// For unknown paths, extract just the base API prefix
	// This prevents cardinality explosion from malicious or unexpected paths
	return extractBasePrefix(path)
}

// isAllowedPath checks if the path is in the allowed list or matches a known prefix
func isAllowedPath(path string) bool {
	// Exact match
	if allowedPaths[path] {
		return true
	}

	// Check prefixes for API v2 routes
	for allowed := range allowedPaths {
		if strings.HasPrefix(path, allowed) {
			return true
		}
	}

	return false
}

// extractBasePrefix extracts the base API prefix from an unknown path
// Returns a generic label to prevent high cardinality
func extractBasePrefix(path string) string {
	// Handle API v2 paths
	if strings.HasPrefix(path, "/api/v2/") {
		parts := strings.SplitN(path, "/", 5) // ["", "api", "v2", "resource", ...]
		if len(parts) >= 4 && parts[3] != "" {
			return "/api/v2/" + parts[3] + "/*"
		}
		return "/api/v2/*"
	}

	// Handle WebSocket paths
	if strings.HasPrefix(path, "/ws/") {
		return "/ws/*"
	}

	// Handle API v1 or other legacy paths
	if strings.HasPrefix(path, "/api/") {
		return "/api/*"
	}

	// Unknown path - use generic label
	return "/unknown"
}

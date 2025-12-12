package metrics

import (
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// HTTPMiddleware returns Gin middleware for collecting HTTP metrics
func HTTPMiddleware(m *RASMetrics) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Skip /metrics and /health endpoints
		if c.Request.URL.Path == "/metrics" || c.Request.URL.Path == "/health" {
			c.Next()
			return
		}

		start := time.Now()
		c.Next()
		duration := time.Since(start).Seconds()

		path := normalizePath(c)
		method := c.Request.Method
		status := strconv.Itoa(c.Writer.Status())

		m.RequestsTotal.WithLabelValues(method, path, status).Inc()
		m.RequestDuration.WithLabelValues(method, path).Observe(duration)
	}
}

// normalizePath returns the route template to avoid high cardinality
func normalizePath(c *gin.Context) string {
	// Use route template instead of actual path to avoid high cardinality
	// e.g., "/api/v2/clusters/:cluster_id/infobases" instead of "/api/v2/clusters/abc123/infobases"
	if fullPath := c.FullPath(); fullPath != "" {
		return fullPath
	}
	return "/unknown"
}

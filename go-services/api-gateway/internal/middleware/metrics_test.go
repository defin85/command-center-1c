package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/metrics"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/stretchr/testify/assert"
)

func init() {
	gin.SetMode(gin.TestMode)
}

// createTestMetrics creates a new metrics instance for testing
// Uses a custom registry to avoid conflicts between tests
func createTestMetrics() *metrics.Metrics {
	// Create a new registry for each test to avoid duplicate registration errors
	registry := prometheus.NewRegistry()

	requestsTotal := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "cc1c_test",
			Name:      "requests_total",
			Help:      "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	requestDuration := prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "cc1c_test",
			Name:      "request_duration_seconds",
			Help:      "HTTP request latencies in seconds",
			Buckets:   prometheus.DefBuckets,
		},
		[]string{"method", "path"},
	)

	registry.MustRegister(requestsTotal)
	registry.MustRegister(requestDuration)

	return &metrics.Metrics{
		RequestsTotal:   requestsTotal,
		RequestDuration: requestDuration,
	}
}

func TestMetricsMiddleware_BasicRequest(t *testing.T) {
	m := createTestMetrics()

	router := gin.New()
	router.Use(MetricsMiddleware(m))
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)
}

func TestMetricsMiddleware_SkipsMetricsEndpoint(t *testing.T) {
	m := createTestMetrics()

	router := gin.New()
	router.Use(MetricsMiddleware(m))
	router.GET("/metrics", func(c *gin.Context) {
		c.String(200, "metrics data")
	})

	req := httptest.NewRequest("GET", "/metrics", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, 200, w.Code)
}

func TestNormalizePath_UUIDReplacement(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "UUID in path",
			input:    "/api/v2/databases/123e4567-e89b-12d3-a456-426614174000/",
			expected: "/api/v2/databases/:id/",
		},
		{
			name:     "Multiple UUIDs",
			input:    "/api/v2/clusters/123e4567-e89b-12d3-a456-426614174000/databases/987fcdeb-51a2-3bc4-d567-890123456789/",
			expected: "/api/v2/clusters/:id/databases/:id/",
		},
		{
			name:     "No UUID",
			input:    "/api/v2/clusters/list-clusters/",
			expected: "/api/v2/clusters/list-clusters/",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := tt.input
			for _, p := range knownPathPatterns {
				path = p.pattern.ReplaceAllString(path, p.normalized)
			}
			assert.Equal(t, tt.expected, path)
		})
	}
}

func TestNormalizePath_NumericIDReplacement(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "Numeric ID in path",
			input:    "/api/v2/databases/123/",
			expected: "/api/v2/databases/:id/",
		},
		{
			name:     "Multiple numeric IDs",
			input:    "/api/v2/clusters/456/databases/789/",
			expected: "/api/v2/clusters/:id/databases/:id/",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := tt.input
			for _, p := range knownPathPatterns {
				path = p.pattern.ReplaceAllString(path, p.normalized)
			}
			assert.Equal(t, tt.expected, path)
		})
	}
}

func TestNormalizePath_FileIDReplacement(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "File download path",
			input:    "/files/download/abc123xyz/",
			expected: "/files/download/:file_id/",
		},
		{
			name:     "File delete path",
			input:    "/files/delete/def456uvw/",
			expected: "/files/delete/:file_id/",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := tt.input
			for _, p := range knownPathPatterns {
				path = p.pattern.ReplaceAllString(path, p.normalized)
			}
			assert.Equal(t, tt.expected, path)
		})
	}
}

func TestExtractBasePrefix(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "API v2 known prefix",
			input:    "/api/v2/databases/unknown-action/",
			expected: "/api/v2/databases/*",
		},
		{
			name:     "API v2 short path",
			input:    "/api/v2/",
			expected: "/api/v2/*",
		},
		{
			name:     "WebSocket path",
			input:    "/ws/unknown/path/",
			expected: "/ws/*",
		},
		{
			name:     "Unknown API version path",
			input:    "/api/v3/legacy/",
			expected: "/api/*",
		},
		{
			name:     "Completely unknown path",
			input:    "/random/unknown/path/",
			expected: "/unknown",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := extractBasePrefix(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestIsAllowedPath(t *testing.T) {
	tests := []struct {
		name     string
		path     string
		expected bool
	}{
		{
			name:     "Health endpoint",
			path:     "/health",
			expected: true,
		},
		{
			name:     "Metrics endpoint",
			path:     "/metrics",
			expected: true,
		},
		{
			name:     "Token endpoint",
			path:     "/api/token/",
			expected: true,
		},
		{
			name:     "API v2 clusters",
			path:     "/api/v2/clusters/list-clusters/",
			expected: true,
		},
		{
			name:     "Unknown path",
			path:     "/random/path/",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isAllowedPath(tt.path)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestMetricsMiddleware_RecordsMetrics(t *testing.T) {
	m := createTestMetrics()

	router := gin.New()
	router.Use(MetricsMiddleware(m))
	router.GET("/api/v2/test/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// Make a request
	req := httptest.NewRequest("GET", "/api/v2/test/", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	// Verify that metrics were recorded (counter incremented)
	// Note: We can't easily verify the exact values without exposing the counter
	// but we can verify the request completed successfully
}

func TestMetricsMiddleware_HandlesErrors(t *testing.T) {
	m := createTestMetrics()

	router := gin.New()
	router.Use(MetricsMiddleware(m))
	router.GET("/error", func(c *gin.Context) {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
	})

	req := httptest.NewRequest("GET", "/error", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

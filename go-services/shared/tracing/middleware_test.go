package tracing

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func setupMiddlewareTestTracer(t *testing.T) {
	t.Helper()
	ctx := context.Background()
	_, err := InitTracing(ctx, Config{
		ServiceName: "test-service",
		Enabled:     false,
	})
	require.NoError(t, err)
}

func TestTracingMiddleware(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	router.GET("/test", func(c *gin.Context) {
		c.String(http.StatusOK, "OK")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "OK", w.Body.String())
}

func TestTracingMiddleware_404(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/nonexistent", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestTracingMiddleware_500(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	router.GET("/error", func(c *gin.Context) {
		c.String(http.StatusInternalServerError, "Internal Error")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/error", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestTracingMiddlewareWithTracer(t *testing.T) {
	setupMiddlewareTestTracer(t)

	tracer := GetTracer()
	router := gin.New()
	router.Use(TracingMiddlewareWithTracer(tracer))

	router.GET("/test", func(c *gin.Context) {
		c.String(http.StatusOK, "OK")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestTracingMiddlewareWithConfigOptions_SkipPaths(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddlewareWithConfigOptions(MiddlewareConfig{
		SkipPaths: []string{"/health"},
	}))

	healthCalled := false
	router.GET("/health", func(c *gin.Context) {
		healthCalled = true
		c.String(http.StatusOK, "healthy")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/health", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.True(t, healthCalled)
}

func TestTracingMiddlewareWithConfigOptions_CustomSpanNameFormatter(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddlewareWithConfigOptions(MiddlewareConfig{
		SpanNameFormatter: func(c *gin.Context) string {
			return "custom-span-" + c.Request.Method
		},
	}))

	router.GET("/test", func(c *gin.Context) {
		c.String(http.StatusOK, "OK")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestRequestTracingContext(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	var traceID, spanID string
	router.GET("/test", func(c *gin.Context) {
		traceID, spanID = RequestTracingContext(c)
		c.String(http.StatusOK, "OK")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	// With noop tracer, IDs will be empty
	assert.Empty(t, traceID)
	assert.Empty(t, spanID)
}

func TestStartHandlerSpan(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	var spanEnded bool
	router.GET("/test", func(c *gin.Context) {
		span, endSpan := StartHandlerSpan(c, "custom-operation")
		defer func() {
			endSpan()
			spanEnded = true
		}()

		assert.NotNil(t, span)
		c.String(http.StatusOK, "OK")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.True(t, spanEnded)
}

func TestGetScheme_HTTP(t *testing.T) {
	router := gin.New()

	router.GET("/test", func(c *gin.Context) {
		scheme := getScheme(c)
		c.String(http.StatusOK, scheme)
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, "http", w.Body.String())
}

func TestGetScheme_XForwardedProto(t *testing.T) {
	router := gin.New()

	router.GET("/test", func(c *gin.Context) {
		scheme := getScheme(c)
		c.String(http.StatusOK, scheme)
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/test", nil)
	req.Header.Set("X-Forwarded-Proto", "https")

	router.ServeHTTP(w, req)

	assert.Equal(t, "https", w.Body.String())
}

func TestTracingMiddleware_POST(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	router.POST("/api/create", func(c *gin.Context) {
		c.JSON(http.StatusCreated, gin.H{"id": "123"})
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("POST", "/api/create", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusCreated, w.Code)
}

func TestTracingMiddleware_WithRouteParams(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	router.GET("/api/users/:id", func(c *gin.Context) {
		id := c.Param("id")
		c.String(http.StatusOK, "User: "+id)
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/api/users/123", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "User: 123", w.Body.String())
}

func TestTracingMiddleware_WithGinErrors(t *testing.T) {
	setupMiddlewareTestTracer(t)

	router := gin.New()
	router.Use(TracingMiddleware())

	router.GET("/error", func(c *gin.Context) {
		c.Error(assert.AnError)
		c.String(http.StatusBadRequest, "Bad Request")
	})

	w := httptest.NewRecorder()
	req, _ := http.NewRequest("GET", "/error", nil)

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

package rest

import (
	"github.com/commandcenter1c/commandcenter/odata-adapter/internal/metrics"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// NewRouter creates a new Gin router with all routes configured
func NewRouter(redisClient *redis.Client, odataMetrics *metrics.ODataMetrics, logger *zap.Logger) *gin.Engine {
	router := gin.New()

	// Global middleware
	router.Use(gin.Recovery())
	router.Use(loggerMiddleware(logger))

	// Prometheus metrics middleware
	if odataMetrics != nil {
		router.Use(metrics.HTTPMiddleware(odataMetrics))
	}

	// Prometheus metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Health checker
	healthChecker := NewHealthChecker(redisClient)

	// Health check endpoints
	router.GET("/health", healthChecker.Health())
	router.GET("/ready", healthChecker.Ready())

	// TODO: API v2 routes will be added here
	// apiV2 := router.Group("/api/v2")
	// v2.SetupRoutes(apiV2, ...)

	return router
}

// loggerMiddleware creates a simple request logging middleware
func loggerMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		path := c.Request.URL.Path
		method := c.Request.Method

		c.Next()

		statusCode := c.Writer.Status()
		logger.Debug("request completed",
			zap.String("method", method),
			zap.String("path", path),
			zap.Int("status", statusCode),
		)
	}
}

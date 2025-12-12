package rest

import (
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/designer-agent/internal/metrics"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/ssh"
)

// NewRouter creates a new Gin router with all routes configured.
func NewRouter(sshPool *ssh.Pool, redisClient *redis.Client, designerMetrics *metrics.DesignerMetrics, logger *zap.Logger) *gin.Engine {
	router := gin.New()

	// Global middleware
	router.Use(gin.Recovery())
	router.Use(loggerMiddleware(logger))
	router.Use(metrics.HTTPMiddleware(designerMetrics))

	// Health checker
	healthChecker := NewHealthChecker(redisClient, sshPool)

	// Health check endpoints
	router.GET("/health", healthChecker.Health())
	router.GET("/ready", healthChecker.Ready())

	// Prometheus metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	return router
}

// loggerMiddleware creates a simple request logging middleware.
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

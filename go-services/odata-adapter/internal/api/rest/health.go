package rest

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

// HealthChecker provides health check functionality
type HealthChecker struct {
	redisClient *redis.Client
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(redisClient *redis.Client) *HealthChecker {
	return &HealthChecker{
		redisClient: redisClient,
	}
}

// Health returns health check handler
func (h *HealthChecker) Health() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "odata-adapter",
		})
	}
}

// Ready returns readiness check handler
func (h *HealthChecker) Ready() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Check Redis connection
		if h.redisClient != nil {
			if err := h.redisClient.Ping(c.Request.Context()).Err(); err != nil {
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"status":  "not_ready",
					"service": "odata-adapter",
					"error":   "redis connection failed",
				})
				return
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"status":  "ready",
			"service": "odata-adapter",
		})
	}
}

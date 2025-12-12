package rest

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/designer-agent/internal/ssh"
	"github.com/commandcenter1c/commandcenter/designer-agent/internal/version"
)

// HealthChecker provides health and readiness check functionality.
type HealthChecker struct {
	redisClient *redis.Client
	sshPool     *ssh.Pool
}

// NewHealthChecker creates a new health checker instance.
func NewHealthChecker(redisClient *redis.Client, sshPool *ssh.Pool) *HealthChecker {
	return &HealthChecker{
		redisClient: redisClient,
		sshPool:     sshPool,
	}
}

// Health returns the health check handler.
// Health check is always OK if the service is running.
func (h *HealthChecker) Health() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "designer-agent",
			"version": version.Version,
		})
	}
}

// Ready returns the readiness check handler.
// Readiness check validates dependencies (Redis, SSH pool).
func (h *HealthChecker) Ready() gin.HandlerFunc {
	return func(c *gin.Context) {
		checks := make(map[string]interface{})
		allHealthy := true

		// Check Redis connection
		if h.redisClient != nil {
			if err := h.redisClient.Ping(c.Request.Context()).Err(); err != nil {
				checks["redis"] = gin.H{
					"status": "unhealthy",
					"error":  err.Error(),
				}
				allHealthy = false
			} else {
				checks["redis"] = gin.H{
					"status": "healthy",
				}
			}
		}

		// Check SSH pool
		if h.sshPool != nil {
			stats := h.sshPool.Stats()
			checks["ssh_pool"] = gin.H{
				"status":             "healthy",
				"total_hosts":        stats.TotalHosts,
				"total_connections":  stats.TotalConnections,
				"active_connections": stats.ActiveConnections,
				"idle_connections":   stats.IdleConnections,
			}
		}

		if !allHealthy {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":  "not_ready",
				"service": "designer-agent",
				"checks":  checks,
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":  "ready",
			"service": "designer-agent",
			"version": version.Version,
			"checks":  checks,
		})
	}
}

package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// HealthCheck handles health check requests
func HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "ok",
		"service": "installation-service",
	})
}

// ReadyCheck handles readiness check requests
func ReadyCheck(c *gin.Context) {
	// Add more sophisticated checks if needed
	c.JSON(http.StatusOK, gin.H{
		"status": "ready",
		"service": "installation-service",
	})
}

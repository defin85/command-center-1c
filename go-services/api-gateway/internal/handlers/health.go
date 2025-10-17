package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// HealthResponse represents health check response
type HealthResponse struct {
	Status    string    `json:"status"`
	Service   string    `json:"service"`
	Timestamp time.Time `json:"timestamp"`
	Version   string    `json:"version"`
}

// HealthCheck handles health check requests
func HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, HealthResponse{
		Status:    "healthy",
		Service:   "api-gateway",
		Timestamp: time.Now(),
		Version:   "0.1.0",
	})
}

// StatusResponse represents system status
type StatusResponse struct {
	ApiGateway    string    `json:"api_gateway"`
	Orchestrator  string    `json:"orchestrator"`
	Timestamp     time.Time `json:"timestamp"`
}

// GetStatus returns system status
func GetStatus(c *gin.Context) {
	// TODO: Check orchestrator health
	c.JSON(http.StatusOK, StatusResponse{
		ApiGateway:   "operational",
		Orchestrator: "unknown", // Will be implemented later
		Timestamp:    time.Now(),
	})
}

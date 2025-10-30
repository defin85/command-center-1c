package handlers

import (
	"github.com/gin-gonic/gin"
)

// MonitoringHandler handles cluster monitoring requests
type MonitoringHandler struct {
	// TODO: Add MonitoringService dependency
}

// NewMonitoringHandler creates a new monitoring handler
func NewMonitoringHandler() *MonitoringHandler {
	// TODO: Implement
	return &MonitoringHandler{}
}

// GetClusters returns list of 1C clusters
// GET /api/v1/clusters?server=localhost:1545
func (h *MonitoringHandler) GetClusters(c *gin.Context) {
	// TODO: Implement
	// - Parse query params (server address)
	// - Call MonitoringService.GetClusters via gRPC
	// - Return JSON response
	c.JSON(501, gin.H{"error": "not implemented"})
}

// GetInfobases returns list of infobases in a cluster
// GET /api/v1/infobases?server=localhost:1545&cluster=uuid
func (h *MonitoringHandler) GetInfobases(c *gin.Context) {
	// TODO: Implement
	// - Parse query params (server, cluster_uuid)
	// - Call MonitoringService.GetInfobases via gRPC
	// - Return JSON response
	c.JSON(501, gin.H{"error": "not implemented"})
}

// GetSessions returns active sessions
// GET /api/v1/sessions?server=localhost:1545&cluster=uuid
func (h *MonitoringHandler) GetSessions(c *gin.Context) {
	// TODO: Implement (Phase 2)
	c.JSON(501, gin.H{"error": "not implemented"})
}

package handlers

import (
	"net/http"

	"github.com/commandcenter1c/commandcenter/api-gateway/internal/middleware"
	"github.com/gin-gonic/gin"
)

// ListOperations handles GET /operations
func ListOperations(c *gin.Context) {
	// TODO: Implement operation listing
	// This will proxy to orchestrator service
	c.JSON(http.StatusOK, gin.H{
		"operations": []interface{}{},
		"total":      0,
		"message":    "Operation listing not yet implemented",
	})
}

// CreateOperation handles POST /operations
func CreateOperation(c *gin.Context) {
	// TODO: Implement operation creation
	// This will proxy to orchestrator service
	var payload map[string]interface{}
	if err := c.ShouldBindJSON(&payload); err != nil {
		c.JSON(http.StatusBadRequest, middleware.CorrelatedErrorPayload(c, err.Error(), nil))
		return
	}

	c.JSON(http.StatusAccepted, gin.H{
		"message": "Operation creation not yet implemented",
		"payload": payload,
	})
}

// GetOperation handles GET /operations/:id
func GetOperation(c *gin.Context) {
	id := c.Param("id")

	// TODO: Implement operation retrieval
	// This will proxy to orchestrator service
	c.JSON(http.StatusOK, gin.H{
		"id":      id,
		"message": "Operation retrieval not yet implemented",
	})
}

// CancelOperation handles DELETE /operations/:id
func CancelOperation(c *gin.Context) {
	id := c.Param("id")

	// TODO: Implement operation cancellation
	// This will proxy to orchestrator service
	c.JSON(http.StatusOK, gin.H{
		"id":      id,
		"message": "Operation cancelled (stub)",
	})
}

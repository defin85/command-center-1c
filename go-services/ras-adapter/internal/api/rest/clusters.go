package rest

import (
	"net/http"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
)

// GetClusters returns handler for GET /api/v1/clusters
func GetClusters(clusterSvc *service.ClusterService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get server parameter (RAS server address)
		serverAddr := c.Query("server")
		if serverAddr == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "server parameter is required (e.g., ?server=localhost:1545)",
			})
			return
		}

		// Get clusters
		clusters, err := clusterSvc.GetClusters(c.Request.Context(), serverAddr)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"clusters": clusters,
		})
	}
}

package rest

import (
	"net/http"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
)

// GetSessions returns handler for GET /api/v1/sessions
func GetSessions(sessionSvc *service.SessionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get cluster_id and infobase_id parameters
		clusterID := c.Query("cluster_id")
		if clusterID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "cluster_id parameter is required",
			})
			return
		}

		infobaseID := c.Query("infobase_id")
		// infobase_id is optional - if not specified, get all sessions for cluster

		// Get sessions
		sessions, err := sessionSvc.GetSessions(c.Request.Context(), clusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"sessions": sessions,
			"count":    len(sessions),
		})
	}
}

// TerminateSessions returns handler for POST /api/v1/sessions/terminate
func TerminateSessions(sessionSvc *service.SessionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Parse request body
		var req models.TerminateSessionsRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// For Week 1, we terminate ALL sessions for the infobase
		// (ignore session_ids parameter for now, use it in future weeks)

		// Terminate sessions
		terminatedCount, err := sessionSvc.TerminateSessions(c.Request.Context(), req.ClusterID, req.InfobaseID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, models.TerminateSessionsResponse{
			TerminatedCount: terminatedCount,
			FailedSessions:  []string{},
		})
	}
}

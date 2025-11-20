package rest

import (
	"net/http"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
)

// GetInfobases returns handler for GET /api/v1/infobases
func GetInfobases(infobaseSvc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get cluster_id parameter
		clusterID := c.Query("cluster_id")
		if clusterID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "cluster_id parameter is required",
			})
			return
		}

		// Get infobases
		infobases, err := infobaseSvc.GetInfobases(c.Request.Context(), clusterID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"infobases": infobases,
		})
	}
}

// LockInfobase handles POST /api/v1/infobases/:infobase_id/lock
func LockInfobase(svc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		infobaseID := c.Param("infobase_id")

		// Validate infobase_id parameter
		if infobaseID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "infobase_id parameter is required",
			})
			return
		}

		var req struct {
			ClusterID string `json:"cluster_id" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Call service
		err := svc.LockInfobase(c.Request.Context(), req.ClusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Infobase locked successfully (scheduled jobs blocked)",
		})
	}
}

// UnlockInfobase handles POST /api/v1/infobases/:infobase_id/unlock
func UnlockInfobase(svc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		infobaseID := c.Param("infobase_id")

		// Validate infobase_id parameter
		if infobaseID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "infobase_id parameter is required",
			})
			return
		}

		var req struct {
			ClusterID string `json:"cluster_id" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Call service
		err := svc.UnlockInfobase(c.Request.Context(), req.ClusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Infobase unlocked successfully (scheduled jobs enabled)",
		})
	}
}

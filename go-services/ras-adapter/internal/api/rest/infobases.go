package rest

import (
	"net/http"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
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

// GetInfobaseByID returns handler for GET /api/v1/infobases/:id
func GetInfobaseByID(infobaseSvc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get infobase ID from URL parameter
		infobaseID := c.Param("id")
		if infobaseID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "infobase ID is required",
			})
			return
		}

		// Get cluster_id parameter
		clusterID := c.Query("cluster_id")
		if clusterID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "cluster_id parameter is required",
			})
			return
		}

		// Get infobase by ID
		infobase, err := infobaseSvc.GetInfobaseByID(c.Request.Context(), clusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, infobase)
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
			DBUser    string `json:"db_user"` // Optional: for databases with authentication
			DBPwd     string `json:"db_pwd"`  // Optional: for databases with authentication
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Call service
		err := svc.LockInfobase(c.Request.Context(), req.ClusterID, infobaseID, req.DBUser, req.DBPwd)
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
			DBUser    string `json:"db_user"` // Optional: for databases with authentication
			DBPwd     string `json:"db_pwd"`  // Optional: for databases with authentication
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Call service
		err := svc.UnlockInfobase(c.Request.Context(), req.ClusterID, infobaseID, req.DBUser, req.DBPwd)
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

// CreateInfobase handles POST /api/v1/infobases
func CreateInfobase(svc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			ClusterID string `json:"cluster_id" binding:"required"`
			Name      string `json:"name" binding:"required"`
			DBMS      string `json:"dbms" binding:"required"`
			DBServer  string `json:"db_server" binding:"required"`
			DBName    string `json:"db_name" binding:"required"`
			DBUser    string `json:"db_user"`
			DBPwd     string `json:"db_pwd"`
			Locale    string `json:"locale" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Create infobase model
		infobase := &models.Infobase{
			Name:     req.Name,
			DBMS:     req.DBMS,
			DBServer: req.DBServer,
			DBName:   req.DBName,
			DBUser:   req.DBUser,
			DBPwd:    req.DBPwd,
			Locale:   req.Locale,
		}

		// Call service
		infobaseID, err := svc.CreateInfobase(c.Request.Context(), req.ClusterID, infobase)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusCreated, gin.H{
			"success":     true,
			"infobase_id": infobaseID,
			"message":     "Infobase created successfully",
		})
	}
}

// DropInfobase handles DELETE /api/v1/infobases/:id
func DropInfobase(svc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		infobaseID := c.Param("id")
		if infobaseID == "" {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "infobase ID is required",
			})
			return
		}

		var req struct {
			ClusterID    string `json:"cluster_id" binding:"required"`
			DropDatabase bool   `json:"drop_database"` // Default: false (keep database)
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Call service
		err := svc.DropInfobase(c.Request.Context(), req.ClusterID, infobaseID, req.DropDatabase)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Infobase dropped successfully",
		})
	}
}

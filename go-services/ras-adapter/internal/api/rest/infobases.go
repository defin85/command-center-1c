package rest

import (
	"net/http"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
	uuid "github.com/satori/go.uuid"
)

// validateInfobaseID validates UUID format and returns error response if invalid
func validateInfobaseID(c *gin.Context, infobaseID string) bool {
	if infobaseID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "infobase_id is required",
		})
		return false
	}

	if _, err := uuid.FromString(infobaseID); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "invalid infobase_id format (expected UUID)",
		})
		return false
	}

	return true
}

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
		if !validateInfobaseID(c, infobaseID) {
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
		if !validateInfobaseID(c, infobaseID) {
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
		if !validateInfobaseID(c, infobaseID) {
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

// BlockSessions handles POST /api/v1/infobases/:infobase_id/block-sessions
func BlockSessions(svc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		infobaseID := c.Param("infobase_id")
		if !validateInfobaseID(c, infobaseID) {
			return
		}

		var req struct {
			ClusterID       string `json:"cluster_id" binding:"required"`
			DBUser          string `json:"db_user"`
			DBPwd           string `json:"db_pwd"`
			DeniedFrom      string `json:"denied_from"`       // RFC3339 format
			DeniedTo        string `json:"denied_to"`         // RFC3339 format
			DeniedMessage   string `json:"denied_message"`
			PermissionCode  string `json:"permission_code"`
			DeniedParameter string `json:"denied_parameter"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Parse denied_from (default: NOW)
		deniedFrom := time.Now()
		if req.DeniedFrom != "" {
			parsed, err := time.Parse(time.RFC3339, req.DeniedFrom)
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{
					"error": "invalid denied_from format, use RFC3339 (e.g., 2025-11-23T18:00:00Z)",
				})
				return
			}
			deniedFrom = parsed
		}

		// Parse denied_to (optional)
		var deniedTo time.Time
		if req.DeniedTo != "" {
			parsed, err := time.Parse(time.RFC3339, req.DeniedTo)
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{
					"error": "invalid denied_to format, use RFC3339",
				})
				return
			}
			deniedTo = parsed

			// Validate range
			if deniedFrom.After(deniedTo) {
				c.JSON(http.StatusBadRequest, gin.H{
					"error": "denied_from must be before denied_to",
				})
				return
			}

			// Warn if denied_to in the past
			if deniedTo.Before(time.Now()) {
				c.JSON(http.StatusBadRequest, gin.H{
					"error": "denied_to is in the past, block would have no effect",
				})
				return
			}
		}

		// Call service
		err := svc.BlockSessions(c.Request.Context(), req.ClusterID, infobaseID,
			req.DBUser, req.DBPwd, deniedFrom, deniedTo,
			req.DeniedMessage, req.PermissionCode, req.DeniedParameter)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		response := gin.H{
			"success": true,
			"message": "Sessions blocked successfully",
		}

		if !deniedFrom.IsZero() {
			response["blocked_from"] = deniedFrom.Format(time.RFC3339)
		}
		if !deniedTo.IsZero() {
			response["blocked_to"] = deniedTo.Format(time.RFC3339)
		}

		c.JSON(http.StatusOK, response)
	}
}

// UnblockSessions handles POST /api/v1/infobases/:infobase_id/unblock-sessions
func UnblockSessions(svc *service.InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		infobaseID := c.Param("infobase_id")
		if !validateInfobaseID(c, infobaseID) {
			return
		}

		var req struct {
			ClusterID string `json:"cluster_id" binding:"required"`
			DBUser    string `json:"db_user"`
			DBPwd     string `json:"db_pwd"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "invalid request body: " + err.Error(),
			})
			return
		}

		// Call service
		err := svc.UnblockSessions(c.Request.Context(), req.ClusterID, infobaseID,
			req.DBUser, req.DBPwd)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": "Sessions unblocked successfully (new connections allowed)",
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
		if !validateInfobaseID(c, infobaseID) {
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

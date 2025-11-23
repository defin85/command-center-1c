package v2

import (
	"net/http"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/gin-gonic/gin"
)

// Infobase Management Handlers

// ListInfobases retrieves all infobases for a cluster
// @Summary      List infobases
// @Description  Get list of all infobases in cluster
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id  query     string  true  "Cluster UUID"
// @Success      200  {object}  InfobasesResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /list-infobases [get]
func ListInfobases(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")

		if clusterID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id is required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id must be a valid UUID",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Call service layer
		infobases, err := svc.GetInfobases(c.Request.Context(), clusterID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to retrieve infobases",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, InfobasesResponse{
			Infobases: infobases,
			Count:     len(infobases),
		})
	}
}

// GetInfobase retrieves specific infobase by ID
// @Summary      Get infobase
// @Description  Get specific infobase details by UUID
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string  true  "Cluster UUID"
// @Param        infobase_id  query     string  true  "Infobase UUID"
// @Success      200  {object}  InfobaseResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      404  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /get-infobase [get]
func GetInfobase(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")

		if clusterID == "" || infobaseID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Call service layer
		infobase, err := svc.GetInfobaseByID(c.Request.Context(), clusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusNotFound, ErrorResponse{
				Error:   "Infobase not found",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, InfobaseResponse{
			Infobase: infobase,
		})
	}
}

// CreateInfobase creates a new infobase
// @Summary      Create infobase
// @Description  Create new 1C infobase in cluster
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id  query     string                  true  "Cluster UUID"
// @Param        request     body      CreateInfobaseRequest   true  "Infobase details"
// @Success      201  {object}  CreateInfobaseResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /create-infobase [post]
func CreateInfobase(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")

		if clusterID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id is required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id must be a valid UUID",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Body params
		var req CreateInfobaseRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error:   "Invalid request body",
				Details: err.Error(),
			})
			return
		}

		// Convert to models.Infobase
		infobase := &models.Infobase{
			Name:              req.Name,
			DBMS:              req.DBMS,
			DBServer:          req.DBServerName,
			DBName:            req.DBName,
			DBUser:            req.DBUser,
			DBPwd:             req.DBPassword,
			Locale:            req.Locale,
			ScheduledJobsDeny: req.ScheduledJobsDenied,
			SessionsDeny:      req.SessionsDenied,
		}

		// Call service layer
		infobaseID, err := svc.CreateInfobase(c.Request.Context(), clusterID, infobase)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to create infobase",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusCreated, CreateInfobaseResponse{
			Success:    true,
			InfobaseID: infobaseID,
			Message:    "Infobase created successfully",
		})
	}
}

// DropInfobase deletes an infobase
// @Summary      Drop infobase
// @Description  Delete infobase and optionally drop associated database
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string                true  "Cluster UUID"
// @Param        infobase_id  query     string                true  "Infobase UUID"
// @Param        request      body      DropInfobaseRequest   false "Drop parameters"
// @Success      200  {object}  SuccessResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /drop-infobase [post]
func DropInfobase(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")

		if clusterID == "" || infobaseID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Body params (optional)
		var req DropInfobaseRequest
		if err := c.ShouldBindJSON(&req); err != nil && c.Request.ContentLength > 0 {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error:   "Invalid request body format",
				Details: err.Error(),
				Code:    "INVALID_JSON",
			})
			return
		}

		// Call service layer
		err := svc.DropInfobase(c.Request.Context(), clusterID, infobaseID, req.DropDatabase)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to drop infobase",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, SuccessResponse{
			Success: true,
			Message: "Infobase dropped successfully",
		})
	}
}

// LockInfobase locks an infobase (blocks scheduled jobs)
// @Summary      Lock infobase
// @Description  Lock infobase to block scheduled jobs execution
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string               true  "Cluster UUID"
// @Param        infobase_id  query     string               true  "Infobase UUID"
// @Param        request      body      LockInfobaseRequest  false "Database credentials"
// @Success      200  {object}  SuccessResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /lock-infobase [post]
func LockInfobase(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")

		if clusterID == "" || infobaseID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Body params (optional DB credentials)
		var req LockInfobaseRequest
		if err := c.ShouldBindJSON(&req); err != nil && c.Request.ContentLength > 0 {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error:   "Invalid request body format",
				Details: err.Error(),
				Code:    "INVALID_JSON",
			})
			return
		}

		// Call service layer
		err := svc.LockInfobase(c.Request.Context(), clusterID, infobaseID, req.DBUser, req.DBPassword)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to lock infobase",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, SuccessResponse{
			Success: true,
			Message: "Infobase locked successfully (scheduled jobs blocked)",
		})
	}
}

// UnlockInfobase unlocks an infobase (enables scheduled jobs)
// @Summary      Unlock infobase
// @Description  Unlock infobase to enable scheduled jobs execution
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string                 true  "Cluster UUID"
// @Param        infobase_id  query     string                 true  "Infobase UUID"
// @Param        request      body      UnlockInfobaseRequest  false "Database credentials"
// @Success      200  {object}  SuccessResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /unlock-infobase [post]
func UnlockInfobase(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")

		if clusterID == "" || infobaseID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Body params (optional DB credentials)
		var req UnlockInfobaseRequest
		if err := c.ShouldBindJSON(&req); err != nil && c.Request.ContentLength > 0 {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error:   "Invalid request body format",
				Details: err.Error(),
				Code:    "INVALID_JSON",
			})
			return
		}

		// Call service layer
		err := svc.UnlockInfobase(c.Request.Context(), clusterID, infobaseID, req.DBUser, req.DBPassword)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to unlock infobase",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, SuccessResponse{
			Success: true,
			Message: "Infobase unlocked successfully (scheduled jobs enabled)",
		})
	}
}

// BlockSessions blocks new user sessions for maintenance
// @Summary      Block sessions
// @Description  Prevent users from starting new sessions during maintenance window
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string                 true  "Cluster UUID"
// @Param        infobase_id  query     string                 true  "Infobase UUID"
// @Param        request      body      BlockSessionsRequest   false "Block parameters"
// @Success      200  {object}  SuccessResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /block-sessions [post]
func BlockSessions(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")

		if clusterID == "" || infobaseID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Body params (optional details)
		var req BlockSessionsRequest
		if err := c.ShouldBindJSON(&req); err != nil && c.Request.ContentLength > 0 {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error:   "Invalid request body format",
				Details: err.Error(),
				Code:    "INVALID_JSON",
			})
			return
		}

		// Convert time pointers to values
		var deniedFrom, deniedTo time.Time
		if req.DeniedFrom != nil {
			deniedFrom = *req.DeniedFrom
		}
		if req.DeniedTo != nil {
			deniedTo = *req.DeniedTo
		}

		// Call service layer
		err := svc.BlockSessions(
			c.Request.Context(),
			clusterID,
			infobaseID,
			req.DBUser,
			req.DBPassword,
			deniedFrom,
			deniedTo,
			req.DeniedMessage,
			req.PermissionCode,
			req.Parameter,
		)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to block sessions",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, SuccessResponse{
			Success: true,
			Message: "User sessions blocked successfully",
		})
	}
}

// UnblockSessions unblocks user sessions
// @Summary      Unblock sessions
// @Description  Allow users to start new sessions after maintenance window
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string                   true  "Cluster UUID"
// @Param        infobase_id  query     string                   true  "Infobase UUID"
// @Param        request      body      UnblockSessionsRequest   false "Database credentials"
// @Success      200  {object}  SuccessResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /unblock-sessions [post]
func UnblockSessions(svc InfobaseService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")

		if clusterID == "" || infobaseID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id and infobase_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// Body params (optional DB credentials)
		var req UnblockSessionsRequest
		if err := c.ShouldBindJSON(&req); err != nil && c.Request.ContentLength > 0 {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error:   "Invalid request body format",
				Details: err.Error(),
				Code:    "INVALID_JSON",
			})
			return
		}

		// Call service layer
		err := svc.UnblockSessions(c.Request.Context(), clusterID, infobaseID, req.DBUser, req.DBPassword)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to unblock sessions",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, SuccessResponse{
			Success: true,
			Message: "User sessions unblocked successfully",
		})
	}
}

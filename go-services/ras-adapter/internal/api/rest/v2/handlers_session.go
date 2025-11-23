package v2

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// Session Management Handlers

// ListSessions retrieves all sessions for a cluster and infobase
// @Summary      List sessions
// @Description  Get list of all user sessions on infobase
// @Tags         Sessions
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string  true  "Cluster UUID"
// @Param        infobase_id  query     string  true  "Infobase UUID"
// @Success      200  {object}  SessionsResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /list-sessions [get]
func ListSessions(svc SessionService) gin.HandlerFunc {
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
		sessions, err := svc.GetSessions(c.Request.Context(), clusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to retrieve sessions",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, SessionsResponse{
			Sessions: sessions,
			Count:    len(sessions),
		})
	}
}

// TerminateSession terminates a specific session
// @Summary      Terminate session
// @Description  Terminate specific user session (NOT IMPLEMENTED - service layer support needed)
// @Tags         Sessions
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string  true  "Cluster UUID"
// @Param        infobase_id  query     string  true  "Infobase UUID"
// @Param        session_id   query     string  true  "Session UUID"
// @Success      200  {object}  TerminateSessionResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      501  {object}  ErrorResponse
// @Router       /terminate-session [post]
func TerminateSession(svc SessionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Query params validation
		clusterID := c.Query("cluster_id")
		infobaseID := c.Query("infobase_id")
		sessionID := c.Query("session_id")

		if clusterID == "" || infobaseID == "" || sessionID == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id, infobase_id, and session_id are required",
				Code:  "MISSING_PARAMETER",
			})
			return
		}

		if !isValidUUID(clusterID) || !isValidUUID(infobaseID) || !isValidUUID(sessionID) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: "cluster_id, infobase_id, and session_id must be valid UUIDs",
				Code:  "INVALID_UUID",
			})
			return
		}

		// TODO(Week 5.2): Implement idempotent TerminateSession(sessionID) in service layer
		// Race condition: Session may terminate between GetSessions() and termination
		// Proper solution: service.TerminateSession(clusterID, sessionID) should be idempotent
		// For now, return 501 Not Implemented to indicate missing functionality
		c.JSON(http.StatusNotImplemented, ErrorResponse{
			Error: "Single session termination not yet implemented in service layer",
			Code:  "NOT_IMPLEMENTED",
		})
	}
}

// TerminateSessions terminates multiple sessions (bulk operation)
// @Summary      Terminate sessions
// @Description  Terminate all or specific user sessions on infobase (selective termination not yet implemented)
// @Tags         Sessions
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string                     true  "Cluster UUID"
// @Param        infobase_id  query     string                     true  "Infobase UUID"
// @Param        request      body      TerminateSessionsRequest   false "Session IDs to terminate (optional)"
// @Success      200  {object}  TerminateSessionsResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      501  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /terminate-sessions [post]
func TerminateSessions(svc SessionService) gin.HandlerFunc {
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

		// Body params (optional - if empty, terminates ALL sessions)
		var req TerminateSessionsRequest
		hasBody := c.ShouldBindJSON(&req) == nil && len(req.SessionIDs) > 0

		if hasBody {
			// Validate UUID format for each session ID
			for _, sid := range req.SessionIDs {
				if !isValidUUID(sid) {
					c.JSON(http.StatusBadRequest, ErrorResponse{
						Error:   "All session_ids must be valid UUIDs",
						Code:    "INVALID_UUID",
						Details: "Invalid session ID: " + sid,
					})
					return
				}
			}

			// TODO: Implement selective termination in service layer
			// For now, terminate all sessions if session_ids provided
			c.JSON(http.StatusNotImplemented, ErrorResponse{
				Error: "Selective session termination not yet implemented",
				Code:  "NOT_IMPLEMENTED",
			})
			return
		}

		// Terminate ALL sessions
		terminatedCount, err := svc.TerminateSessions(c.Request.Context(), clusterID, infobaseID)
		if err != nil {
			c.JSON(http.StatusInternalServerError, ErrorResponse{
				Error:   "Failed to terminate sessions",
				Details: err.Error(),
			})
			return
		}

		c.JSON(http.StatusOK, TerminateSessionsResponse{
			TerminatedCount: terminatedCount,
			FailedCount:     0,
		})
	}
}

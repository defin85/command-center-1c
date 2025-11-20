package handlers

import (
	"net/http"
	"time"

	"github.com/command-center-1c/cluster-service/internal/models"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// SessionsHandler handles session-related requests
type SessionsHandler struct {
	logger *zap.Logger
}

// NewSessionsHandler creates a new SessionsHandler instance
func NewSessionsHandler(logger *zap.Logger) *SessionsHandler {
	return &SessionsHandler{
		logger: logger,
	}
}

// GetSessions returns active sessions for a specific infobase
// MOCK IMPLEMENTATION for P3.3 - returns fake session data
func (h *SessionsHandler) GetSessions(c *gin.Context) {
	infobaseID := c.Query("infobase_id")
	if infobaseID == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "query parameter 'infobase_id' is required",
		})
		return
	}

	h.logger.Info("getting sessions (MOCK)",
		zap.String("infobase_id", infobaseID))

	// MOCK: Return 2 fake sessions for testing
	sessions := []models.Session{
		{
			SessionID:   "session-001",
			UserName:    "test_user_1",
			Application: "1CV8C",
			StartedAt:   time.Now().Add(-30 * time.Minute).Format(time.RFC3339),
		},
		{
			SessionID:   "session-002",
			UserName:    "test_user_2",
			Application: "WebClient",
			StartedAt:   time.Now().Add(-15 * time.Minute).Format(time.RFC3339),
		},
	}

	h.logger.Debug("returning mock sessions",
		zap.Int("count", len(sessions)))

	c.JSON(http.StatusOK, models.SessionsResponse{
		Sessions: sessions,
		Count:    len(sessions),
	})
}

// TerminateSessions terminates multiple sessions
// MOCK IMPLEMENTATION for P3.3 - simulates successful termination
func (h *SessionsHandler) TerminateSessions(c *gin.Context) {
	var req models.TerminateSessionsRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request: " + err.Error(),
		})
		return
	}

	h.logger.Info("terminating sessions (MOCK)",
		zap.String("infobase_id", req.InfobaseID),
		zap.Int("session_count", len(req.SessionIDs)),
		zap.Strings("session_ids", req.SessionIDs))

	// MOCK: Simulate successful termination
	// In real implementation, this would call RAS gRPC service
	terminatedCount := len(req.SessionIDs)
	failedSessions := []string{} // No failures in mock

	h.logger.Info("sessions terminated successfully (MOCK)",
		zap.Int("terminated_count", terminatedCount))

	c.JSON(http.StatusOK, models.TerminateSessionsResponse{
		TerminatedCount: terminatedCount,
		FailedSessions:  failedSessions,
	})
}

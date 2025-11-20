package handlers

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/command-center-1c/cluster-service/internal/models"
	"github.com/command-center-1c/cluster-service/internal/service"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// SessionsMonitor interface for monitoring sessions
type SessionsMonitor interface {
	MonitorInfobase(ctx context.Context, clusterID, infobaseID string) error
}

// InfobaseManagementHandler handles infobase management operations
type InfobaseManagementHandler struct {
	service        *service.InfobaseManagementService
	monitor        SessionsMonitor
	logger         *zap.Logger
	requestTimeout time.Duration
}

// NewInfobaseManagementHandler creates a new InfobaseManagementHandler instance
func NewInfobaseManagementHandler(svc *service.InfobaseManagementService, monitor SessionsMonitor, requestTimeout time.Duration, logger *zap.Logger) *InfobaseManagementHandler {
	return &InfobaseManagementHandler{
		service:        svc,
		monitor:        monitor,
		logger:         logger,
		requestTimeout: requestTimeout,
	}
}

// LockInfobaseRequest represents the request body for locking an infobase
type LockInfobaseRequest struct {
	ClusterID  string `json:"cluster_id" binding:"required"`
	InfobaseID string `json:"infobase_id" binding:"required"`
}

// UnlockInfobaseRequest represents the request body for unlocking an infobase
type UnlockInfobaseRequest struct {
	ClusterID  string `json:"cluster_id" binding:"required"`
	InfobaseID string `json:"infobase_id" binding:"required"`
}

// TerminateSessionsForInfobaseRequest represents the request body for terminating sessions
type TerminateSessionsForInfobaseRequest struct {
	ClusterID  string `json:"cluster_id" binding:"required"`
	InfobaseID string `json:"infobase_id" binding:"required"`
}

// LockInfobase locks an infobase (blocks scheduled jobs)
// POST /api/v1/infobases/lock
func (h *InfobaseManagementHandler) LockInfobase(c *gin.Context) {
	var req LockInfobaseRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request: " + err.Error(),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.requestTimeout)
	defer cancel()

	err := h.service.LockInfobase(ctx, req.ClusterID, req.InfobaseID)
	if err != nil {
		statusCode, errResp := h.mapErrorToHTTP(err)
		c.JSON(statusCode, errResp)
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":                  "locked",
		"cluster_id":              req.ClusterID,
		"infobase_id":             req.InfobaseID,
		"scheduled_jobs_blocked":  true,
	})
}

// UnlockInfobase unlocks an infobase (enables scheduled jobs)
// POST /api/v1/infobases/unlock
func (h *InfobaseManagementHandler) UnlockInfobase(c *gin.Context) {
	var req UnlockInfobaseRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request: " + err.Error(),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.requestTimeout)
	defer cancel()

	err := h.service.UnlockInfobase(ctx, req.ClusterID, req.InfobaseID)
	if err != nil {
		statusCode, errResp := h.mapErrorToHTTP(err)
		c.JSON(statusCode, errResp)
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":      "unlocked",
		"cluster_id":  req.ClusterID,
		"infobase_id": req.InfobaseID,
	})
}

// TerminateInfobaseSessions terminates all sessions for an infobase
// POST /api/v1/infobases/terminate-sessions
func (h *InfobaseManagementHandler) TerminateInfobaseSessions(c *gin.Context) {
	var req TerminateSessionsForInfobaseRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request: " + err.Error(),
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.requestTimeout)
	defer cancel()

	terminated, err := h.service.TerminateSessions(ctx, req.ClusterID, req.InfobaseID)
	if err != nil {
		statusCode, errResp := h.mapErrorToHTTP(err)
		c.JSON(statusCode, errResp)
		return
	}

	// Start background monitor to publish event when sessions=0
	eventChannel := fmt.Sprintf("sessions:%s:closed", req.InfobaseID)

	if h.monitor != nil {
		h.logger.Info("starting background sessions monitor",
			zap.String("infobase_id", req.InfobaseID),
			zap.String("event_channel", eventChannel),
		)

		go func() {
			// Use background context with timeout to avoid blocking shutdown
			monitorCtx, monitorCancel := context.WithTimeout(context.Background(), 5*time.Minute)
			defer monitorCancel()

			if err := h.monitor.MonitorInfobase(monitorCtx, req.ClusterID, req.InfobaseID); err != nil {
				h.logger.Error("sessions monitor failed",
					zap.String("infobase_id", req.InfobaseID),
					zap.Error(err),
				)
			}
		}()
	}

	c.JSON(http.StatusOK, gin.H{
		"terminated_count": terminated,
		"cluster_id":       req.ClusterID,
		"infobase_id":      req.InfobaseID,
		"monitor_started":  h.monitor != nil,
		"event_channel":    eventChannel,
	})
}

// GetSessionsCount returns the count of active sessions for an infobase
// GET /api/v1/infobases/sessions-count?cluster_id=...&infobase_id=...
func (h *InfobaseManagementHandler) GetSessionsCount(c *gin.Context) {
	clusterID := c.Query("cluster_id")
	infobaseID := c.Query("infobase_id")

	if clusterID == "" || infobaseID == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "query parameters 'cluster_id' and 'infobase_id' are required",
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.requestTimeout)
	defer cancel()

	count, err := h.service.GetSessionsCount(ctx, clusterID, infobaseID)
	if err != nil {
		statusCode, errResp := h.mapErrorToHTTP(err)
		c.JSON(statusCode, errResp)
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"cluster_id":     clusterID,
		"infobase_id":    infobaseID,
		"sessions_count": count,
	})
}

// mapErrorToHTTP maps service errors to HTTP status codes
func (h *InfobaseManagementHandler) mapErrorToHTTP(err error) (int, models.ErrorResponse) {
	var svcErr *service.ServiceError
	if errors.As(err, &svcErr) {
		switch svcErr.Code {
		case "INVALID_PARAMS":
			return http.StatusBadRequest, models.ErrorResponse{Error: svcErr.Message}
		case "GRPC_UNAVAILABLE":
			return http.StatusServiceUnavailable, models.ErrorResponse{Error: svcErr.Message}
		}
	}

	return http.StatusInternalServerError, models.ErrorResponse{Error: "internal server error"}
}

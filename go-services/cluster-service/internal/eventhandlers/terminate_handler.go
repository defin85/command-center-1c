package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"

	"go.uber.org/zap"
)

const (
	// Channel names for terminate operations
	TerminateCommandChannel = "commands:cluster-service:sessions:terminate"
	SessionsClosedChannel   = "events:cluster-service:sessions:closed"
	TerminateFailedChannel  = "events:cluster-service:sessions:terminate-failed"

	// Event types for terminate operations
	SessionsClosedEvent        = "cluster.sessions.closed"
	SessionsTerminateFailedEvent = "cluster.sessions.terminate.failed"

	// Monitoring configuration
	monitorPollInterval = 1 * time.Second  // Poll every 1 second
	monitorMaxDuration  = 30 * time.Second // Max monitoring time: 30 seconds
)

// TerminateHandler handles terminate sessions commands from the event bus
type TerminateHandler struct {
	service     InfobaseManager
	publisher   EventPublisher
	redisClient RedisClient
	logger      *zap.Logger
}

// NewTerminateHandler creates a new TerminateHandler instance
func NewTerminateHandler(svc InfobaseManager, pub EventPublisher, redisClient RedisClient, logger *zap.Logger) *TerminateHandler {
	return &TerminateHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		logger:      logger,
	}
}

// checkIdempotency checks if the operation has been already processed using Redis SetNX
func (h *TerminateHandler) checkIdempotency(ctx context.Context, correlationID string, eventType string) (bool, error) {
	// Skip idempotency check if Redis is not configured
	if h.redisClient == nil {
		h.logger.Debug("Redis client not configured, skipping idempotency check",
			zap.String("correlation_id", correlationID))
		return true, nil
	}

	dedupKey := fmt.Sprintf("dedupe:%s:%s", correlationID, eventType)

	// Try to set key (returns true if key didn't exist)
	isFirst, err := h.redisClient.SetNX(ctx, dedupKey, "1", idempotencyTTL).Result()
	if err != nil {
		h.logger.Warn("Redis SetNX failed, allowing operation (fail-open)",
			zap.String("correlation_id", correlationID),
			zap.String("event_type", eventType),
			zap.Error(err))
		return true, nil // Fail-open: allow operation on Redis error
	}

	return isFirst, nil
}

// HandleTerminateCommand handles terminate sessions command from the event bus
func (h *TerminateHandler) HandleTerminateCommand(ctx context.Context, envelope *events.Envelope) error {
	// Parse payload
	var payload TerminateCommandPayload
	if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
		h.logger.Error("failed to parse terminate command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate required fields
	if payload.ClusterID == "" || payload.InfobaseID == "" {
		h.logger.Error("missing required fields in terminate command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("cluster_id and infobase_id are required"))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := h.checkIdempotency(ctx, envelope.CorrelationID, "terminate")
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed → skip operation and publish success (idempotent response)
		h.logger.Info("duplicate terminate command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", payload.InfobaseID))
		// For terminate, we publish success with 0 sessions closed (already handled)
		return h.publishSuccess(ctx, envelope.CorrelationID, payload, 0, 0, 0)
	}

	h.logger.Info("handling terminate sessions command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("infobase_id", payload.InfobaseID),
		zap.String("database_id", payload.DatabaseID))

	// Get initial sessions count
	initialCount, err := h.service.GetSessionsCount(ctx, payload.ClusterID, payload.InfobaseID)
	if err != nil {
		h.logger.Error("failed to get initial sessions count",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, err)
	}

	h.logger.Info("initial sessions count",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.Int("count", initialCount))

	// Terminate sessions
	terminatedCount, err := h.service.TerminateSessions(ctx, payload.ClusterID, payload.InfobaseID)
	if err != nil {
		h.logger.Error("failed to terminate sessions",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, err)
	}

	h.logger.Info("sessions termination initiated",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.Int("initial_count", initialCount),
		zap.Int("terminated_count", terminatedCount))

	// Start monitoring goroutine to check when all sessions are closed
	go h.monitorSessions(context.Background(), envelope.CorrelationID, payload, initialCount, terminatedCount)

	return nil
}

// monitorSessions monitors sessions count until it reaches 0 or timeout
func (h *TerminateHandler) monitorSessions(ctx context.Context, correlationID string, payload TerminateCommandPayload, initialCount, terminatedCount int) {
	ticker := time.NewTicker(monitorPollInterval)
	defer ticker.Stop()

	timeout := time.After(monitorMaxDuration)
	startTime := time.Now()

	h.logger.Info("starting sessions monitoring",
		zap.String("correlation_id", correlationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("infobase_id", payload.InfobaseID),
		zap.Duration("poll_interval", monitorPollInterval),
		zap.Duration("max_duration", monitorMaxDuration))

	for {
		select {
		case <-ctx.Done():
			h.logger.Warn("monitoring cancelled",
				zap.String("correlation_id", correlationID),
				zap.Error(ctx.Err()))
			return

		case <-timeout:
			h.logger.Warn("monitoring timeout reached",
				zap.String("correlation_id", correlationID),
				zap.Duration("duration", monitorMaxDuration))

			// Get final count and publish partial success
			finalCount, err := h.service.GetSessionsCount(ctx, payload.ClusterID, payload.InfobaseID)
			if err != nil {
				h.logger.Error("failed to get final sessions count",
					zap.String("correlation_id", correlationID),
					zap.Error(err))
				return
			}

			h.publishPartialSuccess(ctx, correlationID, payload, initialCount, terminatedCount, finalCount)
			return

		case <-ticker.C:
			// Poll sessions count
			currentCount, err := h.service.GetSessionsCount(ctx, payload.ClusterID, payload.InfobaseID)
			if err != nil {
				h.logger.Error("failed to get sessions count during monitoring",
					zap.String("correlation_id", correlationID),
					zap.Error(err))
				continue // Continue monitoring despite error
			}

			h.logger.Debug("monitoring sessions",
				zap.String("correlation_id", correlationID),
				zap.Int("current_count", currentCount),
				zap.Duration("elapsed", time.Since(startTime)))

			// Check if all sessions are closed
			if currentCount == 0 {
				h.logger.Info("all sessions closed",
					zap.String("correlation_id", correlationID),
					zap.Int("initial_count", initialCount),
					zap.Int("terminated_count", terminatedCount),
					zap.Duration("duration", time.Since(startTime)))

				h.publishSuccess(ctx, correlationID, payload, initialCount, terminatedCount, 0)
				return
			}
		}
	}
}

// publishSuccess publishes a sessions closed event (all sessions terminated)
func (h *TerminateHandler) publishSuccess(ctx context.Context, correlationID string, payload TerminateCommandPayload, initialCount, terminatedCount, remainingCount int) error {
	successPayload := SessionsClosedPayload{
		ClusterID:  payload.ClusterID,
		InfobaseID: payload.InfobaseID,
		DatabaseID: payload.DatabaseID,
		Message:    fmt.Sprintf("All sessions closed successfully (terminated: %d/%d)", terminatedCount, initialCount),
	}

	err := h.publisher.Publish(ctx,
		SessionsClosedChannel,
		SessionsClosedEvent,
		successPayload,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", SessionsClosedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", SessionsClosedChannel),
		zap.String("event_type", SessionsClosedEvent))

	return nil
}

// publishPartialSuccess publishes a partial success event (some sessions still remain)
func (h *TerminateHandler) publishPartialSuccess(ctx context.Context, correlationID string, payload TerminateCommandPayload, initialCount, terminatedCount, remainingCount int) error {
	successPayload := TerminateSuccessPayload{
		ClusterID:       payload.ClusterID,
		InfobaseID:      payload.InfobaseID,
		DatabaseID:      payload.DatabaseID,
		SessionsCount:   initialCount,
		TerminatedCount: terminatedCount,
		RemainingCount:  remainingCount,
		Message:         fmt.Sprintf("Partial success: terminated %d/%d sessions, %d still remaining", terminatedCount, initialCount, remainingCount),
	}

	err := h.publisher.Publish(ctx,
		SessionsClosedChannel,
		SessionsClosedEvent,
		successPayload,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish partial success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", SessionsClosedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish partial success event: %w", err)
	}

	h.logger.Info("partial success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", SessionsClosedChannel),
		zap.Int("remaining_count", remainingCount))

	return nil
}

// publishError publishes an error event to the event bus
func (h *TerminateHandler) publishError(ctx context.Context, correlationID string, payload TerminateCommandPayload, err error) error {
	errorPayload := ErrorPayload{
		ClusterID:  payload.ClusterID,
		InfobaseID: payload.InfobaseID,
		DatabaseID: payload.DatabaseID,
		Error:      err.Error(),
		Message:    "Failed to terminate sessions",
	}

	pubErr := h.publisher.Publish(ctx,
		TerminateFailedChannel,
		SessionsTerminateFailedEvent,
		errorPayload,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", TerminateFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", TerminateFailedChannel),
		zap.String("event_type", SessionsTerminateFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

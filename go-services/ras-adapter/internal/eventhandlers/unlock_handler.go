package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/commandcenter1c/commandcenter/shared/events"

	"go.uber.org/zap"
)

const (
	// Channel names for unlock operations
	// NOTE: Uses "cluster-service" prefix for backwards compatibility with Worker
	// Worker State Machine publishes to this channel, expecting cluster-service to handle it
	// This will be renamed to "ras-adapter" in Week 3+ when Worker is updated
	UnlockCommandChannel = "commands:cluster-service:infobase:unlock"
	UnlockedEventChannel = "events:cluster-service:infobase:unlocked"
	UnlockFailedChannel  = "events:cluster-service:infobase:unlock-failed"

	// Event types for unlock operations
	InfobaseUnlockedEvent     = "cluster.infobase.unlocked"
	InfobaseUnlockFailedEvent = "cluster.infobase.unlock.failed"
)

// UnlockHandler handles unlock infobase commands from the event bus
type UnlockHandler struct {
	service     InfobaseManager
	publisher   EventPublisher
	redisClient RedisClient
	logger      *zap.Logger
}

// NewUnlockHandler creates a new UnlockHandler instance
func NewUnlockHandler(svc InfobaseManager, pub EventPublisher, redisClient RedisClient, logger *zap.Logger) *UnlockHandler {
	return &UnlockHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		logger:      logger,
	}
}


// HandleUnlockCommand handles unlock infobase command from the event bus
func (h *UnlockHandler) HandleUnlockCommand(ctx context.Context, envelope *events.Envelope) error {
	// Parse payload
	var payload UnlockCommandPayload
	if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
		h.logger.Error("failed to parse unlock command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate required fields
	if payload.ClusterID == "" || payload.InfobaseID == "" {
		h.logger.Error("missing required fields in unlock command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("cluster_id and infobase_id are required"))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "unlock", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed → return success (idempotent response)
		h.logger.Info("duplicate unlock command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", payload.InfobaseID))
		return h.publishSuccess(ctx, envelope.CorrelationID, payload)
	}

	h.logger.Info("handling unlock command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("infobase_id", payload.InfobaseID),
		zap.String("database_id", payload.DatabaseID))

	// Call service to unlock infobase
	err = h.service.UnlockInfobase(ctx, payload.ClusterID, payload.InfobaseID)
	if err != nil {
		h.logger.Error("failed to unlock infobase",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, err)
	}

	// Publish success event
	h.logger.Info("infobase unlocked successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("infobase_id", payload.InfobaseID))

	return h.publishSuccess(ctx, envelope.CorrelationID, payload)
}

// publishSuccess publishes a success event to the event bus
func (h *UnlockHandler) publishSuccess(ctx context.Context, correlationID string, payload UnlockCommandPayload) error {
	successPayload := UnlockSuccessPayload{
		ClusterID:  payload.ClusterID,
		InfobaseID: payload.InfobaseID,
		DatabaseID: payload.DatabaseID,
		Message:    "Infobase unlocked successfully (scheduled jobs enabled)",
	}

	err := h.publisher.Publish(ctx,
		UnlockedEventChannel,
		InfobaseUnlockedEvent,
		successPayload,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", UnlockedEventChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", UnlockedEventChannel),
		zap.String("event_type", InfobaseUnlockedEvent))

	return nil
}

// publishError publishes an error event to the event bus
func (h *UnlockHandler) publishError(ctx context.Context, correlationID string, payload UnlockCommandPayload, err error) error {
	errorPayload := ErrorPayload{
		ClusterID:  payload.ClusterID,
		InfobaseID: payload.InfobaseID,
		DatabaseID: payload.DatabaseID,
		Error:      err.Error(),
		Message:    "Failed to unlock infobase",
	}

	pubErr := h.publisher.Publish(ctx,
		UnlockFailedChannel,
		InfobaseUnlockFailedEvent,
		errorPayload,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", UnlockFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", UnlockFailedChannel),
		zap.String("event_type", InfobaseUnlockFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

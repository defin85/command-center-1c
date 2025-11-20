package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"

	"go.uber.org/zap"
)

const (
	// Channel names
	LockCommandChannel = "commands:cluster-service:infobase:lock"
	LockedEventChannel = "events:cluster-service:infobase:locked"
	LockFailedChannel  = "events:cluster-service:infobase:lock-failed"

	// Event types
	InfobaseLockedEvent    = "cluster.infobase.locked"
	InfobaseLockFailedEvent = "cluster.infobase.lock.failed"

	// Idempotency
	idempotencyTTL = 10 * time.Minute
)

// RedisClient interface for idempotency checks
type RedisClient interface {
	SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd
}

// LockHandler handles lock infobase commands from the event bus
type LockHandler struct {
	service     InfobaseManager
	publisher   EventPublisher
	redisClient RedisClient
	logger      *zap.Logger
}

// NewLockHandler creates a new LockHandler instance
func NewLockHandler(svc InfobaseManager, pub EventPublisher, redisClient RedisClient, logger *zap.Logger) *LockHandler {
	return &LockHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		logger:      logger,
	}
}

// checkIdempotency checks if the operation has been already processed using Redis SetNX
func (h *LockHandler) checkIdempotency(ctx context.Context, correlationID string, eventType string) (bool, error) {
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

// HandleLockCommand handles lock infobase command from the event bus
func (h *LockHandler) HandleLockCommand(ctx context.Context, envelope *events.Envelope) error {
	// Parse payload
	var payload LockCommandPayload
	if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
		h.logger.Error("failed to parse lock command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate required fields
	if payload.ClusterID == "" || payload.InfobaseID == "" {
		h.logger.Error("missing required fields in lock command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("cluster_id and infobase_id are required"))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := h.checkIdempotency(ctx, envelope.CorrelationID, "lock")
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed → return success (idempotent response)
		h.logger.Info("duplicate lock command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", payload.InfobaseID))
		return h.publishSuccess(ctx, envelope.CorrelationID, payload)
	}

	h.logger.Info("handling lock command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("infobase_id", payload.InfobaseID),
		zap.String("database_id", payload.DatabaseID))

	// Call service to lock infobase
	err = h.service.LockInfobase(ctx, payload.ClusterID, payload.InfobaseID)
	if err != nil {
		h.logger.Error("failed to lock infobase",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", payload.ClusterID),
			zap.String("infobase_id", payload.InfobaseID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, err)
	}

	// Publish success event
	h.logger.Info("infobase locked successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("infobase_id", payload.InfobaseID))

	return h.publishSuccess(ctx, envelope.CorrelationID, payload)
}

// publishSuccess publishes a success event to the event bus
func (h *LockHandler) publishSuccess(ctx context.Context, correlationID string, payload LockCommandPayload) error {
	successPayload := LockSuccessPayload{
		ClusterID:  payload.ClusterID,
		InfobaseID: payload.InfobaseID,
		DatabaseID: payload.DatabaseID,
		Message:    "Infobase locked successfully (scheduled jobs blocked)",
	}

	err := h.publisher.Publish(ctx,
		LockedEventChannel,
		InfobaseLockedEvent,
		successPayload,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", LockedEventChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", LockedEventChannel),
		zap.String("event_type", InfobaseLockedEvent))

	return nil
}

// publishError publishes an error event to the event bus
func (h *LockHandler) publishError(ctx context.Context, correlationID string, payload LockCommandPayload, err error) error {
	errorPayload := ErrorPayload{
		ClusterID:  payload.ClusterID,
		InfobaseID: payload.InfobaseID,
		DatabaseID: payload.DatabaseID,
		Error:      err.Error(),
		Message:    "Failed to lock infobase",
	}

	pubErr := h.publisher.Publish(ctx,
		LockFailedChannel,
		InfobaseLockFailedEvent,
		errorPayload,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", LockFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", LockFailedChannel),
		zap.String("event_type", InfobaseLockFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

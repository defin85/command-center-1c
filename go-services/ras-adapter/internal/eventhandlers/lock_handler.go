package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/ras"

	"go.uber.org/zap"
)

const (
	// Channel names for lock operations
	// Uses new "ras" prefix as per shared/ras package
	LockCommandChannel = ras.StreamCommandsLock
	LockedEventChannel = ras.StreamEventsCompleted
	LockFailedChannel  = ras.StreamEventsFailed

	// Event types for lock operations
	InfobaseLockedEvent     = "ras.infobase.locked"
	InfobaseLockFailedEvent = "ras.infobase.lock.failed"
)

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

// HandleLockCommand handles lock infobase command from the event bus
func (h *LockHandler) HandleLockCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as RASCommand
	var cmd ras.RASCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse lock command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid lock command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "lock", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate lock command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", cmd.InfobaseID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, 0)
	}

	h.logger.Info("handling lock command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID),
		zap.String("database_id", cmd.DatabaseID))

	// Call service to lock infobase
	// NOTE: Event handlers don't provide db credentials - they should be managed by Orchestrator
	err = h.service.LockInfobase(ctx, cmd.ClusterID, cmd.InfobaseID, "", "")
	if err != nil {
		h.logger.Error("failed to lock infobase",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", cmd.ClusterID),
			zap.String("infobase_id", cmd.InfobaseID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// Publish success event
	h.logger.Info("infobase locked successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID))

	duration := time.Since(start)
	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, duration)
}

// publishSuccess publishes a success event to the event bus
func (h *LockHandler) publishSuccess(ctx context.Context, correlationID string, cmd *ras.RASCommand, duration time.Duration) error {
	result := ras.NewRASResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"message": "Infobase locked successfully (scheduled jobs blocked)",
	}, duration)

	err := h.publisher.Publish(ctx,
		LockedEventChannel,
		InfobaseLockedEvent,
		result,
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
func (h *LockHandler) publishError(ctx context.Context, correlationID string, cmd *ras.RASCommand, err error) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := ras.CommandTypeLock
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := ras.NewRASErrorResult(operationID, databaseID, commandType, err.Error(), 0)

	pubErr := h.publisher.Publish(ctx,
		LockFailedChannel,
		InfobaseLockFailedEvent,
		result,
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

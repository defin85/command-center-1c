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
	// Channel names for unblock operations
	// Uses new "ras" prefix as per shared/ras package
	UnblockCommandChannel  = ras.StreamCommandsUnblock
	UnblockedEventChannel  = ras.StreamEventsCompleted
	UnblockFailedChannel   = ras.StreamEventsFailed

	// Event types for unblock operations
	InfobaseUnblockedEvent     = "ras.infobase.unblocked"
	InfobaseUnblockFailedEvent = "ras.infobase.unblock.failed"
)

// UnblockHandler handles unblock infobase commands from the event bus
type UnblockHandler struct {
	service     SessionUnblocker
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	logger      *zap.Logger
}

// NewUnblockHandler creates a new UnblockHandler instance
func NewUnblockHandler(svc SessionUnblocker, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, logger *zap.Logger) *UnblockHandler {
	return &UnblockHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		logger:      logger,
	}
}

// HandleUnblockCommand handles unblock infobase command from the event bus
func (h *UnblockHandler) HandleUnblockCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as RASCommand
	var cmd ras.RASCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse unblock command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid unblock command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "unblock", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate unblock command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", cmd.InfobaseID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, 0)
	}

	h.logger.Info("handling unblock command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID),
		zap.String("database_id", cmd.DatabaseID))

	// Call service to unblock sessions
	// NOTE: Event handlers don't provide db credentials - they should be managed by Orchestrator
	err = h.service.UnblockSessions(ctx, cmd.ClusterID, cmd.InfobaseID, "", "")
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to unblock infobase sessions",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", cmd.ClusterID),
			zap.String("infobase_id", cmd.InfobaseID),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("unblock", "error", duration.Seconds())
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("unblock", "success", duration.Seconds())
	}

	// Publish success event
	h.logger.Info("infobase sessions unblocked successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, duration)
}

// publishSuccess publishes a success event to the event bus
func (h *UnblockHandler) publishSuccess(ctx context.Context, correlationID string, cmd *ras.RASCommand, duration time.Duration) error {
	result := ras.NewRASResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"message": "Infobase sessions unblocked successfully (new connections allowed)",
	}, duration)

	err := h.publisher.Publish(ctx,
		UnblockedEventChannel,
		InfobaseUnblockedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", UnblockedEventChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", UnblockedEventChannel),
		zap.String("event_type", InfobaseUnblockedEvent))

	return nil
}

// publishError publishes an error event to the event bus
func (h *UnblockHandler) publishError(ctx context.Context, correlationID string, cmd *ras.RASCommand, err error) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := ras.CommandTypeUnblock
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := ras.NewRASErrorResult(operationID, databaseID, commandType, err.Error(), 0)

	pubErr := h.publisher.Publish(ctx,
		UnblockFailedChannel,
		InfobaseUnblockFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", UnblockFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", UnblockFailedChannel),
		zap.String("event_type", InfobaseUnblockFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

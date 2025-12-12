package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"

	"go.uber.org/zap"
)

const (
	// Channel names for delete operations.
	DeleteCommandChannel   = sharedodata.StreamCommandsDelete
	DeleteCompletedChannel = sharedodata.StreamEventsCompleted
	DeleteFailedChannel    = sharedodata.StreamEventsFailed

	// Event types for delete operations.
	DeleteCompletedEvent = "odata.delete.completed"
	DeleteFailedEvent    = "odata.delete.failed"
)

// DeleteHandler handles delete commands from the event bus.
type DeleteHandler struct {
	client      ODataClient
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	logger      *zap.Logger
}

// NewDeleteHandler creates a new DeleteHandler instance.
func NewDeleteHandler(client ODataClient, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, logger *zap.Logger) *DeleteHandler {
	return &DeleteHandler{
		client:      client,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		logger:      logger,
	}
}

// HandleDeleteCommand handles delete command from the event bus.
func (h *DeleteHandler) HandleDeleteCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as ODataCommand
	var cmd sharedodata.ODataCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse delete command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), time.Since(start))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid delete command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, time.Since(start))
	}

	// EntityID is required for delete
	if cmd.EntityID == "" {
		h.logger.Error("entity_id is required for delete",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("entity", cmd.Entity))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, ErrEmptyEntityID, time.Since(start))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "delete", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate delete command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.String("entity", cmd.Entity),
			zap.String("entity_id", cmd.EntityID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, 0)
	}

	h.logger.Info("handling delete command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("entity", cmd.Entity),
		zap.String("entity_id", cmd.EntityID))

	// Execute delete
	err = h.client.Delete(ctx, cmd.Credentials, cmd.Entity, cmd.EntityID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute delete",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("entity", cmd.Entity),
			zap.String("entity_id", cmd.EntityID),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordOperation("delete", "error", duration.Seconds())
			h.metrics.RecordTransaction("delete", duration.Seconds())
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, duration)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordOperation("delete", "success", duration.Seconds())
		h.metrics.RecordTransaction("delete", duration.Seconds())
	}

	// Publish success event
	h.logger.Info("entity deleted successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("entity", cmd.Entity),
		zap.String("entity_id", cmd.EntityID),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, duration)
}

// publishSuccess publishes a success event to the event bus.
func (h *DeleteHandler) publishSuccess(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, duration time.Duration) error {
	result := sharedodata.NewODataResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"entity_id": cmd.EntityID,
		"message":   "Entity deleted successfully",
	}, duration)

	err := h.publisher.Publish(ctx,
		DeleteCompletedChannel,
		DeleteCompletedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", DeleteCompletedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Debug("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", DeleteCompletedChannel),
		zap.String("event_type", DeleteCompletedEvent))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *DeleteHandler) publishError(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, err error, duration time.Duration) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := sharedodata.CommandTypeDelete
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := sharedodata.NewODataErrorResult(operationID, databaseID, commandType, err.Error(), "", duration)

	pubErr := h.publisher.Publish(ctx,
		DeleteFailedChannel,
		DeleteFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", DeleteFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Debug("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", DeleteFailedChannel),
		zap.String("event_type", DeleteFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

package eventhandlers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"

	"go.uber.org/zap"
)

const (
	// Channel names for update operations.
	UpdateCommandChannel   = sharedodata.StreamCommandsUpdate
	UpdateCompletedChannel = sharedodata.StreamEventsCompleted
	UpdateFailedChannel    = sharedodata.StreamEventsFailed

	// Event types for update operations.
	UpdateCompletedEvent = "odata.update.completed"
	UpdateFailedEvent    = "odata.update.failed"
)

// ErrEmptyEntityID indicates that entity_id is required but not provided.
var ErrEmptyEntityID = errors.New("entity_id is required for update operation")

// UpdateHandler handles update commands from the event bus.
type UpdateHandler struct {
	client      ODataClient
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	logger      *zap.Logger
}

// NewUpdateHandler creates a new UpdateHandler instance.
func NewUpdateHandler(client ODataClient, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, logger *zap.Logger) *UpdateHandler {
	return &UpdateHandler{
		client:      client,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		logger:      logger,
	}
}

// HandleUpdateCommand handles update command from the event bus.
func (h *UpdateHandler) HandleUpdateCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as ODataCommand
	var cmd sharedodata.ODataCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse update command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), time.Since(start))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid update command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, time.Since(start))
	}

	// EntityID is required for update
	if cmd.EntityID == "" {
		h.logger.Error("entity_id is required for update",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("entity", cmd.Entity))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, ErrEmptyEntityID, time.Since(start))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "update", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate update command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.String("entity", cmd.Entity),
			zap.String("entity_id", cmd.EntityID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, 0)
	}

	h.logger.Info("handling update command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("entity", cmd.Entity),
		zap.String("entity_id", cmd.EntityID))

	// Execute update
	err = h.client.Update(ctx, cmd.Credentials, cmd.Entity, cmd.EntityID, cmd.Data)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute update",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("entity", cmd.Entity),
			zap.String("entity_id", cmd.EntityID),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordOperation("update", "error", duration.Seconds())
			h.metrics.RecordTransaction("update", duration.Seconds())
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, duration)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordOperation("update", "success", duration.Seconds())
		h.metrics.RecordTransaction("update", duration.Seconds())
	}

	// Publish success event
	h.logger.Info("entity updated successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("entity", cmd.Entity),
		zap.String("entity_id", cmd.EntityID),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, duration)
}

// publishSuccess publishes a success event to the event bus.
func (h *UpdateHandler) publishSuccess(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, duration time.Duration) error {
	result := sharedodata.NewODataResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"entity_id": cmd.EntityID,
		"message":   "Entity updated successfully",
	}, duration)

	err := h.publisher.Publish(ctx,
		UpdateCompletedChannel,
		UpdateCompletedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", UpdateCompletedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Debug("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", UpdateCompletedChannel),
		zap.String("event_type", UpdateCompletedEvent))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *UpdateHandler) publishError(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, err error, duration time.Duration) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := sharedodata.CommandTypeUpdate
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := sharedodata.NewODataErrorResult(operationID, databaseID, commandType, err.Error(), "", duration)

	pubErr := h.publisher.Publish(ctx,
		UpdateFailedChannel,
		UpdateFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", UpdateFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Debug("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", UpdateFailedChannel),
		zap.String("event_type", UpdateFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

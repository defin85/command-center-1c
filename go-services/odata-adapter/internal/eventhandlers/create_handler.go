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
	// Channel names for create operations.
	CreateCommandChannel   = sharedodata.StreamCommandsCreate
	CreateCompletedChannel = sharedodata.StreamEventsCompleted
	CreateFailedChannel    = sharedodata.StreamEventsFailed

	// Event types for create operations.
	CreateCompletedEvent = "odata.create.completed"
	CreateFailedEvent    = "odata.create.failed"
)

// CreateHandler handles create commands from the event bus.
type CreateHandler struct {
	client      ODataClient
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	timeline    TimelineRecorder
	logger      *zap.Logger
}

// NewCreateHandler creates a new CreateHandler instance.
func NewCreateHandler(client ODataClient, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, timeline TimelineRecorder, logger *zap.Logger) *CreateHandler {
	return &CreateHandler{
		client:      client,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		timeline:    timeline,
		logger:      logger,
	}
}

// HandleCreateCommand handles create command from the event bus.
func (h *CreateHandler) HandleCreateCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as ODataCommand
	var cmd sharedodata.ODataCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse create command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), time.Since(start))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid create command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, time.Since(start))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "create", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate create command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.String("entity", cmd.Entity))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, nil, 0)
	}

	h.logger.Info("handling create command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("entity", cmd.Entity))

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "odata.command.received", map[string]string{
			"command_type": cmd.CommandType,
			"entity":       cmd.Entity,
		})
	}

	// Execute create
	createdEntity, err := h.client.Create(ctx, cmd.Credentials, cmd.Entity, cmd.Data)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute create",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("entity", cmd.Entity),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordOperation("create", "error", duration.Seconds())
			h.metrics.RecordTransaction("create", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "odata.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, duration)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordOperation("create", "success", duration.Seconds())
		h.metrics.RecordTransaction("create", duration.Seconds())
	}
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "odata.command.completed", map[string]string{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	// Publish success event
	h.logger.Info("entity created successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("entity", cmd.Entity),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, createdEntity, duration)
}

// publishSuccess publishes a success event to the event bus.
func (h *CreateHandler) publishSuccess(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, data interface{}, duration time.Duration) error {
	result := sharedodata.NewODataResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, data, duration)

	err := h.publisher.Publish(ctx,
		CreateCompletedChannel,
		CreateCompletedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", CreateCompletedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Debug("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", CreateCompletedChannel),
		zap.String("event_type", CreateCompletedEvent))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *CreateHandler) publishError(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, err error, duration time.Duration) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := sharedodata.CommandTypeCreate
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := sharedodata.NewODataErrorResult(operationID, databaseID, commandType, err.Error(), "", duration)

	pubErr := h.publisher.Publish(ctx,
		CreateFailedChannel,
		CreateFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", CreateFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Debug("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", CreateFailedChannel),
		zap.String("event_type", CreateFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

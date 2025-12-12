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
	// Channel names for query operations.
	QueryCommandChannel   = sharedodata.StreamCommandsQuery
	QueryCompletedChannel = sharedodata.StreamEventsCompleted
	QueryFailedChannel    = sharedodata.StreamEventsFailed

	// Event types for query operations.
	QueryCompletedEvent = "odata.query.completed"
	QueryFailedEvent    = "odata.query.failed"
)

// QueryHandler handles query commands from the event bus.
type QueryHandler struct {
	client      ODataClient
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	logger      *zap.Logger
}

// NewQueryHandler creates a new QueryHandler instance.
func NewQueryHandler(client ODataClient, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, logger *zap.Logger) *QueryHandler {
	return &QueryHandler{
		client:      client,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		logger:      logger,
	}
}

// HandleQueryCommand handles query command from the event bus.
func (h *QueryHandler) HandleQueryCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as ODataCommand
	var cmd sharedodata.ODataCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse query command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), time.Since(start))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid query command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, time.Since(start))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "query", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate query command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.String("entity", cmd.Entity))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, nil, 0)
	}

	h.logger.Info("handling query command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("entity", cmd.Entity))

	// Execute query
	data, err := h.client.Query(ctx, cmd.Credentials, cmd.Entity, cmd.Query)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute query",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("entity", cmd.Entity),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordOperation("query", "error", duration.Seconds())
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, duration)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordOperation("query", "success", duration.Seconds())
	}

	// Publish success event
	h.logger.Info("query executed successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("entity", cmd.Entity),
		zap.Int("records_count", len(data)),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, data, duration)
}

// publishSuccess publishes a success event to the event bus.
func (h *QueryHandler) publishSuccess(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, data interface{}, duration time.Duration) error {
	result := sharedodata.NewODataResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, data, duration)

	err := h.publisher.Publish(ctx,
		QueryCompletedChannel,
		QueryCompletedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", QueryCompletedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Debug("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", QueryCompletedChannel),
		zap.String("event_type", QueryCompletedEvent))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *QueryHandler) publishError(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, err error, duration time.Duration) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := sharedodata.CommandTypeQuery
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := sharedodata.NewODataErrorResult(operationID, databaseID, commandType, err.Error(), "", duration)

	pubErr := h.publisher.Publish(ctx,
		QueryFailedChannel,
		QueryFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", QueryFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Debug("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", QueryFailedChannel),
		zap.String("event_type", QueryFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

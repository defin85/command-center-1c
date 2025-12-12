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
	// Channel names for batch operations.
	BatchCommandChannel   = sharedodata.StreamCommandsBatch
	BatchCompletedChannel = sharedodata.StreamEventsCompleted
	BatchFailedChannel    = sharedodata.StreamEventsFailed

	// Event types for batch operations.
	BatchCompletedEvent = "odata.batch.completed"
	BatchFailedEvent    = "odata.batch.failed"

	// MaxBatchTimeout is the maximum time allowed for batch operations (< 15s for 1C transactions).
	MaxBatchTimeout = 14 * time.Second

	// MaxBatchSize is the maximum number of items in a single batch.
	MaxBatchSize = 100
)

// BatchHandler handles batch commands from the event bus.
type BatchHandler struct {
	client      ODataClient
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	logger      *zap.Logger
}

// NewBatchHandler creates a new BatchHandler instance.
func NewBatchHandler(client ODataClient, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, logger *zap.Logger) *BatchHandler {
	return &BatchHandler{
		client:      client,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		logger:      logger,
	}
}

// HandleBatchCommand handles batch command from the event bus.
func (h *BatchHandler) HandleBatchCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as ODataCommand
	var cmd sharedodata.ODataCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse batch command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), time.Since(start))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid batch command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, time.Since(start))
	}

	// Validate command type is batch
	if cmd.CommandType != sharedodata.CommandTypeBatch {
		h.logger.Error("wrong command type for batch handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", sharedodata.CommandTypeBatch),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("expected command type 'batch', got '%s'", cmd.CommandType), time.Since(start))
	}

	// Validate batch size
	if len(cmd.BatchItems) > MaxBatchSize {
		h.logger.Error("batch size exceeds maximum",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Int("batch_size", len(cmd.BatchItems)),
			zap.Int("max_size", MaxBatchSize))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, sharedodata.ErrBatchTooLarge, time.Since(start))
	}

	// Validate each batch item
	for i, item := range cmd.BatchItems {
		if err := item.Validate(); err != nil {
			h.logger.Error("invalid batch item",
				zap.String("correlation_id", envelope.CorrelationID),
				zap.Int("item_index", i),
				zap.String("operation", item.Operation),
				zap.String("entity", item.Entity),
				zap.Error(err))
			return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("batch item %d: %w", i, err), time.Since(start))
		}
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "batch", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate batch command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.Int("batch_size", len(cmd.BatchItems)))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, nil, 0)
	}

	h.logger.Info("handling batch command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.Int("batch_size", len(cmd.BatchItems)))

	// Create timeout context for batch operation (< 15 seconds for 1C transactions)
	batchCtx, cancel := context.WithTimeout(ctx, MaxBatchTimeout)
	defer cancel()

	// Execute batch
	batchResult, err := h.client.ExecuteBatch(batchCtx, cmd.Credentials, cmd.BatchItems)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute batch",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Int("batch_size", len(cmd.BatchItems)),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordOperation("batch", "error", duration.Seconds())
			h.metrics.RecordTransaction("batch", duration.Seconds())
			h.metrics.RecordBatch("batch", len(cmd.BatchItems), 0, len(cmd.BatchItems))
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, duration)
	}

	// Record metrics for completed operation
	if h.metrics != nil {
		status := "success"
		if batchResult.FailureCount > 0 {
			status = "partial"
		}
		h.metrics.RecordOperation("batch", status, duration.Seconds())
		h.metrics.RecordTransaction("batch", duration.Seconds())
		h.metrics.RecordBatch("batch", batchResult.TotalCount, batchResult.SuccessCount, batchResult.FailureCount)
	}

	// Publish success event
	h.logger.Info("batch executed successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.Int("total_count", batchResult.TotalCount),
		zap.Int("success_count", batchResult.SuccessCount),
		zap.Int("failure_count", batchResult.FailureCount),
		zap.Bool("all_succeeded", batchResult.AllSucceeded()),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, batchResult, duration)
}

// publishSuccess publishes a success event to the event bus.
func (h *BatchHandler) publishSuccess(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, batchResult *sharedodata.BatchResult, duration time.Duration) error {
	result := sharedodata.NewODataResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, batchResult, duration)

	// Set affected count from batch result
	if batchResult != nil {
		result.AffectedCount = batchResult.SuccessCount
	}

	err := h.publisher.Publish(ctx,
		BatchCompletedChannel,
		BatchCompletedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", BatchCompletedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Debug("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", BatchCompletedChannel),
		zap.String("event_type", BatchCompletedEvent))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *BatchHandler) publishError(ctx context.Context, correlationID string, cmd *sharedodata.ODataCommand, err error, duration time.Duration) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := sharedodata.CommandTypeBatch
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := sharedodata.NewODataErrorResult(operationID, databaseID, commandType, err.Error(), "", duration)

	pubErr := h.publisher.Publish(ctx,
		BatchFailedChannel,
		BatchFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", BatchFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Debug("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", BatchFailedChannel),
		zap.String("event_type", BatchFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

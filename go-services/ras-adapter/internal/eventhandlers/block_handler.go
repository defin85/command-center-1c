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
	// Channel names for block operations
	// Uses new "ras" prefix as per shared/ras package
	BlockCommandChannel = ras.StreamCommandsBlock
	BlockedEventChannel = ras.StreamEventsCompleted
	BlockFailedChannel  = ras.StreamEventsFailed

	// Event types for block operations
	InfobaseBlockedEvent     = "ras.infobase.blocked"
	InfobaseBlockFailedEvent = "ras.infobase.block.failed"
)

// BlockHandler handles block infobase commands from the event bus
type BlockHandler struct {
	service     SessionBlocker
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	logger      *zap.Logger
}

// NewBlockHandler creates a new BlockHandler instance
func NewBlockHandler(svc SessionBlocker, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, logger *zap.Logger) *BlockHandler {
	return &BlockHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		logger:      logger,
	}
}

// HandleBlockCommand handles block infobase command from the event bus
func (h *BlockHandler) HandleBlockCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as RASCommand
	var cmd ras.RASCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse block command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid block command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "block", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate block command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", cmd.InfobaseID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, 0)
	}

	h.logger.Info("handling block command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID),
		zap.String("database_id", cmd.DatabaseID))

	// Extract optional parameters from Options
	message := getStringOption(cmd.Options, "message", "Maintenance in progress")
	permissionCode := getStringOption(cmd.Options, "permission_code", "")
	parameter := getStringOption(cmd.Options, "parameter", "")

	// Block duration: default 8 hours from now
	deniedFrom := time.Now()
	deniedTo := deniedFrom.Add(8 * time.Hour)

	// Allow overriding duration from options
	if durationMinutes, ok := cmd.Options["duration_minutes"].(float64); ok && durationMinutes > 0 {
		deniedTo = deniedFrom.Add(time.Duration(durationMinutes) * time.Minute)
	}

	// Call service to block sessions
	// NOTE: Event handlers don't provide db credentials - they should be managed by Orchestrator
	err = h.service.BlockSessions(ctx, cmd.ClusterID, cmd.InfobaseID, "", "",
		deniedFrom, deniedTo, message, permissionCode, parameter)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to block infobase sessions",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", cmd.ClusterID),
			zap.String("infobase_id", cmd.InfobaseID),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("block", "error", duration.Seconds())
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("block", "success", duration.Seconds())
	}

	// Publish success event
	h.logger.Info("infobase sessions blocked successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID),
		zap.Time("denied_from", deniedFrom),
		zap.Time("denied_to", deniedTo))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, duration)
}

// publishSuccess publishes a success event to the event bus
func (h *BlockHandler) publishSuccess(ctx context.Context, correlationID string, cmd *ras.RASCommand, duration time.Duration) error {
	result := ras.NewRASResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"message": "Infobase sessions blocked successfully (new connections denied)",
	}, duration)

	err := h.publisher.Publish(ctx,
		BlockedEventChannel,
		InfobaseBlockedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", BlockedEventChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", BlockedEventChannel),
		zap.String("event_type", InfobaseBlockedEvent))

	return nil
}

// publishError publishes an error event to the event bus
func (h *BlockHandler) publishError(ctx context.Context, correlationID string, cmd *ras.RASCommand, err error) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := ras.CommandTypeBlock
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := ras.NewRASErrorResult(operationID, databaseID, commandType, err.Error(), 0)

	pubErr := h.publisher.Publish(ctx,
		BlockFailedChannel,
		InfobaseBlockFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", BlockFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", BlockFailedChannel),
		zap.String("event_type", InfobaseBlockFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

// getStringOption safely extracts a string option from the options map
func getStringOption(options map[string]interface{}, key, defaultValue string) string {
	if options == nil {
		return defaultValue
	}
	if val, ok := options[key].(string); ok && val != "" {
		return val
	}
	return defaultValue
}

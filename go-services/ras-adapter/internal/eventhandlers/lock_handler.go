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
	metrics     MetricsRecorder
	timeline    TimelineRecorder
	credsClient CredentialsFetcher // Fetch credentials from Orchestrator (optional)
	logger      *zap.Logger
}

// NewLockHandler creates a new LockHandler instance
func NewLockHandler(svc InfobaseManager, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, timeline TimelineRecorder, credsClient CredentialsFetcher, logger *zap.Logger) *LockHandler {
	return &LockHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		timeline:    timeline,
		credsClient: credsClient,
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

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "ras.command.received", map[string]interface{}{
			"command_type": cmd.CommandType,
			"cluster_id":   cmd.ClusterID,
			"infobase_id":  cmd.InfobaseID,
		})
	}

	// Fetch credentials from Orchestrator (if credentials client is configured)
	dbUser, dbPwd, err := FetchCredentialsForRAS(ctx, h.credsClient, cmd.DatabaseID, h.logger)
	if err != nil {
		h.logger.Error("failed to fetch credentials",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("database_id", cmd.DatabaseID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("failed to fetch credentials: %w", err))
	}

	// Call service to lock infobase
	err = h.service.LockInfobase(ctx, cmd.ClusterID, cmd.InfobaseID, dbUser, dbPwd)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to lock infobase",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", cmd.ClusterID),
			zap.String("infobase_id", cmd.InfobaseID),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("lock", "error", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "ras.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("lock", "success", duration.Seconds())
	}
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "ras.command.completed", map[string]interface{}{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	// Publish success event
	h.logger.Info("infobase locked successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID))

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

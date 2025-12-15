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
	// Channel names for terminate operations
	// Uses new "ras" prefix as per shared/ras package
	TerminateCommandChannel = ras.StreamCommandsTerminate
	SessionsClosedChannel   = ras.StreamEventsCompleted
	TerminateFailedChannel  = ras.StreamEventsFailed

	// Event types for terminate operations
	SessionsTerminatedEvent      = "ras.sessions.terminated"
	SessionsTerminateFailedEvent = "ras.sessions.terminate.failed"

	// Monitoring configuration
	monitorPollInterval = 1 * time.Second  // Poll every 1 second
	monitorMaxDuration  = 30 * time.Second // Max monitoring time: 30 seconds
)

// TerminateHandler handles terminate sessions commands from the event bus
type TerminateHandler struct {
	service     SessionManager
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	timeline    TimelineRecorder
	logger      *zap.Logger
}

// NewTerminateHandler creates a new TerminateHandler instance
func NewTerminateHandler(svc SessionManager, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, timeline TimelineRecorder, logger *zap.Logger) *TerminateHandler {
	return &TerminateHandler{
		service:     svc,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		timeline:    timeline,
		logger:      logger,
	}
}

// HandleTerminateCommand handles terminate sessions command from the event bus
func (h *TerminateHandler) HandleTerminateCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as RASCommand
	var cmd ras.RASCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse terminate command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid terminate command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "terminate", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		// Already processed -> return success (idempotent response)
		h.logger.Info("duplicate terminate command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("infobase_id", cmd.InfobaseID))
		// For terminate, we publish success with 0 sessions closed (already handled)
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, 0, 0, 0, 0)
	}

	h.logger.Info("handling terminate sessions command",
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

	// Get initial sessions count
	initialCount, err := h.service.GetSessionsCount(ctx, cmd.ClusterID, cmd.InfobaseID)
	if err != nil {
		h.logger.Error("failed to get initial sessions count",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", cmd.ClusterID),
			zap.String("infobase_id", cmd.InfobaseID),
			zap.Error(err))
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "ras.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	h.logger.Info("initial sessions count",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.Int("count", initialCount))

	// Terminate sessions
	terminatedCount, err := h.service.TerminateSessions(ctx, cmd.ClusterID, cmd.InfobaseID)
	if err != nil {
		h.logger.Error("failed to terminate sessions",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("cluster_id", cmd.ClusterID),
			zap.String("infobase_id", cmd.InfobaseID),
			zap.Error(err))
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "ras.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err)
	}

	h.logger.Info("sessions termination initiated",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.Int("initial_count", initialCount),
		zap.Int("terminated_count", terminatedCount))

	// Start monitoring goroutine to check when all sessions are closed
	// Pass start time for duration tracking
	go h.monitorSessions(context.Background(), envelope.CorrelationID, &cmd, initialCount, terminatedCount, start)

	return nil
}

// monitorSessions monitors sessions count until it reaches 0 or timeout
func (h *TerminateHandler) monitorSessions(ctx context.Context, correlationID string, cmd *ras.RASCommand, initialCount, terminatedCount int, startTime time.Time) {
	ticker := time.NewTicker(monitorPollInterval)
	defer ticker.Stop()

	timeout := time.After(monitorMaxDuration)

	h.logger.Info("starting sessions monitoring",
		zap.String("correlation_id", correlationID),
		zap.String("cluster_id", cmd.ClusterID),
		zap.String("infobase_id", cmd.InfobaseID),
		zap.Duration("poll_interval", monitorPollInterval),
		zap.Duration("max_duration", monitorMaxDuration))

	for {
		select {
		case <-ctx.Done():
			h.logger.Warn("monitoring cancelled",
				zap.String("correlation_id", correlationID),
				zap.Error(ctx.Err()))
			return

		case <-timeout:
			h.logger.Warn("monitoring timeout reached",
				zap.String("correlation_id", correlationID),
				zap.Duration("duration", monitorMaxDuration))

			// Get final count and publish partial success
			finalCount, err := h.service.GetSessionsCount(ctx, cmd.ClusterID, cmd.InfobaseID)
			if err != nil {
				h.logger.Error("failed to get final sessions count",
					zap.String("correlation_id", correlationID),
					zap.Error(err))
				return
			}

			duration := time.Since(startTime)
			// Record metrics for partial success (timeout)
			if h.metrics != nil {
				h.metrics.RecordCommand("terminate", "partial", duration.Seconds())
			}
			// Record timeline: command completed (partial)
			if h.timeline != nil {
				h.timeline.Record(ctx, cmd.OperationID, "ras.command.completed", map[string]interface{}{
					"command_type": cmd.CommandType,
					"status":       "partial",
					"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
				})
			}
			h.publishPartialSuccess(ctx, correlationID, cmd, initialCount, terminatedCount, finalCount, duration)
			return

		case <-ticker.C:
			// Poll sessions count
			currentCount, err := h.service.GetSessionsCount(ctx, cmd.ClusterID, cmd.InfobaseID)
			if err != nil {
				h.logger.Error("failed to get sessions count during monitoring",
					zap.String("correlation_id", correlationID),
					zap.Error(err))
				continue // Continue monitoring despite error
			}

			h.logger.Debug("monitoring sessions",
				zap.String("correlation_id", correlationID),
				zap.Int("current_count", currentCount),
				zap.Duration("elapsed", time.Since(startTime)))

			// Check if all sessions are closed
			if currentCount == 0 {
				h.logger.Info("all sessions closed",
					zap.String("correlation_id", correlationID),
					zap.Int("initial_count", initialCount),
					zap.Int("terminated_count", terminatedCount),
					zap.Duration("duration", time.Since(startTime)))

				duration := time.Since(startTime)
				// Record metrics for successful operation
				if h.metrics != nil {
					h.metrics.RecordCommand("terminate", "success", duration.Seconds())
				}
				// Record timeline: command completed (success)
				if h.timeline != nil {
					h.timeline.Record(ctx, cmd.OperationID, "ras.command.completed", map[string]interface{}{
						"command_type": cmd.CommandType,
						"status":       "success",
						"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
					})
				}
				h.publishSuccess(ctx, correlationID, cmd, initialCount, terminatedCount, 0, duration)
				return
			}
		}
	}
}

// publishSuccess publishes a sessions terminated event (all sessions closed)
func (h *TerminateHandler) publishSuccess(ctx context.Context, correlationID string, cmd *ras.RASCommand, initialCount, terminatedCount, remainingCount int, duration time.Duration) error {
	result := ras.NewRASResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"initial_count":    initialCount,
		"terminated_count": terminatedCount,
		"remaining_count":  remainingCount,
		"message":          fmt.Sprintf("All sessions closed successfully (terminated: %d/%d)", terminatedCount, initialCount),
	}, duration)

	err := h.publisher.Publish(ctx,
		SessionsClosedChannel,
		SessionsTerminatedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", SessionsClosedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", SessionsClosedChannel),
		zap.String("event_type", SessionsTerminatedEvent))

	return nil
}

// publishPartialSuccess publishes a partial success event (some sessions still remain)
func (h *TerminateHandler) publishPartialSuccess(ctx context.Context, correlationID string, cmd *ras.RASCommand, initialCount, terminatedCount, remainingCount int, duration time.Duration) error {
	result := ras.NewRASResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"initial_count":    initialCount,
		"terminated_count": terminatedCount,
		"remaining_count":  remainingCount,
		"message":          fmt.Sprintf("Partial success: terminated %d/%d sessions, %d still remaining", terminatedCount, initialCount, remainingCount),
	}, duration)

	err := h.publisher.Publish(ctx,
		SessionsClosedChannel,
		SessionsTerminatedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish partial success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", SessionsClosedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish partial success event: %w", err)
	}

	h.logger.Info("partial success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", SessionsClosedChannel),
		zap.Int("remaining_count", remainingCount))

	return nil
}

// publishError publishes an error event to the event bus
func (h *TerminateHandler) publishError(ctx context.Context, correlationID string, cmd *ras.RASCommand, err error) error {
	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := ras.CommandTypeTerminate
	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := ras.NewRASErrorResult(operationID, databaseID, commandType, err.Error(), 0)

	pubErr := h.publisher.Publish(ctx,
		TerminateFailedChannel,
		SessionsTerminateFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", TerminateFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", TerminateFailedChannel),
		zap.String("event_type", SessionsTerminateFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}

package jobs

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

const (
	// EventReplayJobName is the unique name for the event replay job
	EventReplayJobName = "replay_failed_events"

	// Default values
	defaultEventReplayBatchSize = 100

	// Envelope version for compatibility with Python version
	envelopeVersion = "1.0"
)

// EventReplayMetrics holds metrics for the event replay job
type EventReplayMetrics struct {
	eventsProcessed *prometheus.CounterVec
	eventsReplayed  prometheus.Counter
	eventsFailed    prometheus.Counter
	batchDuration   prometheus.Histogram
}

// newEventReplayMetrics creates and registers event replay metrics
func newEventReplayMetrics() *EventReplayMetrics {
	return &EventReplayMetrics{
		eventsProcessed: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: "cc1c",
				Subsystem: "event_replay",
				Name:      "events_processed_total",
				Help:      "Total number of events processed by replay job",
			},
			[]string{"status"},
		),
		eventsReplayed: promauto.NewCounter(
			prometheus.CounterOpts{
				Namespace: "cc1c",
				Subsystem: "event_replay",
				Name:      "events_replayed_total",
				Help:      "Total number of successfully replayed events",
			},
		),
		eventsFailed: promauto.NewCounter(
			prometheus.CounterOpts{
				Namespace: "cc1c",
				Subsystem: "event_replay",
				Name:      "events_failed_total",
				Help:      "Total number of events that failed replay",
			},
		),
		batchDuration: promauto.NewHistogram(
			prometheus.HistogramOpts{
				Namespace: "cc1c",
				Subsystem: "event_replay",
				Name:      "batch_duration_seconds",
				Help:      "Duration of event replay batch processing",
				Buckets:   []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60},
			},
		),
	}
}

var (
	eventReplayMetrics     *EventReplayMetrics
	eventReplayMetricsOnce sync.Once
)

func getEventReplayMetrics() *EventReplayMetrics {
	eventReplayMetricsOnce.Do(func() {
		eventReplayMetrics = newEventReplayMetrics()
	})
	return eventReplayMetrics
}

// EventReplayJob replays failed events by publishing them to Redis Streams
type EventReplayJob struct {
	orchestratorClient orchestrator.EventReplayClient
	redisClient        redis.Cmdable
	logger             *zap.Logger
	batchSize          int
	metrics            *EventReplayMetrics
}

// NewEventReplayJob creates a new event replay job
func NewEventReplayJob(
	orchestratorClient orchestrator.EventReplayClient,
	redisClient redis.Cmdable,
	logger *zap.Logger,
	batchSize int,
) *EventReplayJob {
	if batchSize <= 0 {
		batchSize = defaultEventReplayBatchSize
	}
	if batchSize > 1000 {
		batchSize = 1000
	}

	return &EventReplayJob{
		orchestratorClient: orchestratorClient,
		redisClient:        redisClient,
		logger:             logger.With(zap.String("job", EventReplayJobName)),
		batchSize:          batchSize,
		metrics:            getEventReplayMetrics(),
	}
}

// Name returns the unique name of the job
func (j *EventReplayJob) Name() string {
	return EventReplayJobName
}

// Execute runs the event replay job
func (j *EventReplayJob) Execute(ctx context.Context) error {
	startTime := time.Now()
	j.logger.Debug("starting event replay job")

	// Step 1: Check Redis availability
	if err := j.checkRedisAvailability(ctx); err != nil {
		j.logger.Error("redis unavailable, skipping event replay",
			zap.Error(err),
		)
		return fmt.Errorf("redis unavailable: %w", err)
	}

	// Step 2: Get pending failed events from Orchestrator
	events, err := j.orchestratorClient.GetPendingFailedEvents(ctx, j.batchSize)
	if err != nil {
		j.logger.Error("failed to get pending failed events",
			zap.Error(err),
		)
		return fmt.Errorf("failed to get pending failed events: %w", err)
	}

	if len(events) == 0 {
		j.logger.Debug("no pending failed events to replay")
		return nil
	}

	j.logger.Info("processing pending failed events",
		zap.Int("count", len(events)),
	)

	// Step 3: Process each event
	var successCount, failCount int
	for _, event := range events {
		if err := j.replayEvent(ctx, event); err != nil {
			j.logger.Warn("failed to replay event",
				zap.Int("event_id", event.ID),
				zap.String("event_type", event.EventType),
				zap.Error(err),
			)
			failCount++
			j.metrics.eventsFailed.Inc()
			j.metrics.eventsProcessed.WithLabelValues("failed").Inc()
		} else {
			successCount++
			j.metrics.eventsReplayed.Inc()
			j.metrics.eventsProcessed.WithLabelValues("success").Inc()
		}
	}

	duration := time.Since(startTime)
	j.metrics.batchDuration.Observe(duration.Seconds())

	j.logger.Info("event replay job completed",
		zap.Int("total", len(events)),
		zap.Int("success", successCount),
		zap.Int("failed", failCount),
		zap.Duration("duration", duration),
	)

	return nil
}

// checkRedisAvailability verifies Redis is available
func (j *EventReplayJob) checkRedisAvailability(ctx context.Context) error {
	if err := j.redisClient.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("redis ping failed: %w", err)
	}
	return nil
}

// replayEvent publishes a single event to Redis Stream
func (j *EventReplayJob) replayEvent(ctx context.Context, event orchestrator.FailedEvent) error {
	// Build envelope compatible with Python version
	envelope := j.buildEnvelope(event)

	// Marshal envelope to JSON
	payloadBytes, err := json.Marshal(envelope)
	if err != nil {
		// Mark event as failed in Orchestrator
		_, markErr := j.orchestratorClient.MarkEventFailed(ctx, event.ID, fmt.Sprintf("failed to marshal envelope: %v", err))
		if markErr != nil {
			j.logger.Warn("failed to mark event as failed after marshal error",
				zap.Int("event_id", event.ID),
				zap.Error(markErr),
			)
		}
		return fmt.Errorf("failed to marshal envelope: %w", err)
	}

	// Publish to Redis Stream using XADD
	streamKey := event.Channel
	_, err = j.redisClient.XAdd(ctx, &redis.XAddArgs{
		Stream: streamKey,
		Values: map[string]interface{}{
			"payload": string(payloadBytes),
		},
	}).Result()

	if err != nil {
		// Mark event as failed in Orchestrator
		_, markErr := j.orchestratorClient.MarkEventFailed(ctx, event.ID, fmt.Sprintf("redis XADD failed: %v", err))
		if markErr != nil {
			j.logger.Warn("failed to mark event as failed after redis error",
				zap.Int("event_id", event.ID),
				zap.Error(markErr),
			)
		}
		return fmt.Errorf("redis XADD failed: %w", err)
	}

	// Mark event as replayed in Orchestrator
	replayedAt := time.Now()
	if err := j.orchestratorClient.MarkEventReplayedAt(ctx, event.ID, &replayedAt); err != nil {
		j.logger.Warn("event published but failed to mark as replayed",
			zap.Int("event_id", event.ID),
			zap.Error(err),
		)
		// Don't return error - the event was successfully published
	}

	j.logger.Debug("event replayed successfully",
		zap.Int("event_id", event.ID),
		zap.String("event_type", event.EventType),
		zap.String("channel", event.Channel),
	)

	return nil
}

// buildEnvelope creates an envelope compatible with Python EventEnvelope format
func (j *EventReplayJob) buildEnvelope(event orchestrator.FailedEvent) map[string]interface{} {
	messageID := fmt.Sprintf("replay-%d-%d", event.ID, time.Now().UnixNano())

	envelope := map[string]interface{}{
		"version":        envelopeVersion,
		"message_id":     messageID,
		"correlation_id": event.CorrelationID,
		"timestamp":      event.OriginalTimestamp.Format(time.RFC3339),
		"event_type":     event.EventType,
		"source_service": event.SourceService,
		"payload":        event.Payload,
		"metadata": map[string]interface{}{
			"replayed":            true,
			"original_created_at": event.OriginalTimestamp.Format(time.RFC3339),
			"replay_count":        event.RetryCount + 1,
		},
	}

	return envelope
}

// StubEventReplayClient is a stub implementation for testing when Orchestrator is unavailable
type StubEventReplayClient struct {
	logger *zap.Logger
}

// NewStubEventReplayClient creates a stub client
func NewStubEventReplayClient(logger *zap.Logger) *StubEventReplayClient {
	return &StubEventReplayClient{
		logger: logger,
	}
}

// GetPendingFailedEvents returns empty list (stub)
func (c *StubEventReplayClient) GetPendingFailedEvents(ctx context.Context, batchSize int) ([]orchestrator.FailedEvent, error) {
	c.logger.Debug("stub GetPendingFailedEvents called")
	return []orchestrator.FailedEvent{}, nil
}

// MarkEventReplayed does nothing (stub)
func (c *StubEventReplayClient) MarkEventReplayed(ctx context.Context, eventID int) error {
	c.logger.Debug("stub MarkEventReplayed called", zap.Int("event_id", eventID))
	return nil
}

// MarkEventReplayedAt does nothing (stub)
func (c *StubEventReplayClient) MarkEventReplayedAt(ctx context.Context, eventID int, replayedAt *time.Time) error {
	c.logger.Debug("stub MarkEventReplayedAt called", zap.Int("event_id", eventID))
	return nil
}

// MarkEventFailed does nothing (stub)
func (c *StubEventReplayClient) MarkEventFailed(ctx context.Context, eventID int, errorMessage string) (*orchestrator.FailedEventFailedResponse, error) {
	c.logger.Debug("stub MarkEventFailed called", zap.Int("event_id", eventID), zap.String("error", errorMessage))
	return &orchestrator.FailedEventFailedResponse{
		Success:    true,
		NewStatus:  "pending",
		RetryCount: 1,
	}, nil
}

// MarkEventFailedWithOptions does nothing (stub)
func (c *StubEventReplayClient) MarkEventFailedWithOptions(ctx context.Context, eventID int, errorMessage string, incrementRetry bool) (*orchestrator.FailedEventFailedResponse, error) {
	c.logger.Debug("stub MarkEventFailedWithOptions called", zap.Int("event_id", eventID))
	return &orchestrator.FailedEventFailedResponse{
		Success:    true,
		NewStatus:  "pending",
		RetryCount: 1,
	}, nil
}

// CleanupOldEvents does nothing (stub)
func (c *StubEventReplayClient) CleanupOldEvents(ctx context.Context, retentionDays int) (int, error) {
	c.logger.Debug("stub CleanupOldEvents called", zap.Int("retention_days", retentionDays))
	return 0, nil
}

// Verify StubEventReplayClient implements EventReplayClient
var _ orchestrator.EventReplayClient = (*StubEventReplayClient)(nil)

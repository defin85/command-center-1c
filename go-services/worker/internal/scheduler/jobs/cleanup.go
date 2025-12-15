package jobs

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

const (
	// CleanupStatusHistoryJobName is the unique name for the status history cleanup job
	CleanupStatusHistoryJobName = "cleanup_old_status_history"
	// CleanupReplayedEventsJobName is the unique name for the replayed events cleanup job
	CleanupReplayedEventsJobName = "cleanup_old_replayed_events"
)

// CleanupMetrics holds metrics for cleanup jobs
type CleanupMetrics struct {
	eventsDeleted   prometheus.Counter
	cleanupDuration prometheus.Histogram
	cleanupErrors   prometheus.Counter
}

// newCleanupMetrics creates and registers cleanup metrics
func newCleanupMetrics() *CleanupMetrics {
	return &CleanupMetrics{
		eventsDeleted: promauto.NewCounter(
			prometheus.CounterOpts{
				Namespace: "cc1c",
				Subsystem: "cleanup",
				Name:      "events_deleted_total",
				Help:      "Total number of old replayed/failed events deleted",
			},
		),
		cleanupDuration: promauto.NewHistogram(
			prometheus.HistogramOpts{
				Namespace: "cc1c",
				Subsystem: "cleanup",
				Name:      "duration_seconds",
				Help:      "Duration of cleanup job execution",
				Buckets:   []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60},
			},
		),
		cleanupErrors: promauto.NewCounter(
			prometheus.CounterOpts{
				Namespace: "cc1c",
				Subsystem: "cleanup",
				Name:      "errors_total",
				Help:      "Total number of cleanup job errors",
			},
		),
	}
}

var (
	cleanupMetrics     *CleanupMetrics
	cleanupMetricsOnce sync.Once
)

func getCleanupMetrics() *CleanupMetrics {
	cleanupMetricsOnce.Do(func() {
		cleanupMetrics = newCleanupMetrics()
	})
	return cleanupMetrics
}

// OrchestratorClient interface for making calls to Orchestrator Internal API
// This will be implemented when the actual client is created
type OrchestratorClient interface {
	// CleanupStatusHistory calls the internal API to cleanup old status history
	CleanupStatusHistory(ctx context.Context, retentionDays int) error
	// CleanupReplayedEvents calls the internal API to cleanup old replayed events
	CleanupReplayedEvents(ctx context.Context, retentionDays int) error
}

// HTTPOrchestratorClient is a simple HTTP client for Orchestrator Internal API
// Used for CleanupStatusHistoryJob (stub implementation for now)
type HTTPOrchestratorClient struct {
	baseURL    string
	httpClient *http.Client
	logger     *zap.Logger
}

// NewHTTPOrchestratorClient creates a new HTTP client for Orchestrator
func NewHTTPOrchestratorClient(baseURL string, logger *zap.Logger) *HTTPOrchestratorClient {
	return &HTTPOrchestratorClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		logger: logger.With(zap.String("client", "orchestrator")),
	}
}

// CleanupStatusHistory calls the internal API to cleanup old status history
// TODO: Implement when Internal API endpoint is created
func (c *HTTPOrchestratorClient) CleanupStatusHistory(ctx context.Context, retentionDays int) error {
	c.logger.Info("cleanup_status_history called (stub)",
		zap.Int("retention_days", retentionDays),
	)
	// TODO: Implement actual HTTP call when Internal API endpoint exists
	// Endpoint: POST /internal/cleanup/status-history
	// Body: { "retention_days": retentionDays }
	return nil
}

// CleanupReplayedEvents calls the internal API to cleanup old replayed events
// This method is kept for interface compatibility but CleanupReplayedEventsJob now uses EventReplayClient
func (c *HTTPOrchestratorClient) CleanupReplayedEvents(ctx context.Context, retentionDays int) error {
	c.logger.Warn("CleanupReplayedEvents called on HTTPOrchestratorClient - use EventReplayClient instead",
		zap.Int("retention_days", retentionDays),
	)
	return nil
}

// CleanupStatusHistoryJob cleans up old status history records
type CleanupStatusHistoryJob struct {
	client        OrchestratorClient
	retentionDays int
	logger        *zap.Logger
}

// NewCleanupStatusHistoryJob creates a new cleanup status history job
func NewCleanupStatusHistoryJob(client OrchestratorClient, retentionDays int, logger *zap.Logger) *CleanupStatusHistoryJob {
	return &CleanupStatusHistoryJob{
		client:        client,
		retentionDays: retentionDays,
		logger:        logger.With(zap.String("job", CleanupStatusHistoryJobName)),
	}
}

// Name returns the unique name of the job
func (j *CleanupStatusHistoryJob) Name() string {
	return CleanupStatusHistoryJobName
}

// Execute runs the cleanup job
func (j *CleanupStatusHistoryJob) Execute(ctx context.Context) error {
	j.logger.Info("starting cleanup of old status history",
		zap.Int("retention_days", j.retentionDays),
	)

	startTime := time.Now()

	if err := j.client.CleanupStatusHistory(ctx, j.retentionDays); err != nil {
		return fmt.Errorf("failed to cleanup status history: %w", err)
	}

	j.logger.Info("completed cleanup of old status history",
		zap.Duration("duration", time.Since(startTime)),
		zap.Int("retention_days", j.retentionDays),
	)

	return nil
}

// CleanupReplayedEventsJob cleans up old replayed/failed events using the real Internal API
type CleanupReplayedEventsJob struct {
	client        orchestrator.EventReplayClient
	retentionDays int
	logger        *zap.Logger
	metrics       *CleanupMetrics
}

// NewCleanupReplayedEventsJob creates a new cleanup replayed events job
// Uses orchestrator.EventReplayClient which calls the real Internal API
func NewCleanupReplayedEventsJob(client orchestrator.EventReplayClient, retentionDays int, logger *zap.Logger) *CleanupReplayedEventsJob {
	// Validate retention days (1-365)
	if retentionDays <= 0 {
		retentionDays = 7 // default
	}
	if retentionDays > 365 {
		retentionDays = 365
	}

	return &CleanupReplayedEventsJob{
		client:        client,
		retentionDays: retentionDays,
		logger:        logger.With(zap.String("job", CleanupReplayedEventsJobName)),
		metrics:       getCleanupMetrics(),
	}
}

// Name returns the unique name of the job
func (j *CleanupReplayedEventsJob) Name() string {
	return CleanupReplayedEventsJobName
}

// Execute runs the cleanup job
// Calls orchestrator.EventReplayClient.CleanupOldEvents which makes a POST to /api/v2/internal/cleanup-failed-events
func (j *CleanupReplayedEventsJob) Execute(ctx context.Context) error {
	j.logger.Info("starting cleanup of old replayed/failed events",
		zap.Int("retention_days", j.retentionDays),
	)

	startTime := time.Now()

	// Call the real Internal API via orchestrator client
	deletedCount, err := j.client.CleanupOldEvents(ctx, j.retentionDays)
	if err != nil {
		j.metrics.cleanupErrors.Inc()
		j.logger.Error("failed to cleanup old events",
			zap.Error(err),
			zap.Int("retention_days", j.retentionDays),
			zap.Duration("duration", time.Since(startTime)),
		)
		return fmt.Errorf("failed to cleanup replayed events: %w", err)
	}

	duration := time.Since(startTime)

	// Update metrics
	j.metrics.eventsDeleted.Add(float64(deletedCount))
	j.metrics.cleanupDuration.Observe(duration.Seconds())

	j.logger.Info("completed cleanup of old replayed/failed events",
		zap.Duration("duration", duration),
		zap.Int("retention_days", j.retentionDays),
		zap.Int("deleted_count", deletedCount),
	)

	return nil
}

package jobs

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.uber.org/zap"
)

const (
	// CleanupStatusHistoryJobName is the unique name for the status history cleanup job
	CleanupStatusHistoryJobName = "cleanup_old_status_history"
	// CleanupReplayedEventsJobName is the unique name for the replayed events cleanup job
	CleanupReplayedEventsJobName = "cleanup_old_replayed_events"
)

// OrchestratorClient interface for making calls to Orchestrator Internal API
// This will be implemented when the actual client is created
type OrchestratorClient interface {
	// CleanupStatusHistory calls the internal API to cleanup old status history
	CleanupStatusHistory(ctx context.Context, retentionDays int) error
	// CleanupReplayedEvents calls the internal API to cleanup old replayed events
	CleanupReplayedEvents(ctx context.Context, retentionDays int) error
}

// HTTPOrchestratorClient is a simple HTTP client for Orchestrator Internal API
// This is a placeholder implementation until the proper client is created
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
// TODO: Implement when Internal API endpoint is created
func (c *HTTPOrchestratorClient) CleanupReplayedEvents(ctx context.Context, retentionDays int) error {
	c.logger.Info("cleanup_replayed_events called (stub)",
		zap.Int("retention_days", retentionDays),
	)
	// TODO: Implement actual HTTP call when Internal API endpoint exists
	// Endpoint: POST /internal/cleanup/replayed-events
	// Body: { "retention_days": retentionDays }
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

// CleanupReplayedEventsJob cleans up old replayed events
type CleanupReplayedEventsJob struct {
	client        OrchestratorClient
	retentionDays int
	logger        *zap.Logger
}

// NewCleanupReplayedEventsJob creates a new cleanup replayed events job
func NewCleanupReplayedEventsJob(client OrchestratorClient, retentionDays int, logger *zap.Logger) *CleanupReplayedEventsJob {
	return &CleanupReplayedEventsJob{
		client:        client,
		retentionDays: retentionDays,
		logger:        logger.With(zap.String("job", CleanupReplayedEventsJobName)),
	}
}

// Name returns the unique name of the job
func (j *CleanupReplayedEventsJob) Name() string {
	return CleanupReplayedEventsJobName
}

// Execute runs the cleanup job
func (j *CleanupReplayedEventsJob) Execute(ctx context.Context) error {
	j.logger.Info("starting cleanup of old replayed events",
		zap.Int("retention_days", j.retentionDays),
	)

	startTime := time.Now()

	if err := j.client.CleanupReplayedEvents(ctx, j.retentionDays); err != nil {
		return fmt.Errorf("failed to cleanup replayed events: %w", err)
	}

	j.logger.Info("completed cleanup of old replayed events",
		zap.Duration("duration", time.Since(startTime)),
		zap.Int("retention_days", j.retentionDays),
	)

	return nil
}

package jobs

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"go.uber.org/zap"
)

const (
	// BatchServiceHealthJobName is the unique name for the batch service health check job
	BatchServiceHealthJobName = "periodic_batch_service_health"
)

// BatchServiceHealthStatus represents the health status of batch-service
type BatchServiceHealthStatus struct {
	Status    string    `json:"status"`
	Service   string    `json:"service"`
	Timestamp time.Time `json:"timestamp"`
	Error     string    `json:"error,omitempty"`
}

// BatchServiceClient interface for health checks
type BatchServiceClient interface {
	// CheckHealth performs a health check against batch-service
	CheckHealth(ctx context.Context) (*BatchServiceHealthStatus, error)
}

// HTTPBatchServiceClient is a simple HTTP client for batch-service health checks
type HTTPBatchServiceClient struct {
	baseURL    string
	httpClient *http.Client
	logger     *zap.Logger
}

// NewHTTPBatchServiceClient creates a new HTTP client for batch-service
func NewHTTPBatchServiceClient(baseURL string, logger *zap.Logger) *HTTPBatchServiceClient {
	return &HTTPBatchServiceClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
		logger: logger.With(zap.String("client", "batch-service")),
	}
}

// CheckHealth performs a health check against batch-service
func (c *HTTPBatchServiceClient) CheckHealth(ctx context.Context) (*BatchServiceHealthStatus, error) {
	url := fmt.Sprintf("%s/health", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return &BatchServiceHealthStatus{
			Status:    "unhealthy",
			Service:   "batch-service",
			Timestamp: time.Now(),
			Error:     err.Error(),
		}, nil
	}
	defer resp.Body.Close()

	var status BatchServiceHealthStatus
	if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
		// If we can't decode, check status code
		if resp.StatusCode == http.StatusOK {
			return &BatchServiceHealthStatus{
				Status:    "healthy",
				Service:   "batch-service",
				Timestamp: time.Now(),
			}, nil
		}
		return &BatchServiceHealthStatus{
			Status:    "unhealthy",
			Service:   "batch-service",
			Timestamp: time.Now(),
			Error:     fmt.Sprintf("HTTP %d", resp.StatusCode),
		}, nil
	}

	status.Timestamp = time.Now()
	return &status, nil
}

// BatchServiceHealthJob performs periodic health checks on batch-service
type BatchServiceHealthJob struct {
	client BatchServiceClient
	logger *zap.Logger

	// Callback for health status updates (optional)
	onHealthUpdate func(status *BatchServiceHealthStatus)
}

// NewBatchServiceHealthJob creates a new batch service health check job
func NewBatchServiceHealthJob(client BatchServiceClient, logger *zap.Logger) *BatchServiceHealthJob {
	return &BatchServiceHealthJob{
		client: client,
		logger: logger.With(zap.String("job", BatchServiceHealthJobName)),
	}
}

// SetOnHealthUpdate sets a callback for health status updates
func (j *BatchServiceHealthJob) SetOnHealthUpdate(callback func(status *BatchServiceHealthStatus)) {
	j.onHealthUpdate = callback
}

// Name returns the unique name of the job
func (j *BatchServiceHealthJob) Name() string {
	return BatchServiceHealthJobName
}

// Execute runs the health check job
func (j *BatchServiceHealthJob) Execute(ctx context.Context) error {
	j.logger.Debug("starting batch-service health check")

	status, err := j.client.CheckHealth(ctx)
	if err != nil {
		j.logger.Error("health check failed",
			zap.Error(err),
		)
		return fmt.Errorf("health check failed: %w", err)
	}

	// Log result
	if status.Status == "healthy" {
		j.logger.Debug("batch-service is healthy",
			zap.String("status", status.Status),
		)
	} else {
		j.logger.Warn("batch-service is unhealthy",
			zap.String("status", status.Status),
			zap.String("error", status.Error),
		)
	}

	// Call update callback if set
	if j.onHealthUpdate != nil {
		j.onHealthUpdate(status)
	}

	return nil
}

// StubBatchServiceClient is a stub implementation for testing
type StubBatchServiceClient struct {
	logger *zap.Logger
}

// NewStubBatchServiceClient creates a stub client
func NewStubBatchServiceClient(logger *zap.Logger) *StubBatchServiceClient {
	return &StubBatchServiceClient{
		logger: logger,
	}
}

// CheckHealth returns a stub healthy response
func (c *StubBatchServiceClient) CheckHealth(ctx context.Context) (*BatchServiceHealthStatus, error) {
	c.logger.Debug("stub batch-service health check called")
	return &BatchServiceHealthStatus{
		Status:    "healthy",
		Service:   "batch-service",
		Timestamp: time.Now(),
	}, nil
}

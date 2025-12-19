package jobs

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"go.uber.org/zap"
)

const (
	// DatabaseHealthJobName is the unique name for the database health check job
	DatabaseHealthJobName = "periodic_database_health_check"

	// Default configuration values
	defaultDatabaseBatchSize    = 10
	defaultDatabaseCheckTimeout = 5 * time.Second
	defaultHTTPClientTimeout    = 10 * time.Second
	odataMetadataPath           = "/$metadata"
)

// DatabaseInfo represents database information for health checks.
// This is a local type that matches the structure from orchestrator.DatabaseForHealthCheck
type DatabaseInfo struct {
	ID       string
	ODataURL string
	Name     string
}

// DatabaseHealthClient interface for database health operations.
// Note: orchestrator.Client implements this interface.
type DatabaseHealthClient interface {
	// GetDatabasesForHealthCheck returns list of active databases to check
	GetDatabasesForHealthCheck(ctx context.Context) ([]DatabaseInfo, error)
	// SetDatabaseHealthy marks a database as healthy
	SetDatabaseHealthy(ctx context.Context, databaseID string, responseTimeMs int) error
	// SetDatabaseUnhealthy marks a database as unhealthy
	SetDatabaseUnhealthy(ctx context.Context, databaseID string, errorMsg, errorCode string) error
}

// DatabaseHealthResult represents the result of a single database health check
type DatabaseHealthResult struct {
	DatabaseID     string
	Healthy        bool
	ResponseTimeMs int
	ErrorMessage   string
	ErrorCode      string
}

// DatabaseHealthJob performs periodic health checks on databases via OData
type DatabaseHealthJob struct {
	client     DatabaseHealthClient
	httpClient *http.Client
	logger     *zap.Logger
	batchSize  int
	timeout    time.Duration

	// Callback for health check completion (optional)
	onHealthCheckComplete func(stats *DatabaseHealthStats)
}

// DatabaseHealthStats holds statistics from a health check run
type DatabaseHealthStats struct {
	TotalChecked   int
	HealthyCount   int
	UnhealthyCount int
	ErrorCount     int
	DurationMs     int64
	Timestamp      time.Time
}

// DatabaseHealthJobConfig holds configuration for DatabaseHealthJob
type DatabaseHealthJobConfig struct {
	Client    DatabaseHealthClient
	Logger    *zap.Logger
	BatchSize int           // Number of databases to check in parallel (default: 10)
	Timeout   time.Duration // Timeout for each OData check (default: 5s)
}

// NewDatabaseHealthJob creates a new database health check job
func NewDatabaseHealthJob(cfg DatabaseHealthJobConfig) *DatabaseHealthJob {
	batchSize := cfg.BatchSize
	if batchSize <= 0 {
		batchSize = defaultDatabaseBatchSize
	}

	timeout := cfg.Timeout
	if timeout <= 0 {
		timeout = defaultDatabaseCheckTimeout
	}

	return &DatabaseHealthJob{
		client:    cfg.Client,
		logger:    cfg.Logger.With(zap.String("job", DatabaseHealthJobName)),
		batchSize: batchSize,
		timeout:   timeout,
		httpClient: &http.Client{
			Timeout: defaultHTTPClientTimeout,
		},
	}
}

// SetOnHealthCheckComplete sets a callback for health check completion
func (j *DatabaseHealthJob) SetOnHealthCheckComplete(callback func(stats *DatabaseHealthStats)) {
	j.onHealthCheckComplete = callback
}

// Name returns the unique name of the job
func (j *DatabaseHealthJob) Name() string {
	return DatabaseHealthJobName
}

// Execute runs the database health check job
func (j *DatabaseHealthJob) Execute(ctx context.Context) error {
	startTime := time.Now()
	j.logger.Debug("starting database health check job")

	// Step 1: Get list of databases to check
	databases, err := j.client.GetDatabasesForHealthCheck(ctx)
	if err != nil {
		j.logger.Error("failed to get databases for health check",
			zap.Error(err),
		)
		return fmt.Errorf("failed to get databases: %w", err)
	}

	if len(databases) == 0 {
		j.logger.Debug("no databases to check")
		return nil
	}

	j.logger.Info("checking database health",
		zap.Int("database_count", len(databases)),
		zap.Int("batch_size", j.batchSize),
	)

	// Step 2: Process databases in batches
	stats := &DatabaseHealthStats{
		Timestamp: startTime,
	}

	for i := 0; i < len(databases); i += j.batchSize {
		end := i + j.batchSize
		if end > len(databases) {
			end = len(databases)
		}

		batch := databases[i:end]
		results := j.checkBatch(ctx, batch)

		// Step 3: Update health status for each result
		for _, result := range results {
			stats.TotalChecked++

			if result.Healthy {
				stats.HealthyCount++
				if err := j.client.SetDatabaseHealthy(ctx, result.DatabaseID, result.ResponseTimeMs); err != nil {
					j.logger.Warn("failed to update healthy status",
						zap.String("database_id", result.DatabaseID),
						zap.Error(err),
					)
					stats.ErrorCount++
				}
			} else {
				stats.UnhealthyCount++
				if err := j.client.SetDatabaseUnhealthy(ctx, result.DatabaseID, result.ErrorMessage, result.ErrorCode); err != nil {
					j.logger.Warn("failed to update unhealthy status",
						zap.String("database_id", result.DatabaseID),
						zap.Error(err),
					)
					stats.ErrorCount++
				}
			}
		}

		// Check context cancellation between batches
		select {
		case <-ctx.Done():
			j.logger.Warn("database health check cancelled",
				zap.Int("checked", stats.TotalChecked),
				zap.Int("remaining", len(databases)-stats.TotalChecked),
			)
			return ctx.Err()
		default:
		}
	}

	stats.DurationMs = time.Since(startTime).Milliseconds()

	// Step 4: Log statistics
	j.logger.Info("database health check completed",
		zap.Int("total_checked", stats.TotalChecked),
		zap.Int("healthy", stats.HealthyCount),
		zap.Int("unhealthy", stats.UnhealthyCount),
		zap.Int("update_errors", stats.ErrorCount),
		zap.Int64("duration_ms", stats.DurationMs),
	)

	// Call completion callback if set
	if j.onHealthCheckComplete != nil {
		j.onHealthCheckComplete(stats)
	}

	return nil
}

// checkBatch performs health checks on a batch of databases in parallel
func (j *DatabaseHealthJob) checkBatch(ctx context.Context, databases []DatabaseInfo) []DatabaseHealthResult {
	results := make([]DatabaseHealthResult, len(databases))
	var wg sync.WaitGroup
	var processed int32

	for i, db := range databases {
		wg.Add(1)
		go func(idx int, database DatabaseInfo) {
			defer wg.Done()

			result := j.checkDatabase(ctx, database)
			results[idx] = result

			count := atomic.AddInt32(&processed, 1)
			j.logger.Debug("checked database",
				zap.String("database_id", database.ID),
				zap.Bool("healthy", result.Healthy),
				zap.Int("response_time_ms", result.ResponseTimeMs),
				zap.Int32("batch_progress", count),
				zap.Int("batch_size", len(databases)),
			)
		}(i, db)
	}

	wg.Wait()
	return results
}

// checkDatabase performs a single database health check via OData $metadata
func (j *DatabaseHealthJob) checkDatabase(ctx context.Context, db DatabaseInfo) DatabaseHealthResult {
	result := DatabaseHealthResult{
		DatabaseID: db.ID,
	}

	// Validate OData URL
	if db.ODataURL == "" {
		result.Healthy = false
		result.ErrorMessage = "OData URL is empty"
		result.ErrorCode = "MISSING_ODATA_URL"
		return result
	}

	// Build $metadata URL
	metadataURL := db.ODataURL + odataMetadataPath

	// Create request with timeout
	checkCtx, cancel := context.WithTimeout(ctx, j.timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(checkCtx, http.MethodGet, metadataURL, nil)
	if err != nil {
		result.Healthy = false
		result.ErrorMessage = fmt.Sprintf("failed to create request: %v", err)
		result.ErrorCode = "REQUEST_CREATE_ERROR"
		return result
	}

	// Measure response time
	startTime := time.Now()
	resp, err := j.httpClient.Do(req)
	responseTime := time.Since(startTime)

	result.ResponseTimeMs = int(responseTime.Milliseconds())

	if err != nil {
		httptrace.LogRequestErrorZap(j.logger, req, responseTime, err)
		result.Healthy = false
		result.ErrorMessage = err.Error()
		result.ErrorCode = j.categorizeError(err)
		return result
	}
	defer resp.Body.Close()

	httptrace.LogRequestZap(j.logger, req, resp.StatusCode, responseTime)

	// Check HTTP status code
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		result.Healthy = true
	} else {
		result.Healthy = false
		result.ErrorMessage = fmt.Sprintf("HTTP %d: %s", resp.StatusCode, resp.Status)
		result.ErrorCode = fmt.Sprintf("HTTP_%d", resp.StatusCode)
	}

	return result
}

// categorizeError categorizes network errors into error codes
func (j *DatabaseHealthJob) categorizeError(err error) string {
	errStr := err.Error()

	// Check for common error types
	switch {
	case contains(errStr, "connection refused"):
		return "CONNECTION_REFUSED"
	case contains(errStr, "no such host"):
		return "DNS_ERROR"
	case contains(errStr, "timeout"):
		return "TIMEOUT"
	case contains(errStr, "certificate"):
		return "TLS_ERROR"
	case contains(errStr, "connection reset"):
		return "CONNECTION_RESET"
	case contains(errStr, "context canceled"):
		return "CONTEXT_CANCELED"
	case contains(errStr, "context deadline exceeded"):
		return "TIMEOUT"
	default:
		return "NETWORK_ERROR"
	}
}

// contains checks if s contains substr (case-insensitive for common patterns)
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsLower(s, substr))
}

func containsLower(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if matchesLower(s[i:i+len(substr)], substr) {
			return true
		}
	}
	return false
}

func matchesLower(a, b string) bool {
	for i := 0; i < len(a); i++ {
		ca, cb := a[i], b[i]
		if ca >= 'A' && ca <= 'Z' {
			ca += 'a' - 'A'
		}
		if cb >= 'A' && cb <= 'Z' {
			cb += 'a' - 'A'
		}
		if ca != cb {
			return false
		}
	}
	return true
}

// StubDatabaseHealthClient is a stub implementation for testing
type StubDatabaseHealthClient struct {
	logger    *zap.Logger
	databases []DatabaseInfo
}

// NewStubDatabaseHealthClient creates a stub client with predefined databases
func NewStubDatabaseHealthClient(logger *zap.Logger, databases []DatabaseInfo) *StubDatabaseHealthClient {
	return &StubDatabaseHealthClient{
		logger:    logger,
		databases: databases,
	}
}

// GetDatabasesForHealthCheck returns the predefined list of databases
func (c *StubDatabaseHealthClient) GetDatabasesForHealthCheck(ctx context.Context) ([]DatabaseInfo, error) {
	c.logger.Debug("stub GetDatabasesForHealthCheck called",
		zap.Int("database_count", len(c.databases)),
	)
	return c.databases, nil
}

// SetDatabaseHealthy logs the healthy status update
func (c *StubDatabaseHealthClient) SetDatabaseHealthy(ctx context.Context, databaseID string, responseTimeMs int) error {
	c.logger.Debug("stub SetDatabaseHealthy called",
		zap.String("database_id", databaseID),
		zap.Int("response_time_ms", responseTimeMs),
	)
	return nil
}

// SetDatabaseUnhealthy logs the unhealthy status update
func (c *StubDatabaseHealthClient) SetDatabaseUnhealthy(ctx context.Context, databaseID string, errorMsg, errorCode string) error {
	c.logger.Debug("stub SetDatabaseUnhealthy called",
		zap.String("database_id", databaseID),
		zap.String("error_msg", errorMsg),
		zap.String("error_code", errorCode),
	)
	return nil
}

// OrchestratorDatabaseHealthAdapter adapts orchestrator.Client to DatabaseHealthClient interface.
// This adapter converts between orchestrator.DatabaseForHealthCheck and jobs.DatabaseInfo types.
type OrchestratorDatabaseHealthAdapter struct {
	client DatabaseOrchestratorClient
}

// DatabaseOrchestratorClient defines the methods we need from orchestrator.Client for database health checks
type DatabaseOrchestratorClient interface {
	GetDatabasesForHealthCheck(ctx context.Context) ([]OrchestratorDatabaseInfo, error)
	SetDatabaseHealthy(ctx context.Context, databaseID string, responseTimeMs int) error
	SetDatabaseUnhealthy(ctx context.Context, databaseID string, errorMessage, errorCode string) error
}

// OrchestratorDatabaseInfo mirrors orchestrator.DatabaseForHealthCheck
type OrchestratorDatabaseInfo struct {
	ID       string
	ODataURL string
	Name     string
}

// NewOrchestratorDatabaseHealthAdapter creates a new adapter for orchestrator.Client
func NewOrchestratorDatabaseHealthAdapter(client DatabaseOrchestratorClient) *OrchestratorDatabaseHealthAdapter {
	return &OrchestratorDatabaseHealthAdapter{client: client}
}

// GetDatabasesForHealthCheck implements DatabaseHealthClient interface
func (a *OrchestratorDatabaseHealthAdapter) GetDatabasesForHealthCheck(ctx context.Context) ([]DatabaseInfo, error) {
	orchDBs, err := a.client.GetDatabasesForHealthCheck(ctx)
	if err != nil {
		return nil, err
	}

	result := make([]DatabaseInfo, len(orchDBs))
	for i, db := range orchDBs {
		result[i] = DatabaseInfo{
			ID:       db.ID,
			ODataURL: db.ODataURL,
			Name:     db.Name,
		}
	}
	return result, nil
}

// SetDatabaseHealthy implements DatabaseHealthClient interface
func (a *OrchestratorDatabaseHealthAdapter) SetDatabaseHealthy(ctx context.Context, databaseID string, responseTimeMs int) error {
	return a.client.SetDatabaseHealthy(ctx, databaseID, responseTimeMs)
}

// SetDatabaseUnhealthy implements DatabaseHealthClient interface
func (a *OrchestratorDatabaseHealthAdapter) SetDatabaseUnhealthy(ctx context.Context, databaseID string, errorMsg, errorCode string) error {
	return a.client.SetDatabaseUnhealthy(ctx, databaseID, errorMsg, errorCode)
}

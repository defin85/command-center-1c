package jobs

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
)

const (
	// ClusterHealthJobName is the unique name for the cluster health check job
	ClusterHealthJobName = "periodic_cluster_health_check"
)

// ============================================================================
// Interfaces (for testing and dependency injection)
// ============================================================================

// RASAdapterClient interface for RAS Adapter communication
type RASAdapterClient interface {
	// ListClusters retrieves list of clusters from specified RAS server
	ListClusters(ctx context.Context, server string) ([]ClusterInfo, error)
	// Health checks RAS Adapter service health
	Health(ctx context.Context) error
}

// OrchestratorHealthClient interface for updating cluster health in Orchestrator
type OrchestratorHealthClient interface {
	// SetClusterHealthy marks a cluster as healthy with response time
	SetClusterHealthy(ctx context.Context, clusterID string, responseTimeMs int) error
	// SetClusterUnhealthy marks a cluster as unhealthy with error details
	SetClusterUnhealthy(ctx context.Context, clusterID string, errorMsg, errorCode string) error
}

// ============================================================================
// Types
// ============================================================================

// ClusterInfo represents simplified cluster information for health checks
type ClusterInfo struct {
	UUID string
	Name string
	Host string
	Port int
}

// ClusterHealthResult stores the result of a single cluster health check
type ClusterHealthResult struct {
	ClusterID      string
	ClusterName    string
	Server         string
	Healthy        bool
	ResponseTimeMs int
	ErrorMessage   string
	ErrorCode      string
}

// ============================================================================
// RAS Adapter Client Adapter
// ============================================================================

// RASClientAdapter adapts rasadapter.Client to RASAdapterClient interface
type RASClientAdapter struct {
	client *rasadapter.Client
}

// NewRASClientAdapter creates a new adapter for rasadapter.Client
func NewRASClientAdapter(client *rasadapter.Client) *RASClientAdapter {
	return &RASClientAdapter{client: client}
}

// Health checks RAS Adapter service health
func (a *RASClientAdapter) Health(ctx context.Context) error {
	_, err := a.client.Health(ctx)
	return err
}

// ListClusters retrieves list of clusters from specified RAS server
func (a *RASClientAdapter) ListClusters(ctx context.Context, server string) ([]ClusterInfo, error) {
	resp, err := a.client.ListClusters(ctx, server)
	if err != nil {
		return nil, err
	}

	// Convert []*rasadapter.Cluster to []ClusterInfo
	result := make([]ClusterInfo, len(resp.Clusters))
	for i, c := range resp.Clusters {
		result[i] = ClusterInfo{
			UUID: c.UUID,
			Name: c.Name,
			Host: c.Host,
			Port: int(c.Port),
		}
	}
	return result, nil
}

// ============================================================================
// Stub Orchestrator Health Client (for standalone testing)
// ============================================================================

// StubOrchestratorHealthClient is a stub implementation for testing
type StubOrchestratorHealthClient struct {
	logger *zap.Logger
}

// NewStubOrchestratorHealthClient creates a stub client
func NewStubOrchestratorHealthClient(logger *zap.Logger) *StubOrchestratorHealthClient {
	return &StubOrchestratorHealthClient{
		logger: logger,
	}
}

// SetClusterHealthy logs the health update (stub)
func (c *StubOrchestratorHealthClient) SetClusterHealthy(ctx context.Context, clusterID string, responseTimeMs int) error {
	c.logger.Debug("stub: set cluster healthy",
		zap.String("cluster_id", clusterID),
		zap.Int("response_time_ms", responseTimeMs),
	)
	return nil
}

// SetClusterUnhealthy logs the health update (stub)
func (c *StubOrchestratorHealthClient) SetClusterUnhealthy(ctx context.Context, clusterID string, errorMsg, errorCode string) error {
	c.logger.Debug("stub: set cluster unhealthy",
		zap.String("cluster_id", clusterID),
		zap.String("error_message", errorMsg),
		zap.String("error_code", errorCode),
	)
	return nil
}

// ============================================================================
// Cluster Health Job
// ============================================================================

// ClusterHealthJob performs periodic health checks on 1C clusters
type ClusterHealthJob struct {
	rasClient    RASAdapterClient
	orchestrator OrchestratorHealthClient
	rasServers   []string // List of RAS servers to check (from RAS_SERVERS env var)
	logger       *zap.Logger

	// Callback for health results (optional)
	onHealthResult func(result *ClusterHealthResult)
}

// NewClusterHealthJob creates a new cluster health check job
func NewClusterHealthJob(
	rasClient RASAdapterClient,
	orchestrator OrchestratorHealthClient,
	logger *zap.Logger,
) *ClusterHealthJob {
	// Parse RAS_SERVERS from environment (comma-separated)
	servers := parseRASServers(os.Getenv("RAS_SERVERS"))

	return &ClusterHealthJob{
		rasClient:    rasClient,
		orchestrator: orchestrator,
		rasServers:   servers,
		logger:       logger.With(zap.String("job", ClusterHealthJobName)),
	}
}

// NewClusterHealthJobWithServers creates a new cluster health check job with explicit servers
func NewClusterHealthJobWithServers(
	rasClient RASAdapterClient,
	orchestrator OrchestratorHealthClient,
	servers []string,
	logger *zap.Logger,
) *ClusterHealthJob {
	return &ClusterHealthJob{
		rasClient:    rasClient,
		orchestrator: orchestrator,
		rasServers:   servers,
		logger:       logger.With(zap.String("job", ClusterHealthJobName)),
	}
}

// SetOnHealthResult sets a callback for health check results
func (j *ClusterHealthJob) SetOnHealthResult(callback func(result *ClusterHealthResult)) {
	j.onHealthResult = callback
}

// Name returns the unique name of the job
func (j *ClusterHealthJob) Name() string {
	return ClusterHealthJobName
}

// Execute runs the cluster health check job
func (j *ClusterHealthJob) Execute(ctx context.Context) error {
	j.logger.Debug("starting cluster health check",
		zap.Int("ras_servers_count", len(j.rasServers)),
	)

	startTime := time.Now()

	// Check if we have any servers to check
	if len(j.rasServers) == 0 {
		j.logger.Warn("no RAS servers configured, skipping cluster health check",
			zap.String("hint", "set RAS_SERVERS environment variable (comma-separated)"),
		)
		return nil
	}

	// First, check RAS Adapter health
	if err := j.rasClient.Health(ctx); err != nil {
		j.logger.Error("RAS Adapter is unhealthy, cannot check clusters",
			zap.Error(err),
		)
		return fmt.Errorf("RAS Adapter health check failed: %w", err)
	}

	var (
		totalClusters   int
		healthyClusters int
		failedClusters  int
	)

	// Check clusters on each RAS server
	for _, server := range j.rasServers {
		results, err := j.checkServerClusters(ctx, server)
		if err != nil {
			j.logger.Error("failed to check clusters on server",
				zap.String("server", server),
				zap.Error(err),
			)
			continue
		}

		for _, result := range results {
			totalClusters++
			if result.Healthy {
				healthyClusters++
			} else {
				failedClusters++
			}

			// Call callback if set
			if j.onHealthResult != nil {
				j.onHealthResult(&result)
			}
		}
	}

	duration := time.Since(startTime)

	j.logger.Info("cluster health check completed",
		zap.Duration("duration", duration),
		zap.Int("total_clusters", totalClusters),
		zap.Int("healthy_clusters", healthyClusters),
		zap.Int("failed_clusters", failedClusters),
		zap.Int("ras_servers_checked", len(j.rasServers)),
	)

	return nil
}

// checkServerClusters checks all clusters on a specific RAS server
func (j *ClusterHealthJob) checkServerClusters(ctx context.Context, server string) ([]ClusterHealthResult, error) {
	j.logger.Debug("checking clusters on RAS server", zap.String("server", server))

	startTime := time.Now()

	// Get list of clusters from RAS server
	clusters, err := j.rasClient.ListClusters(ctx, server)
	if err != nil {
		return nil, fmt.Errorf("failed to list clusters: %w", err)
	}

	responseTimeMs := int(time.Since(startTime).Milliseconds())

	j.logger.Debug("retrieved clusters from server",
		zap.String("server", server),
		zap.Int("cluster_count", len(clusters)),
		zap.Int("response_time_ms", responseTimeMs),
	)

	results := make([]ClusterHealthResult, 0, len(clusters))

	for _, cluster := range clusters {
		result := ClusterHealthResult{
			ClusterID:      cluster.UUID,
			ClusterName:    cluster.Name,
			Server:         server,
			Healthy:        true,
			ResponseTimeMs: responseTimeMs,
		}

		// Mark cluster as healthy in Orchestrator
		if err := j.orchestrator.SetClusterHealthy(ctx, cluster.UUID, responseTimeMs); err != nil {
			j.logger.Warn("failed to update cluster health in orchestrator",
				zap.String("cluster_id", cluster.UUID),
				zap.String("cluster_name", cluster.Name),
				zap.Error(err),
			)
			// Don't fail the entire job if we can't update one cluster
		} else {
			j.logger.Debug("cluster marked as healthy",
				zap.String("cluster_id", cluster.UUID),
				zap.String("cluster_name", cluster.Name),
				zap.Int("response_time_ms", responseTimeMs),
			)
		}

		results = append(results, result)
	}

	return results, nil
}

// ============================================================================
// Helper Functions
// ============================================================================

// parseRASServers parses comma-separated list of RAS servers
func parseRASServers(serversEnv string) []string {
	if serversEnv == "" {
		return nil
	}

	servers := strings.Split(serversEnv, ",")
	result := make([]string, 0, len(servers))

	for _, s := range servers {
		s = strings.TrimSpace(s)
		if s != "" {
			result = append(result, s)
		}
	}

	return result
}

// ============================================================================
// HTTP Orchestrator Health Client
// ============================================================================

// HTTPOrchestratorHealthClient is an HTTP client for Orchestrator cluster health updates
type HTTPOrchestratorHealthClient struct {
	baseURL    string
	token      string
	httpClient *http.Client
	logger     *zap.Logger
}

// NewHTTPOrchestratorHealthClient creates a new HTTP client for Orchestrator health updates
func NewHTTPOrchestratorHealthClient(baseURL, token string, logger *zap.Logger) *HTTPOrchestratorHealthClient {
	return &HTTPOrchestratorHealthClient{
		baseURL: baseURL,
		token:   token,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
		logger: logger.With(zap.String("client", "orchestrator-health")),
	}
}

// SetClusterHealthy marks a cluster as healthy with response time
func (c *HTTPOrchestratorHealthClient) SetClusterHealthy(ctx context.Context, clusterID string, responseTimeMs int) error {
	now := time.Now()
	return c.updateHealth(ctx, clusterID, &clusterHealthRequest{
		Healthy:        true,
		LastCheckAt:    &now,
		ResponseTimeMs: responseTimeMs,
	})
}

// SetClusterUnhealthy marks a cluster as unhealthy with error details
func (c *HTTPOrchestratorHealthClient) SetClusterUnhealthy(ctx context.Context, clusterID string, errorMsg, errorCode string) error {
	now := time.Now()
	return c.updateHealth(ctx, clusterID, &clusterHealthRequest{
		Healthy:      false,
		ErrorMessage: errorMsg,
		ErrorCode:    errorCode,
		LastCheckAt:  &now,
	})
}

// clusterHealthRequest represents request to update cluster health status
type clusterHealthRequest struct {
	Healthy        bool       `json:"healthy"`
	ErrorMessage   string     `json:"error_message,omitempty"`
	ErrorCode      string     `json:"error_code,omitempty"`
	LastCheckAt    *time.Time `json:"last_check_at,omitempty"`
	ResponseTimeMs int        `json:"response_time_ms,omitempty"`
}

// updateHealth sends health update to Orchestrator
func (c *HTTPOrchestratorHealthClient) updateHealth(ctx context.Context, clusterID string, req *clusterHealthRequest) error {
	url := fmt.Sprintf("%s/api/v2/internal/update-cluster-health?cluster_id=%s", c.baseURL, clusterID)

	body, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		httpReq.Header.Set("X-Internal-Token", c.token)
	}

	start := time.Now()
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		httptrace.LogRequestErrorZap(c.logger, httpReq, time.Since(start), err)
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	httptrace.LogRequestZap(c.logger, httpReq, resp.StatusCode, time.Since(start))

	if resp.StatusCode >= 400 {
		return fmt.Errorf("health update failed: HTTP %d", resp.StatusCode)
	}

	return nil
}

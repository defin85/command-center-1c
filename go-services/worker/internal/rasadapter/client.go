package rasadapter

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"github.com/commandcenter1c/commandcenter/shared/logger"
)

const (
	// Default configuration values
	defaultTimeout     = 10 * time.Second
	defaultMaxRetries  = 3
	defaultBaseBackoff = 300 * time.Millisecond
	maxBackoff         = 5 * time.Second

	// Header names
	headerContentType = "Content-Type"
	headerRequestID   = "X-Request-ID"

	// Content types
	contentTypeJSON = "application/json"
)

// ClientConfig holds configuration for the RAS Adapter client.
type ClientConfig struct {
	BaseURL     string
	Timeout     time.Duration
	MaxRetries  int
	BaseBackoff time.Duration
}

// Client provides methods to interact with RAS Adapter API.
type Client struct {
	baseURL     string
	httpClient  *http.Client
	maxRetries  int
	baseBackoff time.Duration
}

// ClientError represents an error from the RAS Adapter API.
type ClientError struct {
	StatusCode int
	Message    string
	Code       string
	Details    string
	RequestID  string
}

func (e *ClientError) Error() string {
	if e.RequestID != "" {
		return fmt.Sprintf("ras-adapter API error: %s (code=%s, status=%d, request_id=%s)",
			e.Message, e.Code, e.StatusCode, e.RequestID)
	}
	return fmt.Sprintf("ras-adapter API error: %s (code=%s, status=%d)",
		e.Message, e.Code, e.StatusCode)
}

// IsNotFound returns true if the error is a 404 Not Found.
func (e *ClientError) IsNotFound() bool {
	return e.StatusCode == http.StatusNotFound
}

// IsBadRequest returns true if the error is a 400 Bad Request.
func (e *ClientError) IsBadRequest() bool {
	return e.StatusCode == http.StatusBadRequest
}

// IsRetryable returns true if the error is retryable (5xx or connection errors).
func (e *ClientError) IsRetryable() bool {
	return e.StatusCode >= 500 || e.StatusCode == http.StatusTooManyRequests
}

// NewClient creates a new RAS Adapter client with configuration from environment.
func NewClient() (*Client, error) {
	baseURL := os.Getenv("RAS_ADAPTER_URL")
	if baseURL == "" {
		baseURL = "http://localhost:8188"
	}

	timeout := defaultTimeout
	if timeoutStr := os.Getenv("RAS_ADAPTER_CLIENT_TIMEOUT"); timeoutStr != "" {
		if parsed, err := time.ParseDuration(timeoutStr); err == nil {
			timeout = parsed
		}
	}

	return NewClientWithConfig(ClientConfig{
		BaseURL:     baseURL,
		Timeout:     timeout,
		MaxRetries:  defaultMaxRetries,
		BaseBackoff: defaultBaseBackoff,
	})
}

// NewClientWithConfig creates a new RAS Adapter client with explicit configuration.
func NewClientWithConfig(cfg ClientConfig) (*Client, error) {
	if cfg.BaseURL == "" {
		return nil, fmt.Errorf("base URL is required")
	}

	timeout := cfg.Timeout
	if timeout == 0 {
		timeout = defaultTimeout
	}

	maxRetries := cfg.MaxRetries
	if maxRetries == 0 {
		maxRetries = defaultMaxRetries
	}

	baseBackoff := cfg.BaseBackoff
	if baseBackoff == 0 {
		baseBackoff = defaultBaseBackoff
	}

	return &Client{
		baseURL: cfg.BaseURL,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		maxRetries:  maxRetries,
		baseBackoff: baseBackoff,
	}, nil
}

// doRequest performs an HTTP request with retry logic and error handling.
func (c *Client) doRequest(ctx context.Context, method, path string, body interface{}, result interface{}) error {
	reqURL := c.baseURL + path

	var bodyReader io.Reader
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("failed to marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(bodyBytes)
	}

	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// Calculate backoff with exponential increase
			backoff := c.baseBackoff * time.Duration(1<<uint(attempt-1))
			if backoff > maxBackoff {
				backoff = maxBackoff
			}

			logger.Debugf("ras-adapter client: retrying request (attempt %d/%d, backoff %v)",
				attempt+1, c.maxRetries+1, backoff)

			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}

			// Reset body reader for retry
			if body != nil {
				bodyBytes, _ := json.Marshal(body)
				bodyReader = bytes.NewReader(bodyBytes)
			}
		}

		req, err := http.NewRequestWithContext(ctx, method, reqURL, bodyReader)
		if err != nil {
			return fmt.Errorf("failed to create request: %w", err)
		}

		req.Header.Set(headerContentType, contentTypeJSON)

		attemptStart := time.Now()
		resp, err := c.httpClient.Do(req)
		if err != nil {
			elapsed := time.Since(attemptStart)
			httptrace.LogError(logger.GetLogger(), method, path, elapsed, err)
			lastErr = fmt.Errorf("request failed: %w", err)
			logger.Warnf("ras-adapter client: request error (attempt %d/%d): %v",
				attempt+1, c.maxRetries+1, err)
			logger.Debugf("ras-adapter client: request timing (%s %s, attempt=%d/%d, elapsed_ms=%d, status=error)",
				method, path, attempt+1, c.maxRetries+1, elapsed.Milliseconds())
			if elapsed >= 2*time.Second {
				logger.Warnf("ras-adapter client: slow request (%s %s, attempt=%d/%d, elapsed_ms=%d, status=error)",
					method, path, attempt+1, c.maxRetries+1, elapsed.Milliseconds())
			}
			continue
		}

		// Read response body and close immediately (no defer in loop!)
		respBody, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			elapsed := time.Since(attemptStart)
			httptrace.LogResponse(logger.GetLogger(), method, path, resp.StatusCode, elapsed)
			lastErr = fmt.Errorf("failed to read response body: %w", err)
			logger.Debugf("ras-adapter client: request timing (%s %s, attempt=%d/%d, elapsed_ms=%d, status=%d)",
				method, path, attempt+1, c.maxRetries+1, elapsed.Milliseconds(), resp.StatusCode)
			continue
		}

		elapsed := time.Since(attemptStart)
		httptrace.LogResponse(logger.GetLogger(), method, path, resp.StatusCode, elapsed)
		logger.Debugf("ras-adapter client: request timing (%s %s, attempt=%d/%d, elapsed_ms=%d, status=%d, request_id=%s)",
			method, path, attempt+1, c.maxRetries+1, elapsed.Milliseconds(), resp.StatusCode, resp.Header.Get(headerRequestID))
		if elapsed >= 2*time.Second {
			logger.Infof("ras-adapter client: slow request (%s %s, elapsed_ms=%d, status=%d)",
				method, path, elapsed.Milliseconds(), resp.StatusCode)
		}

		// Handle error responses
		if resp.StatusCode >= 400 {
			apiErr := c.parseErrorResponse(resp, respBody)

			// Non-retryable errors - return immediately
			if !apiErr.IsRetryable() {
				return apiErr
			}

			lastErr = apiErr
			logger.Warnf("ras-adapter client: retryable error (attempt %d/%d): %v",
				attempt+1, c.maxRetries+1, apiErr)
			continue
		}

		// Parse successful response
		if result != nil && len(respBody) > 0 {
			if err := json.Unmarshal(respBody, result); err != nil {
				return fmt.Errorf("failed to decode response: %w", err)
			}
		}

		logger.Debugf("ras-adapter client: request successful (%s %s, status=%d)",
			method, path, resp.StatusCode)
		return nil
	}

	return fmt.Errorf("all retry attempts failed: %w", lastErr)
}

// parseErrorResponse parses error response from API.
func (c *Client) parseErrorResponse(resp *http.Response, body []byte) *ClientError {
	var apiErr ErrorResponse
	if err := json.Unmarshal(body, &apiErr); err != nil {
		// If we can't parse the error response, create a generic one
		return &ClientError{
			StatusCode: resp.StatusCode,
			Message:    string(body),
			Code:       "UNKNOWN",
			RequestID:  resp.Header.Get(headerRequestID),
		}
	}

	return &ClientError{
		StatusCode: resp.StatusCode,
		Message:    apiErr.Error,
		Code:       apiErr.Code,
		Details:    apiErr.Details,
		RequestID:  resp.Header.Get(headerRequestID),
	}
}

// get performs a GET request.
func (c *Client) get(ctx context.Context, path string, result interface{}) error {
	return c.doRequest(ctx, http.MethodGet, path, nil, result)
}

// post performs a POST request.
func (c *Client) post(ctx context.Context, path string, body interface{}, result interface{}) error {
	return c.doRequest(ctx, http.MethodPost, path, body, result)
}

// BaseURL returns the configured base URL.
func (c *Client) BaseURL() string {
	return c.baseURL
}

// ============================================================================
// Health API
// ============================================================================

// Health checks RAS Adapter service health.
func (c *Client) Health(ctx context.Context) (*HealthResponse, error) {
	var resp HealthResponse
	if err := c.get(ctx, "/health", &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ============================================================================
// Cluster API
// ============================================================================

// ListClusters retrieves all clusters from specified RAS server.
func (c *Client) ListClusters(ctx context.Context, server string) (*ClustersResponse, error) {
	path := fmt.Sprintf("/api/v2/list-clusters?server=%s", url.QueryEscape(server))

	var resp ClustersResponse
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// GetCluster retrieves specific cluster by ID from RAS server.
func (c *Client) GetCluster(ctx context.Context, server, clusterID string) (*ClusterResponse, error) {
	path := fmt.Sprintf("/api/v2/get-cluster?server=%s&cluster_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID))

	var resp ClusterResponse
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ============================================================================
// Infobase API
// ============================================================================

// ListInfobases retrieves all infobases from specified cluster.
func (c *Client) ListInfobases(ctx context.Context, server, clusterID string) (*InfobasesResponse, error) {
	path := fmt.Sprintf("/api/v2/list-infobases?server=%s&cluster_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID))

	var resp InfobasesResponse
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// GetInfobase retrieves specific infobase by ID.
func (c *Client) GetInfobase(ctx context.Context, server, clusterID, infobaseID string) (*InfobaseResponse, error) {
	path := fmt.Sprintf("/api/v2/get-infobase?server=%s&cluster_id=%s&infobase_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp InfobaseResponse
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// LockInfobase locks an infobase (denies new sessions and scheduled jobs).
func (c *Client) LockInfobase(ctx context.Context, server, clusterID, infobaseID string, req *LockInfobaseRequest) (*SuccessResponse, error) {
	path := fmt.Sprintf("/api/v2/lock-infobase?server=%s&cluster_id=%s&infobase_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SuccessResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// UnlockInfobase unlocks an infobase (allows sessions and scheduled jobs).
func (c *Client) UnlockInfobase(ctx context.Context, server, clusterID, infobaseID string, req *UnlockInfobaseRequest) (*SuccessResponse, error) {
	path := fmt.Sprintf("/api/v2/unlock-infobase?server=%s&cluster_id=%s&infobase_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SuccessResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ============================================================================
// Session API
// ============================================================================

// ListSessions retrieves all sessions for specified infobase.
func (c *Client) ListSessions(ctx context.Context, server, clusterID, infobaseID string) (*SessionsResponse, error) {
	path := fmt.Sprintf("/api/v2/list-sessions?server=%s&cluster_id=%s&infobase_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SessionsResponse
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// TerminateSessions terminates multiple sessions.
func (c *Client) TerminateSessions(ctx context.Context, server, clusterID string, sessionIDs []string) (*TerminateSessionsResponse, error) {
	path := fmt.Sprintf("/api/v2/terminate-sessions?server=%s&cluster_id=%s",
		url.QueryEscape(server), url.QueryEscape(clusterID))

	req := TerminateSessionsRequest{SessionIDs: sessionIDs}

	var resp TerminateSessionsResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ============================================================================
// Session Blocking API (Phase 4 - Context Menu Actions)
// ============================================================================

// BlockSessions blocks new user sessions for an infobase.
// This prevents new connections during maintenance windows.
func (c *Client) BlockSessions(ctx context.Context, clusterID, infobaseID string, req *BlockSessionsRequest) (*SuccessResponse, error) {
	path := fmt.Sprintf("/api/v2/block-sessions?cluster_id=%s&infobase_id=%s",
		url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SuccessResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// UnblockSessions unblocks user sessions for an infobase.
// This allows new connections after maintenance windows.
func (c *Client) UnblockSessions(ctx context.Context, clusterID, infobaseID string, req *UnblockSessionsRequest) (*SuccessResponse, error) {
	path := fmt.Sprintf("/api/v2/unblock-sessions?cluster_id=%s&infobase_id=%s",
		url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SuccessResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// TerminateAllSessions terminates all sessions for an infobase.
// This is used for maintenance operations.
func (c *Client) TerminateAllSessions(ctx context.Context, clusterID, infobaseID string) (*TerminateSessionsResponse, error) {
	path := fmt.Sprintf("/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s",
		url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	// Empty body terminates ALL sessions
	var resp TerminateSessionsResponse
	if err := c.post(ctx, path, nil, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// ============================================================================
// Simplified Infobase Lock/Unlock API (without server parameter)
// These methods use cluster_id and infobase_id only, for use in worker operations.
// ============================================================================

// LockScheduledJobs locks scheduled jobs for an infobase (sets ScheduledJobsDeny = true).
func (c *Client) LockScheduledJobs(ctx context.Context, clusterID, infobaseID string, req *LockInfobaseRequest) (*SuccessResponse, error) {
	path := fmt.Sprintf("/api/v2/lock-infobase?cluster_id=%s&infobase_id=%s",
		url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SuccessResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// UnlockScheduledJobs unlocks scheduled jobs for an infobase (sets ScheduledJobsDeny = false).
func (c *Client) UnlockScheduledJobs(ctx context.Context, clusterID, infobaseID string, req *UnlockInfobaseRequest) (*SuccessResponse, error) {
	path := fmt.Sprintf("/api/v2/unlock-infobase?cluster_id=%s&infobase_id=%s",
		url.QueryEscape(clusterID), url.QueryEscape(infobaseID))

	var resp SuccessResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

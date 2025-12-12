package odata

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"go.uber.org/zap"
)

// Client executes OData operations.
// Unlike worker's client, credentials are passed with each request.
type Client struct {
	pool       *Pool
	maxRetries int
	retryWait  time.Duration
	logger     *zap.Logger
}

// ClientConfig contains client configuration.
type ClientConfig struct {
	Pool          *Pool
	MaxRetries    int
	RetryWaitTime time.Duration
	Logger        *zap.Logger
}

// QueryResponse represents query result from OData.
type QueryResponse struct {
	Value []map[string]interface{} `json:"value"`
}

// NewClient creates a new OData client.
func NewClient(config ClientConfig) *Client {
	// Set defaults
	if config.MaxRetries <= 0 {
		config.MaxRetries = 3
	}
	if config.RetryWaitTime <= 0 {
		config.RetryWaitTime = 500 * time.Millisecond
	}
	if config.Logger == nil {
		config.Logger = zap.NewNop()
	}

	return &Client{
		pool:       config.Pool,
		maxRetries: config.MaxRetries,
		retryWait:  config.RetryWaitTime,
		logger:     config.Logger,
	}
}

// Query executes SELECT query (GET).
func (c *Client) Query(ctx context.Context, creds sharedodata.ODataCredentials, entity string, query *sharedodata.QueryParams) ([]map[string]interface{}, error) {
	baseURL := BuildEntityURL(creds.BaseURL, entity, "")

	// Build query parameters
	queryString := BuildQueryString(query)
	fullURL := baseURL
	if queryString != "" {
		fullURL += "?" + queryString
	}

	c.logger.Debug("executing OData query",
		zap.String("entity", entity),
		zap.String("url", fullURL),
	)

	var response QueryResponse
	err := c.doWithRetry(ctx, creds, "GET", fullURL, nil, &response)
	if err != nil {
		return nil, err
	}

	return response.Value, nil
}

// Create creates entity (POST).
func (c *Client) Create(ctx context.Context, creds sharedodata.ODataCredentials, entity string, data map[string]interface{}) (map[string]interface{}, error) {
	url := BuildEntityURL(creds.BaseURL, entity, "")

	// Marshal data to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal data: %w", err)
	}

	c.logger.Debug("executing OData create",
		zap.String("entity", entity),
		zap.String("url", url),
	)

	// Make request with retry
	var result map[string]interface{}
	err = c.doWithRetry(ctx, creds, "POST", url, jsonData, &result)
	if err != nil {
		return nil, err
	}

	return result, nil
}

// Update updates entity (PATCH).
func (c *Client) Update(ctx context.Context, creds sharedodata.ODataCredentials, entity string, entityID string, data map[string]interface{}) error {
	url := BuildEntityURL(creds.BaseURL, entity, entityID)

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	c.logger.Debug("executing OData update",
		zap.String("entity", entity),
		zap.String("entityID", entityID),
		zap.String("url", url),
	)

	// PATCH may return 204 No Content (no response body)
	err = c.doWithRetry(ctx, creds, "PATCH", url, jsonData, nil)
	return err
}

// Delete deletes entity (DELETE).
func (c *Client) Delete(ctx context.Context, creds sharedodata.ODataCredentials, entity string, entityID string) error {
	url := BuildEntityURL(creds.BaseURL, entity, entityID)

	c.logger.Debug("executing OData delete",
		zap.String("entity", entity),
		zap.String("entityID", entityID),
		zap.String("url", url),
	)

	// DELETE usually returns 204 No Content
	err := c.doWithRetry(ctx, creds, "DELETE", url, nil, nil)
	return err
}

// ExecuteBatch executes batch operation (POST /$batch).
// Uses multipart/mixed format with changeset for atomic transaction.
func (c *Client) ExecuteBatch(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
	// Build batch URL
	batchURL := creds.BaseURL + "/$batch"

	// Build multipart body
	body, contentType, err := buildBatchBody(creds.BaseURL, items)
	if err != nil {
		return nil, fmt.Errorf("failed to build batch body: %w", err)
	}

	c.logger.Debug("executing OData batch",
		zap.String("url", batchURL),
		zap.Int("items", len(items)),
	)

	// Execute request
	httpClient := c.getHTTPClient(creds.BaseURL)

	req, err := http.NewRequestWithContext(ctx, "POST", batchURL, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.SetBasicAuth(creds.Username, creds.Password)
	req.Header.Set("Content-Type", contentType)
	req.Header.Set("Accept", "multipart/mixed")

	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, &ODataError{
			Code:        ErrorCategoryNetwork,
			Message:     fmt.Sprintf("batch request failed: %v", err),
			StatusCode:  0,
			IsTransient: true,
		}
	}
	defer resp.Body.Close()

	// Read response body with size limit to prevent memory exhaustion
	const maxBatchResponseSize = 50 * 1024 * 1024 // 50 MB
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, maxBatchResponseSize))
	if err != nil {
		return nil, fmt.Errorf("failed to read batch response: %w", err)
	}

	// Check for HTTP error
	if resp.StatusCode >= 400 {
		return nil, &ODataError{
			Code:        ErrorCategoryHTTP,
			Message:     fmt.Sprintf("batch request failed with status %d: %s", resp.StatusCode, string(respBody)),
			StatusCode:  resp.StatusCode,
			IsTransient: resp.StatusCode >= 500,
		}
	}

	// Parse multipart response
	result, err := parseBatchResponse(respBody, resp.Header.Get("Content-Type"), items)
	if err != nil {
		return nil, fmt.Errorf("failed to parse batch response: %w", err)
	}

	return result, nil
}

// HealthCheck checks if OData endpoint is accessible.
func (c *Client) HealthCheck(ctx context.Context, creds sharedodata.ODataCredentials) error {
	httpClient := c.getHTTPClient(creds.BaseURL)

	req, err := http.NewRequestWithContext(ctx, "GET", creds.BaseURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.SetBasicAuth(creds.Username, creds.Password)
	req.Header.Set("Accept", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return ParseODataError(resp)
	}

	return nil
}

// doWithRetry executes HTTP request with retry logic.
func (c *Client) doWithRetry(ctx context.Context, creds sharedodata.ODataCredentials, method, url string, body []byte, result interface{}) error {
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// Wait before retry (exponential backoff)
			waitTime := c.retryWait * time.Duration(1<<uint(attempt-1))

			c.logger.Debug("retrying request",
				zap.Int("attempt", attempt),
				zap.Duration("wait", waitTime),
				zap.Error(lastErr),
			)

			select {
			case <-time.After(waitTime):
			case <-ctx.Done():
				return ctx.Err()
			}
		}

		err := c.doRequest(ctx, creds, method, url, body, result)
		if err == nil {
			return nil // Success
		}

		// Check if error is transient
		if !IsTransient(err) {
			return err // Don't retry non-transient errors
		}

		lastErr = err
	}

	return fmt.Errorf("max retries exceeded: %w", lastErr)
}

// doRequest executes single HTTP request.
func (c *Client) doRequest(ctx context.Context, creds sharedodata.ODataCredentials, method, url string, body []byte, result interface{}) error {
	httpClient := c.getHTTPClient(creds.BaseURL)

	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.SetBasicAuth(creds.Username, creds.Password)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json;odata=nometadata")
	}

	// Execute request
	resp, err := httpClient.Do(req)
	if err != nil {
		return &ODataError{
			Code:        ErrorCategoryNetwork,
			Message:     fmt.Sprintf("HTTP request failed: %v", err),
			StatusCode:  0,
			IsTransient: true,
		}
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode >= 400 {
		return ParseODataError(resp)
	}

	// Parse response body if result is provided
	if result != nil && resp.StatusCode != 204 { // 204 = No Content
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			return fmt.Errorf("failed to read response: %w", err)
		}

		if err := json.Unmarshal(respBody, result); err != nil {
			return fmt.Errorf("failed to parse response: %w", err)
		}
	}

	return nil
}

// getHTTPClient returns HTTP client for the given baseURL.
// Uses pooled transport for connection reuse.
func (c *Client) getHTTPClient(baseURL string) *http.Client {
	transport := c.pool.GetTransport(baseURL)
	return &http.Client{
		Transport: transport,
		Timeout:   c.pool.timeout,
	}
}

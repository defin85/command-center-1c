// go-services/worker/internal/odata/client.go
package odata

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

// Client is a lightweight HTTP client for 1C OData API
type Client struct {
	baseURL    string
	auth       Auth
	httpClient *http.Client
	maxRetries int
	retryWait  time.Duration
}

// NewClient creates a new OData client
func NewClient(config ClientConfig) *Client {
	// Set defaults
	if config.Timeout == 0 {
		config.Timeout = 30 * time.Second
	}
	if config.MaxRetries == 0 {
		config.MaxRetries = 3
	}
	if config.RetryWaitTime == 0 {
		config.RetryWaitTime = 500 * time.Millisecond
	}

	return &Client{
		baseURL: config.BaseURL,
		auth:    config.Auth,
		httpClient: &http.Client{
			Timeout: config.Timeout,
		},
		maxRetries: config.MaxRetries,
		retryWait:  config.RetryWaitTime,
	}
}

// HealthCheck checks if OData endpoint is accessible
func (c *Client) HealthCheck(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, "GET", c.baseURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	c.setAuth(req)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return ParseODataError(resp)
	}

	return nil
}

// Create creates a new entity (POST)
func (c *Client) Create(ctx context.Context, entity string, data map[string]interface{}) (map[string]interface{}, error) {
	url := BuildEntityURL(c.baseURL, entity, "")

	// Marshal data to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal data: %w", err)
	}

	// Make request with retry
	var result map[string]interface{}
	err = c.doWithRetry(ctx, "POST", url, jsonData, &result)
	if err != nil {
		return nil, err
	}

	return result, nil
}

// Update updates an existing entity (PATCH)
func (c *Client) Update(ctx context.Context, entity string, id string, data map[string]interface{}) error {
	url := BuildEntityURL(c.baseURL, entity, id)

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	// PATCH может вернуть 204 No Content (no response body)
	err = c.doWithRetry(ctx, "PATCH", url, jsonData, nil)
	return err
}

// Delete deletes an entity (DELETE)
func (c *Client) Delete(ctx context.Context, entity string, id string) error {
	url := BuildEntityURL(c.baseURL, entity, id)

	// DELETE обычно возвращает 204 No Content
	err := c.doWithRetry(ctx, "DELETE", url, nil, nil)
	return err
}

// Query queries entities with OData filters (GET)
func (c *Client) Query(ctx context.Context, req QueryRequest) ([]map[string]interface{}, error) {
	baseURL := BuildEntityURL(c.baseURL, req.Entity, "")

	// Build query parameters
	params := url.Values{}
	if req.Filter != "" {
		params.Set("$filter", req.Filter)
	}
	if len(req.Select) > 0 {
		// Join select fields
		selectStr := ""
		for i, field := range req.Select {
			if i > 0 {
				selectStr += ","
			}
			selectStr += field
		}
		params.Set("$select", selectStr)
	}
	if req.Top > 0 {
		params.Set("$top", fmt.Sprintf("%d", req.Top))
	}
	if req.Skip > 0 {
		params.Set("$skip", fmt.Sprintf("%d", req.Skip))
	}
	if req.OrderBy != "" {
		params.Set("$orderby", req.OrderBy)
	}
	if req.Expand != "" {
		params.Set("$expand", req.Expand)
	}

	// Append query params
	fullURL := baseURL
	if len(params) > 0 {
		fullURL += "?" + params.Encode()
	}

	var response QueryResponse
	err := c.doWithRetry(ctx, "GET", fullURL, nil, &response)
	if err != nil {
		return nil, err
	}

	return response.Value, nil
}

// ExecuteBatch executes batch operation (POST /$batch).
// Uses multipart/mixed format with changeset for atomic transaction.
func (c *Client) ExecuteBatch(ctx context.Context, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
	batchURL := c.baseURL + "/$batch"

	body, contentType, err := buildBatchBody(c.baseURL, items)
	if err != nil {
		return nil, fmt.Errorf("failed to build batch body: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", batchURL, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.SetBasicAuth(c.auth.Username, c.auth.Password)
	req.Header.Set("Content-Type", contentType)
	req.Header.Set("Accept", "multipart/mixed")

	start := time.Now()
	resp, err := c.httpClient.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		return nil, &ODataError{
			Code:        ErrorCategoryNetwork,
			Message:     fmt.Sprintf("batch request failed: %v", err),
			StatusCode:  0,
			IsTransient: true,
		}
	}
	defer resp.Body.Close()

	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	respBody, err := io.ReadAll(io.LimitReader(resp.Body, maxBatchResponseSize))
	if err != nil {
		return nil, fmt.Errorf("failed to read batch response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, &ODataError{
			Code:        categorizeByStatus(resp.StatusCode),
			Message:     fmt.Sprintf("batch request failed with status %d: %s", resp.StatusCode, string(respBody)),
			StatusCode:  resp.StatusCode,
			IsTransient: isTransientStatus(resp.StatusCode),
		}
	}

	result, err := parseBatchResponse(respBody, resp.Header.Get("Content-Type"), items)
	if err != nil {
		return nil, fmt.Errorf("failed to parse batch response: %w", err)
	}

	return result, nil
}

// doWithRetry executes HTTP request with retry logic
func (c *Client) doWithRetry(ctx context.Context, method, url string, body []byte, result interface{}) error {
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		attemptNumber := attempt + 1
		resendAttempt := attemptNumber > 1
		if resendAttempt {
			recordTransportResendAttempt(ctx, method)
		}

		attemptStart := time.Now()
		statusCode, err := c.doRequest(ctx, method, url, body, result)
		duration := time.Since(attemptStart)
		if err == nil {
			statusClass := statusClassFromStatusCode(statusCode)
			recordTransportLatency(ctx, method, duration, statusClass, resendAttempt)
			emitTransportTrace(ctx, "external.odata.transport.request.completed", map[string]interface{}{
				"method":         strings.ToUpper(method),
				"attempt":        attemptNumber,
				"resend_attempt": resendAttempt,
				"status_code":    statusCode,
				"status_class":   statusClass,
				"duration_ms":    duration.Milliseconds(),
			})
			return nil // Success
		}

		normalized := NormalizeError(err)
		if normalized.StatusCode <= 0 {
			normalized.StatusCode = statusCode
		}
		recordTransportLatency(ctx, method, duration, normalized.StatusClass(), resendAttempt)
		recordTransportError(ctx, method, normalized)
		emitTransportTrace(ctx, "external.odata.transport.request.failed", map[string]interface{}{
			"method":         strings.ToUpper(method),
			"attempt":        attemptNumber,
			"resend_attempt": resendAttempt,
			"duration_ms":    duration.Milliseconds(),
			"error_code":     normalized.Code,
			"error_class":    normalized.Class,
			"status_class":   normalized.StatusClass(),
			"retryable":      normalized.Retryable,
			"error":          normalized.Message,
		})

		// Check if error is transient
		if !IsTransient(err) {
			return err // Don't retry non-transient errors
		}

		lastErr = err
		if attempt == c.maxRetries {
			break
		}

		waitTime := ComputeExponentialBackoffWithJitter(c.retryWait, attemptNumber)
		recordTransportRetry(ctx, method, normalized)
		emitTransportTrace(ctx, "external.odata.transport.retry.scheduled", map[string]interface{}{
			"method":         strings.ToUpper(method),
			"attempt":        attemptNumber,
			"next_attempt":   attemptNumber + 1,
			"resend_attempt": true,
			"backoff_ms":     waitTime.Milliseconds(),
			"error_code":     normalized.Code,
			"error_class":    normalized.Class,
			"status_class":   normalized.StatusClass(),
			"retryable":      normalized.Retryable,
		})
		select {
		case <-time.After(waitTime):
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return fmt.Errorf("max retries exceeded: %w", lastErr)
}

// doRequest executes single HTTP request
func (c *Client) doRequest(ctx context.Context, method, url string, body []byte, result interface{}) (int, error) {
	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
	if err != nil {
		return 0, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	c.setAuth(req)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json;odata=nometadata")
	}

	// Execute request
	start := time.Now()
	resp, err := c.httpClient.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		return 0, &ODataError{
			Code:        ErrorCategoryNetwork,
			Message:     fmt.Sprintf("HTTP request failed: %v", err),
			StatusCode:  0,
			IsTransient: true,
		}
	}
	defer resp.Body.Close()

	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	// Check status code
	if resp.StatusCode >= 400 {
		return resp.StatusCode, ParseODataError(resp)
	}

	// Parse response body if result is provided
	if result != nil && resp.StatusCode != 204 { // 204 = No Content
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			return resp.StatusCode, fmt.Errorf("failed to read response: %w", err)
		}

		if err := json.Unmarshal(respBody, result); err != nil {
			return resp.StatusCode, fmt.Errorf("failed to parse response: %w", err)
		}
	}

	return resp.StatusCode, nil
}

// setAuth sets Basic Auth header
func (c *Client) setAuth(req *http.Request) {
	req.SetBasicAuth(c.auth.Username, c.auth.Password)
}

// Close closes the HTTP client (cleanup connections)
func (c *Client) Close() {
	c.httpClient.CloseIdleConnections()
}

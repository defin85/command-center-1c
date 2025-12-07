package orchestrator

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
)

const (
	// Default configuration values
	defaultTimeout     = 30 * time.Second
	defaultMaxRetries  = 3
	defaultBaseBackoff = 500 * time.Millisecond
	maxBackoff         = 10 * time.Second

	// Header names
	headerInternalToken = "X-Internal-Token"
	headerContentType   = "Content-Type"
	headerRequestID     = "X-Request-ID"

	// Content types
	contentTypeJSON = "application/json"
)

// ClientConfig holds configuration for the Orchestrator client.
type ClientConfig struct {
	BaseURL     string
	Token       string
	Timeout     time.Duration
	MaxRetries  int
	BaseBackoff time.Duration
}

// Client provides methods to interact with Django Orchestrator Internal API.
type Client struct {
	baseURL     string
	token       string
	httpClient  *http.Client
	maxRetries  int
	baseBackoff time.Duration
}

// ClientError represents an error from the Orchestrator API.
type ClientError struct {
	StatusCode int
	Message    string
	Code       string
	RequestID  string
}

func (e *ClientError) Error() string {
	if e.RequestID != "" {
		return fmt.Sprintf("orchestrator API error: %s (code=%s, status=%d, request_id=%s)",
			e.Message, e.Code, e.StatusCode, e.RequestID)
	}
	return fmt.Sprintf("orchestrator API error: %s (code=%s, status=%d)",
		e.Message, e.Code, e.StatusCode)
}

// IsNotFound returns true if the error is a 404 Not Found.
func (e *ClientError) IsNotFound() bool {
	return e.StatusCode == http.StatusNotFound
}

// IsUnauthorized returns true if the error is a 401 Unauthorized.
func (e *ClientError) IsUnauthorized() bool {
	return e.StatusCode == http.StatusUnauthorized
}

// IsRetryable returns true if the error is retryable (5xx or connection errors).
func (e *ClientError) IsRetryable() bool {
	return e.StatusCode >= 500 || e.StatusCode == http.StatusTooManyRequests
}

// NewClient creates a new Orchestrator client with configuration from environment.
func NewClient() (*Client, error) {
	baseURL := os.Getenv("ORCHESTRATOR_INTERNAL_URL")
	if baseURL == "" {
		baseURL = os.Getenv("ORCHESTRATOR_URL")
	}
	if baseURL == "" {
		baseURL = "http://localhost:8200"
	}

	token := os.Getenv("INTERNAL_API_TOKEN")
	if token == "" {
		return nil, fmt.Errorf("INTERNAL_API_TOKEN environment variable is required")
	}

	timeout := defaultTimeout
	if timeoutStr := os.Getenv("ORCHESTRATOR_CLIENT_TIMEOUT"); timeoutStr != "" {
		if parsed, err := time.ParseDuration(timeoutStr); err == nil {
			timeout = parsed
		}
	}

	return NewClientWithConfig(ClientConfig{
		BaseURL:     baseURL,
		Token:       token,
		Timeout:     timeout,
		MaxRetries:  defaultMaxRetries,
		BaseBackoff: defaultBaseBackoff,
	})
}

// NewClientWithConfig creates a new Orchestrator client with explicit configuration.
func NewClientWithConfig(cfg ClientConfig) (*Client, error) {
	if cfg.BaseURL == "" {
		return nil, fmt.Errorf("base URL is required")
	}
	if cfg.Token == "" {
		return nil, fmt.Errorf("token is required")
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
		token:   cfg.Token,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		maxRetries:  maxRetries,
		baseBackoff: baseBackoff,
	}, nil
}

// doRequest performs an HTTP request with retry logic and error handling.
func (c *Client) doRequest(ctx context.Context, method, path string, body interface{}, result interface{}) error {
	url := c.baseURL + path

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

			logger.Debugf("orchestrator client: retrying request (attempt %d/%d, backoff %v)",
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

		req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
		if err != nil {
			return fmt.Errorf("failed to create request: %w", err)
		}

		req.Header.Set(headerInternalToken, c.token)
		req.Header.Set(headerContentType, contentTypeJSON)

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("request failed: %w", err)
			logger.Warnf("orchestrator client: request error (attempt %d/%d): %v",
				attempt+1, c.maxRetries+1, err)
			continue
		}

		defer resp.Body.Close()

		// Read response body
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = fmt.Errorf("failed to read response body: %w", err)
			continue
		}

		// Handle error responses
		if resp.StatusCode >= 400 {
			apiErr := c.parseErrorResponse(resp, respBody)

			// Non-retryable errors - return immediately
			if !apiErr.IsRetryable() {
				return apiErr
			}

			lastErr = apiErr
			logger.Warnf("orchestrator client: retryable error (attempt %d/%d): %v",
				attempt+1, c.maxRetries+1, apiErr)
			continue
		}

		// Parse successful response
		if result != nil && len(respBody) > 0 {
			if err := json.Unmarshal(respBody, result); err != nil {
				return fmt.Errorf("failed to decode response: %w", err)
			}
		}

		logger.Debugf("orchestrator client: request successful (%s %s, status=%d)",
			method, path, resp.StatusCode)
		return nil
	}

	return fmt.Errorf("all retry attempts failed: %w", lastErr)
}

// parseErrorResponse parses error response from API.
func (c *Client) parseErrorResponse(resp *http.Response, body []byte) *ClientError {
	var apiErr APIError
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
		RequestID:  apiErr.RequestID,
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

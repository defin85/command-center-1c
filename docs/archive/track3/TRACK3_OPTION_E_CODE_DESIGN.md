# Track 3: Option E - Code Design & Examples

**Статус:** 📐 DETAILED DESIGN
**Дата:** 2025-11-09
**Prerequisite:** TRACK3_ARCHITECTURE_OPTIONS.md (Option E approved)

Детальный дизайн кода для Lightweight Go HTTP OData Client.

---

## 📋 Структура файлов

```
go-services/worker/internal/odata/
├── client.go          # Main OData HTTP client (150 LOC)
├── client_test.go     # Unit tests (200 LOC)
├── types.go           # Data structures (50 LOC)
├── errors.go          # Error handling (80 LOC)
├── utils.go           # Helpers (GUID, datetime) (30 LOC)
└── README.md          # Documentation

Total: ~510 LOC
```

---

## 📐 Детальный дизайн

### 1. types.go - Data Structures

```go
// go-services/worker/internal/odata/types.go
package odata

import "time"

// Auth contains authentication credentials
type Auth struct {
	Username string
	Password string
}

// ClientConfig contains client configuration
type ClientConfig struct {
	BaseURL        string
	Auth           Auth
	Timeout        time.Duration
	MaxRetries     int
	RetryWaitTime  time.Duration
}

// CreateRequest represents entity creation request
type CreateRequest struct {
	Entity string                 `json:"-"` // Entity name (e.g., "Catalog_Пользователи")
	Data   map[string]interface{} `json:"-"` // Entity data
}

// UpdateRequest represents entity update request
type UpdateRequest struct {
	Entity string                 `json:"-"`
	ID     string                 `json:"-"` // Entity ID (e.g., "guid'...'")
	Data   map[string]interface{} `json:"-"`
}

// DeleteRequest represents entity deletion request
type DeleteRequest struct {
	Entity string `json:"-"`
	ID     string `json:"-"`
}

// QueryRequest represents entity query request
type QueryRequest struct {
	Entity string   `json:"-"`
	Filter string   `json:"-"` // OData $filter query
	Select []string `json:"-"` // Fields to select
	Top    int      `json:"-"` // Limit
	Skip   int      `json:"-"` // Offset
}

// QueryResponse represents query result from OData
type QueryResponse struct {
	Value []map[string]interface{} `json:"value"`
}

// ODataErrorResponse represents 1C OData error format
type ODataErrorResponse struct {
	Error ODataErrorDetail `json:"odata.error"`
}

type ODataErrorDetail struct {
	Code    string              `json:"code"`
	Message ODataErrorMessage   `json:"message"`
}

type ODataErrorMessage struct {
	Lang  string `json:"lang"`
	Value string `json:"value"`
}
```

---

### 2. errors.go - Error Handling

```go
// go-services/worker/internal/odata/errors.go
package odata

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// ODataError represents OData operation error
type ODataError struct {
	Code       string // Error code from 1C
	Message    string // Human-readable message
	StatusCode int    // HTTP status code
	IsTransient bool  // Can retry?
}

func (e *ODataError) Error() string {
	return fmt.Sprintf("OData error (status=%d, code=%s): %s", e.StatusCode, e.Code, e.Message)
}

// Error categories for retry logic
const (
	ErrorCategoryAuth       = "AUTH_ERROR"         // 401 - don't retry
	ErrorCategoryNotFound   = "NOT_FOUND"          // 404 - don't retry
	ErrorCategoryValidation = "VALIDATION_ERROR"   // 400 - don't retry
	ErrorCategoryServer     = "SERVER_ERROR"       // 5xx - retry
	ErrorCategoryTimeout    = "TIMEOUT"            // timeout - retry
	ErrorCategoryNetwork    = "NETWORK_ERROR"      // connection - retry
	ErrorCategoryUnknown    = "UNKNOWN_ERROR"
)

// ParseODataError extracts error from HTTP response
func ParseODataError(resp *http.Response) error {
	statusCode := resp.StatusCode

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return &ODataError{
			Code:       ErrorCategoryUnknown,
			Message:    fmt.Sprintf("Failed to read error response: %v", err),
			StatusCode: statusCode,
			IsTransient: false,
		}
	}

	// Try to parse 1C OData error format
	var odataErr ODataErrorResponse
	if err := json.Unmarshal(body, &odataErr); err == nil {
		if odataErr.Error.Message.Value != "" {
			return &ODataError{
				Code:       odataErr.Error.Code,
				Message:    odataErr.Error.Message.Value,
				StatusCode: statusCode,
				IsTransient: isTransientStatus(statusCode),
			}
		}
	}

	// Fallback: use raw body as message
	message := string(body)
	if len(message) > 500 {
		message = message[:500] + "..." // Truncate long messages
	}

	return &ODataError{
		Code:       categorizeByStatus(statusCode),
		Message:    message,
		StatusCode: statusCode,
		IsTransient: isTransientStatus(statusCode),
	}
}

// categorizeByStatus categorizes error by HTTP status code
func categorizeByStatus(statusCode int) string {
	switch {
	case statusCode == 401:
		return ErrorCategoryAuth
	case statusCode == 404:
		return ErrorCategoryNotFound
	case statusCode == 400:
		return ErrorCategoryValidation
	case statusCode >= 500:
		return ErrorCategoryServer
	default:
		return ErrorCategoryUnknown
	}
}

// isTransientStatus determines if error is transient (can retry)
func isTransientStatus(statusCode int) bool {
	switch statusCode {
	case 408, 429, 500, 502, 503, 504:
		return true
	default:
		return false
	}
}

// IsTransient checks if error can be retried
func IsTransient(err error) bool {
	if odataErr, ok := err.(*ODataError); ok {
		return odataErr.IsTransient
	}
	return false
}
```

---

### 3. utils.go - Helper Functions

```go
// go-services/worker/internal/odata/utils.go
package odata

import (
	"fmt"
	"time"
)

// FormatGUID formats UUID for 1C OData
// Example: "12345678-1234-1234-1234-123456789012" → "guid'12345678-1234-1234-1234-123456789012'"
func FormatGUID(guid string) string {
	return fmt.Sprintf("guid'%s'", guid)
}

// FormatDatetime formats datetime for 1C OData
// Example: 2025-11-09T12:00:00 → "datetime'2025-11-09T12:00:00'"
func FormatDatetime(t time.Time) string {
	return fmt.Sprintf("datetime'%s'", t.Format("2006-01-02T15:04:05"))
}

// FormatDate formats date for 1C OData
// Example: 2025-11-09 → "datetime'2025-11-09T00:00:00'"
func FormatDate(t time.Time) string {
	return fmt.Sprintf("datetime'%s'", t.Format("2006-01-02T00:00:00"))
}

// BuildEntityURL constructs entity URL
// Examples:
//   - BuildEntityURL("http://server/odata", "Catalog_Пользователи", "") 
//     → "http://server/odata/Catalog_Пользователи"
//   - BuildEntityURL("http://server/odata", "Catalog_Пользователи", "guid'...'")
//     → "http://server/odata/Catalog_Пользователи(guid'...')"
func BuildEntityURL(baseURL, entity, id string) string {
	if id != "" {
		return fmt.Sprintf("%s/%s(%s)", baseURL, entity, id)
	}
	return fmt.Sprintf("%s/%s", baseURL, entity)
}
```

---

### 4. client.go - Main OData Client

```go
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
	"time"
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

// doWithRetry executes HTTP request with retry logic
func (c *Client) doWithRetry(ctx context.Context, method, url string, body []byte, result interface{}) error {
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// Wait before retry (exponential backoff)
			waitTime := c.retryWait * time.Duration(1<<uint(attempt-1))
			select {
			case <-time.After(waitTime):
			case <-ctx.Done():
				return ctx.Err()
			}
		}

		err := c.doRequest(ctx, method, url, body, result)
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

// doRequest executes single HTTP request
func (c *Client) doRequest(ctx context.Context, method, url string, body []byte, result interface{}) error {
	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	c.setAuth(req)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json;odata=nometadata")
	}

	// Execute request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return &ODataError{
			Code:       ErrorCategoryNetwork,
			Message:    fmt.Sprintf("HTTP request failed: %v", err),
			StatusCode: 0,
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

// setAuth sets Basic Auth header
func (c *Client) setAuth(req *http.Request) {
	req.SetBasicAuth(c.auth.Username, c.auth.Password)
}

// Close closes the HTTP client (cleanup connections)
func (c *Client) Close() {
	c.httpClient.CloseIdleConnections()
}
```

---

### 5. client_test.go - Unit Tests

```go
// go-services/worker/internal/odata/client_test.go
package odata

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestClient_Create(t *testing.T) {
	// Mock 1C OData server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify method
		if r.Method != "POST" {
			t.Errorf("Expected POST, got %s", r.Method)
		}

		// Verify path
		if r.URL.Path != "/Catalog_Test" {
			t.Errorf("Expected /Catalog_Test, got %s", r.URL.Path)
		}

		// Verify auth
		username, password, ok := r.BasicAuth()
		if !ok || username != "testuser" || password != "testpass" {
			t.Error("Invalid auth")
		}

		// Verify content-type
		contentType := r.Header.Get("Content-Type")
		if contentType != "application/json;odata=nometadata" {
			t.Errorf("Expected application/json;odata=nometadata, got %s", contentType)
		}

		// Read request body
		var reqData map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&reqData); err != nil {
			t.Fatalf("Failed to decode request: %v", err)
		}

		// Verify request data
		if reqData["Name"] != "Test Entity" {
			t.Errorf("Expected Name='Test Entity', got %v", reqData["Name"])
		}

		// Return mock response
		response := map[string]interface{}{
			"Ref_Key": "guid'12345678-1234-1234-1234-123456789012'",
			"Name":    "Test Entity",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	// Create client
	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth: Auth{
			Username: "testuser",
			Password: "testpass",
		},
	})

	// Test Create
	ctx := context.Background()
	result, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{
		"Name": "Test Entity",
	})

	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}

	if result["Ref_Key"] != "guid'12345678-1234-1234-1234-123456789012'" {
		t.Errorf("Unexpected Ref_Key: %v", result["Ref_Key"])
	}
}

func TestClient_Create_AuthError(t *testing.T) {
	// Mock server returning 401
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ODataErrorResponse{
			Error: ODataErrorDetail{
				Code: "AUTH_FAILED",
				Message: ODataErrorMessage{
					Lang:  "ru",
					Value: "Неправильное имя пользователя или пароль",
				},
			},
		})
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth: Auth{
			Username: "wrong",
			Password: "wrong",
		},
	})

	ctx := context.Background()
	_, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{})

	if err == nil {
		t.Fatal("Expected error, got nil")
	}

	odataErr, ok := err.(*ODataError)
	if !ok {
		t.Fatalf("Expected ODataError, got %T", err)
	}

	if odataErr.StatusCode != 401 {
		t.Errorf("Expected status 401, got %d", odataErr.StatusCode)
	}

	if odataErr.IsTransient {
		t.Error("Auth error should not be transient")
	}
}

func TestClient_Create_Retry(t *testing.T) {
	attempts := 0

	// Mock server failing twice, then succeeding
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts <= 2 {
			w.WriteHeader(http.StatusServiceUnavailable) // 503 - transient
			return
		}

		// Success on 3rd attempt
		response := map[string]interface{}{"Ref_Key": "guid'...'"}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL:       server.URL,
		Auth:          Auth{Username: "test", Password: "test"},
		MaxRetries:    3,
		RetryWaitTime: 10 * time.Millisecond, // Fast retry for testing
	})

	ctx := context.Background()
	result, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{})

	if err != nil {
		t.Fatalf("Expected success after retries, got error: %v", err)
	}

	if attempts != 3 {
		t.Errorf("Expected 3 attempts, got %d", attempts)
	}

	if result["Ref_Key"] != "guid'...'" {
		t.Error("Invalid result")
	}
}

func TestClient_Update(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "PATCH" {
			t.Errorf("Expected PATCH, got %s", r.Method)
		}

		expectedPath := "/Catalog_Test(guid'12345')"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected %s, got %s", expectedPath, r.URL.Path)
		}

		w.WriteHeader(http.StatusNoContent) // PATCH часто возвращает 204
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	err := client.Update(ctx, "Catalog_Test", "guid'12345'", map[string]interface{}{
		"Name": "Updated Name",
	})

	if err != nil {
		t.Fatalf("Update failed: %v", err)
	}
}

func TestClient_Delete(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "DELETE" {
			t.Errorf("Expected DELETE, got %s", r.Method)
		}

		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	err := client.Delete(ctx, "Catalog_Test", "guid'12345'")

	if err != nil {
		t.Fatalf("Delete failed: %v", err)
	}
}

func TestClient_Query(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("Expected GET, got %s", r.Method)
		}

		// Check query params
		filter := r.URL.Query().Get("$filter")
		if filter != "Name eq 'Test'" {
			t.Errorf("Expected filter 'Name eq 'Test'', got %s", filter)
		}

		top := r.URL.Query().Get("$top")
		if top != "10" {
			t.Errorf("Expected top=10, got %s", top)
		}

		// Return mock data
		response := QueryResponse{
			Value: []map[string]interface{}{
				{"Ref_Key": "guid'1'", "Name": "Entity 1"},
				{"Ref_Key": "guid'2'", "Name": "Entity 2"},
			},
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	results, err := client.Query(ctx, QueryRequest{
		Entity: "Catalog_Test",
		Filter: "Name eq 'Test'",
		Top:    10,
	})

	if err != nil {
		t.Fatalf("Query failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 results, got %d", len(results))
	}

	if results[0]["Name"] != "Entity 1" {
		t.Error("Invalid result")
	}
}
```

---

## 🔧 Интеграция с Processor

```go
// go-services/worker/internal/processor/processor.go (updated)

import (
    "github.com/commandcenter1c/commandcenter/worker/internal/odata"
)

type TaskProcessor struct {
    config        *config.Config
    credsClient   *credentials.Client
    odataClients  map[string]*odata.Client // Cache clients per database
    clientsMutex  sync.RWMutex
    workerID      string
}

func (p *TaskProcessor) getODataClient(creds *credentials.DatabaseCredentials) *odata.Client {
    p.clientsMutex.RLock()
    if client, exists := p.odataClients[creds.DatabaseID]; exists {
        p.clientsMutex.RUnlock()
        return client
    }
    p.clientsMutex.RUnlock()

    // Create new client
    p.clientsMutex.Lock()
    defer p.clientsMutex.Unlock()

    // Double-check after acquiring write lock
    if client, exists := p.odataClients[creds.DatabaseID]; exists {
        return client
    }

    client := odata.NewClient(odata.ClientConfig{
        BaseURL: creds.ODataURL,
        Auth: odata.Auth{
            Username: creds.Username,
            Password: creds.Password,
        },
        Timeout:    30 * time.Second,
        MaxRetries: 3,
    })

    p.odataClients[creds.DatabaseID] = client
    return client
}

func (p *TaskProcessor) executeCreate(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
    client := p.getODataClient(creds)

    // Create entity via OData
    result, err := client.Create(ctx, msg.Entity, msg.Payload.Data)
    if err != nil {
        return models.DatabaseResultV2{
            Success:   false,
            Error:     err.Error(),
            ErrorCode: categorizeODataError(err),
        }
    }

    return models.DatabaseResultV2{
        Success: true,
        Data:    result,
    }
}

func categorizeODataError(err error) string {
    if odataErr, ok := err.(*odata.ODataError); ok {
        return odataErr.Code
    }
    return "UNKNOWN_ERROR"
}
```

---

## ✅ Testing Strategy

### Unit Tests
```bash
cd go-services/worker/internal/odata
go test -v -cover
```

**Target:** > 80% coverage

### Integration Tests (with mock server)
```bash
go test -v -tags=integration
```

### E2E Test (with real 1C)
```bash
# Requires 1C test environment
export ODATA_TEST_URL="http://localhost/test/odata/standard.odata"
export ODATA_TEST_USER="test"
export ODATA_TEST_PASSWORD="password"
go test -v -tags=e2e
```

---

## 📊 Performance Benchmarks

```go
// client_bench_test.go
func BenchmarkClient_Create(b *testing.B) {
    // Setup mock server
    server := setupMockServer()
    defer server.Close()

    client := NewClient(ClientConfig{BaseURL: server.URL, ...})
    ctx := context.Background()

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        client.Create(ctx, "Catalog_Test", map[string]interface{}{"Name": "Test"})
    }
}
```

**Expected results:**
- Create: ~1000 ns/op (< 1ms)
- Memory: < 1KB per operation

---

## 📅 Implementation Timeline

**Day 1:**
- [ ] Implement types.go, errors.go, utils.go (3 hours)
- [ ] Implement client.go basic structure (3 hours)
- [ ] Unit tests for errors and utils (2 hours)

**Day 2:**
- [ ] Complete client.go (Create, Update, Delete, Query) (4 hours)
- [ ] Unit tests for client (4 hours)

**Day 3:**
- [ ] Integration with processor.go (2 hours)
- [ ] Integration tests (3 hours)
- [ ] E2E test (if 1C available) (2 hours)

**Day 4:**
- [ ] Documentation (2 hours)
- [ ] Code review fixes (3 hours)
- [ ] Performance testing (2 hours)

**Total:** 3-4 days

---

**Версия:** 1.0
**Дата:** 2025-11-09
**Статус:** ✅ READY FOR IMPLEMENTATION (после approval)

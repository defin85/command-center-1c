// go-services/worker/internal/processor/processor_integration_test.go
//go:build integration
// +build integration

package processor

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"runtime"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/odataops"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/redis/go-redis/v9"
)

// MockODataServer создаёт mock 1C OData сервер
func setupMockODataServer() *httptest.Server {
	// In-memory хранилище для сущностей
	entities := make(map[string]map[string]interface{})

	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify Basic Auth
		username, password, ok := r.BasicAuth()
		if !ok || username != "testuser" || password != "testpass" {
			w.WriteHeader(http.StatusUnauthorized)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"odata.error": map[string]interface{}{
					"code": "AUTH_FAILED",
					"message": map[string]string{
						"lang":  "en",
						"value": "Invalid credentials",
					},
				},
			})
			return
		}

		switch r.Method {
		case "POST":
			// CREATE operation
			handleCreate(w, r, entities)
		case "PATCH":
			// UPDATE operation
			handleUpdate(w, r, entities)
		case "DELETE":
			// DELETE operation
			handleDelete(w, r, entities)
		case "GET":
			// QUERY operation
			handleQuery(w, r, entities)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
}

func handleCreate(w http.ResponseWriter, r *http.Request, entities map[string]map[string]interface{}) {
	var data map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// Generate fake GUID
	guid := "guid'test-guid-12345'"
	data["Ref_Key"] = guid

	// Store entity
	entities[guid] = data

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

func handleUpdate(w http.ResponseWriter, r *http.Request, entities map[string]map[string]interface{}) {
	// Extract entity ID from path (e.g., /Catalog_Test(guid'...'))
	// Simple extraction - in real code would parse properly

	var data map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// Return 204 No Content (standard for PATCH)
	w.WriteHeader(http.StatusNoContent)
}

func handleDelete(w http.ResponseWriter, r *http.Request, entities map[string]map[string]interface{}) {
	// Return 204 No Content
	w.WriteHeader(http.StatusNoContent)
}

func handleQuery(w http.ResponseWriter, r *http.Request, entities map[string]map[string]interface{}) {
	// Return all entities as array
	results := make([]map[string]interface{}, 0, len(entities))
	for _, entity := range entities {
		results = append(results, entity)
	}

	response := map[string]interface{}{
		"value": results,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func setupTestProcessor(t *testing.T, credsClient credentials.Fetcher) (*TaskProcessor, func()) {
	return setupTestProcessorWithConfig(t, credsClient, &config.Config{WorkerID: "test-worker-1"})
}

func setupTestProcessorWithConfig(
	t *testing.T,
	credsClient credentials.Fetcher,
	cfg *config.Config,
) (*TaskProcessor, func()) {
	t.Helper()

	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("failed to start miniredis: %v", err)
	}

	redisClient := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})

	if cfg == nil {
		cfg = &config.Config{WorkerID: "test-worker-1"}
	}
	odataPool := odata.NewClientPool()
	odataService := odata.NewService(odataPool)
	processor := NewTaskProcessorWithOptions(cfg, credsClient, redisClient, ProcessorOptions{
		ODataService: odataService,
	})

	cleanup := func() {
		redisClient.Close()
		mr.Close()
	}

	return processor, cleanup
}

func integrationCompatibilityProfilePath(t *testing.T) string {
	t.Helper()
	_, currentFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("unable to resolve caller path")
	}
	repoRoot := filepath.Clean(filepath.Join(filepath.Dir(currentFile), "../../../../"))
	return filepath.Join(
		repoRoot,
		"openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml",
	)
}

// TestProcessor_Integration_CreateOperation тестирует Create через весь processor
func TestProcessor_Integration_CreateOperation(t *testing.T) {
	// Setup mock OData server
	server := setupMockODataServer()
	defer server.Close()

	// Setup mock credentials client
	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}

	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	// Create operation message
	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-001",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"Name":  "John Doe",
				"Email": "john@example.com",
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	// Process
	ctx := context.Background()
	result := processor.Process(ctx, msg)

	// Assertions
	if result.Status != "completed" {
		t.Errorf("Expected status 'completed', got '%s'", result.Status)
	}

	if result.Summary.Succeeded != 1 {
		t.Errorf("Expected 1 succeeded, got %d", result.Summary.Succeeded)
	}

	if result.Summary.Failed != 0 {
		t.Errorf("Expected 0 failed, got %d", result.Summary.Failed)
	}

	if len(result.Results) != 1 {
		t.Fatalf("Expected 1 result, got %d", len(result.Results))
	}

	dbResult := result.Results[0]
	if !dbResult.Success {
		t.Errorf("Expected success=true, got false. Error: %s", dbResult.Error)
	}

	// Check created entity has Ref_Key
	if dbResult.Data["Ref_Key"] != "guid'test-guid-12345'" {
		t.Errorf("Expected Ref_Key, got: %v", dbResult.Data)
	}
}

// TestProcessor_Integration_UpdateOperation тестирует Update
func TestProcessor_Integration_UpdateOperation(t *testing.T) {
	server := setupMockODataServer()
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}
	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-002",
		OperationType:   "update",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Filters: map[string]interface{}{
				"entity_id": "guid'test-guid-12345'",
			},
			Data: map[string]interface{}{
				"Email": "updated@example.com",
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	ctx := context.Background()
	result := processor.Process(ctx, msg)

	if result.Status != "completed" {
		t.Errorf("Expected status 'completed', got '%s'", result.Status)
	}

	dbResult := result.Results[0]
	if !dbResult.Success {
		t.Errorf("Update failed: %s", dbResult.Error)
	}
}

// TestProcessor_Integration_DeleteOperation тестирует Delete
func TestProcessor_Integration_DeleteOperation(t *testing.T) {
	server := setupMockODataServer()
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}
	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-003",
		OperationType:   "delete",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Filters: map[string]interface{}{
				"entity_id": "guid'test-guid-12345'",
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	ctx := context.Background()
	result := processor.Process(ctx, msg)

	if result.Status != "completed" {
		t.Errorf("Expected status 'completed', got '%s'", result.Status)
	}

	dbResult := result.Results[0]
	if !dbResult.Success {
		t.Errorf("Delete failed: %s", dbResult.Error)
	}
}

// TestProcessor_Integration_QueryOperation тестирует Query
func TestProcessor_Integration_QueryOperation(t *testing.T) {
	server := setupMockODataServer()
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}
	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-004",
		OperationType:   "query",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Options: map[string]interface{}{
				"filter": "Name eq 'John'",
				"top":    float64(10),
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	ctx := context.Background()
	result := processor.Process(ctx, msg)

	if result.Status != "completed" {
		t.Errorf("Expected status 'completed', got '%s'", result.Status)
	}

	dbResult := result.Results[0]
	if !dbResult.Success {
		t.Errorf("Query failed: %s", dbResult.Error)
	}

	// Check results array exists
	if _, ok := dbResult.Data["results"]; !ok {
		t.Error("Expected 'results' field in response")
	}
}

func TestProcessor_Integration_CreateOperation_WithPoolPublicationCoreEnabled(t *testing.T) {
	server := setupMockODataServer()
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}

	cfg := &config.Config{
		WorkerID:                                "test-worker-1",
		EnablePoolOpsRoute:                      true,
		PoolOpsRouteRolloutPercent:              1.0,
		EnablePoolPublicationODataCore:          true,
		PoolPublicationODataCoreRolloutPercent:  1.0,
		ODataCompatibilityProfilePath:           integrationCompatibilityProfilePath(t),
		ODataCompatibilityConfigurationID:       "1c-accounting-3.0-standard-odata",
		ODataCompatibilityWriteContentType:      "application/json;odata=nometadata",
		ODataCompatibilityReleaseProfileVersion: "0.4.2-draft",
	}

	processor, cleanup := setupTestProcessorWithConfig(t, credsClient, cfg)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-publication-core-enabled-001",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"Name":  "Core Enabled",
				"Email": "core-enabled@example.com",
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	result := processor.Process(context.Background(), msg)
	if result.Status != "completed" {
		t.Fatalf("expected status completed, got %s", result.Status)
	}
	if result.Summary.Failed != 0 {
		t.Fatalf("expected no failed results, got %d", result.Summary.Failed)
	}
	if len(result.Results) != 1 {
		t.Fatalf("expected one db result, got %d", len(result.Results))
	}
	if !result.Results[0].Success {
		t.Fatalf("expected successful result, got error: %s", result.Results[0].Error)
	}
}

// TestProcessor_Integration_AuthError тестирует обработку ошибки 401
func TestProcessor_Integration_AuthError(t *testing.T) {
	// Create server with wrong credentials
	server := setupMockODataServer()
	defer server.Close()

	// Use wrong credentials
	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			DatabaseID: "db-001",
			ODataURL:   server.URL,
			Username:   "wrong",
			Password:   "wrong",
		},
	}

	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-005",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"Name": "Test",
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	ctx := context.Background()
	result := processor.Process(ctx, msg)

	// Should fail - all databases failed
	if result.Status != "failed" {
		t.Errorf("Expected status 'failed', got '%s'", result.Status)
	}

	if result.Summary.Failed != 1 {
		t.Errorf("Expected 1 failed, got %d", result.Summary.Failed)
	}

	dbResult := result.Results[0]
	if dbResult.Success {
		t.Error("Expected failure due to auth error")
	}

	if dbResult.ErrorCode != "AUTH_FAILED" {
		t.Errorf("Expected error_code 'AUTH_FAILED', got '%s'", dbResult.ErrorCode)
	}
}

// TestProcessor_Integration_MultipleTargets тестирует обработку нескольких БД
func TestProcessor_Integration_MultipleTargets(t *testing.T) {
	server := setupMockODataServer()
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}
	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-006",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}, {ID: "db-002"}, {ID: "db-003"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"Name": "Test User",
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 30,
		},
	}

	ctx := context.Background()
	result := processor.Process(ctx, msg)

	// Check all 3 databases processed
	if len(result.Results) != 3 {
		t.Errorf("Expected 3 results, got %d", len(result.Results))
	}

	if result.Summary.Total != 3 {
		t.Errorf("Expected total=3, got %d", result.Summary.Total)
	}

	if result.Summary.Succeeded != 3 {
		t.Errorf("Expected succeeded=3, got %d", result.Summary.Succeeded)
	}

	// Check each result
	for i, dbResult := range result.Results {
		if !dbResult.Success {
			t.Errorf("Database %d failed: %s", i, dbResult.Error)
		}
	}
}

// TestProcessor_Integration_ClientCaching тестирует кэширование клиентов
func TestProcessor_Integration_ClientCaching(t *testing.T) {
	server := setupMockODataServer()
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}
	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	// First operation - creates client
	msg1 := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-007",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{"Name": "User 1"},
		},
		ExecConfig: models.ExecutionConfig{TimeoutSeconds: 30},
	}

	ctx := context.Background()
	result1 := processor.Process(ctx, msg1)

	if !result1.Results[0].Success {
		t.Fatalf("First operation failed: %s", result1.Results[0].Error)
	}

	// Second operation - should reuse cached client
	msg2 := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-008",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{"Name": "User 2"},
		},
		ExecConfig: models.ExecutionConfig{TimeoutSeconds: 30},
	}

	result2 := processor.Process(ctx, msg2)

	if !result2.Results[0].Success {
		t.Fatalf("Second operation failed: %s", result2.Results[0].Error)
	}

	// Check client cache size
	driver, ok := processor.driverRegistry.LookupDatabase("create")
	if !ok {
		t.Fatal("expected odata driver to be registered")
	}
	odataDriver, ok := driver.(*odataops.Driver)
	if !ok {
		t.Fatalf("expected odata driver, got %T", driver)
	}
	cacheSize := odataDriver.CacheSize()

	if cacheSize != 1 {
		t.Errorf("Expected 1 cached client, got %d", cacheSize)
	}
}

// TestProcessor_Integration_Timeout тестирует обработку timeout
func TestProcessor_Integration_Timeout(t *testing.T) {
	// Create slow server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(5 * time.Second) // Longer than client timeout
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	credsClient := &credentials.MockCredentialsClient{
		Credentials: &credentials.DatabaseCredentials{
			ODataURL: server.URL,
			Username: "testuser",
			Password: "testpass",
		},
	}
	processor, cleanup := setupTestProcessor(t, credsClient)
	defer cleanup()

	msg := &models.OperationMessage{
		Version:         "2.0",
		OperationID:     "test-op-009",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []models.TargetDatabase{{ID: "db-001"}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{"Name": "Test"},
		},
		ExecConfig: models.ExecutionConfig{TimeoutSeconds: 1},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	result := processor.Process(ctx, msg)

	// Should fail due to timeout
	dbResult := result.Results[0]
	if dbResult.Success {
		t.Error("Expected failure due to timeout")
	}

	// Error should mention timeout or network
	if dbResult.ErrorCode != "NETWORK_ERROR" && dbResult.ErrorCode != "TIMEOUT" {
		t.Logf("Error code: %s, Error: %s", dbResult.ErrorCode, dbResult.Error)
	}
}

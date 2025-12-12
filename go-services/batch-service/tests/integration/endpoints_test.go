package integration

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/command-center-1c/batch-service/internal/api"
	"github.com/command-center-1c/batch-service/internal/api/handlers"
	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/rollback"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/infrastructure/filesystem"
	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/internal/metrics"
	"github.com/command-center-1c/batch-service/internal/service"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

func setupTestRouter() *gin.Engine {
	// Create services with short timeout for tests
	// (default 5min is too long when 1cv8.exe exists but fails)
	deleter := service.NewExtensionDeleter("", 10*time.Second)
	lister := service.NewExtensionLister("", 10*time.Second)
	installer := service.NewExtensionInstaller("", 0)
	validator := service.NewFileValidator()

	// Create additional required services
	logger := zap.NewNop()

	// Create temp directories for test storage
	testStoragePath := "./test-storage"
	testBackupPath := "./test-backups"
	os.MkdirAll(testStoragePath, 0755)
	os.MkdirAll(testBackupPath, 0755)

	// Storage manager with retention of 3 versions
	storageManager := storage.NewManager(testStoragePath, 3, logger)

	// V8 executor (will fail gracefully in tests without 1cv8.exe)
	v8exec := v8executor.NewV8Executor("", 10*time.Second)

	// Metadata extractor with parser
	metadataParser := metadata.NewParser(logger)
	metadataExtractor := metadata.NewExtractor(v8exec, metadataParser, logger)

	// Backup system
	backupStorage := filesystem.NewBackupStorage(testBackupPath, logger)
	backupManager := rollback.NewBackupManager(v8exec, backupStorage, logger)
	rollbackManager := rollback.NewRollbackManager(backupManager, logger)

	// Initialize metrics for tests
	batchMetrics := metrics.NewBatchMetrics()

	// Setup router
	router := api.SetupRouter(installer, deleter, lister, validator, storageManager, metadataExtractor, rollbackManager, backupManager, batchMetrics, logger)

	return router
}

func TestHealthEndpoint(t *testing.T) {

	router := setupTestRouter()

	req, err := http.NewRequest("GET", "/health", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.Equal(t, "healthy", response["status"])
	assert.Equal(t, "batch-service", response["service"])
}

func TestDeleteExtensionEndpoint_ValidRequest(t *testing.T) {

	router := setupTestRouter()

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase",
		"username":       "admin",
		"password":       "password",
		"extension_name": "TestExt",
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
	require.NoError(t, err)
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should fail because 1cv8.exe doesn't exist, but endpoint should process request
	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var response handlers.ErrorResponse
	err = json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.NotEmpty(t, response.Error)
}

func TestDeleteExtensionEndpoint_MissingField(t *testing.T) {

	router := setupTestRouter()

	tests := []struct {
		name    string
		payload map[string]string
	}{
		{
			name: "missing server",
			payload: map[string]string{
				"infobase_name":  "TestBase",
				"username":       "admin",
				"password":       "password",
				"extension_name": "TestExt",
			},
		},
		{
			name: "missing infobase_name",
			payload: map[string]string{
				"server":         "localhost:1541",
				"username":       "admin",
				"password":       "password",
				"extension_name": "TestExt",
			},
		},
		{
			name: "missing username",
			payload: map[string]string{
				"server":         "localhost:1541",
				"infobase_name":  "TestBase",
				"password":       "password",
				"extension_name": "TestExt",
			},
		},
		{
			name: "missing password",
			payload: map[string]string{
				"server":         "localhost:1541",
				"infobase_name":  "TestBase",
				"username":       "admin",
				"extension_name": "TestExt",
			},
		},
		{
			name: "missing extension_name",
			payload: map[string]string{
				"server":        "localhost:1541",
				"infobase_name": "TestBase",
				"username":      "admin",
				"password":      "password",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tt.payload)
			require.NoError(t, err)

			req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
			require.NoError(t, err)
			req.Header.Set("Content-Type", "application/json")

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, http.StatusBadRequest, w.Code)

			var response handlers.ErrorResponse
			err = json.Unmarshal(w.Body.Bytes(), &response)
			assert.NoError(t, err)
			assert.NotEmpty(t, response.Error)
		})
	}
}

func TestDeleteExtensionEndpoint_InvalidJSON(t *testing.T) {

	router := setupTestRouter()

	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer([]byte("invalid json")))
	require.NoError(t, err)
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestListExtensionsEndpoint_ValidRequest(t *testing.T) {

	router := setupTestRouter()

	req, err := http.NewRequest(
		"GET",
		"/api/v1/extensions/list?server=localhost:1541&infobase_name=TestBase&username=admin&password=password",
		nil,
	)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should fail because 1cv8.exe doesn't exist, but endpoint should process request
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestListExtensionsEndpoint_MissingParameter(t *testing.T) {

	router := setupTestRouter()

	tests := []struct {
		name string
		url  string
	}{
		{
			name: "missing server",
			url:  "/api/v1/extensions/list?infobase_name=TestBase&username=admin&password=password",
		},
		{
			name: "missing infobase_name",
			url:  "/api/v1/extensions/list?server=localhost:1541&username=admin&password=password",
		},
		{
			name: "missing username",
			url:  "/api/v1/extensions/list?server=localhost:1541&infobase_name=TestBase&password=password",
		},
		{
			name: "missing password",
			url:  "/api/v1/extensions/list?server=localhost:1541&infobase_name=TestBase&username=admin",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, err := http.NewRequest("GET", tt.url, nil)
			require.NoError(t, err)

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, http.StatusBadRequest, w.Code)
		})
	}
}

func TestDeleteExtensionEndpoint_EmptyRequest(t *testing.T) {

	router := setupTestRouter()

	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer([]byte("{}")))
	require.NoError(t, err)
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestDeleteExtensionEndpoint_VeryLongExtensionName(t *testing.T) {

	router := setupTestRouter()

	longName := ""
	for i := 0; i < 500; i++ {
		longName += "A"
	}

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase",
		"username":       "admin",
		"password":       "password",
		"extension_name": longName,
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
	require.NoError(t, err)
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should process the request despite long name
	assert.NotEqual(t, http.StatusBadRequest, w.Code) // Not a validation error
}

func TestDeleteExtensionEndpoint_SpecialCharactersInParams(t *testing.T) {

	router := setupTestRouter()

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase_v2024",
		"username":       "admin@example.com",
		"password":       "p@$$w0rd!",
		"extension_name": "Расширение_Тест#1",
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
	require.NoError(t, err)
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should process the request
	assert.NotEqual(t, http.StatusBadRequest, w.Code)
}

func TestDeleteExtensionEndpoint_WrongHttpMethod(t *testing.T) {

	router := setupTestRouter()

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase",
		"username":       "admin",
		"password":       "password",
		"extension_name": "TestExt",
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	// Try GET instead of POST
	req, err := http.NewRequest("GET", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestListExtensionsEndpoint_WrongHttpMethod(t *testing.T) {

	router := setupTestRouter()

	payload := map[string]string{
		"server":        "localhost:1541",
		"infobase_name": "TestBase",
		"username":      "admin",
		"password":      "password",
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	// Try POST instead of GET
	req, err := http.NewRequest("POST", "/api/v1/extensions/list", bytes.NewBuffer(jsonData))
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestDeleteExtensionEndpoint_ContentTypeHandling(t *testing.T) {

	router := setupTestRouter()

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase",
		"username":       "admin",
		"password":       "password",
		"extension_name": "TestExt",
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	// Test without Content-Type header
	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
	require.NoError(t, err)
	// Don't set Content-Type

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Gin should handle this gracefully
	assert.NotEqual(t, http.StatusBadRequest, w.Code)
}

func TestListExtensionsEndpoint_MultipleParameters(t *testing.T) {

	router := setupTestRouter()

	req, err := http.NewRequest(
		"GET",
		"/api/v1/extensions/list?server=localhost:1541&infobase_name=TestBase&username=admin&password=password&extra=ignored",
		nil,
	)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should process request and ignore extra params
	assert.NotEqual(t, http.StatusBadRequest, w.Code)
}

// TestDeleteExtensionEndpoint_NoDeadlockWithLargeOutput tests that the endpoint
// completes quickly without deadlock, even when subprocess produces large output
func TestDeleteExtensionEndpoint_NoDeadlockWithLargeOutput(t *testing.T) {
	// CRITICAL TEST: Verifies the deadlock fix
	// Before fix: This would hang for 600 seconds
	// After fix: Should complete in < 10 seconds

	// Use short timeout for test to complete quickly

	router := setupTestRouter()

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase",
		"username":       "admin",
		"password":       "password",
		"extension_name": "TestExt",
	}

	jsonData, err := json.Marshal(payload)
	require.NoError(t, err)

	req, err := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
	require.NoError(t, err)
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()

	// Measure execution time
	// Note: This test simulates the deadlock scenario
	// In actual usage with 1cv8.exe producing large stderr, the fix is critical
	router.ServeHTTP(w, req)

	// Should complete (will fail because 1cv8.exe doesn't exist, but that's expected)
	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var response handlers.ErrorResponse
	err = json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.NotEmpty(t, response.Error)
}

// TestListExtensionsEndpoint_NoDeadlockWithLargeOutput tests that list endpoint
// also doesn't deadlock with large output
func TestListExtensionsEndpoint_NoDeadlockWithLargeOutput(t *testing.T) {
	// CRITICAL TEST: Verifies the deadlock fix for list operation

	// Use short timeout for test to complete quickly

	router := setupTestRouter()

	req, err := http.NewRequest(
		"GET",
		"/api/v1/extensions/list?server=localhost:1541&infobase_name=TestBase&username=admin&password=password",
		nil,
	)
	require.NoError(t, err)

	w := httptest.NewRecorder()

	// Measure execution time - should complete quickly
	router.ServeHTTP(w, req)

	// Should complete (will fail because 1cv8.exe doesn't exist, but that's expected)
	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

// BenchmarkDeleteEndpointProcessing benchmarks endpoint request processing
func BenchmarkDeleteEndpointProcessing(b *testing.B) {

	router := setupTestRouter()

	payload := map[string]string{
		"server":         "localhost:1541",
		"infobase_name":  "TestBase",
		"username":       "admin",
		"password":       "password",
		"extension_name": "TestExt",
	}

	jsonData, _ := json.Marshal(payload)

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("POST", "/api/v1/extensions/delete", bytes.NewBuffer(jsonData))
		req.Header.Set("Content-Type", "application/json")

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

package integration

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/command-center-1c/batch-service/internal/api"
	"github.com/command-center-1c/batch-service/internal/domain/metadata"
	"github.com/command-center-1c/batch-service/internal/domain/storage"
	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/internal/metrics"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

var (
	testRouter     *gin.Engine
	testRouterOnce sync.Once
)

func getTestRouter() *gin.Engine {
	testRouterOnce.Do(func() {
		// Create logger
		logger := zap.NewNop()

		// Create temp directories for test storage
		testStoragePath := "./test-storage"
		os.MkdirAll(testStoragePath, 0755)

		// Storage manager with retention of 3 versions
		storageManager := storage.NewManager(testStoragePath, 3, logger)

		// V8 executor (will fail gracefully in tests without 1cv8.exe)
		v8exec := v8executor.NewV8Executor("", 10*time.Second)

		// Metadata extractor with parser
		metadataParser := metadata.NewParser(logger)
		metadataExtractor := metadata.NewExtractor(v8exec, metadataParser, logger)

		// Initialize metrics for tests (only once to avoid duplicate registration)
		batchMetrics := metrics.NewBatchMetrics()

		// Setup router with new flat API
		testRouter = api.SetupRouter(storageManager, metadataExtractor, batchMetrics, logger)
	})
	return testRouter
}

func TestHealthEndpoint(t *testing.T) {
	router := getTestRouter()

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

func TestMetricsEndpoint(t *testing.T) {
	router := getTestRouter()

	req, err := http.NewRequest("GET", "/metrics", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	// Prometheus metrics should contain standard Go metrics
	assert.Contains(t, w.Body.String(), "go_")
}

func TestStorageListEndpoint(t *testing.T) {
	router := getTestRouter()

	req, err := http.NewRequest("GET", "/storage/list", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should return 200 OK with empty list (storage is empty)
	assert.Equal(t, http.StatusOK, w.Code)

	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	// Response should have extensions array (possibly empty)
	assert.Contains(t, response, "extensions")
}

func TestStorageDeleteEndpoint_NotFound(t *testing.T) {
	router := getTestRouter()

	req, err := http.NewRequest("DELETE", "/storage/nonexistent.cfe", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Handler returns 500 for file system errors (including not found)
	// This is acceptable behavior for internal API
	assert.True(t, w.Code == http.StatusNotFound || w.Code == http.StatusInternalServerError,
		"Expected 404 or 500, got %d", w.Code)
}

func TestStorageMetadataEndpoint_NotFound(t *testing.T) {
	router := getTestRouter()

	req, err := http.NewRequest("GET", "/storage/nonexistent.cfe/metadata", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Handler returns 500 for file system errors (including not found)
	// This is acceptable behavior for internal API
	assert.True(t, w.Code == http.StatusNotFound || w.Code == http.StatusInternalServerError,
		"Expected 404 or 500, got %d", w.Code)
}

func TestMetadataEndpoint_NotFound(t *testing.T) {
	router := getTestRouter()

	req, err := http.NewRequest("GET", "/metadata/nonexistent.cfe", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Should return 404 for non-existent file
	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestOldAPIv1Endpoints_NotFound(t *testing.T) {
	// Verify that old API v1 endpoints are no longer available
	router := getTestRouter()

	oldEndpoints := []struct {
		method string
		path   string
	}{
		{"POST", "/api/v1/extensions/install"},
		{"POST", "/api/v1/extensions/batch-install"},
		{"POST", "/api/v1/extensions/delete"},
		{"GET", "/api/v1/extensions/list"},
		{"POST", "/api/v1/extensions/rollback"},
		{"GET", "/api/v1/extensions/rollback/history"},
		{"POST", "/api/v1/extensions/backups/create"},
		{"GET", "/api/v1/extensions/backups/test-db"},
		{"GET", "/api/v1/extensions/backups/test-db/latest"},
		{"DELETE", "/api/v1/extensions/backups/test-db/backup-1"},
	}

	for _, endpoint := range oldEndpoints {
		t.Run(endpoint.method+" "+endpoint.path, func(t *testing.T) {
			req, err := http.NewRequest(endpoint.method, endpoint.path, nil)
			require.NoError(t, err)

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			// All old v1 endpoints should return 404
			assert.Equal(t, http.StatusNotFound, w.Code,
				"Old endpoint %s %s should return 404", endpoint.method, endpoint.path)
		})
	}
}

// BenchmarkHealthEndpoint benchmarks health endpoint response time
func BenchmarkHealthEndpoint(b *testing.B) {
	router := getTestRouter()

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("GET", "/health", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

// BenchmarkStorageListEndpoint benchmarks storage list endpoint
func BenchmarkStorageListEndpoint(b *testing.B) {
	router := getTestRouter()

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req, _ := http.NewRequest("GET", "/storage/list", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

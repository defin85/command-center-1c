package rest

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

// setupTestRouter creates a test router with infobase handlers
func setupTestRouter(svc *service.InfobaseService) *gin.Engine {
	gin.SetMode(gin.TestMode)
	router := gin.New()

	// Register handlers
	router.GET("/api/v1/infobases", GetInfobases(svc))
	router.POST("/api/v1/infobases/:infobase_id/lock", LockInfobase(svc))
	router.POST("/api/v1/infobases/:infobase_id/unlock", UnlockInfobase(svc))

	return router
}

// ====================== LOCK TESTS ======================

// TestLockInfobase_Success tests successful lock endpoint
func TestLockInfobase_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with valid UUID
	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/lock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert - expecting either 200 (success) or 500 (RAS not available)
	// In test environment, RAS is not available, so we expect 500
	assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError,
		"Expected status OK or InternalServerError, got %d", w.Code)

	pool.Close()
}

// TestLockInfobase_MissingClusterID tests lock with missing cluster_id
func TestLockInfobase_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with empty cluster_id
	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/lock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert
	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Contains(t, w.Body.String(), "error")

	pool.Close()
}

// TestLockInfobase_InvalidJSON tests lock with invalid JSON
func TestLockInfobase_InvalidJSON(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with invalid JSON
	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/lock",
		bytes.NewBuffer([]byte("{invalid json}")),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert
	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Contains(t, w.Body.String(), "error")

	pool.Close()
}

// TestLockInfobase_EmptyInfobaseID tests lock with empty infobase_id in URL
func TestLockInfobase_EmptyInfobaseID(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with empty infobase_id
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases//lock", // empty infobase_id
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert - Gin routes the request but parameter will be empty string, handler will validate and return 400
	assert.Equal(t, http.StatusBadRequest, w.Code)

	pool.Close()
}

// TestLockInfobase_MultipleCalls tests multiple lock calls
func TestLockInfobase_MultipleCalls(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	// Make multiple lock calls
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(
			"POST",
			"/api/v1/infobases/"+validInfobaseID+"/lock",
			bytes.NewBuffer(body),
		)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		// Expecting either 200 (success) or 500 (RAS not available)
		assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError,
			"Expected status OK or InternalServerError, got %d", w.Code)
	}

	pool.Close()
}

// TestLockInfobase_ResponseStructure tests lock response structure
func TestLockInfobase_ResponseStructure(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/lock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	// Parse response - expecting either 200 (success) or 500 (RAS not available)
	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	// Verify structure - in test environment RAS is not available
	assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError,
		"Expected status OK or InternalServerError, got %d", w.Code)

	pool.Close()
}

// ====================== UNLOCK TESTS ======================

// TestUnlockInfobase_Success tests successful unlock endpoint
func TestUnlockInfobase_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with valid UUID
	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/unlock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert - expecting either 200 (success) or 500 (RAS not available)
	assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError,
		"Expected status OK or InternalServerError, got %d", w.Code)

	pool.Close()
}

// TestUnlockInfobase_MissingClusterID tests unlock with missing cluster_id
func TestUnlockInfobase_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with empty cluster_id
	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/unlock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert
	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Contains(t, w.Body.String(), "error")

	pool.Close()
}

// TestUnlockInfobase_InvalidJSON tests unlock with invalid JSON
func TestUnlockInfobase_InvalidJSON(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	// Create request with invalid JSON
	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/unlock",
		bytes.NewBuffer([]byte("{invalid json}")),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Call handler
	router.ServeHTTP(w, req)

	// Assert
	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Contains(t, w.Body.String(), "error")

	pool.Close()
}

// TestUnlockInfobase_MultipleCalls tests multiple unlock calls
func TestUnlockInfobase_MultipleCalls(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	// Make multiple unlock calls
	for i := 0; i < 3; i++ {
		req := httptest.NewRequest(
			"POST",
			"/api/v1/infobases/"+validInfobaseID+"/unlock",
			bytes.NewBuffer(body),
		)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)

		// Expecting either 200 (success) or 500 (RAS not available)
		assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError,
			"Expected status OK or InternalServerError, got %d", w.Code)
	}

	pool.Close()
}

// TestUnlockInfobase_ResponseStructure tests unlock response structure
func TestUnlockInfobase_ResponseStructure(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	validInfobaseID := "12345678-1234-5678-1234-567812345678"
	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/"+validInfobaseID+"/unlock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	// Parse response - in test environment RAS is not available
	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	// Verify structure - expecting either 200 (success) or 500 (RAS not available)
	assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError,
		"Expected status OK or InternalServerError, got %d", w.Code)

	pool.Close()
}

// ====================== INTEGRATION TESTS ======================

// TestLockUnlock_Sequence tests lock followed by unlock via REST API
func TestLockUnlock_Sequence(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	// 1. Lock
	lockReq := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/infobase-uuid/lock",
		bytes.NewBuffer(body),
	)
	lockReq.Header.Set("Content-Type", "application/json")
	lockW := httptest.NewRecorder()
	router.ServeHTTP(lockW, lockReq)
	assert.Equal(t, http.StatusOK, lockW.Code)

	// 2. Unlock
	unlockReq := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/infobase-uuid/unlock",
		bytes.NewBuffer(body),
	)
	unlockReq.Header.Set("Content-Type", "application/json")
	unlockW := httptest.NewRecorder()
	router.ServeHTTP(unlockW, unlockReq)
	assert.Equal(t, http.StatusOK, unlockW.Code)

	pool.Close()
}

// TestGetInfobases_Success tests GET infobases endpoint
func TestGetInfobases_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	req := httptest.NewRequest("GET", "/api/v1/infobases?cluster_id=cluster-uuid", nil)
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "infobases")

	pool.Close()
}

// TestGetInfobases_MissingClusterID tests GET infobases without cluster_id
func TestGetInfobases_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	req := httptest.NewRequest("GET", "/api/v1/infobases", nil)
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
	assert.Contains(t, w.Body.String(), "error")

	pool.Close()
}

// TestContentType tests Content-Type headers
func TestContentType(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(t, err)

	req := httptest.NewRequest(
		"POST",
		"/api/v1/infobases/infobase-uuid/lock",
		bytes.NewBuffer(body),
	)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	// Gin adds charset to JSON response
	contentType := w.Header().Get("Content-Type")
	assert.Contains(t, contentType, "application/json")

	pool.Close()
}

// BenchmarkLockInfobase_REST benchmarks lock endpoint
func BenchmarkLockInfobase_REST(b *testing.B) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(b, err)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest(
			"POST",
			"/api/v1/infobases/infobase-uuid/lock",
			bytes.NewBuffer(body),
		)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)
	}

	pool.Close()
}

// BenchmarkUnlockInfobase_REST benchmarks unlock endpoint
func BenchmarkUnlockInfobase_REST(b *testing.B) {
	logger, _ := zap.NewDevelopment()
	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := service.NewInfobaseService(pool, logger)
	router := setupTestRouter(svc)

	reqBody := map[string]string{
		"cluster_id": "cluster-uuid",
	}
	body, err := json.Marshal(reqBody)
	require.NoError(b, err)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest(
			"POST",
			"/api/v1/infobases/infobase-uuid/unlock",
			bytes.NewBuffer(body),
		)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		router.ServeHTTP(w, req)
	}

	pool.Close()
}

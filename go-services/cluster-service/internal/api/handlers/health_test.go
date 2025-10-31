package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/command-center-1c/cluster-service/internal/models"
	"github.com/command-center-1c/cluster-service/internal/version"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewHealthHandler(t *testing.T) {
	handler := NewHealthHandler()
	assert.NotNil(t, handler)
}

func TestHealthHandler_Health(t *testing.T) {
	gin.SetMode(gin.TestMode)

	handler := NewHealthHandler()

	router := gin.New()
	router.GET("/health", handler.Health)

	req, err := http.NewRequest("GET", "/health", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем status code
	assert.Equal(t, http.StatusOK, w.Code)

	// Проверяем content type
	assert.Equal(t, "application/json; charset=utf-8", w.Header().Get("Content-Type"))

	// Декодируем response body
	var response models.HealthResponse
	err = json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	// Проверяем поля response
	assert.Equal(t, "healthy", response.Status)
	assert.Equal(t, "cluster-service", response.Service)
	assert.Equal(t, version.Version, response.Version)
}

func TestHealthHandler_Health_ResponseStructure(t *testing.T) {
	gin.SetMode(gin.TestMode)

	handler := NewHealthHandler()

	router := gin.New()
	router.GET("/health", handler.Health)

	req, err := http.NewRequest("GET", "/health", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем что response содержит все необходимые поля
	assert.Contains(t, w.Body.String(), `"status"`)
	assert.Contains(t, w.Body.String(), `"service"`)
	assert.Contains(t, w.Body.String(), `"version"`)
	assert.Contains(t, w.Body.String(), `"healthy"`)
	assert.Contains(t, w.Body.String(), `"cluster-service"`)
}

func TestHealthHandler_Health_MultipleRequests(t *testing.T) {
	gin.SetMode(gin.TestMode)

	handler := NewHealthHandler()

	router := gin.New()
	router.GET("/health", handler.Health)

	// Выполняем несколько запросов подряд
	for i := 0; i < 5; i++ {
		req, err := http.NewRequest("GET", "/health", nil)
		require.NoError(t, err)

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)

		var response models.HealthResponse
		err = json.Unmarshal(w.Body.Bytes(), &response)
		require.NoError(t, err)

		assert.Equal(t, "healthy", response.Status)
	}
}

func TestHealthHandler_Health_WithDifferentHTTPMethods(t *testing.T) {
	gin.SetMode(gin.TestMode)

	handler := NewHealthHandler()

	router := gin.New()
	router.GET("/health", handler.Health)

	tests := []struct {
		name           string
		method         string
		expectedStatus int
	}{
		{"GET method", "GET", http.StatusOK},
		{"POST method", "POST", http.StatusNotFound}, // Gin вернет 404 для неподдерживаемого метода
		{"PUT method", "PUT", http.StatusNotFound},
		{"DELETE method", "DELETE", http.StatusNotFound},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, err := http.NewRequest(tt.method, "/health", nil)
			require.NoError(t, err)

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}

func TestHealthResponse_Model(t *testing.T) {
	response := models.HealthResponse{
		Status:  "healthy",
		Service: "test-service",
		Version: "1.0.0",
	}

	assert.Equal(t, "healthy", response.Status)
	assert.Equal(t, "test-service", response.Service)
	assert.Equal(t, "1.0.0", response.Version)
}

package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/command-center-1c/cluster-service/internal/api/handlers"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap/zaptest"
)

func TestSetupRouter(t *testing.T) {
	logger := zaptest.NewLogger(t)
	monitoringHandler := handlers.NewMonitoringHandler(nil, 10*time.Second, logger)

	router := SetupRouter(monitoringHandler, logger)

	assert.NotNil(t, router)
}

func TestSetupRouter_HealthEndpoint(t *testing.T) {
	logger := zaptest.NewLogger(t)
	monitoringHandler := handlers.NewMonitoringHandler(nil, 10*time.Second, logger)

	router := SetupRouter(monitoringHandler, logger)

	req, err := http.NewRequest("GET", "/health", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "healthy")
}

func TestSetupRouter_APIv1Routes(t *testing.T) {
	logger := zaptest.NewLogger(t)
	monitoringHandler := handlers.NewMonitoringHandler(nil, 10*time.Second, logger)

	router := SetupRouter(monitoringHandler, logger)

	tests := []struct {
		name           string
		path           string
		expectedStatus int
	}{
		{
			name:           "GET /api/v1/clusters without server param",
			path:           "/api/v1/clusters",
			expectedStatus: http.StatusBadRequest, // Missing server param
		},
		{
			name:           "GET /api/v1/infobases without server param",
			path:           "/api/v1/infobases",
			expectedStatus: http.StatusBadRequest, // Missing server param
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, err := http.NewRequest("GET", tt.path, nil)
			require.NoError(t, err)

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}

func TestSetupRouter_Middleware(t *testing.T) {
	logger := zaptest.NewLogger(t)
	monitoringHandler := handlers.NewMonitoringHandler(nil, 10*time.Second, logger)

	router := SetupRouter(monitoringHandler, logger)

	// Проверяем что middleware применены (Recovery и Logger)
	req, err := http.NewRequest("GET", "/health", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Если middleware применены, запрос должен пройти успешно
	assert.Equal(t, http.StatusOK, w.Code)
}

func TestSetupRouter_NotFoundRoute(t *testing.T) {
	logger := zaptest.NewLogger(t)
	monitoringHandler := handlers.NewMonitoringHandler(nil, 10*time.Second, logger)

	router := SetupRouter(monitoringHandler, logger)

	req, err := http.NewRequest("GET", "/non-existent", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Gin вернет 404 для несуществующего route
	assert.Equal(t, http.StatusNotFound, w.Code)
}

func TestSetupRouter_MultipleRequests(t *testing.T) {
	logger := zaptest.NewLogger(t)
	monitoringHandler := handlers.NewMonitoringHandler(nil, 10*time.Second, logger)

	router := SetupRouter(monitoringHandler, logger)

	// Проверяем что router может обрабатывать множественные запросы
	for i := 0; i < 10; i++ {
		req, err := http.NewRequest("GET", "/health", nil)
		require.NoError(t, err)

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
	}
}

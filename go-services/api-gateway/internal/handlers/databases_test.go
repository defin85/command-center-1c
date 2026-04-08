package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/commandcenter1c/commandcenter/api-gateway/internal/middleware"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestProxyToOrchestratorV2_ProxyFailureIncludesCorrelationPayload(t *testing.T) {
	gin.SetMode(gin.TestMode)

	previousURL := orchestratorURL
	orchestratorURL = "http://127.0.0.1:1"
	t.Cleanup(func() {
		orchestratorURL = previousURL
	})

	router := gin.New()
	router.Use(middleware.LoggerMiddleware())
	router.GET("/api/v2/test", ProxyToOrchestratorV2)

	req := httptest.NewRequest(http.MethodGet, "/api/v2/test", nil)
	req.Header.Set("X-Request-ID", "req-ui-1")
	req.Header.Set("X-UI-Action-ID", "uia-1")
	w := httptest.NewRecorder()

	router.ServeHTTP(w, req)

	require.Equal(t, http.StatusBadGateway, w.Code)
	assert.Equal(t, "req-ui-1", w.Header().Get("X-Request-ID"))
	assert.Equal(t, "uia-1", w.Header().Get("X-UI-Action-ID"))

	var payload map[string]string
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &payload))
	assert.Equal(t, "Failed to proxy request to Orchestrator", payload["error"])
	assert.Equal(t, "req-ui-1", payload["request_id"])
	assert.Equal(t, "uia-1", payload["ui_action_id"])
}

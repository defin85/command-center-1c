package routes

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

func TestServiceUnavailableHandler_ReturnsCorrelatedPayload(t *testing.T) {
	router := gin.New()
	router.Use(middleware.LoggerMiddleware())
	router.GET("/api/v2/tracing/test", serviceUnavailableHandler("Jaeger"))

	req := httptest.NewRequest(http.MethodGet, "/api/v2/tracing/test", nil)
	req.Header.Set("X-Request-ID", "req-ui-jaeger")
	req.Header.Set("X-UI-Action-ID", "uia-jaeger")
	resp := httptest.NewRecorder()
	router.ServeHTTP(resp, req)

	require.Equal(t, http.StatusServiceUnavailable, resp.Code)
	assert.Equal(t, "req-ui-jaeger", resp.Header().Get("X-Request-ID"))
	assert.Equal(t, "uia-jaeger", resp.Header().Get("X-UI-Action-ID"))

	var payload map[string]string
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &payload))
	assert.Equal(t, "Jaeger service unavailable", payload["error"])
	assert.Equal(t, "SERVICE_UNAVAILABLE", payload["code"])
	assert.Equal(t, "req-ui-jaeger", payload["request_id"])
	assert.Equal(t, "uia-jaeger", payload["ui_action_id"])
}

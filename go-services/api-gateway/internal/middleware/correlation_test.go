package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCorrelatedErrorPayloadFromHTTP_PreservesCorrelationAndSanitizesMessage(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/v2/test", nil)
	req.Header.Set("X-Request-ID", "req-ui-1")
	req.Header.Set("X-UI-Action-ID", "uia-1")
	w := httptest.NewRecorder()

	payload := CorrelatedErrorPayloadFromHTTP(w, req, "token=super-secret password=hunter2", gin.H{
		"code": "UPSTREAM_UNAVAILABLE",
	})

	assert.Equal(t, "req-ui-1", w.Header().Get("X-Request-ID"))
	assert.Equal(t, "uia-1", w.Header().Get("X-UI-Action-ID"))
	assert.Equal(t, "token=[redacted] password=[redacted]", payload["error"])
	assert.Equal(t, "req-ui-1", payload["request_id"])
	assert.Equal(t, "uia-1", payload["ui_action_id"])
	assert.Equal(t, "UPSTREAM_UNAVAILABLE", payload["code"])
}

func TestRateLimitMiddleware_ReturnsCorrelatedErrorPayload(t *testing.T) {
	limiter = nil

	router := gin.New()
	router.Use(LoggerMiddleware())
	router.Use(RateLimitMiddleware(1, time.Minute))
	router.GET("/api/v2/test/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	firstReq := httptest.NewRequest(http.MethodGet, "/api/v2/test/", nil)
	firstReq.Header.Set("X-Request-ID", "req-ui-2")
	firstReq.Header.Set("X-UI-Action-ID", "uia-2")
	firstResp := httptest.NewRecorder()
	router.ServeHTTP(firstResp, firstReq)
	require.Equal(t, http.StatusOK, firstResp.Code)

	secondReq := httptest.NewRequest(http.MethodGet, "/api/v2/test/", nil)
	secondReq.Header.Set("X-Request-ID", "req-ui-2")
	secondReq.Header.Set("X-UI-Action-ID", "uia-2")
	secondResp := httptest.NewRecorder()
	router.ServeHTTP(secondResp, secondReq)

	require.Equal(t, http.StatusTooManyRequests, secondResp.Code)
	assert.Equal(t, "req-ui-2", secondResp.Header().Get("X-Request-ID"))
	assert.Equal(t, "uia-2", secondResp.Header().Get("X-UI-Action-ID"))

	var payload map[string]string
	require.NoError(t, json.Unmarshal(secondResp.Body.Bytes(), &payload))
	assert.Equal(t, "Rate limit exceeded", payload["error"])
	assert.Equal(t, "req-ui-2", payload["request_id"])
	assert.Equal(t, "uia-2", payload["ui_action_id"])
}

func TestAPIKeyMiddleware_ReturnsCorrelatedErrorPayload(t *testing.T) {
	router := gin.New()
	router.Use(LoggerMiddleware())
	router.Use(APIKeyMiddleware("valid-key"))
	router.GET("/api/v2/test/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v2/test/", nil)
	req.Header.Set("X-API-Key", "invalid-key")
	req.Header.Set("X-Request-ID", "req-ui-3")
	req.Header.Set("X-UI-Action-ID", "uia-3")
	resp := httptest.NewRecorder()
	router.ServeHTTP(resp, req)

	require.Equal(t, http.StatusUnauthorized, resp.Code)
	assert.Equal(t, "req-ui-3", resp.Header().Get("X-Request-ID"))
	assert.Equal(t, "uia-3", resp.Header().Get("X-UI-Action-ID"))

	var payload map[string]string
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &payload))
	assert.Equal(t, "Invalid API key", payload["error"])
	assert.Equal(t, "req-ui-3", payload["request_id"])
	assert.Equal(t, "uia-3", payload["ui_action_id"])
}

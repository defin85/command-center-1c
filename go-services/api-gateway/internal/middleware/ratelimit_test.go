package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestRateLimitMiddleware_IsolatesBudgetsByClass(t *testing.T) {
	router := gin.New()
	router.Use(func(c *gin.Context) {
		c.Set("user_id", "user-1")
		c.Next()
	})

	background := router.Group("")
	background.Use(RateLimitMiddleware(
		config.GatewayRateLimitClassBackground,
		config.GatewayRateLimitBudget{Requests: 1, Window: time.Minute},
	))
	background.GET("/api/v2/background/", func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	shell := router.Group("")
	shell.Use(RateLimitMiddleware(
		config.GatewayRateLimitClassShellCritical,
		config.GatewayRateLimitBudget{Requests: 1, Window: time.Minute},
	))
	shell.GET("/api/v2/system/bootstrap/", func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	firstBackground := httptest.NewRecorder()
	firstBackgroundReq := httptest.NewRequest(http.MethodGet, "/api/v2/background/", nil)
	firstBackgroundReq.Header.Set("X-CC1C-Tenant-ID", "tenant-a")
	router.ServeHTTP(firstBackground, firstBackgroundReq)
	require.Equal(t, http.StatusOK, firstBackground.Code)

	secondBackground := httptest.NewRecorder()
	secondBackgroundReq := httptest.NewRequest(http.MethodGet, "/api/v2/background/", nil)
	secondBackgroundReq.Header.Set("X-CC1C-Tenant-ID", "tenant-a")
	router.ServeHTTP(secondBackground, secondBackgroundReq)
	require.Equal(t, http.StatusTooManyRequests, secondBackground.Code)

	shellResp := httptest.NewRecorder()
	shellReq := httptest.NewRequest(http.MethodGet, "/api/v2/system/bootstrap/", nil)
	shellReq.Header.Set("X-CC1C-Tenant-ID", "tenant-a")
	router.ServeHTTP(shellResp, shellReq)
	require.Equal(t, http.StatusOK, shellResp.Code)
}

func TestRateLimitMiddleware_IsolatesBudgetsByTenant(t *testing.T) {
	router := gin.New()
	router.Use(func(c *gin.Context) {
		c.Set("user_id", "user-1")
		c.Next()
	})

	background := router.Group("")
	background.Use(RateLimitMiddleware(
		config.GatewayRateLimitClassBackground,
		config.GatewayRateLimitBudget{Requests: 1, Window: time.Minute},
	))
	background.GET("/api/v2/background/", func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	firstTenantA := httptest.NewRecorder()
	firstTenantAReq := httptest.NewRequest(http.MethodGet, "/api/v2/background/", nil)
	firstTenantAReq.Header.Set("X-CC1C-Tenant-ID", "tenant-a")
	router.ServeHTTP(firstTenantA, firstTenantAReq)
	require.Equal(t, http.StatusOK, firstTenantA.Code)

	secondTenantA := httptest.NewRecorder()
	secondTenantAReq := httptest.NewRequest(http.MethodGet, "/api/v2/background/", nil)
	secondTenantAReq.Header.Set("X-CC1C-Tenant-ID", "tenant-a")
	router.ServeHTTP(secondTenantA, secondTenantAReq)
	require.Equal(t, http.StatusTooManyRequests, secondTenantA.Code)

	tenantB := httptest.NewRecorder()
	tenantBReq := httptest.NewRequest(http.MethodGet, "/api/v2/background/", nil)
	tenantBReq.Header.Set("X-CC1C-Tenant-ID", "tenant-b")
	router.ServeHTTP(tenantB, tenantBReq)
	require.Equal(t, http.StatusOK, tenantB.Code)
}

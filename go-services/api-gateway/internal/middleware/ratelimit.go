package middleware

import (
	"fmt"
	"math"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/sirupsen/logrus"
)

var gatewayRateLimitDecisionsTotal = promauto.NewCounterVec(
	prometheus.CounterOpts{
		Name: "cc1c_api_gateway_rate_limit_decisions_total",
		Help: "Gateway request budget allow/deny decisions by workload class.",
	},
	[]string{"rate_limit_class", "verdict"},
)

type rateLimiter struct {
	visitors map[string]*visitor
	mu       sync.Mutex
	rate     int
	window   time.Duration
}

type visitor struct {
	tokens    int
	lastReset time.Time
}

type budgetScope struct {
	TenantID    string
	Principal   string
	BudgetClass config.GatewayRateLimitClass
}

func (scope budgetScope) key() string {
	return strings.Join([]string{scope.TenantID, scope.Principal, string(scope.BudgetClass)}, "|")
}

func (scope budgetScope) label() string {
	return fmt.Sprintf("tenant=%s;principal=%s;class=%s", scope.TenantID, scope.Principal, scope.BudgetClass)
}

// RateLimitMiddleware creates a class-aware request budget middleware.
func RateLimitMiddleware(
	budgetClass config.GatewayRateLimitClass,
	budget config.GatewayRateLimitBudget,
) gin.HandlerFunc {
	limiter := &rateLimiter{
		visitors: make(map[string]*visitor),
		rate:     budget.Requests,
		window:   budget.Window,
	}

	go limiter.cleanup()

	return func(c *gin.Context) {
		scope := resolveBudgetScope(c, budgetClass)
		allowed, retryAfter := limiter.allow(scope.key())
		if allowed {
			gatewayRateLimitDecisionsTotal.WithLabelValues(string(budgetClass), "allow").Inc()
			c.Next()
			return
		}

		gatewayRateLimitDecisionsTotal.WithLabelValues(string(budgetClass), "deny").Inc()

		requestID, uiActionID := ensureRequestCorrelation(c)
		retryAfterSeconds := int(math.Ceil(retryAfter.Seconds()))
		if retryAfterSeconds < 1 {
			retryAfterSeconds = 1
		}
		c.Header("Retry-After", strconv.Itoa(retryAfterSeconds))

		logger.WithFields(logrus.Fields{
			"request_id":          requestID,
			"ui_action_id":        uiActionID,
			"method":              c.Request.Method,
			"path":                c.Request.URL.Path,
			"rate_limit_class":    string(budgetClass),
			"retry_after_seconds": retryAfterSeconds,
			"budget_scope":        scope.label(),
		}).Warn("API request exceeded gateway request budget")

		c.JSON(http.StatusTooManyRequests, buildCorrelatedErrorPayload(requestID, uiActionID, "Rate limit exceeded", gin.H{
			"code":                "RATE_LIMIT_EXCEEDED",
			"rate_limit_class":    string(budgetClass),
			"retry_after_seconds": retryAfterSeconds,
			"budget_scope":        scope.label(),
		}))
		c.Abort()
	}
}

func (rl *rateLimiter) allow(clientID string) (bool, time.Duration) {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	v, exists := rl.visitors[clientID]

	if !exists {
		rl.visitors[clientID] = &visitor{
			tokens:    rl.rate - 1,
			lastReset: now,
		}
		return true, 0
	}

	if now.Sub(v.lastReset) >= rl.window {
		v.tokens = rl.rate
		v.lastReset = now
	}

	if v.tokens > 0 {
		v.tokens--
		return true, 0
	}

	retryAfter := rl.window - now.Sub(v.lastReset)
	if retryAfter < 0 {
		retryAfter = 0
	}
	return false, retryAfter
}

func (rl *rateLimiter) cleanup() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		rl.mu.Lock()
		now := time.Now()
		for id, v := range rl.visitors {
			if now.Sub(v.lastReset) > rl.window*2 {
				delete(rl.visitors, id)
			}
		}
		rl.mu.Unlock()
	}
}

func resolveBudgetScope(c *gin.Context, budgetClass config.GatewayRateLimitClass) budgetScope {
	return budgetScope{
		TenantID:    resolveTenantID(c),
		Principal:   resolvePrincipalID(c),
		BudgetClass: budgetClass,
	}
}

func resolveTenantID(c *gin.Context) string {
	if tenantID := strings.TrimSpace(c.GetHeader("X-CC1C-Tenant-ID")); tenantID != "" {
		return tenantID
	}
	return "tenant:unknown"
}

func resolvePrincipalID(c *gin.Context) string {
	if userID, exists := c.Get("user_id"); exists {
		if uid, ok := userID.(string); ok && strings.TrimSpace(uid) != "" {
			return "user:" + strings.TrimSpace(uid)
		}
	}

	if ip := strings.TrimSpace(c.ClientIP()); ip != "" {
		return "ip:" + ip
	}
	return "ip:unknown"
}

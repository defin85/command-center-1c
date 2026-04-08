package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

// Simple in-memory rate limiter
// TODO: Replace with Redis-based rate limiter for production

type rateLimiter struct {
	visitors map[string]*visitor
	mu       sync.RWMutex
	rate     int
	window   time.Duration
}

type visitor struct {
	tokens    int
	lastReset time.Time
}

var limiter *rateLimiter

// RateLimitMiddleware creates rate limiting middleware
func RateLimitMiddleware(requestsPerWindow int, window time.Duration) gin.HandlerFunc {
	if limiter == nil {
		limiter = &rateLimiter{
			visitors: make(map[string]*visitor),
			rate:     requestsPerWindow,
			window:   window,
		}

		// Cleanup old visitors every 5 minutes
		go limiter.cleanup()
	}

	return func(c *gin.Context) {
		// Get client identifier (user_id or IP)
		clientID := getClientID(c)

		if !limiter.allow(clientID) {
			c.JSON(http.StatusTooManyRequests, CorrelatedErrorPayload(c, "Rate limit exceeded", nil))
			c.Abort()
			return
		}

		c.Next()
	}
}

func (rl *rateLimiter) allow(clientID string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	v, exists := rl.visitors[clientID]

	if !exists {
		rl.visitors[clientID] = &visitor{
			tokens:    rl.rate - 1,
			lastReset: now,
		}
		return true
	}

	// Reset tokens if window has passed
	if now.Sub(v.lastReset) > rl.window {
		v.tokens = rl.rate
		v.lastReset = now
	}

	if v.tokens > 0 {
		v.tokens--
		return true
	}

	return false
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

func getClientID(c *gin.Context) string {
	// Try to get user_id from context (set by auth middleware)
	if userID, exists := c.Get("user_id"); exists {
		if uid, ok := userID.(string); ok {
			return uid
		}
	}

	// Fallback to IP address
	return c.ClientIP()
}

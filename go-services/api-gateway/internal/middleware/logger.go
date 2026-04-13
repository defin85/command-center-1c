package middleware

import (
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"
)

var skippedAccessLogPaths = map[string]struct{}{
	"/metrics": {},
}

// LoggerMiddleware logs HTTP requests
func LoggerMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		requestID, uiActionID := ensureRequestCorrelation(c)
		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method

		// Process request
		c.Next()

		if shouldSkipAccessLog(path) {
			return
		}

		// Calculate latency
		latency := time.Since(start)
		statusCode := c.Writer.Status()

		// Log with structured fields
		logger.WithFields(logrus.Fields{
			"method":       method,
			"path":         path,
			"status":       statusCode,
			"latency_ms":   latency.Milliseconds(),
			"ip":           c.ClientIP(),
			"user_agent":   c.Request.UserAgent(),
			"request_id":   requestID,
			"ui_action_id": uiActionID,
		}).Info("HTTP request")
	}
}

func shouldSkipAccessLog(path string) bool {
	_, skip := skippedAccessLogPaths[path]
	return skip
}

// CORSConfig holds CORS configuration
type CORSConfig struct {
	AllowedOrigins []string
}

// CORSMiddleware handles CORS headers
// IMPORTANT: Allow-Origin: * + Allow-Credentials: true is FORBIDDEN by CORS spec
// We must echo the exact origin if it's in the allowed list
func CORSMiddleware(cfg *CORSConfig) gin.HandlerFunc {
	// Build a map for O(1) lookup
	allowedMap := make(map[string]bool)
	for _, origin := range cfg.AllowedOrigins {
		allowedMap[origin] = true
	}

	return func(c *gin.Context) {
		origin := c.Request.Header.Get("Origin")

		// Check if origin is allowed
		if origin != "" && allowedMap[origin] {
			// Echo exact origin (NOT wildcard) when credentials are used
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		} else if origin == "" {
			// Same-origin requests (no Origin header) - allow for API calls from same domain
			c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		}
		// If origin is set but not in allowed list - don't set CORS headers (browser will block)

		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, Last-Event-ID, X-Request-ID, X-UI-Action-ID, X-CC1C-Locale, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "X-Request-ID, X-UI-Action-ID")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE, PATCH")
		c.Writer.Header().Set("Access-Control-Max-Age", "86400") // 24 hours preflight cache

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

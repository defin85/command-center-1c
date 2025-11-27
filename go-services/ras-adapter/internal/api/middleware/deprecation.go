package middleware

import (
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// Default sunset date in RFC 7231 format
// Can be overridden via API_V1_SUNSET_DATE environment variable
const defaultSunsetDate = "Sun, 01 Mar 2026 00:00:00 GMT"

// DeprecationConfig holds configuration for the deprecation middleware
type DeprecationConfig struct {
	SunsetDate       string // RFC 7231 date (e.g., "Sun, 01 Mar 2026 00:00:00 GMT")
	SuccessorVersion string // e.g., "/api/v2"
	Logger           *zap.Logger
}

// Deprecation returns middleware that adds deprecation headers to v1 API responses
// and logs warnings about deprecated API usage.
//
// Headers added:
// - Deprecation: true
// - Sunset: <date> (when the API will be removed, RFC 7231 format)
// - Link: </api/v2>; rel="successor-version"
func Deprecation(config DeprecationConfig) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Add deprecation headers
		c.Header("Deprecation", "true")

		if config.SunsetDate != "" {
			c.Header("Sunset", config.SunsetDate)
		}

		if config.SuccessorVersion != "" {
			c.Header("Link", "<"+config.SuccessorVersion+">; rel=\"successor-version\"")
		}

		// Log warning about deprecated API usage
		if config.Logger != nil {
			config.Logger.Warn("deprecated v1 API called",
				zap.String("method", c.Request.Method),
				zap.String("path", c.Request.URL.Path),
				zap.String("client_ip", c.ClientIP()),
				zap.String("user_agent", c.Request.UserAgent()),
				zap.String("sunset_date", config.SunsetDate),
			)
		}

		c.Next()
	}
}

// DefaultDeprecationConfig returns the default deprecation configuration
// for ras-adapter v1 API.
// Reads sunset date from API_V1_SUNSET_DATE environment variable if set,
// otherwise uses the default date.
func DefaultDeprecationConfig(logger *zap.Logger) DeprecationConfig {
	sunsetDate := getSunsetDateFromEnv()

	return DeprecationConfig{
		SunsetDate:       sunsetDate,
		SuccessorVersion: "/api/v2",
		Logger:           logger,
	}
}

// getSunsetDateFromEnv reads the sunset date from environment variable.
// Supports both RFC 7231 format and simple YYYY-MM-DD format (auto-converts).
// Returns default date if not set or invalid.
func getSunsetDateFromEnv() string {
	envDate := os.Getenv("API_V1_SUNSET_DATE")
	if envDate == "" {
		return defaultSunsetDate
	}

	// Try parsing as RFC 7231 first (already correct format)
	if _, err := time.Parse(time.RFC1123, envDate); err == nil {
		return envDate
	}

	// Try parsing as simple date format (YYYY-MM-DD) and convert to RFC 7231
	if t, err := time.Parse("2006-01-02", envDate); err == nil {
		return t.Format(time.RFC1123)
	}

	// If parsing fails, return the value as-is (caller's responsibility)
	return envDate
}

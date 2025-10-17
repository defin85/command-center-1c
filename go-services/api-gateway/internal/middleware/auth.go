package middleware

import (
	"github.com/gin-gonic/gin"
)

// Auth middleware is handled by shared/auth package
// This file is a placeholder for any additional auth-related middleware

// Example: API Key authentication (if needed in addition to JWT)
func APIKeyMiddleware(validAPIKey string) gin.HandlerFunc {
	return func(c *gin.Context) {
		apiKey := c.GetHeader("X-API-Key")

		if apiKey == "" {
			c.Next() // API key is optional, JWT auth will handle it
			return
		}

		if apiKey != validAPIKey {
			c.JSON(401, gin.H{"error": "Invalid API key"})
			c.Abort()
			return
		}

		c.Set("api_key_valid", true)
		c.Next()
	}
}

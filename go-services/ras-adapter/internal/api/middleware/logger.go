package middleware

import (
	"net/url"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func sanitizeQuery(query string) string {
	if query == "" {
		return ""
	}

	// Список чувствительных параметров для маскирования
	sensitive := []string{"password", "token", "secret", "api_key", "apikey", "auth"}

	values, err := url.ParseQuery(query)
	if err != nil {
		// Если не можем распарсить - возвращаем как есть
		return query
	}

	// Маскируем чувствительные параметры
	for _, key := range sensitive {
		for k := range values {
			// Case-insensitive поиск
			if len(k) >= len(key) {
				kLower := ""
				for _, c := range k {
					if c >= 'A' && c <= 'Z' {
						kLower += string(c + 32)
					} else {
						kLower += string(c)
					}
				}
				if kLower == key {
					values.Set(k, "***")
				}
			}
		}
	}

	return values.Encode()
}

func Logger(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		query := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)

		logger.Info("request completed",
			zap.String("method", c.Request.Method),
			zap.String("path", path),
			zap.String("query", sanitizeQuery(query)),
			zap.Int("status", c.Writer.Status()),
			zap.Duration("latency", latency),
			zap.String("client_ip", c.ClientIP()),
		)
	}
}

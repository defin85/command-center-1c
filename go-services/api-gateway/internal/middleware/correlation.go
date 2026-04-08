package middleware

import (
	"regexp"
	"strings"

	"github.com/google/uuid"
	"github.com/gin-gonic/gin"
)

const (
	headerRequestID  = "X-Request-ID"
	headerUIActionID = "X-UI-Action-ID"
)

var correlationValuePattern = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,160}$`)

func normalizeCorrelationValue(raw string) string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" || !correlationValuePattern.MatchString(trimmed) {
		return ""
	}
	return trimmed
}

func ensureRequestCorrelation(c *gin.Context) (string, string) {
	requestID := normalizeCorrelationValue(c.GetHeader(headerRequestID))
	if requestID == "" {
		requestID = "req-" + uuid.NewString()
	}

	uiActionID := normalizeCorrelationValue(c.GetHeader(headerUIActionID))

	c.Request.Header.Set(headerRequestID, requestID)
	c.Writer.Header().Set(headerRequestID, requestID)
	if uiActionID != "" {
		c.Request.Header.Set(headerUIActionID, uiActionID)
		c.Writer.Header().Set(headerUIActionID, uiActionID)
	} else {
		c.Request.Header.Del(headerUIActionID)
		c.Writer.Header().Del(headerUIActionID)
	}

	return requestID, uiActionID
}

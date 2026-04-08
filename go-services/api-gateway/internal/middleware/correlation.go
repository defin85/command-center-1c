package middleware

import (
	"net/http"
	"regexp"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

const (
	headerRequestID  = "X-Request-ID"
	headerUIActionID = "X-UI-Action-ID"
)

var correlationValuePattern = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,160}$`)
var sensitiveDiagnosticValuePattern = regexp.MustCompile(`(?i)\b(password|passwd|pwd|token|authorization|secret|cookie|api[_-]?key|access[_-]?key)\b\s*[:=]\s*([^\s,;]+)`)

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

func ensureHTTPCorrelation(w http.ResponseWriter, req *http.Request) (string, string) {
	requestID := ""
	uiActionID := ""
	if req != nil {
		requestID = normalizeCorrelationValue(req.Header.Get(headerRequestID))
		uiActionID = normalizeCorrelationValue(req.Header.Get(headerUIActionID))
	}
	if requestID == "" {
		requestID = "req-" + uuid.NewString()
	}

	if req != nil {
		req.Header.Set(headerRequestID, requestID)
		if uiActionID != "" {
			req.Header.Set(headerUIActionID, uiActionID)
		} else {
			req.Header.Del(headerUIActionID)
		}
	}
	if w != nil {
		w.Header().Set(headerRequestID, requestID)
		if uiActionID != "" {
			w.Header().Set(headerUIActionID, uiActionID)
		} else {
			w.Header().Del(headerUIActionID)
		}
	}

	return requestID, uiActionID
}

func sanitizeDiagnosticText(raw string) string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return ""
	}
	redacted := sensitiveDiagnosticValuePattern.ReplaceAllString(trimmed, `$1=[redacted]`)
	if len(redacted) > 512 {
		return redacted[:509] + "..."
	}
	return redacted
}

func buildCorrelatedErrorPayload(requestID, uiActionID, message string, extra gin.H) gin.H {
	payload := gin.H{
		"error":      sanitizeDiagnosticText(message),
		"request_id": requestID,
	}
	if uiActionID != "" {
		payload["ui_action_id"] = uiActionID
	}
	for key, value := range extra {
		if textValue, ok := value.(string); ok {
			payload[key] = sanitizeDiagnosticText(textValue)
			continue
		}
		payload[key] = value
	}
	return payload
}

func CorrelatedErrorPayload(c *gin.Context, message string, extra gin.H) gin.H {
	requestID, uiActionID := ensureRequestCorrelation(c)
	return buildCorrelatedErrorPayload(requestID, uiActionID, message, extra)
}

func CorrelatedErrorPayloadFromHTTP(w http.ResponseWriter, req *http.Request, message string, extra gin.H) gin.H {
	requestID, uiActionID := ensureHTTPCorrelation(w, req)
	return buildCorrelatedErrorPayload(requestID, uiActionID, message, extra)
}

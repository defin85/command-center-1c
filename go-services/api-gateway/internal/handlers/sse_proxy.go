package handlers

import (
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// SSEOperationStreamProxy proxies SSE stream for operations to Django Orchestrator
// GET /api/v2/operations/stream/?operation_id=xxx&token=xxx
func SSEOperationStreamProxy(c *gin.Context) {
	log := logger.GetLogger()

	operationID := c.Query("operation_id")
	token := c.Query("token")

	if operationID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "operation_id is required"})
		return
	}

	// Build upstream URL
	target, err := url.Parse(orchestratorURL)
	if err != nil {
		log.Error("Failed to parse orchestrator URL",
			zap.String("url", orchestratorURL),
			zap.Error(err),
		)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal configuration error"})
		return
	}

	// Build query string
	queryParams := url.Values{}
	queryParams.Set("operation_id", operationID)
	if token != "" {
		queryParams.Set("token", token)
	}

	proxy := &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			req.URL.Scheme = target.Scheme
			req.URL.Host = target.Host
			req.URL.Path = "/api/v2/operations/stream/"
			req.URL.RawQuery = queryParams.Encode()
			req.Host = target.Host

			// Forward X-Forwarded-For header
			if clientIP := c.ClientIP(); clientIP != "" {
				existing := req.Header.Get("X-Forwarded-For")
				if existing != "" {
					req.Header.Set("X-Forwarded-For", existing+", "+clientIP)
				} else {
					req.Header.Set("X-Forwarded-For", clientIP)
				}
			}

			// Forward Authorization header if present
			if auth := c.GetHeader("Authorization"); auth != "" {
				req.Header.Set("Authorization", auth)
			}

			log.Debug("SSE proxy request",
				zap.String("operation_id", operationID),
				zap.String("target", req.URL.String()),
			)
		},
		// CRITICAL: FlushInterval enables streaming for SSE
		FlushInterval: 100 * time.Millisecond,
		ModifyResponse: func(resp *http.Response) error {
			// Disable buffering for SSE
			resp.Header.Set("X-Accel-Buffering", "no")
			resp.Header.Set("Cache-Control", "no-cache")
			return nil
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			log.Error("SSE proxy error",
				zap.String("operation_id", operationID),
				zap.Error(err),
			)
			w.WriteHeader(http.StatusBadGateway)
			io.WriteString(w, `{"error": "SSE upstream unavailable"}`)
		},
	}

	proxy.ServeHTTP(c.Writer, c.Request)
}

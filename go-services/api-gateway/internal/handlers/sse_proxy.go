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

// SSEOperationStreamProxy proxies SSE streams to Django Orchestrator.
// Supports ticket-based auth for /api/v2/*/stream/ endpoints.
func SSEOperationStreamProxy(c *gin.Context) {
	log := logger.GetLogger()

	operationID := c.Query("operation_id")
	hasTicket := c.Query("ticket") != ""
	targetPath := c.Request.URL.Path
	rawQuery := c.Request.URL.RawQuery

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

	proxy := &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			req.URL.Scheme = target.Scheme
			req.URL.Host = target.Host
			req.URL.Path = targetPath
			req.URL.RawQuery = rawQuery
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
				zap.String("path", targetPath),
				zap.String("operation_id", operationID),
				zap.Bool("has_ticket", hasTicket),
				zap.String("target", req.URL.String()),
			)
		},
		// CRITICAL: FlushInterval enables streaming for SSE
		FlushInterval: 100 * time.Millisecond,
		ModifyResponse: func(resp *http.Response) error {
			// Prevent duplicate CORS headers from upstream
			resp.Header.Del("Access-Control-Allow-Origin")
			resp.Header.Del("Access-Control-Allow-Credentials")
			resp.Header.Del("Access-Control-Allow-Headers")
			resp.Header.Del("Access-Control-Allow-Methods")
			resp.Header.Del("Access-Control-Max-Age")

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

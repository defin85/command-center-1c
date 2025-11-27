package handlers

import (
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// RASProxyHandler handles reverse proxy to RAS Adapter service
type RASProxyHandler struct {
	targetURL *url.URL
	proxy     *httputil.ReverseProxy
}

// NewRASProxyHandler creates a new RAS Adapter proxy handler
func NewRASProxyHandler(rasAdapterURL string) (*RASProxyHandler, error) {
	targetURL, err := url.Parse(rasAdapterURL)
	if err != nil {
		return nil, err
	}

	proxy := httputil.NewSingleHostReverseProxy(targetURL)

	// Configure connection pooling for better performance
	transport := &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 20,
		IdleConnTimeout:     90 * time.Second,
		TLSHandshakeTimeout: 10 * time.Second,
	}
	proxy.Transport = transport

	// Customize director to transform paths
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)

		// Path is already /api/v2/* from gateway, RAS Adapter expects the same
		// No transformation needed since RAS Adapter already uses v2 paths

		logger.GetLogger().Debug("RAS proxy request",
			zap.String("method", req.Method),
			zap.String("path", req.URL.Path),
			zap.String("target", targetURL.String()),
		)
	}

	// Custom error handler
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		logger.GetLogger().Error("RAS proxy error",
			zap.Error(err),
			zap.String("path", r.URL.Path),
		)
		w.WriteHeader(http.StatusBadGateway)
		io.WriteString(w, `{"error": "RAS Adapter unavailable"}`)
	}

	// Modify response to add tracing headers if needed
	proxy.ModifyResponse = func(resp *http.Response) error {
		// Pass through X-Request-ID for tracing
		return nil
	}

	return &RASProxyHandler{
		targetURL: targetURL,
		proxy:     proxy,
	}, nil
}

// Handle proxies the request to RAS Adapter
func (h *RASProxyHandler) Handle(c *gin.Context) {
	// Copy authorization and other headers
	h.copyRequestHeaders(c)
	h.proxy.ServeHTTP(c.Writer, c.Request)
}

// copyRequestHeaders ensures important headers are passed through
func (h *RASProxyHandler) copyRequestHeaders(c *gin.Context) {
	// Note: Do not auto-set Content-Type - let the client control this
	// The upstream service should handle missing Content-Type appropriately

	// Add X-Forwarded headers
	if clientIP := c.ClientIP(); clientIP != "" {
		existing := c.Request.Header.Get("X-Forwarded-For")
		if existing != "" {
			c.Request.Header.Set("X-Forwarded-For", existing+", "+clientIP)
		} else {
			c.Request.Header.Set("X-Forwarded-For", clientIP)
		}
	}

	c.Request.Header.Set("X-Forwarded-Proto", "http")
	if c.Request.TLS != nil {
		c.Request.Header.Set("X-Forwarded-Proto", "https")
	}
}

// ProxyRASEndpoint creates a handler for specific RAS endpoint
// Useful when you need endpoint-specific logic
func (h *RASProxyHandler) ProxyRASEndpoint(endpoint string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Override path if needed
		if endpoint != "" && !strings.HasPrefix(c.Request.URL.Path, "/api/v2/"+endpoint) {
			c.Request.URL.Path = "/api/v2/" + endpoint
		}
		h.Handle(c)
	}
}

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

// JaegerProxyHandler handles reverse proxy to Jaeger UI/API
type JaegerProxyHandler struct {
	targetURL *url.URL
	proxy     *httputil.ReverseProxy
}

// NewJaegerProxyHandler creates a new Jaeger proxy handler
func NewJaegerProxyHandler(jaegerURL string) (*JaegerProxyHandler, error) {
	targetURL, err := url.Parse(jaegerURL)
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

		// Save original path before transformation for logging
		originalPath := req.URL.Path

		// Transform: /api/v2/tracing/* -> /api/*
		// Gateway receives: /api/v2/tracing/traces
		// Jaeger expects:   /api/traces
		if strings.HasPrefix(originalPath, "/api/v2/tracing") {
			req.URL.Path = strings.Replace(originalPath, "/api/v2/tracing", "/api", 1)
		}

		logger.GetLogger().Debug("Jaeger proxy request",
			zap.String("method", req.Method),
			zap.String("original_path", originalPath),
			zap.String("transformed_path", req.URL.Path),
			zap.String("target", targetURL.String()),
		)
	}

	// Custom error handler
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		logger.GetLogger().Error("Jaeger proxy error",
			zap.Error(err),
			zap.String("path", r.URL.Path),
		)
		w.WriteHeader(http.StatusBadGateway)
		io.WriteString(w, `{"error": "Jaeger unavailable"}`)
	}

	return &JaegerProxyHandler{
		targetURL: targetURL,
		proxy:     proxy,
	}, nil
}

// Handle proxies the request to Jaeger
func (h *JaegerProxyHandler) Handle(c *gin.Context) {
	// Add forwarding headers
	h.addForwardingHeaders(c)
	h.proxy.ServeHTTP(c.Writer, c.Request)
}

// addForwardingHeaders adds standard proxy headers
func (h *JaegerProxyHandler) addForwardingHeaders(c *gin.Context) {
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

package handlers

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/commandcenter1c/commandcenter/api-gateway/internal/middleware"
	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"github.com/commandcenter1c/commandcenter/shared/logger"
)

var orchestratorURL = getOrchestratorURL()

func correlatedErrorPayload(c *gin.Context, message string) gin.H {
	return middleware.CorrelatedErrorPayload(c, message, nil)
}

func getOrchestratorURL() string {
	url := os.Getenv("ORCHESTRATOR_URL")
	if url == "" {
		url = "http://localhost:8200"
	}
	return url
}

// ProxyToOrchestratorV2 proxies v2 API requests to Django Orchestrator
// V2 uses /api/v2/* paths and maintains the same path structure
func ProxyToOrchestratorV2(c *gin.Context) {
	// Get the full path - for v2 we keep the same structure
	path := c.Request.URL.Path

	// Remove /api/v2 prefix and map to Orchestrator's /api/v2
	path = strings.TrimPrefix(path, "/api/v2")

	// Django always requires trailing slash
	if !strings.HasSuffix(path, "/") {
		path += "/"
	}

	// Build URL to Orchestrator v2 API
	targetURL := orchestratorURL + "/api/v2" + path
	if c.Request.URL.RawQuery != "" {
		targetURL += "?" + c.Request.URL.RawQuery
	}

	// Read request body into buffer
	var bodyBytes []byte
	if c.Request.Body != nil {
		bodyBytes, _ = io.ReadAll(c.Request.Body)
		c.Request.Body.Close()
	}

	// Create new request with buffered body
	req, err := http.NewRequest(c.Request.Method, targetURL, bytes.NewReader(bodyBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, correlatedErrorPayload(c, "Failed to create request"))
		return
	}

	// Copy headers
	for key, values := range c.Request.Header {
		if key == "Host" || key == "Connection" {
			continue
		}
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Ensure Content-Type for POST/PUT
	if c.Request.Method == "POST" || c.Request.Method == "PUT" || c.Request.Method == "PATCH" {
		contentType := c.Request.Header.Get("Content-Type")
		if contentType != "" {
			req.Header.Set("Content-Type", contentType)
		}
		contentLength := c.Request.Header.Get("Content-Length")
		if contentLength != "" {
			req.Header.Set("Content-Length", contentLength)
		}
	}

	// Send request
	client := &http.Client{}
	start := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		c.JSON(http.StatusBadGateway, correlatedErrorPayload(c, "Failed to proxy request to Orchestrator"))
		return
	}
	defer resp.Body.Close()
	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			c.Header(key, value)
		}
	}

	// Copy response body
	c.Status(resp.StatusCode)
	if _, err := io.Copy(c.Writer, resp.Body); err != nil {
		logger.GetLogger().WithError(err).Warn("Failed to copy response body from Orchestrator")
	}
}

// ProxyToOrchestratorAuth proxies auth requests to Django Orchestrator
// This handler is for public endpoints (no JWT required)
func ProxyToOrchestratorAuth(c *gin.Context) {
	// Get the path (e.g., /api/token or /api/token/refresh)
	path := c.Request.URL.Path

	// Django always requires trailing slash
	if !strings.HasSuffix(path, "/") {
		path += "/"
	}

	// Build URL to Orchestrator
	targetURL := orchestratorURL + path
	if c.Request.URL.RawQuery != "" {
		targetURL += "?" + c.Request.URL.RawQuery
	}

	// Read request body into buffer
	var bodyBytes []byte
	if c.Request.Body != nil {
		bodyBytes, _ = io.ReadAll(c.Request.Body)
		c.Request.Body.Close()
	}

	// Create new request with buffered body
	req, err := http.NewRequest(c.Request.Method, targetURL, bytes.NewReader(bodyBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, correlatedErrorPayload(c, "Failed to create request"))
		return
	}

	// Copy headers
	for key, values := range c.Request.Header {
		if key == "Host" || key == "Connection" {
			continue
		}
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Ensure Content-Type for POST
	contentType := c.Request.Header.Get("Content-Type")
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}

	// Send request
	client := &http.Client{}
	start := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		c.JSON(http.StatusBadGateway, correlatedErrorPayload(c, "Failed to proxy auth request"))
		return
	}
	defer resp.Body.Close()
	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			c.Header(key, value)
		}
	}

	// Copy response body
	c.Status(resp.StatusCode)
	if _, err := io.Copy(c.Writer, resp.Body); err != nil {
		logger.GetLogger().WithError(err).Warn("Failed to copy response body from Orchestrator auth endpoint")
	}
}

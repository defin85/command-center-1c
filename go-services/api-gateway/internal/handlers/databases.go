package handlers

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/gin-gonic/gin"
)

var orchestratorURL = getOrchestratorURL()

func getOrchestratorURL() string {
	url := os.Getenv("ORCHESTRATOR_URL")
	if url == "" {
		url = "http://localhost:8200"
	}
	return url
}

// ProxyToOrchestrator proxies requests to Django Orchestrator
func ProxyToOrchestrator(c *gin.Context) {
	// Получаем полный путь после /api/v1/
	path := c.Request.URL.Path
	path = strings.TrimPrefix(path, "/api/v1")

	// Трансформируем /databases/clusters в /clusters для Django
	path = strings.Replace(path, "/databases/clusters", "/clusters", 1)

	// Django всегда требует trailing slash - добавляем если его нет
	if !strings.HasSuffix(path, "/") {
		path += "/"
	}

	// Строим URL к Orchestrator
	targetURL := orchestratorURL + "/api/v1" + path
	if c.Request.URL.RawQuery != "" {
		targetURL += "?" + c.Request.URL.RawQuery
	}

	// Читаем тело запроса в буфер (для multipart/form-data)
	var bodyBytes []byte
	if c.Request.Body != nil {
		bodyBytes, _ = io.ReadAll(c.Request.Body)
		c.Request.Body.Close()
	}

	// Создаем новый запрос с буферизованным телом
	req, err := http.NewRequest(c.Request.Method, targetURL, bytes.NewReader(bodyBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
		return
	}

	// Копируем заголовки (включая Content-Type для multipart/form-data)
	for key, values := range c.Request.Header {
		// Пропускаем заголовки, которые Go HTTP client добавит сам
		if key == "Host" || key == "Connection" {
			continue
		}
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Логируем важные заголовки для отладки
	if c.Request.Method == "POST" || c.Request.Method == "PUT" {
		contentType := c.Request.Header.Get("Content-Type")
		contentLength := c.Request.Header.Get("Content-Length")
		if contentType != "" {
			req.Header.Set("Content-Type", contentType)
		}
		if contentLength != "" {
			req.Header.Set("Content-Length", contentLength)
		}
	}

	// Отправляем запрос
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "Failed to proxy request"})
		return
	}
	defer resp.Body.Close()

	// Копируем заголовки ответа
	for key, values := range resp.Header {
		for _, value := range values {
			c.Header(key, value)
		}
	}

	// Копируем тело ответа
	c.Status(resp.StatusCode)
	io.Copy(c.Writer, resp.Body)
} // ListDatabases handles GET /databases
func ListDatabases(c *gin.Context) {
	ProxyToOrchestrator(c)
}

// GetDatabase handles GET /databases/:id
func GetDatabase(c *gin.Context) {
	ProxyToOrchestrator(c)
}

// CheckDatabaseHealth handles GET /databases/:id/health
func CheckDatabaseHealth(c *gin.Context) {
	ProxyToOrchestrator(c)
}

// ProxyToOrchestratorV2 proxies v2 API requests to Django Orchestrator
// V2 uses /api/v2/* paths and maintains the same path structure
func ProxyToOrchestratorV2(c *gin.Context) {
	// Get the full path - for v2 we keep the same structure
	path := c.Request.URL.Path

	// Remove /api/v2 prefix and map to Orchestrator's /api/v2
	path = strings.TrimPrefix(path, "/api/v2")

	// Handle wildcard paths (e.g., /operations/*path becomes /operations/...)
	// Gin uses *path param, we need to include it
	if wildcardPath := c.Param("path"); wildcardPath != "" {
		// Path already includes the wildcard portion from Gin
	}

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
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
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
	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "Failed to proxy request to Orchestrator"})
		return
	}
	defer resp.Body.Close()

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			c.Header(key, value)
		}
	}

	// Copy response body
	c.Status(resp.StatusCode)
	io.Copy(c.Writer, resp.Body)
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
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
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
	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "Failed to proxy auth request"})
		return
	}
	defer resp.Body.Close()

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			c.Header(key, value)
		}
	}

	// Copy response body
	c.Status(resp.StatusCode)
	io.Copy(c.Writer, resp.Body)
}

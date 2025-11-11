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
		url = "http://localhost:8000"
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

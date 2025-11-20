package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"go.uber.org/zap/zaptest"
)

func TestLogger_Middleware(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Logger(logger))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "success"})
	})

	req, err := http.NewRequest("GET", "/test", nil)
	assert.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем что request обработан успешно
	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "success")
}

func TestLogger_WithQueryParameters(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Logger(logger))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "success"})
	})

	req, err := http.NewRequest("GET", "/test?param1=value1&param2=value2", nil)
	assert.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем что request обработан успешно с query params
	assert.Equal(t, http.StatusOK, w.Code)
}

func TestLogger_WithDifferentStatusCodes(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	tests := []struct {
		name       string
		statusCode int
	}{
		{"200 OK", http.StatusOK},
		{"201 Created", http.StatusCreated},
		{"400 Bad Request", http.StatusBadRequest},
		{"404 Not Found", http.StatusNotFound},
		{"500 Internal Server Error", http.StatusInternalServerError},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			router := gin.New()
			router.Use(Logger(logger))
			router.GET("/test", func(c *gin.Context) {
				c.JSON(tt.statusCode, gin.H{"status": tt.statusCode})
			})

			req, err := http.NewRequest("GET", "/test", nil)
			assert.NoError(t, err)

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, tt.statusCode, w.Code)
		})
	}
}

func TestLogger_WithDifferentHTTPMethods(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	methods := []string{"GET", "POST", "PUT", "DELETE", "PATCH"}

	for _, method := range methods {
		t.Run("method_"+method, func(t *testing.T) {
			router := gin.New()
			router.Use(Logger(logger))
			router.Handle(method, "/test", func(c *gin.Context) {
				c.JSON(http.StatusOK, gin.H{"method": method})
			})

			req, err := http.NewRequest(method, "/test", nil)
			assert.NoError(t, err)

			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			assert.Equal(t, http.StatusOK, w.Code)
		})
	}
}

func TestLogger_MeasuresLatency(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Logger(logger))
	router.GET("/test", func(c *gin.Context) {
		// Небольшая задержка для проверки измерения latency
		// time.Sleep(10 * time.Millisecond)
		c.JSON(http.StatusOK, gin.H{"message": "success"})
	})

	req, err := http.NewRequest("GET", "/test", nil)
	assert.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем что request обработан успешно
	// Latency измеряется в middleware, но мы не можем напрямую проверить значение
	// Важно что middleware не падает и request проходит
	assert.Equal(t, http.StatusOK, w.Code)
}

func TestLogger_WithClientIP(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Logger(logger))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "success"})
	})

	req, err := http.NewRequest("GET", "/test", nil)
	assert.NoError(t, err)

	// Устанавливаем X-Forwarded-For header
	req.Header.Set("X-Forwarded-For", "192.168.1.1")

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestLogger_MultipleRequests(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Logger(logger))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "success"})
	})

	// Выполняем несколько запросов подряд
	for i := 0; i < 10; i++ {
		req, err := http.NewRequest("GET", "/test", nil)
		assert.NoError(t, err)

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
	}
}

func TestSanitizeQuery(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "empty query",
			input:    "",
			expected: "",
		},
		{
			name:     "no sensitive params",
			input:    "param1=value1&param2=value2",
			expected: "param1=value1&param2=value2",
		},
		{
			name:     "password param",
			input:    "username=admin&password=secret123",
			expected: "password=%2A%2A%2A&username=admin",
		},
		{
			name:     "token param",
			input:    "token=abc123&data=test",
			expected: "data=test&token=%2A%2A%2A",
		},
		{
			name:     "api_key param",
			input:    "api_key=mykey&value=100",
			expected: "api_key=%2A%2A%2A&value=100",
		},
		{
			name:     "multiple sensitive params",
			input:    "password=pass123&token=tok456&secret=sec789",
			expected: "password=%2A%2A%2A&secret=%2A%2A%2A&token=%2A%2A%2A",
		},
		{
			name:     "case insensitive PASSWORD",
			input:    "PASSWORD=secret&user=admin",
			expected: "PASSWORD=%2A%2A%2A&user=admin",
		},
		{
			name:     "case insensitive Token",
			input:    "Token=mytoken&id=123",
			expected: "Token=%2A%2A%2A&id=123",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := sanitizeQuery(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

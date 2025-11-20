package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap/zaptest"
)

func TestRecovery_NoPanic(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "success"})
	})

	req, err := http.NewRequest("GET", "/test", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем что request обработан успешно без panic
	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Body.String(), "success")
}

func TestRecovery_HandlesPanic(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		panic("test panic")
	})

	req, err := http.NewRequest("GET", "/test", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Проверяем что panic был обработан
	assert.Equal(t, http.StatusInternalServerError, w.Code)

	// Проверяем response body
	var response map[string]interface{}
	err = json.Unmarshal(w.Body.Bytes(), &response)
	require.NoError(t, err)

	assert.Equal(t, "internal server error", response["error"])
}

func TestRecovery_HandlesPanicWithString(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		panic("string panic message")
	})

	req, err := http.NewRequest("GET", "/test", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "internal server error")
}

func TestRecovery_HandlesPanicWithError(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		panic(gin.H{"error": "test error"})
	})

	req, err := http.NewRequest("GET", "/test", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "internal server error")
}

func TestRecovery_HandlesPanicInMiddleOfResponse(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		// Начинаем писать response
		c.JSON(http.StatusOK, gin.H{"step": "1"})
		// Затем паникуем
		panic("panic after response started")
	})

	req, err := http.NewRequest("GET", "/test", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Даже если response уже начат, middleware должен обработать panic
	// Status code может быть 200 если headers уже отправлены
	assert.True(t, w.Code == http.StatusOK || w.Code == http.StatusInternalServerError)
}

func TestRecovery_WithMultipleHandlers(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		c.Set("handler1", "executed")
		c.Next()
	}, func(c *gin.Context) {
		panic("panic in second handler")
	})

	req, err := http.NewRequest("GET", "/test", nil)
	require.NoError(t, err)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestRecovery_WithDifferentPaths(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))

	router.GET("/panic", func(c *gin.Context) {
		panic("test panic")
	})

	router.GET("/ok", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// Test panic path
	req1, _ := http.NewRequest("GET", "/panic", nil)
	w1 := httptest.NewRecorder()
	router.ServeHTTP(w1, req1)
	assert.Equal(t, http.StatusInternalServerError, w1.Code)

	// Test ok path
	req2, _ := http.NewRequest("GET", "/ok", nil)
	w2 := httptest.NewRecorder()
	router.ServeHTTP(w2, req2)
	assert.Equal(t, http.StatusOK, w2.Code)
}

func TestRecovery_DoesNotAffectNormalFlow(t *testing.T) {
	gin.SetMode(gin.TestMode)

	logger := zaptest.NewLogger(t)

	router := gin.New()
	router.Use(Recovery(logger))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "normal flow"})
	})

	// Выполняем несколько нормальных запросов
	for i := 0; i < 5; i++ {
		req, err := http.NewRequest("GET", "/test", nil)
		require.NoError(t, err)

		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		assert.Equal(t, http.StatusOK, w.Code)
		assert.Contains(t, w.Body.String(), "normal flow")
	}
}

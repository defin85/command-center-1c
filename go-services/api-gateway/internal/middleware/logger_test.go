package middleware

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"

	sharedlogger "github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
)

func captureAccessLoggerOutput(t *testing.T) *bytes.Buffer {
	t.Helper()

	buffer := &bytes.Buffer{}
	log := sharedlogger.GetLogger()
	previousOutput := log.Out
	previousFormatter := log.Formatter
	previousLevel := log.Level

	log.SetOutput(buffer)
	log.SetFormatter(&logrus.JSONFormatter{})
	log.SetLevel(logrus.InfoLevel)

	t.Cleanup(func() {
		log.SetOutput(previousOutput)
		log.SetFormatter(previousFormatter)
		log.SetLevel(previousLevel)
	})

	return buffer
}

func TestLoggerMiddleware_SkipsMetricsEndpoint(t *testing.T) {
	logOutput := captureAccessLoggerOutput(t)

	router := gin.New()
	router.Use(LoggerMiddleware())
	router.GET("/metrics", func(c *gin.Context) {
		c.String(http.StatusOK, "metrics")
	})

	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Empty(t, logOutput.String())
}

func TestLoggerMiddleware_LogsRegularRequests(t *testing.T) {
	logOutput := captureAccessLoggerOutput(t)

	router := gin.New()
	router.Use(LoggerMiddleware())
	router.GET("/api/v2/test/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v2/test/", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, logOutput.String(), "\"msg\":\"HTTP request\"")
	assert.Contains(t, logOutput.String(), "\"path\":\"/api/v2/test/\"")
}

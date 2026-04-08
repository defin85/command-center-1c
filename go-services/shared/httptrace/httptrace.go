package httptrace

import (
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/sirupsen/logrus"
	"go.uber.org/zap"
)

var (
	externalHTTPRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "external_http_requests_total",
			Help: "Total number of external HTTP requests",
		},
		[]string{"method", "path", "status"},
	)
	externalHTTPDurationSeconds = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "external_http_duration_seconds",
			Help:    "Duration of external HTTP requests in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path"},
	)
)

const (
	headerRequestID  = "X-Request-ID"
	headerUIActionID = "X-UI-Action-ID"
)

// PathFromURL returns URL path with query if present.
func PathFromURL(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}

	path := parsed.Path
	if path == "" {
		path = "/"
	}
	if parsed.RawQuery != "" {
		path += "?" + parsed.RawQuery
	}
	return path
}

// PathFromRequest returns request path with query if present.
func PathFromRequest(req *http.Request) string {
	if req == nil || req.URL == nil {
		return ""
	}
	path := req.URL.Path
	if path == "" {
		path = "/"
	}
	if req.URL.RawQuery != "" {
		path += "?" + req.URL.RawQuery
	}
	return path
}

// PathForMetricsFromRequest returns request path without query for metrics labels.
func PathForMetricsFromRequest(req *http.Request) string {
	if req == nil || req.URL == nil {
		return ""
	}
	if req.URL.Path == "" {
		return "/"
	}
	return req.URL.Path
}

// PathForMetricsFromURL returns URL path without query for metrics labels.
func PathForMetricsFromURL(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	if parsed.Path == "" {
		return "/"
	}
	return parsed.Path
}

func recordMetrics(method, path string, status int, elapsed time.Duration) {
	statusLabel := "error"
	if status > 0 {
		statusLabel = strconv.Itoa(status)
	}
	externalHTTPRequestsTotal.WithLabelValues(method, path, statusLabel).Inc()
	externalHTTPDurationSeconds.WithLabelValues(method, path).Observe(elapsed.Seconds())
}

// LogResponse logs HTTP call timing with status using logrus and records metrics.
func LogResponse(log *logrus.Logger, method, path string, status int, elapsed time.Duration) {
	metricsPath := PathForMetricsFromURL(path)
	recordMetrics(method, metricsPath, status, elapsed)
	if log == nil {
		return
	}
	log.WithFields(logrus.Fields{
		"method":     method,
		"path":       path,
		"status":     status,
		"elapsed_ms": elapsed.Milliseconds(),
	}).Info("http_call")
}

// LogError logs failed HTTP call timing with error using logrus and records metrics.
func LogError(log *logrus.Logger, method, path string, elapsed time.Duration, err error) {
	metricsPath := PathForMetricsFromURL(path)
	recordMetrics(method, metricsPath, 0, elapsed)
	if log == nil {
		return
	}
	log.WithFields(logrus.Fields{
		"method":     method,
		"path":       path,
		"status":     0,
		"elapsed_ms": elapsed.Milliseconds(),
		"error":      err.Error(),
	}).Warn("http_call")
}

// LogRequest logs using http.Request (logrus) and records metrics.
func LogRequest(log *logrus.Logger, req *http.Request, status int, elapsed time.Duration) {
	if req == nil {
		return
	}
	logPath := PathFromRequest(req)
	metricsPath := PathForMetricsFromRequest(req)
	recordMetrics(req.Method, metricsPath, status, elapsed)
	if log == nil {
		return
	}
	fields := logrus.Fields{
		"method":     req.Method,
		"path":       logPath,
		"status":     status,
		"elapsed_ms": elapsed.Milliseconds(),
	}
	if requestID := req.Header.Get(headerRequestID); requestID != "" {
		fields["request_id"] = requestID
	}
	if uiActionID := req.Header.Get(headerUIActionID); uiActionID != "" {
		fields["ui_action_id"] = uiActionID
	}
	log.WithFields(fields).Info("http_call")
}

// LogRequestError logs error using http.Request (logrus) and records metrics.
func LogRequestError(log *logrus.Logger, req *http.Request, elapsed time.Duration, err error) {
	if req == nil {
		return
	}
	logPath := PathFromRequest(req)
	metricsPath := PathForMetricsFromRequest(req)
	recordMetrics(req.Method, metricsPath, 0, elapsed)
	if log == nil {
		return
	}
	fields := logrus.Fields{
		"method":     req.Method,
		"path":       logPath,
		"status":     0,
		"elapsed_ms": elapsed.Milliseconds(),
		"error":      err.Error(),
	}
	if requestID := req.Header.Get(headerRequestID); requestID != "" {
		fields["request_id"] = requestID
	}
	if uiActionID := req.Header.Get(headerUIActionID); uiActionID != "" {
		fields["ui_action_id"] = uiActionID
	}
	log.WithFields(fields).Warn("http_call")
}

// LogResponseZap logs HTTP call timing with status using zap and records metrics.
func LogResponseZap(log *zap.Logger, method, path string, status int, elapsed time.Duration) {
	metricsPath := PathForMetricsFromURL(path)
	recordMetrics(method, metricsPath, status, elapsed)
	if log == nil {
		return
	}
	log.Info("http_call",
		zap.String("method", method),
		zap.String("path", path),
		zap.Int("status", status),
		zap.Int64("elapsed_ms", elapsed.Milliseconds()),
	)
}

// LogErrorZap logs failed HTTP call timing with error using zap and records metrics.
func LogErrorZap(log *zap.Logger, method, path string, elapsed time.Duration, err error) {
	metricsPath := PathForMetricsFromURL(path)
	recordMetrics(method, metricsPath, 0, elapsed)
	if log == nil {
		return
	}
	log.Warn("http_call",
		zap.String("method", method),
		zap.String("path", path),
		zap.Int("status", 0),
		zap.Int64("elapsed_ms", elapsed.Milliseconds()),
		zap.String("error", err.Error()),
	)
}

// LogRequestZap logs using http.Request (zap) and records metrics.
func LogRequestZap(log *zap.Logger, req *http.Request, status int, elapsed time.Duration) {
	if req == nil {
		return
	}
	logPath := PathFromRequest(req)
	metricsPath := PathForMetricsFromRequest(req)
	recordMetrics(req.Method, metricsPath, status, elapsed)
	if log == nil {
		return
	}
	log.Info("http_call",
		zap.String("method", req.Method),
		zap.String("path", logPath),
		zap.Int("status", status),
		zap.Int64("elapsed_ms", elapsed.Milliseconds()),
	)
}

// LogRequestErrorZap logs error using http.Request (zap) and records metrics.
func LogRequestErrorZap(log *zap.Logger, req *http.Request, elapsed time.Duration, err error) {
	if req == nil {
		return
	}
	logPath := PathFromRequest(req)
	metricsPath := PathForMetricsFromRequest(req)
	recordMetrics(req.Method, metricsPath, 0, elapsed)
	if log == nil {
		return
	}
	log.Warn("http_call",
		zap.String("method", req.Method),
		zap.String("path", logPath),
		zap.Int("status", 0),
		zap.Int64("elapsed_ms", elapsed.Milliseconds()),
		zap.String("error", err.Error()),
	)
}

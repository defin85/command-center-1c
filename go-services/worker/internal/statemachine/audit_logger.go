package statemachine

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"github.com/commandcenter1c/commandcenter/shared/logger"
)

// HTTPAuditLogger sends compensation audit logs to Orchestrator API
type HTTPAuditLogger struct {
	orchestratorURL string
	serviceToken    string // WORKER_API_KEY for internal service authentication
	httpClient      *http.Client
}

// NewHTTPAuditLogger creates a new HTTP audit logger
// serviceToken should be the WORKER_API_KEY from config
func NewHTTPAuditLogger(orchestratorURL, serviceToken string) *HTTPAuditLogger {
	return &HTTPAuditLogger{
		orchestratorURL: orchestratorURL,
		serviceToken:    serviceToken,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// LogCompensation sends compensation result to Orchestrator API
// Implements AuditLogger interface
func (l *HTTPAuditLogger) LogCompensation(ctx context.Context, operationID string, result *CompensationResult) error {
	// Build request payload
	payload := map[string]interface{}{
		"operation_id": operationID,
		"results": []map[string]interface{}{
			{
				"name":           result.Name,
				"success":        result.Success,
				"attempts":       result.Attempts,
				"total_duration": result.TotalDuration.Seconds(),
				"error":          result.Error,
				"executed_at":    result.ExecutedAt.UTC().Format(time.RFC3339),
			},
		},
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal error: %w", err)
	}

	url := fmt.Sprintf("%s/api/v2/audit/log-compensation/", l.orchestratorURL)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create request error: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if l.serviceToken != "" {
		req.Header.Set("X-Internal-Service-Token", l.serviceToken)
	}

	start := time.Now()
	resp, err := l.httpClient.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		return fmt.Errorf("http error: %w", err)
	}
	defer resp.Body.Close()

	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	if resp.StatusCode >= 400 {
		return fmt.Errorf("orchestrator returned status %d", resp.StatusCode)
	}

	fmt.Printf("[AuditLogger] Logged compensation '%s' for operation %s (success=%v)\n",
		result.Name, operationID, result.Success)

	return nil
}

// LogCompensationBatch sends multiple compensation results in one request
func (l *HTTPAuditLogger) LogCompensationBatch(ctx context.Context, operationID string, results []*CompensationResult) error {
	if len(results) == 0 {
		return nil
	}

	// Build batch payload
	resultPayloads := make([]map[string]interface{}, len(results))
	for i, result := range results {
		resultPayloads[i] = map[string]interface{}{
			"name":           result.Name,
			"success":        result.Success,
			"attempts":       result.Attempts,
			"total_duration": result.TotalDuration.Seconds(),
			"error":          result.Error,
			"executed_at":    result.ExecutedAt.UTC().Format(time.RFC3339),
		}
	}

	payload := map[string]interface{}{
		"operation_id": operationID,
		"results":      resultPayloads,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal error: %w", err)
	}

	url := fmt.Sprintf("%s/api/v2/audit/log-compensation/", l.orchestratorURL)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create request error: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if l.serviceToken != "" {
		req.Header.Set("X-Internal-Service-Token", l.serviceToken)
	}

	start := time.Now()
	resp, err := l.httpClient.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		return fmt.Errorf("http error: %w", err)
	}
	defer resp.Body.Close()

	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	if resp.StatusCode >= 400 {
		return fmt.Errorf("orchestrator returned status %d", resp.StatusCode)
	}

	fmt.Printf("[AuditLogger] Logged %d compensations for operation %s\n",
		len(results), operationID)

	return nil
}

// NoOpAuditLogger is a no-operation audit logger for testing
type NoOpAuditLogger struct{}

// NewNoOpAuditLogger creates a no-op audit logger
func NewNoOpAuditLogger() *NoOpAuditLogger {
	return &NoOpAuditLogger{}
}

// LogCompensation does nothing (for testing or when audit is disabled)
func (l *NoOpAuditLogger) LogCompensation(ctx context.Context, operationID string, result *CompensationResult) error {
	return nil
}

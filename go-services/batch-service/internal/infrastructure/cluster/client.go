package cluster

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/sony/gobreaker"
	"go.uber.org/zap"
	"github.com/command-center-1c/batch-service/internal/models"
)

// ClusterClient is an HTTP client for cluster-service with circuit breaker protection
type ClusterClient struct {
	baseURL    string // http://localhost:8088
	httpClient *http.Client
	logger     *zap.Logger
	breaker    *gobreaker.CircuitBreaker
}

// NewClusterClient creates a new ClusterClient instance with circuit breaker
// Circuit breaker prevents cascade failures when cluster-service is unavailable
func NewClusterClient(baseURL string, timeout time.Duration, logger *zap.Logger) *ClusterClient {
	// Circuit breaker settings
	// Opens after 60% failures (min 3 requests)
	// Half-open state allows 3 test requests
	// Automatically closes if test requests succeed
	settings := gobreaker.Settings{
		Name:        "cluster-service",
		MaxRequests: 3,                // Half-open state: max 3 requests для проверки
		Interval:    10 * time.Second, // Reset counts every 10 sec
		Timeout:     timeout * 2,      // Open → Half-Open после timeout*2
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 3 && failureRatio >= 0.6
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			logger.Info("circuit breaker state changed",
				zap.String("service", name),
				zap.String("from", from.String()),
				zap.String("to", to.String()))
		},
	}

	return &ClusterClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		logger:  logger,
		breaker: gobreaker.NewCircuitBreaker(settings),
	}
}

// GetSessions retrieves active sessions for a specific infobase
// Protected by circuit breaker to prevent cascade failures
func (c *ClusterClient) GetSessions(infobaseID string) ([]models.Session, error) {
	result, err := c.breaker.Execute(func() (interface{}, error) {
		url := fmt.Sprintf("%s/api/v1/sessions?infobase_id=%s", c.baseURL, infobaseID)

		c.logger.Debug("fetching sessions from cluster-service",
			zap.String("url", url),
			zap.String("infobase_id", infobaseID))

		resp, err := c.httpClient.Get(url)
		if err != nil {
			c.logger.Error("failed to get sessions", zap.Error(err))
			return nil, fmt.Errorf("cluster-service request failed: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			c.logger.Error("cluster-service returned error",
				zap.Int("status_code", resp.StatusCode),
				zap.String("body", string(body)))
			return nil, fmt.Errorf("cluster-service error: %d - %s", resp.StatusCode, string(body))
		}

		var sessionsResp models.SessionsResponse
		if err := json.NewDecoder(resp.Body).Decode(&sessionsResp); err != nil {
			c.logger.Error("failed to decode response", zap.Error(err))
			return nil, fmt.Errorf("failed to decode response: %w", err)
		}

		c.logger.Debug("sessions retrieved successfully",
			zap.Int("count", sessionsResp.Count))

		return sessionsResp.Sessions, nil
	})

	if err != nil {
		return nil, err
	}

	sessions, ok := result.([]models.Session)
	if !ok {
		return nil, fmt.Errorf("unexpected result type")
	}

	return sessions, nil
}

// TerminateSessions terminates multiple sessions
// Protected by circuit breaker to prevent cascade failures
func (c *ClusterClient) TerminateSessions(infobaseID string, sessionIDs []string) (*models.TerminateSessionsResponse, error) {
	result, err := c.breaker.Execute(func() (interface{}, error) {
		url := fmt.Sprintf("%s/api/v1/sessions/terminate", c.baseURL)

		reqBody := models.TerminateSessionsRequest{
			InfobaseID: infobaseID,
			SessionIDs: sessionIDs,
		}

		c.logger.Debug("terminating sessions",
			zap.String("infobase_id", infobaseID),
			zap.Int("session_count", len(sessionIDs)))

		jsonData, err := json.Marshal(reqBody)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request: %w", err)
		}

		resp, err := c.httpClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
		if err != nil {
			c.logger.Error("failed to terminate sessions", zap.Error(err))
			return nil, fmt.Errorf("cluster-service request failed: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			c.logger.Error("session termination failed",
				zap.Int("status_code", resp.StatusCode),
				zap.String("body", string(body)))
			return nil, fmt.Errorf("terminate failed: %d - %s", resp.StatusCode, string(body))
		}

		var terminateResp models.TerminateSessionsResponse
		if err := json.NewDecoder(resp.Body).Decode(&terminateResp); err != nil {
			c.logger.Error("failed to decode response", zap.Error(err))
			return nil, fmt.Errorf("failed to decode response: %w", err)
		}

		c.logger.Info("sessions terminated successfully",
			zap.Int("terminated_count", terminateResp.TerminatedCount),
			zap.Int("failed_count", len(terminateResp.FailedSessions)))

		return &terminateResp, nil
	})

	if err != nil {
		return nil, err
	}

	response, ok := result.(*models.TerminateSessionsResponse)
	if !ok {
		return nil, fmt.Errorf("unexpected result type")
	}

	return response, nil
}

// HealthCheck checks if cluster-service is available
func (c *ClusterClient) HealthCheck() error {
	url := fmt.Sprintf("%s/health", c.baseURL)

	resp, err := c.httpClient.Get(url)
	if err != nil {
		c.logger.Warn("cluster-service health check failed", zap.Error(err))
		return fmt.Errorf("cluster-service unavailable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		c.logger.Warn("cluster-service health check returned non-200",
			zap.Int("status_code", resp.StatusCode),
			zap.String("body", string(body)))
		return fmt.Errorf("cluster-service unhealthy: status %d", resp.StatusCode)
	}

	c.logger.Debug("cluster-service health check passed")
	return nil
}

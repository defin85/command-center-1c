package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/command-center-1c/cluster-service/internal/grpc"
	"github.com/command-center-1c/cluster-service/internal/models"

	// Use v8platform protos for all operations
	apiv1 "github.com/v8platform/protos/gen/ras/service/api/v1"
	messagesv1 "github.com/v8platform/protos/gen/ras/messages/v1"

	"go.uber.org/zap"
)

// InfobaseManagementService handles infobase management operations (lock, unlock, terminate sessions)
type InfobaseManagementService struct {
	grpcClient *grpc.Client
	logger     *zap.Logger
	httpClient *http.Client     // For calling ras-grpc-gw HTTP endpoints
	rasGWURL   string           // ras-grpc-gw HTTP server URL (default: http://localhost:8081)
}

// NewInfobaseManagementService creates a new InfobaseManagementService instance
func NewInfobaseManagementService(client *grpc.Client, logger *zap.Logger, rasGWURL string) *InfobaseManagementService {
	if rasGWURL == "" {
		rasGWURL = "http://localhost:8081" // Default ras-grpc-gw HTTP server address
	}

	return &InfobaseManagementService{
		grpcClient: client,
		logger:     logger,
		httpClient: &http.Client{
			Timeout: 10 * time.Second, // Default timeout for HTTP requests
		},
		rasGWURL: rasGWURL,
	}
}

// LockInfobase locks an infobase (blocks scheduled jobs)
//
// REAL IMPLEMENTATION: Calls ras-grpc-gw HTTP API /api/v1/infobases/lock
// Blocks only scheduled jobs (scheduled_jobs_deny=true), does NOT block user sessions
func (s *InfobaseManagementService) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	if clusterID == "" || infobaseID == "" {
		return &ServiceError{
			Code:    "INVALID_PARAMS",
			Message: "cluster_id and infobase_id are required",
		}
	}

	s.logger.Info("locking infobase (scheduled jobs only)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Authenticate cluster first
	if err := s.authenticateCluster(ctx, clusterID); err != nil {
		return err
	}

	// Build HTTP request to ras-grpc-gw
	url := fmt.Sprintf("%s/api/v1/infobases/lock", s.rasGWURL)

	reqBody := map[string]interface{}{
		"cluster_id":          clusterID,
		"infobase_id":         infobaseID,
		"sessions_deny":       false, // Do NOT block user sessions
		"scheduled_jobs_deny": true,  // Block ONLY scheduled jobs
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Execute HTTP request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response body: %w", err)
	}

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ras-grpc-gw returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var response struct {
		Success bool   `json:"success"`
		Message string `json:"message"`
		Error   string `json:"error,omitempty"`
	}

	if err := json.Unmarshal(respBody, &response); err != nil {
		return fmt.Errorf("failed to parse response: %w", err)
	}

	if !response.Success {
		return fmt.Errorf("lock failed: %s", response.Error)
	}

	s.logger.Info("infobase locked successfully",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID),
		zap.String("message", response.Message))

	return nil
}

// UnlockInfobase unlocks an infobase (enables scheduled jobs)
//
// REAL IMPLEMENTATION: Calls ras-grpc-gw HTTP API /api/v1/infobases/unlock
// Unlocks scheduled jobs (unlock_scheduled_jobs=true), does NOT unlock user sessions
func (s *InfobaseManagementService) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	if clusterID == "" || infobaseID == "" {
		return &ServiceError{
			Code:    "INVALID_PARAMS",
			Message: "cluster_id and infobase_id are required",
		}
	}

	s.logger.Info("unlocking infobase (scheduled jobs only)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Authenticate cluster first
	if err := s.authenticateCluster(ctx, clusterID); err != nil {
		return err
	}

	// Build HTTP request to ras-grpc-gw
	url := fmt.Sprintf("%s/api/v1/infobases/unlock", s.rasGWURL)

	reqBody := map[string]interface{}{
		"cluster_id":             clusterID,
		"infobase_id":            infobaseID,
		"unlock_sessions":        false, // Do NOT unlock user sessions (we didn't lock them)
		"unlock_scheduled_jobs":  true,  // Unlock ONLY scheduled jobs
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Execute HTTP request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response body: %w", err)
	}

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ras-grpc-gw returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var response struct {
		Success bool   `json:"success"`
		Message string `json:"message"`
		Error   string `json:"error,omitempty"`
	}

	if err := json.Unmarshal(respBody, &response); err != nil {
		return fmt.Errorf("failed to parse response: %w", err)
	}

	if !response.Success {
		return fmt.Errorf("unlock failed: %s", response.Error)
	}

	s.logger.Info("infobase unlocked successfully",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID),
		zap.String("message", response.Message))

	return nil
}

// TerminateSessions terminates all sessions for an infobase
//
// REAL IMPLEMENTATION: Calls ras-grpc-gw HTTP endpoint /api/v1/sessions/terminate
// для каждой сессии в infobase
func (s *InfobaseManagementService) TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error) {
	if clusterID == "" || infobaseID == "" {
		return 0, &ServiceError{
			Code:    "INVALID_PARAMS",
			Message: "cluster_id and infobase_id are required",
		}
	}

	s.logger.Info("terminating sessions",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Authenticate cluster first
	if err := s.authenticateCluster(ctx, clusterID); err != nil {
		return 0, err
	}

	// Get all sessions for infobase
	sessions, err := s.getSessions(ctx, clusterID, infobaseID)
	if err != nil {
		return 0, err
	}

	if len(sessions) == 0 {
		s.logger.Info("no active sessions to terminate")
		return 0, nil
	}

	// Terminate each session via ras-grpc-gw HTTP API
	terminated := 0
	for _, session := range sessions {
		err := s.terminateSingleSession(ctx, clusterID, session.UUID)
		if err != nil {
			s.logger.Warn("failed to terminate session",
				zap.String("session_id", session.UUID),
				zap.Error(err))
			continue // Continue terminating other sessions
		}
		terminated++
	}

	s.logger.Info("session termination completed",
		zap.Int("total", len(sessions)),
		zap.Int("terminated", terminated),
		zap.Int("failed", len(sessions)-terminated))

	return terminated, nil
}

// GetSessionsCount returns the count of active sessions for an infobase
func (s *InfobaseManagementService) GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error) {
	if clusterID == "" || infobaseID == "" {
		return 0, &ServiceError{
			Code:    "INVALID_PARAMS",
			Message: "cluster_id and infobase_id are required",
		}
	}

	// Authenticate cluster first
	if err := s.authenticateCluster(ctx, clusterID); err != nil {
		return 0, err
	}

	// Get sessions
	sessions, err := s.getSessions(ctx, clusterID, infobaseID)
	if err != nil {
		return 0, err
	}

	return len(sessions), nil
}

// authenticateCluster authenticates with the cluster (required even for security-level: 0)
func (s *InfobaseManagementService) authenticateCluster(ctx context.Context, clusterID string) error {
	authClient := apiv1.NewAuthServiceClient(s.grpcClient.GetConnection())

	authReq := &messagesv1.ClusterAuthenticateRequest{
		ClusterId: clusterID,
		User:      "", // empty for security-level: 0
		Password:  "", // empty for security-level: 0
	}

	_, err := authClient.AuthenticateCluster(ctx, authReq)
	if err != nil {
		s.logger.Error("cluster authentication failed",
			zap.String("cluster_id", clusterID),
			zap.Error(err))
		return fmt.Errorf("cluster authentication failed: %w", err)
	}

	s.logger.Debug("cluster authenticated successfully",
		zap.String("cluster_id", clusterID))

	return nil
}

// getSessions retrieves all sessions for an infobase
func (s *InfobaseManagementService) getSessions(ctx context.Context, clusterID, infobaseID string) ([]models.Session, error) {
	client := apiv1.NewSessionsServiceClient(s.grpcClient.GetConnection())

	req := &messagesv1.GetSessionsRequest{
		ClusterId: clusterID,
	}

	resp, err := client.GetSessions(ctx, req)
	if err != nil {
		s.logger.Error("failed to get sessions",
			zap.String("cluster_id", clusterID),
			zap.Error(err))
		return nil, fmt.Errorf("get sessions failed: %w", err)
	}

	// Filter sessions for this infobase and convert to domain models
	sessions := make([]models.Session, 0)
	for _, sess := range resp.Sessions {
		if sess.InfobaseId == infobaseID {
			sessions = append(sessions, models.Session{
				UUID:        sess.Uuid,
				SessionID:   sess.Uuid, // Legacy field for compatibility
				UserName:    sess.UserName,
				Application: sess.AppId,
				StartedAt:   sess.StartedAt.AsTime().Format("2006-01-02T15:04:05Z"),
			})
		}
	}

	return sessions, nil
}

// terminateSingleSession terminates a single session via ras-grpc-gw HTTP API
func (s *InfobaseManagementService) terminateSingleSession(ctx context.Context, clusterID, sessionID string) error {
	// Build HTTP request
	url := fmt.Sprintf("%s/api/v1/sessions/terminate", s.rasGWURL)

	reqBody := map[string]string{
		"cluster_id": clusterID,
		"session_id": sessionID,
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Execute HTTP request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response body: %w", err)
	}

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ras-grpc-gw returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var response struct {
		Success bool   `json:"success"`
		Error   string `json:"error,omitempty"`
	}

	if err := json.Unmarshal(respBody, &response); err != nil {
		return fmt.Errorf("failed to parse response: %w", err)
	}

	if !response.Success {
		return fmt.Errorf("termination failed: %s", response.Error)
	}

	return nil
}

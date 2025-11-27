package service

import (
	"context"
	"fmt"
	"strings"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"go.uber.org/zap"
)

// SessionService handles session-related operations
type SessionService struct {
	rasPool *ras.Pool
	logger  *zap.Logger
}

// NewSessionService creates a new SessionService instance
func NewSessionService(rasPool *ras.Pool, logger *zap.Logger) *SessionService {
	return &SessionService{
		rasPool: rasPool,
		logger:  logger,
	}
}

// GetSessions retrieves list of sessions for a cluster and infobase
func (s *SessionService) GetSessions(ctx context.Context, clusterID, infobaseID string) ([]*models.Session, error) {
	if clusterID == "" {
		return nil, fmt.Errorf("cluster_id is required")
	}

	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return nil, fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Get sessions
	sessions, err := client.GetSessions(ctx, clusterID, infobaseID)
	if err != nil {
		s.logger.Error("failed to get sessions from RAS",
			zap.String("cluster_id", clusterID),
			zap.String("infobase_id", infobaseID),
			zap.Error(err))
		return nil, fmt.Errorf("failed to get sessions: %w", err)
	}

	s.logger.Info("retrieved sessions",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID),
		zap.Int("count", len(sessions)))

	return sessions, nil
}

// TerminateSessions terminates all sessions for a cluster and infobase
func (s *SessionService) TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error) {
	if clusterID == "" || infobaseID == "" {
		return 0, fmt.Errorf("cluster_id and infobase_id are required")
	}

	s.logger.Info("terminating sessions",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return 0, fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Get all sessions for infobase
	sessions, err := client.GetSessions(ctx, clusterID, infobaseID)
	if err != nil {
		s.logger.Error("failed to get sessions",
			zap.String("cluster_id", clusterID),
			zap.String("infobase_id", infobaseID),
			zap.Error(err))
		return 0, fmt.Errorf("failed to get sessions: %w", err)
	}

	if len(sessions) == 0 {
		s.logger.Info("no active sessions to terminate")
		return 0, nil
	}

	// Terminate each session
	terminated := 0
	for _, session := range sessions {
		err := client.TerminateSession(ctx, clusterID, session.UUID)
		if err != nil {
			s.logger.Warn("failed to terminate session",
				zap.String("session_id", session.UUID),
				zap.Error(err))
			continue
		}
		terminated++
	}

	s.logger.Info("session termination completed",
		zap.Int("total", len(sessions)),
		zap.Int("terminated", terminated),
		zap.Int("failed", len(sessions)-terminated))

	return terminated, nil
}

// TerminateSession terminates a single session by ID.
// This method is idempotent - if the session doesn't exist, it returns nil (success).
// Optimized: directly calls TerminateSession and treats "session not found" errors as success.
func (s *SessionService) TerminateSession(ctx context.Context, clusterID, sessionID string) error {
	if clusterID == "" {
		return fmt.Errorf("cluster_id is required")
	}
	if sessionID == "" {
		return fmt.Errorf("session_id is required")
	}

	s.logger.Info("terminating single session",
		zap.String("cluster_id", clusterID),
		zap.String("session_id", sessionID))

	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Optimized: directly terminate - no pre-check needed for idempotency
	// Handle "session not found" error as success (idempotent behavior)
	err = client.TerminateSession(ctx, clusterID, sessionID)
	if err != nil {
		// Check if error indicates session not found (idempotent success case)
		errStr := err.Error()
		if isSessionNotFoundError(errStr) {
			s.logger.Info("session not found (already terminated or never existed) - idempotent success",
				zap.String("cluster_id", clusterID),
				zap.String("session_id", sessionID))
			return nil
		}

		s.logger.Error("failed to terminate session",
			zap.String("cluster_id", clusterID),
			zap.String("session_id", sessionID),
			zap.Error(err))
		return fmt.Errorf("failed to terminate session: %w", err)
	}

	s.logger.Info("session terminated successfully",
		zap.String("cluster_id", clusterID),
		zap.String("session_id", sessionID))

	return nil
}

// isSessionNotFoundError checks if the error indicates that the session was not found.
// This allows idempotent behavior - treating "not found" as success.
func isSessionNotFoundError(errStr string) bool {
	// Common error patterns from RAS when session is not found
	// These patterns may need adjustment based on actual RAS error messages
	notFoundPatterns := []string{
		"session not found",
		"session does not exist",
		"no such session",
		"invalid session",
	}

	errLower := strings.ToLower(errStr)
	for _, pattern := range notFoundPatterns {
		if strings.Contains(errLower, pattern) {
			return true
		}
	}
	return false
}

// GetSessionsCount returns the count of active sessions for a cluster and infobase
func (s *SessionService) GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error) {
	if clusterID == "" {
		return 0, fmt.Errorf("cluster_id is required")
	}

	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return 0, fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Get sessions
	sessions, err := client.GetSessions(ctx, clusterID, infobaseID)
	if err != nil {
		s.logger.Error("failed to get sessions",
			zap.String("cluster_id", clusterID),
			zap.String("infobase_id", infobaseID),
			zap.Error(err))
		return 0, fmt.Errorf("failed to get sessions: %w", err)
	}

	return len(sessions), nil
}

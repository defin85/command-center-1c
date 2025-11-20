package service

import (
	"context"
	"fmt"

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

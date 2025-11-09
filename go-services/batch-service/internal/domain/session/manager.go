package session

import (
	"errors"
	"fmt"
	"time"

	"go.uber.org/zap"
	"github.com/command-center-1c/batch-service/internal/infrastructure/cluster"
)

// Error definitions
var (
	ErrClusterServiceUnavailable = errors.New("cluster-service unavailable")
	ErrSessionsNotTerminated     = errors.New("failed to terminate all sessions")
	ErrSessionCheckFailed        = errors.New("failed to check session status")
)

// SessionManager handles session termination logic with retry mechanism
type SessionManager struct {
	clusterClient *cluster.ClusterClient
	logger        *zap.Logger
}

// NewSessionManager creates a new SessionManager instance
func NewSessionManager(clusterClient *cluster.ClusterClient, logger *zap.Logger) *SessionManager {
	return &SessionManager{
		clusterClient: clusterClient,
		logger:        logger,
	}
}

// TerminateSessionsIfNeeded terminates active sessions for an infobase if force is true
// Returns error if termination fails or sessions still active after retries
func (m *SessionManager) TerminateSessionsIfNeeded(infobaseID string, force bool) error {
	if !force {
		m.logger.Info("session termination not requested, skipping",
			zap.String("infobase_id", infobaseID))
		return nil
	}

	m.logger.Info("checking for active sessions",
		zap.String("infobase_id", infobaseID))

	// 1. Get list of active sessions
	sessions, err := m.clusterClient.GetSessions(infobaseID)
	if err != nil {
		m.logger.Error("failed to get sessions", zap.Error(err))
		return fmt.Errorf("%w: %v", ErrClusterServiceUnavailable, err)
	}

	if len(sessions) == 0 {
		m.logger.Info("no active sessions found",
			zap.String("infobase_id", infobaseID))
		return nil
	}

	m.logger.Info("found active sessions",
		zap.String("infobase_id", infobaseID),
		zap.Int("count", len(sessions)))

	// Log session details
	for _, s := range sessions {
		m.logger.Debug("active session",
			zap.String("session_id", s.SessionID),
			zap.String("user", s.UserName),
			zap.String("app", s.Application))
	}

	// 2. Collect session IDs
	sessionIDs := make([]string, len(sessions))
	for i, s := range sessions {
		sessionIDs[i] = s.SessionID
	}

	// 3. Terminate sessions
	m.logger.Info("terminating sessions",
		zap.String("infobase_id", infobaseID),
		zap.Int("session_count", len(sessionIDs)))

	terminateResp, err := m.clusterClient.TerminateSessions(infobaseID, sessionIDs)
	if err != nil {
		m.logger.Error("failed to terminate sessions", zap.Error(err))
		return fmt.Errorf("terminate request failed: %w", err)
	}

	m.logger.Info("sessions terminated",
		zap.Int("terminated_count", terminateResp.TerminatedCount),
		zap.Int("failed_count", len(terminateResp.FailedSessions)))

	// Log failed sessions if any
	if len(terminateResp.FailedSessions) > 0 {
		m.logger.Warn("some sessions failed to terminate",
			zap.Strings("failed_session_ids", terminateResp.FailedSessions))
	}

	// 4. Grace period (7 seconds)
	gracePeriod := 7 * time.Second
	m.logger.Info("waiting for grace period",
		zap.Duration("duration", gracePeriod))
	time.Sleep(gracePeriod)

	// 5. Retry verification (up to 3 attempts)
	const maxRetries = 3
	retryInterval := 3 * time.Second

	for attempt := 1; attempt <= maxRetries; attempt++ {
		m.logger.Info("verifying session termination",
			zap.Int("attempt", attempt),
			zap.Int("max_retries", maxRetries))

		remainingSessions, err := m.clusterClient.GetSessions(infobaseID)
		if err != nil {
			m.logger.Error("failed to verify session termination",
				zap.Int("attempt", attempt),
				zap.Error(err))
			return fmt.Errorf("%w: attempt %d failed: %v", ErrSessionCheckFailed, attempt, err)
		}

		if len(remainingSessions) == 0 {
			m.logger.Info("all sessions terminated successfully",
				zap.Int("attempts_taken", attempt))
			return nil
		}

		m.logger.Warn("sessions still active after termination",
			zap.Int("attempt", attempt),
			zap.Int("remaining_count", len(remainingSessions)))

		// Log remaining session IDs
		remainingIDs := make([]string, len(remainingSessions))
		for i, s := range remainingSessions {
			remainingIDs[i] = s.SessionID
		}
		m.logger.Debug("remaining sessions",
			zap.Strings("session_ids", remainingIDs))

		// Wait before next retry (except on last attempt)
		if attempt < maxRetries {
			m.logger.Info("waiting before next retry",
				zap.Duration("interval", retryInterval))
			time.Sleep(retryInterval)
		}
	}

	// All retries exhausted
	m.logger.Error("failed to terminate all sessions after max retries",
		zap.Int("max_retries", maxRetries),
		zap.String("infobase_id", infobaseID))

	return fmt.Errorf("%w: %d attempts exhausted", ErrSessionsNotTerminated, maxRetries)
}

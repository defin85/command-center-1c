package monitor

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/command-center-1c/cluster-service/internal/service"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// SessionsMonitor monitors active sessions and publishes events when they close
type SessionsMonitor struct {
	infobaseService *service.InfobaseManagementService
	redisClient     *redis.Client
	pollInterval    time.Duration
	logger          *zap.Logger
}

// MonitorConfig contains configuration for SessionsMonitor
type MonitorConfig struct {
	PollInterval time.Duration
}

// NewSessionsMonitor creates a new SessionsMonitor instance
func NewSessionsMonitor(
	infobaseService *service.InfobaseManagementService,
	redisClient *redis.Client,
	cfg MonitorConfig,
	logger *zap.Logger,
) *SessionsMonitor {
	// Default poll interval if not provided
	if cfg.PollInterval == 0 {
		cfg.PollInterval = 1 * time.Second
	}

	return &SessionsMonitor{
		infobaseService: infobaseService,
		redisClient:     redisClient,
		pollInterval:    cfg.PollInterval,
		logger:          logger,
	}
}

// SessionsClosedEvent represents the event published when all sessions are closed
type SessionsClosedEvent struct {
	InfobaseID    string `json:"infobase_id"`
	ClusterID     string `json:"cluster_id"`
	Timestamp     int64  `json:"timestamp"`
	SessionsCount int    `json:"sessions_count"`
}

// MonitorInfobase monitors sessions for a specific infobase and publishes event when sessions=0
// This function blocks until sessions are closed or context is cancelled
func (m *SessionsMonitor) MonitorInfobase(ctx context.Context, clusterID, infobaseID string) error {
	channel := fmt.Sprintf("sessions:%s:closed", infobaseID)

	m.logger.Info("starting sessions monitor",
		zap.String("infobase_id", infobaseID),
		zap.String("cluster_id", clusterID),
		zap.String("channel", channel),
		zap.Duration("poll_interval", m.pollInterval),
	)

	ticker := time.NewTicker(m.pollInterval)
	defer ticker.Stop()

	// Track attempts for logging
	attempt := 0

	for {
		select {
		case <-ctx.Done():
			m.logger.Info("sessions monitor cancelled",
				zap.String("infobase_id", infobaseID),
				zap.Int("attempts", attempt),
			)
			return ctx.Err()

		case <-ticker.C:
			attempt++

			// Get sessions count from RAS
			count, err := m.infobaseService.GetSessionsCount(ctx, clusterID, infobaseID)
			if err != nil {
				m.logger.Error("failed to get sessions count",
					zap.String("infobase_id", infobaseID),
					zap.Int("attempt", attempt),
					zap.Error(err),
				)
				// Continue monitoring despite error
				continue
			}

			if count == 0 {
				// No sessions! Publish event
				m.logger.Info("all sessions closed, publishing event",
					zap.String("infobase_id", infobaseID),
					zap.String("channel", channel),
					zap.Int("attempts", attempt),
				)

				event := SessionsClosedEvent{
					InfobaseID:    infobaseID,
					ClusterID:     clusterID,
					Timestamp:     time.Now().Unix(),
					SessionsCount: 0,
				}

				eventJSON, err := json.Marshal(event)
				if err != nil {
					m.logger.Error("failed to marshal event",
						zap.String("infobase_id", infobaseID),
						zap.Error(err),
					)
					return fmt.Errorf("failed to marshal event: %w", err)
				}

				// Publish to Redis channel
				if err := m.redisClient.Publish(ctx, channel, eventJSON).Err(); err != nil {
					m.logger.Error("failed to publish event",
						zap.String("infobase_id", infobaseID),
						zap.String("channel", channel),
						zap.Error(err),
					)
					return fmt.Errorf("failed to publish event: %w", err)
				}

				m.logger.Info("event published successfully",
					zap.String("infobase_id", infobaseID),
					zap.String("channel", channel),
					zap.Int("total_attempts", attempt),
				)

				// Stop monitoring after event is published
				return nil
			}

			// Log progress every 5 attempts
			if attempt%5 == 0 {
				m.logger.Debug("still waiting for sessions to close",
					zap.String("infobase_id", infobaseID),
					zap.Int("sessions_count", count),
					zap.Int("attempt", attempt),
				)
			}
		}
	}
}

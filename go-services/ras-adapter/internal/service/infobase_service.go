package service

import (
	"context"
	"fmt"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"go.uber.org/zap"
)

// InfobaseService handles infobase-related operations
type InfobaseService struct {
	rasPool *ras.Pool
	logger  *zap.Logger
}

// NewInfobaseService creates a new InfobaseService instance
func NewInfobaseService(rasPool *ras.Pool, logger *zap.Logger) *InfobaseService {
	return &InfobaseService{
		rasPool: rasPool,
		logger:  logger,
	}
}

// GetInfobases retrieves list of infobases for a cluster
func (s *InfobaseService) GetInfobases(ctx context.Context, clusterID string) ([]*models.Infobase, error) {
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

	// Get infobases
	infobases, err := client.GetInfobases(ctx, clusterID)
	if err != nil {
		s.logger.Error("failed to get infobases from RAS",
			zap.String("cluster_id", clusterID),
			zap.Error(err))
		return nil, fmt.Errorf("failed to get infobases: %w", err)
	}

	s.logger.Info("retrieved infobases",
		zap.String("cluster_id", clusterID),
		zap.Int("count", len(infobases)))

	return infobases, nil
}

// LockInfobase locks an infobase (blocks scheduled jobs)
func (s *InfobaseService) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	if clusterID == "" || infobaseID == "" {
		return fmt.Errorf("cluster_id and infobase_id are required")
	}

	s.logger.Info("locking infobase (scheduled jobs only)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Call RAS client LockInfobase
	err = client.LockInfobase(ctx, clusterID, infobaseID)
	if err != nil {
		s.logger.Error("failed to lock infobase",
			zap.String("cluster_id", clusterID),
			zap.String("infobase_id", infobaseID),
			zap.Error(err))
		return fmt.Errorf("lock infobase failed: %w", err)
	}

	s.logger.Info("infobase locked successfully",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	return nil
}

// UnlockInfobase unlocks an infobase (enables scheduled jobs)
func (s *InfobaseService) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	if clusterID == "" || infobaseID == "" {
		return fmt.Errorf("cluster_id and infobase_id are required")
	}

	s.logger.Info("unlocking infobase (scheduled jobs only)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Call RAS client UnlockInfobase
	err = client.UnlockInfobase(ctx, clusterID, infobaseID)
	if err != nil {
		s.logger.Error("failed to unlock infobase",
			zap.String("cluster_id", clusterID),
			zap.String("infobase_id", infobaseID),
			zap.Error(err))
		return fmt.Errorf("unlock infobase failed: %w", err)
	}

	s.logger.Info("infobase unlocked successfully",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	return nil
}

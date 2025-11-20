package service

import (
	"context"
	"fmt"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"go.uber.org/zap"
)

// ClusterService handles cluster-related operations
type ClusterService struct {
	rasPool *ras.Pool
	logger  *zap.Logger
}

// NewClusterService creates a new ClusterService instance
func NewClusterService(rasPool *ras.Pool, logger *zap.Logger) *ClusterService {
	return &ClusterService{
		rasPool: rasPool,
		logger:  logger,
	}
}

// GetClusters retrieves list of clusters from RAS server
func (s *ClusterService) GetClusters(ctx context.Context, serverAddr string) ([]*models.Cluster, error) {
	// Get RAS client from pool
	client, err := s.rasPool.GetConnection(ctx)
	if err != nil {
		s.logger.Error("failed to get RAS client from pool", zap.Error(err))
		return nil, fmt.Errorf("failed to get RAS client: %w", err)
	}
	defer s.rasPool.ReleaseConnection(client)

	// Get clusters
	clusters, err := client.GetClusters(ctx)
	if err != nil {
		s.logger.Error("failed to get clusters from RAS", zap.Error(err))
		return nil, fmt.Errorf("failed to get clusters: %w", err)
	}

	s.logger.Info("retrieved clusters",
		zap.String("server", serverAddr),
		zap.Int("count", len(clusters)))

	return clusters, nil
}

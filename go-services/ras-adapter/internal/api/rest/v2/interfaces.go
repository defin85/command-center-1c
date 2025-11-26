package v2

import (
	"context"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
)

// Service interfaces for dependency injection and testing

// ClusterService defines the interface for cluster operations
type ClusterService interface {
	GetClusters(ctx context.Context, serverAddr string) ([]*models.Cluster, error)
	GetClusterByID(ctx context.Context, serverAddr, clusterID string) (*models.Cluster, error)
}

// InfobaseService defines the interface for infobase operations
type InfobaseService interface {
	GetInfobases(ctx context.Context, clusterID string) ([]*models.Infobase, error)
	GetInfobaseByID(ctx context.Context, clusterID, infobaseID string) (*models.Infobase, error)
	CreateInfobase(ctx context.Context, clusterID string, infobase *models.Infobase) (string, error)
	DropInfobase(ctx context.Context, clusterID, infobaseID string, dropDB bool) error
	LockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error
	UnlockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error
	BlockSessions(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string, deniedFrom, deniedTo time.Time, deniedMsg, permCode, param string) error
	UnblockSessions(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error
}

// SessionService defines the interface for session operations
type SessionService interface {
	GetSessions(ctx context.Context, clusterID, infobaseID string) ([]*models.Session, error)
	TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error)
}

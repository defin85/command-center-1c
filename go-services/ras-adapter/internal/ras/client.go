package ras

import (
	"context"
	"fmt"
	"time"

	rclient "github.com/khorevaa/ras-client"
	"github.com/khorevaa/ras-client/serialize"
	uuid "github.com/satori/go.uuid"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"go.uber.org/zap"
)

// Client represents a RAS protocol client
// Week 3: Real RAS binary protocol implementation using khorevaa/ras-client
type Client struct {
	rasClient   *rclient.Client // Real RAS client
	serverAddr  string
	connTimeout time.Duration
	reqTimeout  time.Duration
	logger      *zap.Logger
}

// NewClient creates a new RAS client with real protocol implementation
func NewClient(serverAddr string, connTimeout, reqTimeout time.Duration, logger *zap.Logger) (*Client, error) {
	if serverAddr == "" {
		return nil, ErrInvalidParams
	}

	if logger == nil {
		logger = zap.NewNop()
	}

	// Create real RAS client using khorevaa/ras-client
	rasClient := rclient.NewClient(serverAddr)

	logger.Info("RAS client created successfully",
		zap.String("server", serverAddr),
		zap.Duration("conn_timeout", connTimeout),
		zap.Duration("req_timeout", reqTimeout))

	return &Client{
		rasClient:   rasClient,
		serverAddr:  serverAddr,
		connTimeout: connTimeout,
		reqTimeout:  reqTimeout,
		logger:      logger,
	}, nil
}

// Close closes RAS connection
func (c *Client) Close() error {
	if c.rasClient != nil {
		c.logger.Info("Closing RAS client connection")
		return c.rasClient.Close()
	}
	return nil
}

// GetClusters retrieves list of clusters from RAS server (REAL implementation)
func (c *Client) GetClusters(ctx context.Context) ([]*models.Cluster, error) {
	c.logger.Debug("GetClusters called (REAL RAS protocol)")

	// Call real RAS client
	rasClusters, err := c.rasClient.GetClusters(ctx)
	if err != nil {
		c.logger.Error("RAS GetClusters failed", zap.Error(err))
		return nil, fmt.Errorf("RAS GetClusters failed: %w", err)
	}

	// Convert RAS types → domain models
	clusters := make([]*models.Cluster, 0, len(rasClusters))
	for _, rasCluster := range rasClusters {
		clusters = append(clusters, &models.Cluster{
			UUID: rasCluster.UUID.String(),
			Name: rasCluster.Name,
			Host: rasCluster.Host,
			Port: int32(rasCluster.Port),
		})
	}

	c.logger.Debug("GetClusters completed", zap.Int("count", len(clusters)))
	return clusters, nil
}

// GetInfobases retrieves list of infobases for a cluster (REAL implementation)
func (c *Client) GetInfobases(ctx context.Context, clusterID string) ([]*models.Infobase, error) {
	if clusterID == "" {
		return nil, ErrInvalidParams
	}

	c.logger.Debug("GetInfobases called (REAL RAS protocol)", zap.String("cluster_id", clusterID))

	// Parse cluster UUID
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return nil, fmt.Errorf("invalid cluster UUID: %w", err)
	}

	// Authenticate cluster first (required even for security-level=0)
	c.rasClient.AuthenticateCluster(clusterUUID, "", "")

	// Call real RAS client
	rasInfobasesSummary, err := c.rasClient.GetClusterInfobases(ctx, clusterUUID)
	if err != nil {
		c.logger.Error("RAS GetClusterInfobases failed", zap.Error(err))
		return nil, fmt.Errorf("RAS GetClusterInfobases failed: %w", err)
	}

	// Convert RAS types → domain models
	infobases := make([]*models.Infobase, 0, len(rasInfobasesSummary))
	for _, rasIBSummary := range rasInfobasesSummary {
		// Retrieve full info to get ScheduledJobsDeny and SessionsDeny
		fullInfo, err := c.rasClient.GetInfobaseInfo(ctx, clusterUUID, rasIBSummary.UUID)
		if err != nil {
			c.logger.Warn("Failed to get full infobase info",
				zap.String("infobase_id", rasIBSummary.UUID.String()),
				zap.Error(err))
			// Continue with summary info
			infobases = append(infobases, &models.Infobase{
				UUID:              rasIBSummary.UUID.String(),
				Name:              rasIBSummary.Name,
				DBMS:              "",
				DBServer:          "",
				DBName:            "",
				ScheduledJobsDeny: false, // Default if full info unavailable
				SessionsDeny:      false,
			})
			continue
		}

		infobases = append(infobases, &models.Infobase{
			UUID:              fullInfo.UUID.String(),
			Name:              fullInfo.Name,
			DBMS:              fullInfo.Dbms,
			DBServer:          fullInfo.DbServer,
			DBName:            fullInfo.DbName,
			ScheduledJobsDeny: fullInfo.ScheduledJobsDeny,
			SessionsDeny:      fullInfo.SessionsDeny,
		})
	}

	c.logger.Debug("GetInfobases completed", zap.Int("count", len(infobases)))
	return infobases, nil
}
// GetSessions retrieves list of sessions for a cluster and infobase (REAL implementation)
func (c *Client) GetSessions(ctx context.Context, clusterID, infobaseID string) ([]*models.Session, error) {
	if clusterID == "" {
		return nil, ErrInvalidParams
	}

	c.logger.Debug("GetSessions called (REAL RAS protocol)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Parse cluster UUID
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return nil, fmt.Errorf("invalid cluster UUID: %w", err)
	}

	// Authenticate cluster
	c.rasClient.AuthenticateCluster(clusterUUID, "", "")

	// Call real RAS client
	var rasSessions serialize.SessionInfoList
	if infobaseID != "" {
		// Get sessions for specific infobase
		infobaseUUID, err := uuid.FromString(infobaseID)
		if err != nil {
			return nil, fmt.Errorf("invalid infobase UUID: %w", err)
		}
		rasSessions, err = c.rasClient.GetInfobaseSessions(ctx, clusterUUID, infobaseUUID)
	} else {
		// Get all cluster sessions
		rasSessions, err = c.rasClient.GetClusterSessions(ctx, clusterUUID)
	}

	if err != nil {
		c.logger.Error("RAS GetSessions failed", zap.Error(err))
		return nil, fmt.Errorf("RAS GetSessions failed: %w", err)
	}

	// Convert RAS types → domain models
	sessions := make([]*models.Session, 0, len(rasSessions))
	for _, rasSess := range rasSessions {
		sessions = append(sessions, &models.Session{
			UUID:        rasSess.UUID.String(),
			SessionID:   rasSess.UUID.String(), // UUID as SessionID for compatibility
			UserName:    rasSess.UserName,
			Application: rasSess.AppId,
			StartedAt:   rasSess.StartedAt.Format(time.RFC3339),
		})
	}

	c.logger.Debug("GetSessions completed", zap.Int("count", len(sessions)))
	return sessions, nil
}

// GetInfobaseInfo retrieves detailed infobase info (REAL implementation)
func (c *Client) GetInfobaseInfo(ctx context.Context, clusterID, infobaseID string) (*models.Infobase, error) {
	if clusterID == "" || infobaseID == "" {
		return nil, ErrInvalidParams
	}

	c.logger.Debug("GetInfobaseInfo called (REAL RAS protocol)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Parse UUIDs
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return nil, fmt.Errorf("invalid cluster UUID: %w", err)
	}

	infobaseUUID, err := uuid.FromString(infobaseID)
	if err != nil {
		return nil, fmt.Errorf("invalid infobase UUID: %w", err)
	}

	// Authenticate cluster
	c.rasClient.AuthenticateCluster(clusterUUID, "", "")

	// Call real RAS client
	rasIB, err := c.rasClient.GetInfobaseInfo(ctx, clusterUUID, infobaseUUID)
	if err != nil {
		c.logger.Error("RAS GetInfobaseInfo failed", zap.Error(err))
		return nil, fmt.Errorf("RAS GetInfobaseInfo failed: %w", err)
	}

	// Convert RAS type → domain model
	infobase := &models.Infobase{
		UUID:              rasIB.UUID.String(),
		Name:              rasIB.Name,
		DBMS:              rasIB.Dbms,
		DBServer:          rasIB.DbServer,
		DBName:            rasIB.DbName,
		ScheduledJobsDeny: rasIB.ScheduledJobsDeny,
		SessionsDeny:      rasIB.SessionsDeny,
	}

	c.logger.Debug("GetInfobaseInfo completed",
		zap.String("name", infobase.Name),
		zap.Bool("scheduled_jobs_deny", infobase.ScheduledJobsDeny))

	return infobase, nil
}
// RegInfoBase registers/updates infobase (REAL implementation - CRITICAL for Lock/Unlock!)
func (c *Client) RegInfoBase(ctx context.Context, clusterID string, infobase *models.Infobase) error {
	if clusterID == "" || infobase == nil {
		return ErrInvalidParams
	}

	c.logger.Debug("RegInfoBase called (REAL RAS protocol)",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobase.UUID),
		zap.Bool("scheduled_jobs_deny", infobase.ScheduledJobsDeny),
		zap.Bool("sessions_deny", infobase.SessionsDeny))

	// Parse UUIDs
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return fmt.Errorf("invalid cluster UUID: %w", err)
	}

	infobaseUUID, err := uuid.FromString(infobase.UUID)
	if err != nil {
		return fmt.Errorf("invalid infobase UUID: %w", err)
	}

	// Authenticate cluster
	c.rasClient.AuthenticateCluster(clusterUUID, "", "")

	// Convert domain model → RAS type
	rasInfobase := serialize.InfobaseInfo{
		UUID:              infobaseUUID,
		Name:              infobase.Name,
		Dbms:              infobase.DBMS,
		DbServer:          infobase.DBServer,
		DbName:            infobase.DBName,
		ScheduledJobsDeny: infobase.ScheduledJobsDeny, // KEY FIELD for Lock/Unlock
		SessionsDeny:      infobase.SessionsDeny,
	}

	// Call real RAS UpdateInfobase
	err = c.rasClient.UpdateInfobase(ctx, clusterUUID, rasInfobase)
	if err != nil {
		c.logger.Error("RAS UpdateInfobase failed", zap.Error(err))
		return fmt.Errorf("RAS UpdateInfobase failed: %w", err)
	}

	c.logger.Info("RegInfoBase completed successfully",
		zap.String("infobase_id", infobase.UUID),
		zap.Bool("scheduled_jobs_deny", infobase.ScheduledJobsDeny))

	return nil
}

// TerminateSession terminates a single session (REAL implementation)
func (c *Client) TerminateSession(ctx context.Context, clusterID, sessionID string) error {
	if clusterID == "" || sessionID == "" {
		return ErrInvalidParams
	}

	c.logger.Debug("TerminateSession called (REAL RAS protocol)",
		zap.String("cluster_id", clusterID),
		zap.String("session_id", sessionID))

	// Parse UUIDs
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return fmt.Errorf("invalid cluster UUID: %w", err)
	}

	sessionUUID, err := uuid.FromString(sessionID)
	if err != nil {
		return fmt.Errorf("invalid session UUID: %w", err)
	}

	// Authenticate cluster
	c.rasClient.AuthenticateCluster(clusterUUID, "", "")

	// Call real RAS client
	err = c.rasClient.TerminateSession(ctx, clusterUUID, sessionUUID, "Terminated by RAS Adapter")
	if err != nil {
		c.logger.Error("RAS TerminateSession failed", zap.Error(err))
		return fmt.Errorf("RAS TerminateSession failed: %w", err)
	}

	c.logger.Info("TerminateSession completed successfully", zap.String("session_id", sessionID))
	return nil
}

// LockInfobase locks an infobase (blocks scheduled jobs)
func (c *Client) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	if clusterID == "" || infobaseID == "" {
		return ErrInvalidParams
	}

	// 1. Get current infobase info
	infobase, err := c.GetInfobaseInfo(ctx, clusterID, infobaseID)
	if err != nil {
		return fmt.Errorf("failed to get infobase info: %w", err)
	}

	// Nil-check to prevent panic
	if infobase == nil {
		return fmt.Errorf("infobase is nil after GetInfobaseInfo (cluster: %s, infobase: %s)", clusterID, infobaseID)
	}

	// 2. Modify ONLY scheduled_jobs_deny field
	infobase.ScheduledJobsDeny = true
	infobase.SessionsDeny = false // Explicitly keep sessions allowed

	// 3. Call RegInfoBase
	err = c.RegInfoBase(ctx, clusterID, infobase)
	if err != nil {
		return fmt.Errorf("RegInfoBase failed: %w", err)
	}

	return nil
}

// UnlockInfobase unlocks an infobase (enables scheduled jobs)
func (c *Client) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	if clusterID == "" || infobaseID == "" {
		return ErrInvalidParams
	}

	// 1. Get current infobase info
	infobase, err := c.GetInfobaseInfo(ctx, clusterID, infobaseID)
	if err != nil {
		return fmt.Errorf("failed to get infobase info: %w", err)
	}

	// Nil-check to prevent panic
	if infobase == nil {
		return fmt.Errorf("infobase is nil after GetInfobaseInfo (cluster: %s, infobase: %s)", clusterID, infobaseID)
	}

	// 2. Modify ONLY scheduled_jobs_deny field
	infobase.ScheduledJobsDeny = false
	infobase.SessionsDeny = false

	// 3. Call RegInfoBase
	err = c.RegInfoBase(ctx, clusterID, infobase)
	if err != nil {
		return fmt.Errorf("RegInfoBase failed: %w", err)
	}

	return nil
}

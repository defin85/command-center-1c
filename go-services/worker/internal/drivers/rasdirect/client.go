package rasdirect

import (
	"context"
	"fmt"
	"time"

	rclient "github.com/commandcenter1c/commandcenter/ras-adapter/ras-client"
	"github.com/commandcenter1c/commandcenter/ras-adapter/ras-client/serialize"
	uuid "github.com/satori/go.uuid"
)

type Client struct {
	serverAddr string
	ras        *rclient.Client
}

func NewClient(serverAddr string) (*Client, error) {
	if serverAddr == "" {
		return nil, fmt.Errorf("ras_server is required")
	}
	return &Client{
		serverAddr: serverAddr,
		ras:        rclient.NewClient(serverAddr),
	}, nil
}

func (c *Client) Close() error {
	if c.ras == nil {
		return nil
	}
	return c.ras.Close()
}

type Cluster struct {
	UUID string
	Name string
	Host string
	Port int
}

func (c *Client) GetClusters(ctx context.Context) ([]Cluster, error) {
	clusters, err := c.ras.GetClusters(ctx)
	if err != nil {
		return nil, fmt.Errorf("ras get clusters: %w", err)
	}

	out := make([]Cluster, 0, len(clusters))
	for _, cl := range clusters {
		out = append(out, Cluster{
			UUID: cl.UUID.String(),
			Name: cl.Name,
			Host: cl.Host,
			Port: int(cl.Port),
		})
	}
	return out, nil
}

type Infobase struct {
	UUID              string
	Name              string
	DBMS              string
	DBServer          string
	DBName            string
	DBUser            string
	DBPwd             string
	Locale            string
	ScheduledJobsDeny bool
	SessionsDeny      bool

	DeniedFrom      time.Time
	DeniedTo        time.Time
	DeniedMessage   string
	DeniedParameter string
	PermissionCode  string
}

func (c *Client) GetInfobases(ctx context.Context, clusterID, clusterUser, clusterPwd string) ([]Infobase, error) {
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return nil, fmt.Errorf("invalid cluster UUID: %w", err)
	}

	c.ras.AuthenticateCluster(clusterUUID, clusterUser, clusterPwd)

	summary, err := c.ras.GetClusterInfobases(ctx, clusterUUID)
	if err != nil {
		return nil, fmt.Errorf("ras get cluster infobases: %w", err)
	}

	out := make([]Infobase, 0, len(summary))
	for _, s := range summary {
		full, err := c.ras.GetInfobaseInfo(ctx, clusterUUID, s.UUID)
		if err != nil {
			out = append(out, Infobase{
				UUID: s.UUID.String(),
				Name: s.Name,
			})
			continue
		}
		out = append(out, fromRASInfobase(full))
	}
	return out, nil
}

func (c *Client) GetInfobaseInfo(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string) (*Infobase, error) {
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return nil, fmt.Errorf("invalid cluster UUID: %w", err)
	}
	infobaseUUID, err := uuid.FromString(infobaseID)
	if err != nil {
		return nil, fmt.Errorf("invalid infobase UUID: %w", err)
	}

	c.ras.AuthenticateCluster(clusterUUID, clusterUser, clusterPwd)

	ib, err := c.ras.GetInfobaseInfo(ctx, clusterUUID, infobaseUUID)
	if err != nil {
		return nil, fmt.Errorf("ras get infobase info: %w", err)
	}
	res := fromRASInfobase(ib)
	return &res, nil
}

func fromRASInfobase(ib serialize.InfobaseInfo) Infobase {
	return Infobase{
		UUID:              ib.UUID.String(),
		Name:              ib.Name,
		DBMS:              ib.Dbms,
		DBServer:          ib.DbServer,
		DBName:            ib.DbName,
		DBUser:            ib.DbUser,
		DBPwd:             ib.DbPwd,
		Locale:            ib.Locale,
		ScheduledJobsDeny: ib.ScheduledJobsDeny,
		SessionsDeny:      ib.SessionsDeny,

		DeniedFrom:      ib.DeniedFrom,
		DeniedTo:        ib.DeniedTo,
		DeniedMessage:   ib.DeniedMessage,
		DeniedParameter: ib.DeniedParameter,
		PermissionCode:  ib.PermissionCode,
	}
}

func (c *Client) UpdateInfobase(ctx context.Context, clusterID string, ib Infobase, clusterUser, clusterPwd string) error {
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return fmt.Errorf("invalid cluster UUID: %w", err)
	}
	infobaseUUID, err := uuid.FromString(ib.UUID)
	if err != nil {
		return fmt.Errorf("invalid infobase UUID: %w", err)
	}

	c.ras.AuthenticateCluster(clusterUUID, clusterUser, clusterPwd)

	req := serialize.InfobaseInfo{
		UUID:              infobaseUUID,
		Name:              ib.Name,
		Dbms:              ib.DBMS,
		DbServer:          ib.DBServer,
		DbName:            ib.DBName,
		DbUser:            ib.DBUser,
		DbPwd:             ib.DBPwd,
		Locale:            ib.Locale,
		ScheduledJobsDeny: ib.ScheduledJobsDeny,
		SessionsDeny:      ib.SessionsDeny,
		DeniedFrom:        ib.DeniedFrom,
		DeniedTo:          ib.DeniedTo,
		DeniedMessage:     ib.DeniedMessage,
		PermissionCode:    ib.PermissionCode,
		DeniedParameter:   ib.DeniedParameter,
	}

	if err := c.ras.UpdateInfobase(ctx, clusterUUID, req); err != nil {
		return fmt.Errorf("ras update infobase: %w", err)
	}
	return nil
}

func (c *Client) LockScheduledJobs(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string) error {
	ib, err := c.GetInfobaseInfo(ctx, clusterID, infobaseID, clusterUser, clusterPwd)
	if err != nil {
		return err
	}
	ib.ScheduledJobsDeny = true
	return c.UpdateInfobase(ctx, clusterID, *ib, clusterUser, clusterPwd)
}

func (c *Client) UnlockScheduledJobs(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string) error {
	ib, err := c.GetInfobaseInfo(ctx, clusterID, infobaseID, clusterUser, clusterPwd)
	if err != nil {
		return err
	}
	ib.ScheduledJobsDeny = false
	return c.UpdateInfobase(ctx, clusterID, *ib, clusterUser, clusterPwd)
}

func (c *Client) BlockSessions(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string, deniedFrom, deniedTo time.Time, message, permissionCode, parameter string) error {
	ib, err := c.GetInfobaseInfo(ctx, clusterID, infobaseID, clusterUser, clusterPwd)
	if err != nil {
		return err
	}
	ib.SessionsDeny = true
	ib.DeniedFrom = deniedFrom
	ib.DeniedTo = deniedTo
	ib.DeniedMessage = message
	ib.PermissionCode = permissionCode
	ib.DeniedParameter = parameter
	return c.UpdateInfobase(ctx, clusterID, *ib, clusterUser, clusterPwd)
}

func (c *Client) UnblockSessions(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string) error {
	ib, err := c.GetInfobaseInfo(ctx, clusterID, infobaseID, clusterUser, clusterPwd)
	if err != nil {
		return err
	}
	ib.SessionsDeny = false
	ib.DeniedFrom = time.Time{}
	ib.DeniedTo = time.Time{}
	ib.DeniedMessage = ""
	ib.PermissionCode = ""
	ib.DeniedParameter = ""
	return c.UpdateInfobase(ctx, clusterID, *ib, clusterUser, clusterPwd)
}

func (c *Client) TerminateAllSessions(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string) error {
	clusterUUID, err := uuid.FromString(clusterID)
	if err != nil {
		return fmt.Errorf("invalid cluster UUID: %w", err)
	}
	infobaseUUID, err := uuid.FromString(infobaseID)
	if err != nil {
		return fmt.Errorf("invalid infobase UUID: %w", err)
	}

	c.ras.AuthenticateCluster(clusterUUID, clusterUser, clusterPwd)

	sessions, err := c.ras.GetInfobaseSessions(ctx, clusterUUID, infobaseUUID)
	if err != nil {
		return fmt.Errorf("ras get infobase sessions: %w", err)
	}
	for _, s := range sessions {
		if err := c.ras.TerminateSession(ctx, clusterUUID, s.UUID, "Terminated by Worker"); err != nil {
			return fmt.Errorf("ras terminate session %s: %w", s.UUID.String(), err)
		}
	}
	return nil
}

package rasops

import (
	"context"
	"fmt"
	"os"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/clusterinfo"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/rasdirect"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
)

type InfobaseDriver struct {
	workerID        string
	clusterResolver clusterinfo.Resolver
	timeline        tracing.TimelineRecorder
	rasAdapterURL   string
}

func NewInfobaseDriver(workerID string, clusterResolver clusterinfo.Resolver, timeline tracing.TimelineRecorder, rasAdapterURL string) *InfobaseDriver {
	return &InfobaseDriver{
		workerID:        workerID,
		clusterResolver: clusterResolver,
		timeline:        timeline,
		rasAdapterURL:   rasAdapterURL,
	}
}

func (d *InfobaseDriver) Name() string { return "rasops-infobase" }

func (d *InfobaseDriver) OperationTypes() []string {
	return InfobaseOperationTypes()
}

func (d *InfobaseDriver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	start := time.Now()
	log := logger.GetLogger()

	eventBase := fmt.Sprintf("ras.%s", msg.OperationType)
	d.timeline.Record(ctx, msg.OperationID, eventBase+".started", map[string]interface{}{
		"database_id": databaseID,
	})

	clusterInfo, err := d.clusterResolver.Resolve(ctx, databaseID)
	if err != nil {
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", map[string]interface{}{
			"database_id":  databaseID,
			"error":        err.Error(),
			"duration_ms":  time.Since(start).Milliseconds(),
			"error_source": "cluster_info",
		})
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to resolve cluster info: %v", err),
			ErrorCode:  "CLUSTER_INFO_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, nil
	}

	clusterID := clusterInfo.ClusterID
	infobaseID := clusterInfo.InfobaseID
	payload := msg.Payload.Data

	useDirect := os.Getenv("USE_DIRECT_RAS") != "false"
	var opErr error
	if useDirect && clusterInfo.RASServer != "" {
		dc, err := rasdirect.NewClient(clusterInfo.RASServer)
		if err != nil {
			opErr = err
		} else {
			defer dc.Close()
			switch msg.OperationType {
			case "lock_scheduled_jobs":
				opErr = dc.LockScheduledJobs(ctx, clusterID, infobaseID, clusterInfo.ClusterUser, clusterInfo.ClusterPwd)
			case "unlock_scheduled_jobs":
				opErr = dc.UnlockScheduledJobs(ctx, clusterID, infobaseID, clusterInfo.ClusterUser, clusterInfo.ClusterPwd)
			case "block_sessions":
				deniedFrom, deniedTo, err := parseDeniedWindow(payload)
				if err != nil {
					opErr = err
					break
				}
				opErr = dc.BlockSessions(
					ctx,
					clusterID,
					infobaseID,
					clusterInfo.ClusterUser,
					clusterInfo.ClusterPwd,
					deniedFrom,
					deniedTo,
					extractString(payload, "message"),
					extractString(payload, "permission_code"),
					extractString(payload, "parameter"),
				)
			case "unblock_sessions":
				opErr = dc.UnblockSessions(ctx, clusterID, infobaseID, clusterInfo.ClusterUser, clusterInfo.ClusterPwd)
			case "terminate_sessions":
				opErr = dc.TerminateAllSessions(ctx, clusterID, infobaseID, clusterInfo.ClusterUser, clusterInfo.ClusterPwd)
			default:
				opErr = fmt.Errorf("unsupported RAS operation type: %s", msg.OperationType)
			}
		}
	} else {
		if d.rasAdapterURL == "" {
			opErr = fmt.Errorf("ras adapter base URL is required (RAS_ADAPTER_URL)")
		} else {
			client, err := rasadapter.NewClientWithConfig(rasadapter.ClientConfig{
				BaseURL:     d.rasAdapterURL,
				Timeout:     30 * time.Second,
				MaxRetries:  2,
				BaseBackoff: 300 * time.Millisecond,
			})
			if err != nil {
				opErr = err
			} else {
				switch msg.OperationType {
				case "lock_scheduled_jobs":
					_, opErr = client.LockScheduledJobs(ctx, clusterID, infobaseID, &rasadapter.LockInfobaseRequest{})
				case "unlock_scheduled_jobs":
					_, opErr = client.UnlockScheduledJobs(ctx, clusterID, infobaseID, &rasadapter.UnlockInfobaseRequest{})
				case "block_sessions":
					deniedFrom, deniedTo, err := parseDeniedWindow(payload)
					if err != nil {
						opErr = err
						break
					}
					req := &rasadapter.BlockSessionsRequest{
						DeniedFrom:     deniedFrom.UTC().Format(time.RFC3339),
						DeniedTo:       deniedTo.UTC().Format(time.RFC3339),
						DeniedMessage:  extractString(payload, "message"),
						PermissionCode: extractString(payload, "permission_code"),
						Parameter:      extractString(payload, "parameter"),
					}
					_, opErr = client.BlockSessions(ctx, clusterID, infobaseID, req)
				case "unblock_sessions":
					_, opErr = client.UnblockSessions(ctx, clusterID, infobaseID, &rasadapter.UnblockSessionsRequest{})
				case "terminate_sessions":
					_, opErr = client.TerminateAllSessions(ctx, clusterID, infobaseID)
				default:
					opErr = fmt.Errorf("unsupported RAS operation type: %s", msg.OperationType)
				}
			}
		}
	}

	duration := time.Since(start)
	if opErr != nil {
		log.Warn("RAS infobase operation failed",
			zap.String("operation_id", msg.OperationID),
			zap.String("operation_type", msg.OperationType),
			zap.String("database_id", databaseID),
			zap.String("cluster_id", clusterID),
			zap.String("infobase_id", infobaseID),
			zap.Error(opErr),
		)
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", map[string]interface{}{
			"database_id": databaseID,
			"cluster_id":  clusterID,
			"infobase_id": infobaseID,
			"error":       opErr.Error(),
			"duration_ms": duration.Milliseconds(),
		})
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      opErr.Error(),
			ErrorCode:  "RAS_ERROR",
			Duration:   duration.Seconds(),
		}, nil
	}

	d.timeline.Record(ctx, msg.OperationID, eventBase+".completed", map[string]interface{}{
		"database_id": databaseID,
		"cluster_id":  clusterID,
		"infobase_id": infobaseID,
		"duration_ms": duration.Milliseconds(),
	})

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Data: map[string]interface{}{
			"cluster_id":  clusterID,
			"infobase_id": infobaseID,
		},
		Duration: duration.Seconds(),
	}, nil
}

func parseDeniedWindow(payload map[string]interface{}) (time.Time, time.Time, error) {
	now := time.Now().UTC()
	from := now
	to := now.Add(24 * time.Hour)

	if s := extractString(payload, "denied_from"); s != "" {
		t, err := time.Parse(time.RFC3339, s)
		if err != nil {
			return time.Time{}, time.Time{}, fmt.Errorf("invalid denied_from (expected RFC3339): %w", err)
		}
		from = t.UTC()
	}
	if s := extractString(payload, "denied_to"); s != "" {
		t, err := time.Parse(time.RFC3339, s)
		if err != nil {
			return time.Time{}, time.Time{}, fmt.Errorf("invalid denied_to (expected RFC3339): %w", err)
		}
		to = t.UTC()
	}
	if !to.After(from) {
		return time.Time{}, time.Time{}, fmt.Errorf("invalid denied window: denied_to must be after denied_from")
	}
	return from, to, nil
}

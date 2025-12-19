package processor

import (
	"context"
	"fmt"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
)

var rasInfobaseOperationTypes = map[string]struct{}{
	"lock_scheduled_jobs":   {},
	"unlock_scheduled_jobs": {},
	"block_sessions":        {},
	"unblock_sessions":      {},
	"terminate_sessions":    {},
}

func RasInfobaseOperationTypes() []string {
	out := make([]string, 0, len(rasInfobaseOperationTypes))
	for t := range rasInfobaseOperationTypes {
		out = append(out, t)
	}
	return out
}

func isRasInfobaseOperationType(operationType string) bool {
	_, ok := rasInfobaseOperationTypes[operationType]
	return ok
}

func extractString(data map[string]interface{}, key string) string {
	if data == nil {
		return ""
	}
	v, ok := data[key]
	if !ok || v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprintf("%v", v)
}

func (p *TaskProcessor) getRasHTTPClient() (*rasadapter.Client, error) {
	if p.rasHTTPClient != nil {
		return p.rasHTTPClient, nil
	}

	client, err := rasadapter.NewClientWithConfig(rasadapter.ClientConfig{
		BaseURL:     p.config.RASAdapterURL,
		Timeout:     30 * time.Second,
		MaxRetries:  2,
		BaseBackoff: 300 * time.Millisecond,
	})
	if err != nil {
		return nil, err
	}

	p.rasHTTPClient = client
	return client, nil
}

func (p *TaskProcessor) processRasInfobaseOperation(
	ctx context.Context,
	msg *models.OperationMessage,
	databaseID string,
) models.DatabaseResultV2 {
	start := time.Now()
	log := logger.GetLogger()

	eventBase := fmt.Sprintf("ras.%s", msg.OperationType)
	p.timeline.Record(ctx, msg.OperationID, eventBase+".started", map[string]interface{}{
		"database_id": databaseID,
	})

	clusterInfo, err := p.clusterResolver.Resolve(ctx, databaseID)
	if err != nil {
		p.timeline.Record(ctx, msg.OperationID, eventBase+".failed", map[string]interface{}{
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
		}
	}

	client, err := p.getRasHTTPClient()
	if err != nil {
		p.timeline.Record(ctx, msg.OperationID, eventBase+".failed", map[string]interface{}{
			"database_id":  databaseID,
			"error":        err.Error(),
			"duration_ms":  time.Since(start).Milliseconds(),
			"error_source": "ras_client",
		})
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to create RAS adapter client: %v", err),
			ErrorCode:  "CLIENT_ERROR",
			Duration:   time.Since(start).Seconds(),
		}
	}

	clusterID := clusterInfo.ClusterID
	infobaseID := clusterInfo.InfobaseID

	data := msg.Payload.Data
	var opErr error

	switch msg.OperationType {
	case "lock_scheduled_jobs":
		_, opErr = client.LockScheduledJobs(ctx, clusterID, infobaseID, &rasadapter.LockInfobaseRequest{})
	case "unlock_scheduled_jobs":
		_, opErr = client.UnlockScheduledJobs(ctx, clusterID, infobaseID, &rasadapter.UnlockInfobaseRequest{})
	case "block_sessions":
		req := &rasadapter.BlockSessionsRequest{
			DeniedMessage:  extractString(data, "message"),
			PermissionCode: extractString(data, "permission_code"),
		}
		_, opErr = client.BlockSessions(ctx, clusterID, infobaseID, req)
	case "unblock_sessions":
		_, opErr = client.UnblockSessions(ctx, clusterID, infobaseID, &rasadapter.UnblockSessionsRequest{})
	case "terminate_sessions":
		_, opErr = client.TerminateAllSessions(ctx, clusterID, infobaseID)
	default:
		opErr = fmt.Errorf("unsupported RAS operation type: %s", msg.OperationType)
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
		p.timeline.Record(ctx, msg.OperationID, eventBase+".failed", map[string]interface{}{
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
		}
	}

	p.timeline.Record(ctx, msg.OperationID, eventBase+".completed", map[string]interface{}{
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
	}
}

package rasops

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/rasdirect"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
)

type MetaDriver struct {
	workerID       string
	redisClient    *redis.Client
	eventPublisher *events.EventPublisher
	timeline       tracing.TimelineRecorder
}

func NewMetaDriver(workerID string, redisClient *redis.Client, publisher *events.EventPublisher, timeline tracing.TimelineRecorder) *MetaDriver {
	return &MetaDriver{
		workerID:       workerID,
		redisClient:    redisClient,
		eventPublisher: publisher,
		timeline:       timeline,
	}
}

func (d *MetaDriver) Name() string { return "rasops-meta" }

func (d *MetaDriver) OperationTypes() []string {
	return []string{"sync_cluster", "discover_clusters"}
}

func (d *MetaDriver) Execute(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error) {
	switch msg.OperationType {
	case "sync_cluster":
		return d.executeSyncCluster(ctx, msg)
	case "discover_clusters":
		return d.executeDiscoverClusters(ctx, msg)
	default:
		return nil, fmt.Errorf("rasops meta driver: unsupported operation_type=%q", msg.OperationType)
	}
}

func (d *MetaDriver) executeSyncCluster(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error) {
	log := logger.GetLogger()
	start := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    d.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	if err := d.eventPublisher.PublishProcessing(ctx, msg.OperationID, "cluster", d.workerID); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	payload, err := parseSyncClusterPayload(msg.Payload.Data)
	if err != nil {
		return d.failSyncCluster(result, start, fmt.Sprintf("failed to parse payload: %v", err), "PAYLOAD_ERROR"), nil
	}
	if err := validateSyncClusterPayload(payload); err != nil {
		return d.failSyncCluster(result, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	d.timeline.Record(ctx, msg.OperationID, "cluster.sync.started", map[string]interface{}{
		"worker_id":  d.workerID,
		"cluster_id": payload.ClusterID,
	})

	directClient, err := rasdirect.NewClient(payload.RASServer)
	if err != nil {
		return d.failSyncCluster(result, start, fmt.Sprintf("failed to create direct RAS client: %v", err), "CLIENT_ERROR"), nil
	}
	defer directClient.Close()

	rasClusterUUID := payload.RASClusterUUID
	if rasClusterUUID == "" {
		resolveStart := time.Now()
		d.timeline.Record(ctx, msg.OperationID, "cluster.sync.resolving.started", map[string]interface{}{
			"cluster_name": payload.ClusterName,
			"ras_server":   payload.RASServer,
		})

		clusterName := normalizeClusterName(payload.ClusterName)
		if clusterName == "" {
			return d.failSyncCluster(result, start, "cluster_name is required when ras_cluster_uuid is empty", "VALIDATION_ERROR"), nil
		}

		list, err := directClient.GetClusters(ctx)
		if err != nil {
			return d.failSyncCluster(result, start, fmt.Sprintf("failed to resolve cluster UUID (direct): %v", err), "CLUSTER_LOOKUP_ERROR"), nil
		}
		for _, c := range list {
			if strings.EqualFold(normalizeClusterName(c.Name), clusterName) {
				rasClusterUUID = c.UUID
				break
			}
		}
		if rasClusterUUID == "" {
			return d.failSyncCluster(result, start, fmt.Sprintf("cluster not found by name: %s", payload.ClusterName), "CLUSTER_LOOKUP_ERROR"), nil
		}

		d.timeline.Record(ctx, msg.OperationID, "cluster.sync.resolving.finished", map[string]interface{}{
			"ras_cluster_uuid": rasClusterUUID,
			"duration_ms":      time.Since(resolveStart).Milliseconds(),
		})
	}

	d.timeline.Record(ctx, msg.OperationID, "cluster.sync.fetching.started", map[string]interface{}{
		"ras_cluster_uuid": rasClusterUUID,
	})

	fetchStart := time.Now()
	var infobasesCount int
	var infobases []map[string]interface{}
	list, err := directClient.GetInfobases(ctx, rasClusterUUID, payload.ClusterUser, payload.ClusterPwd)
	if err != nil {
		return d.failSyncCluster(result, start, fmt.Sprintf("failed to list infobases (direct): %v", err), "RAS_ERROR"), nil
	}
	infobasesCount = len(list)
	infobases = make([]map[string]interface{}, 0, len(list))
	for _, ib := range list {
		infobases = append(infobases, map[string]interface{}{
			"uuid":                ib.UUID,
			"name":                ib.Name,
			"dbms":                ib.DBMS,
			"db_server":           ib.DBServer,
			"db_name":             ib.DBName,
			"scheduled_jobs_deny": ib.ScheduledJobsDeny,
			"sessions_deny":       ib.SessionsDeny,
			"denied_from":         ib.DeniedFrom,
			"denied_to":           ib.DeniedTo,
			"denied_message":      ib.DeniedMessage,
			"permission_code":     ib.PermissionCode,
			"denied_parameter":    ib.DeniedParameter,
		})
	}

	d.timeline.Record(ctx, msg.OperationID, "cluster.sync.fetching.finished", map[string]interface{}{
		"ras_cluster_uuid": rasClusterUUID,
		"infobases_count":  infobasesCount,
		"duration_ms":      time.Since(fetchStart).Milliseconds(),
	})

	syncResult := SyncClusterResult{
		OperationID:    msg.OperationID,
		ClusterID:      payload.ClusterID,
		RASClusterUUID: rasClusterUUID,
		Infobases:      infobases,
		Success:        true,
	}

	publishStart := time.Now()
	d.timeline.Record(ctx, msg.OperationID, "cluster.sync.publish_result.started", map[string]interface{}{
		"stream": StreamKeyClusterSynced,
	})
	if err := publishSyncClusterResult(d.redisClient, syncResult); err != nil {
		log.Error("failed to publish sync result to Redis Stream", zap.Error(err))
		d.timeline.Record(ctx, msg.OperationID, "cluster.sync.publish_result.failed", map[string]interface{}{
			"duration_ms": time.Since(publishStart).Milliseconds(),
			"error":       err.Error(),
		})
	} else {
		d.timeline.Record(ctx, msg.OperationID, "cluster.sync.publish_result.finished", map[string]interface{}{
			"duration_ms": time.Since(publishStart).Milliseconds(),
		})
	}

	{
		publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := d.eventPublisher.PublishSuccess(publishCtx, msg.OperationID); err != nil {
			log.Error("failed to publish SUCCESS event", zap.Error(err))
		}
	}

	duration := time.Since(start).Seconds()
	result.Status = "completed"
	result.Results = append(result.Results, models.DatabaseResultV2{
		DatabaseID: "cluster:" + payload.ClusterID,
		Success:    true,
		Data: map[string]interface{}{
			"cluster_id":       payload.ClusterID,
			"ras_cluster_uuid": rasClusterUUID,
			"infobases_count":  infobasesCount,
			"infobases":        infobases,
		},
		Duration: duration,
	})
	result.Summary = models.ResultSummary{
		Total:       1,
		Succeeded:   1,
		Failed:      0,
		AvgDuration: duration,
	}

	d.timeline.Record(ctx, msg.OperationID, "cluster.sync.completed", map[string]interface{}{
		"cluster_id":      payload.ClusterID,
		"infobases_count": infobasesCount,
		"duration_ms":     time.Since(start).Milliseconds(),
	})

	return result, nil
}

func (d *MetaDriver) executeDiscoverClusters(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error) {
	log := logger.GetLogger()
	start := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    d.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	if err := d.eventPublisher.PublishProcessing(ctx, msg.OperationID, "discovery", d.workerID); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	payload, err := parseDiscoverClustersPayload(msg.Payload.Data)
	if err != nil {
		return d.failDiscoverClusters(result, start, fmt.Sprintf("failed to parse payload: %v", err), "PAYLOAD_ERROR"), nil
	}
	if err := validateDiscoverClustersPayload(payload); err != nil {
		return d.failDiscoverClusters(result, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	d.timeline.Record(ctx, msg.OperationID, "clusters.discover.started", map[string]interface{}{
		"worker_id":   d.workerID,
		"ras_server":  payload.RASServer,
	})

	var clusters []map[string]interface{}
	var clustersCount int
	client, err := rasdirect.NewClient(payload.RASServer)
	if err != nil {
		return d.failDiscoverClusters(result, start, fmt.Sprintf("failed to create direct RAS client: %v", err), "CLIENT_ERROR"), nil
	}
	defer client.Close()

	list, err := client.GetClusters(ctx)
	if err != nil {
		return d.failDiscoverClusters(result, start, fmt.Sprintf("failed to list clusters (direct RAS): %v", err), "RAS_ERROR"), nil
	}
	clustersCount = len(list)
	clusters = make([]map[string]interface{}, 0, len(list))
	for _, c := range list {
		clusters = append(clusters, map[string]interface{}{
			"uuid": c.UUID,
			"name": c.Name,
			"host": c.Host,
			"port": c.Port,
		})
	}

	discoverResult := DiscoverClustersResult{
		OperationID: msg.OperationID,
		RASServer:   payload.RASServer,
		Clusters:    clusters,
		Success:     true,
	}
	if err := publishDiscoverClustersResult(d.redisClient, ctx, discoverResult); err != nil {
		log.Error("failed to publish discover result to Redis Stream", zap.Error(err))
	}

	if err := d.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
		log.Error("failed to publish SUCCESS event", zap.Error(err))
	}

	duration := time.Since(start).Seconds()
	result.Status = "completed"
	result.Results = append(result.Results, models.DatabaseResultV2{
		DatabaseID: "discovery:" + payload.RASServer,
		Success:    true,
		Data: map[string]interface{}{
			"ras_server":     payload.RASServer,
			"clusters_count": clustersCount,
			"clusters":       clusters,
		},
		Duration: duration,
	})
	result.Summary = models.ResultSummary{
		Total:       1,
		Succeeded:   1,
		Failed:      0,
		AvgDuration: duration,
	}

	d.timeline.Record(ctx, msg.OperationID, "clusters.discover.completed", map[string]interface{}{
		"ras_server":     payload.RASServer,
		"clusters_count": clustersCount,
		"duration_ms":    time.Since(start).Milliseconds(),
	})

	return result, nil
}

func (d *MetaDriver) failSyncCluster(result *models.OperationResultV2, start time.Time, errorMsg, errorCode string) *models.OperationResultV2 {
	log := logger.GetLogger()
	duration := time.Since(start).Seconds()
	durationMs := time.Since(start).Milliseconds()

	d.timeline.Record(context.Background(), result.OperationID, "cluster.sync.failed", map[string]interface{}{
		"error_code":  errorCode,
		"error":       errorMsg,
		"duration_ms": durationMs,
	})

	log.Error("sync_cluster failed",
		zap.String("operation_id", result.OperationID),
		zap.String("error", errorMsg),
		zap.String("error_code", errorCode),
	)

	{
		publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := d.eventPublisher.PublishFailed(publishCtx, result.OperationID, errorMsg); err != nil {
			log.Error("failed to publish FAILED event", zap.Error(err))
		}
	}

	result.Status = "failed"
	result.Results = append(result.Results, models.DatabaseResultV2{
		DatabaseID: "cluster",
		Success:    false,
		Error:      errorMsg,
		ErrorCode:  errorCode,
		Duration:   duration,
	})
	result.Summary = models.ResultSummary{
		Total:       1,
		Succeeded:   0,
		Failed:      1,
		AvgDuration: duration,
	}
	return result
}

func (d *MetaDriver) failDiscoverClusters(result *models.OperationResultV2, start time.Time, errorMsg, errorCode string) *models.OperationResultV2 {
	log := logger.GetLogger()
	duration := time.Since(start).Seconds()

	d.timeline.Record(context.Background(), result.OperationID, "clusters.discover.failed", map[string]interface{}{
		"error_code":  errorCode,
		"error":       errorMsg,
		"duration_ms": time.Since(start).Milliseconds(),
	})

	log.Error("discover_clusters failed",
		zap.String("operation_id", result.OperationID),
		zap.String("error", errorMsg),
		zap.String("error_code", errorCode),
	)

	{
		publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := d.eventPublisher.PublishFailed(publishCtx, result.OperationID, errorMsg); err != nil {
			log.Error("failed to publish FAILED event", zap.Error(err))
		}
	}

	result.Status = "failed"
	result.Results = append(result.Results, models.DatabaseResultV2{
		DatabaseID: "discovery",
		Success:    false,
		Error:      errorMsg,
		ErrorCode:  errorCode,
		Duration:   duration,
	})
	result.Summary = models.ResultSummary{
		Total:       1,
		Succeeded:   0,
		Failed:      1,
		AvgDuration: duration,
	}
	return result
}

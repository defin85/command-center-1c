// go-services/worker/internal/processor/sync_cluster.go
package processor

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
)

// SyncClusterPayload contains data for sync_cluster operation
type SyncClusterPayload struct {
	ClusterID         string `json:"cluster_id"`          // Django Cluster ID (UUID)
	RASServer         string `json:"ras_server"`          // RAS server address (host:port)
	RASClusterUUID    string `json:"ras_cluster_uuid"`    // RAS cluster UUID (may be empty)
	ClusterServiceURL string `json:"cluster_service_url"` // RAS Adapter URL
	ClusterName       string `json:"cluster_name"`        // Cluster name for lookup
	ClusterUser       string `json:"cluster_user"`        // Cluster admin user
	ClusterPwd        string `json:"cluster_pwd"`         // Cluster admin password
}

// SyncClusterResult contains the result of sync_cluster operation
type SyncClusterResult struct {
	OperationID    string                   `json:"operation_id"`
	ClusterID      string                   `json:"cluster_id"`
	RASClusterUUID string                   `json:"ras_cluster_uuid"`
	Infobases      []map[string]interface{} `json:"infobases"`
	Success        bool                     `json:"success"`
	Error          string                   `json:"error,omitempty"`
}

// processSyncCluster handles sync_cluster operation type.
// This operation syncs infobases from RAS cluster to Orchestrator.
func (p *TaskProcessor) processSyncCluster(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()
	start := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	// Publish PROCESSING event
	if err := p.eventPublisher.PublishProcessing(ctx, msg.OperationID, "cluster", p.workerID); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	// Parse payload (before timeline.started - validation first)
	payload, err := parseSyncClusterPayload(msg.Payload.Data)
	if err != nil {
		return p.failSyncCluster(ctx, result, start, fmt.Sprintf("failed to parse payload: %v", err), "PAYLOAD_ERROR")
	}

	// Validate required fields (before timeline.started)
	if err := validateSyncClusterPayload(payload); err != nil {
		return p.failSyncCluster(ctx, result, start, err.Error(), "VALIDATION_ERROR")
	}

	// Timeline: operation started (AFTER successful validation)
	p.timeline.Record(ctx, msg.OperationID, "cluster.sync.started", map[string]interface{}{
		"worker_id":  p.workerID,
		"cluster_id": payload.ClusterID,
	})

	log.Info("starting sync_cluster operation",
		zap.String("operation_id", msg.OperationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.String("ras_server", payload.RASServer),
		zap.String("cluster_name", payload.ClusterName),
	)

	// Create RAS Adapter client
	rasClient, err := rasadapter.NewClientWithConfig(rasadapter.ClientConfig{
		BaseURL:    payload.ClusterServiceURL,
		Timeout:    30 * time.Second,
		MaxRetries: 3,
	})
	if err != nil {
		return p.failSyncCluster(ctx, result, start, fmt.Sprintf("failed to create RAS client: %v", err), "CLIENT_ERROR")
	}

	// Resolve RAS cluster UUID if not provided
	rasClusterUUID := payload.RASClusterUUID
	if rasClusterUUID == "" {
		resolveStart := time.Now()
		// Timeline: resolving cluster UUID
		p.timeline.Record(ctx, msg.OperationID, "cluster.sync.resolving.started", map[string]interface{}{
			"cluster_name": payload.ClusterName,
			"ras_server":   payload.RASServer,
		})

		log.Info("RAS cluster UUID not provided, looking up by name",
			zap.String("cluster_name", payload.ClusterName),
		)

		resolved, err := resolveClusterUUID(ctx, rasClient, payload.RASServer, payload.ClusterName)
		if err != nil {
			return p.failSyncCluster(ctx, result, start, fmt.Sprintf("failed to resolve cluster UUID: %v", err), "CLUSTER_LOOKUP_ERROR")
		}
		rasClusterUUID = resolved

		p.timeline.Record(ctx, msg.OperationID, "cluster.sync.resolving.finished", map[string]interface{}{
			"ras_cluster_uuid": rasClusterUUID,
			"duration_ms":      time.Since(resolveStart).Milliseconds(),
		})

		log.Info("resolved RAS cluster UUID",
			zap.String("cluster_name", payload.ClusterName),
			zap.String("ras_cluster_uuid", rasClusterUUID),
		)
	}

	// Timeline: fetching infobases from RAS
	p.timeline.Record(ctx, msg.OperationID, "cluster.sync.fetching.started", map[string]interface{}{
		"ras_cluster_uuid": rasClusterUUID,
	})

	// Fetch infobases from RAS
	fetchStart := time.Now()
	infobasesResp, err := rasClient.ListInfobases(ctx, payload.RASServer, rasClusterUUID)
	if err != nil {
		return p.failSyncCluster(ctx, result, start, fmt.Sprintf("failed to list infobases: %v", err), "RAS_ERROR")
	}
	p.timeline.Record(ctx, msg.OperationID, "cluster.sync.fetching.finished", map[string]interface{}{
		"ras_cluster_uuid": rasClusterUUID,
		"infobases_count":  infobasesResp.Count,
		"duration_ms":      time.Since(fetchStart).Milliseconds(),
	})

	log.Info("fetched infobases from RAS",
		zap.String("cluster_id", payload.ClusterID),
		zap.Int("count", infobasesResp.Count),
	)

	// Convert infobases to generic format for Orchestrator
	infobases := convertInfobasesToMap(infobasesResp.Infobases)

	// Publish result to Redis Stream for Orchestrator
	syncResult := SyncClusterResult{
		OperationID:    msg.OperationID,
		ClusterID:      payload.ClusterID,
		RASClusterUUID: rasClusterUUID,
		Infobases:      infobases,
		Success:        true,
	}

	publishStart := time.Now()
	p.timeline.Record(ctx, msg.OperationID, "cluster.sync.publish_result.started", map[string]interface{}{
		"stream": "events:worker:cluster-synced",
	})
	if err := p.publishSyncClusterResult(ctx, syncResult); err != nil {
		log.Error("failed to publish sync result to Redis Stream", zap.Error(err))
		p.timeline.Record(ctx, msg.OperationID, "cluster.sync.publish_result.failed", map[string]interface{}{
			"duration_ms": time.Since(publishStart).Milliseconds(),
			"error":       err.Error(),
		})
		// Don't fail the operation - data was fetched successfully
	} else {
		p.timeline.Record(ctx, msg.OperationID, "cluster.sync.publish_result.finished", map[string]interface{}{
			"duration_ms": time.Since(publishStart).Milliseconds(),
		})
	}

	// Publish SUCCESS event
	{
		publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := p.eventPublisher.PublishSuccess(publishCtx, msg.OperationID); err != nil {
			log.Error("failed to publish SUCCESS event", zap.Error(err))
		}
	}

	// Build success result
	duration := time.Since(start).Seconds()
	result.Status = "completed"
	result.Results = append(result.Results, models.DatabaseResultV2{
		DatabaseID: "cluster:" + payload.ClusterID,
		Success:    true,
		Data: map[string]interface{}{
			"cluster_id":       payload.ClusterID,
			"ras_cluster_uuid": rasClusterUUID,
			"infobases_count":  infobasesResp.Count,
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

	// Timeline: sync completed successfully
	p.timeline.Record(ctx, msg.OperationID, "cluster.sync.completed", map[string]interface{}{
		"cluster_id":      payload.ClusterID,
		"infobases_count": infobasesResp.Count,
		"duration_ms":     time.Since(start).Milliseconds(),
	})

	log.Info("sync_cluster completed successfully",
		zap.String("operation_id", msg.OperationID),
		zap.String("cluster_id", payload.ClusterID),
		zap.Int("infobases_count", infobasesResp.Count),
		zap.Float64("duration_seconds", duration),
	)

	return result
}

// failSyncCluster creates a failed result and publishes FAILED event
func (p *TaskProcessor) failSyncCluster(ctx context.Context, result *models.OperationResultV2, start time.Time, errorMsg, errorCode string) *models.OperationResultV2 {
	log := logger.GetLogger()
	duration := time.Since(start).Seconds()
	durationMs := time.Since(start).Milliseconds()

	// Timeline: sync failed
	p.timeline.Record(ctx, result.OperationID, "cluster.sync.failed", map[string]interface{}{
		"error_code":  errorCode,
		"error":       errorMsg,
		"duration_ms": durationMs,
	})

	log.Error("sync_cluster failed",
		zap.String("operation_id", result.OperationID),
		zap.String("error", errorMsg),
		zap.String("error_code", errorCode),
	)

	// Publish FAILED event
	{
		publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := p.eventPublisher.PublishFailed(publishCtx, result.OperationID, errorMsg); err != nil {
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

// parseSyncClusterPayload parses the payload data into SyncClusterPayload
func parseSyncClusterPayload(data map[string]interface{}) (*SyncClusterPayload, error) {
	// Marshal to JSON and unmarshal to struct for type-safe parsing
	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal payload data: %w", err)
	}

	var payload SyncClusterPayload
	if err := json.Unmarshal(jsonData, &payload); err != nil {
		return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
	}

	return &payload, nil
}

// validateSyncClusterPayload validates required fields in payload
func validateSyncClusterPayload(payload *SyncClusterPayload) error {
	if payload.ClusterID == "" {
		return fmt.Errorf("cluster_id is required")
	}
	if payload.RASServer == "" {
		return fmt.Errorf("ras_server is required")
	}
	if payload.ClusterServiceURL == "" {
		return fmt.Errorf("cluster_service_url is required")
	}
	// cluster_name is required if ras_cluster_uuid is not provided
	if payload.RASClusterUUID == "" && payload.ClusterName == "" {
		return fmt.Errorf("either ras_cluster_uuid or cluster_name is required")
	}
	return nil
}

// resolveClusterUUID looks up cluster UUID by name from RAS server
func resolveClusterUUID(ctx context.Context, client *rasadapter.Client, server, clusterName string) (string, error) {
	clustersResp, err := client.ListClusters(ctx, server)
	if err != nil {
		return "", fmt.Errorf("failed to list clusters: %w", err)
	}

	// Find cluster by name (case-insensitive comparison)
	for _, cluster := range clustersResp.Clusters {
		if cluster.Name == clusterName {
			return cluster.UUID, nil
		}
	}

	// If exact match not found, try case-insensitive
	for _, cluster := range clustersResp.Clusters {
		if stringToLower(cluster.Name) == stringToLower(clusterName) {
			return cluster.UUID, nil
		}
	}

	return "", fmt.Errorf("cluster with name '%s' not found on server %s", clusterName, server)
}

// convertInfobasesToMap converts Infobase structs to generic maps
func convertInfobasesToMap(infobases []*rasadapter.Infobase) []map[string]interface{} {
	result := make([]map[string]interface{}, 0, len(infobases))

	for _, ib := range infobases {
		item := map[string]interface{}{
			"uuid":                 ib.UUID,
			"name":                 ib.Name,
			"description":          ib.Description,
			"dbms":                 ib.DBMS,
			"db_server":            ib.DBServerName, // Match Python field name (db_server)
			"db_name":              ib.DBName,
			"sessions_deny":        ib.SessionsDenied,      // Match Python field name
			"scheduled_jobs_deny":  ib.ScheduledJobsDenied, // Match Python field name
			"license_distribution": ib.LicenseDistribution,
		}
		result = append(result, item)
	}

	return result
}

// publishSyncClusterResult publishes sync result to Redis Stream for Orchestrator
func (p *TaskProcessor) publishSyncClusterResult(ctx context.Context, result SyncClusterResult) error {
	if p.redisClient == nil {
		return fmt.Errorf("redis client not initialized")
	}

	// Decouple event publishing from operation timeout context.
	// Sync operations may run close to their deadline; publishing the cluster-synced
	// event is critical for Orchestrator to import databases.
	publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Serialize result to JSON
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	// Publish to Redis Stream
	streamKey := "events:worker:cluster-synced"
	_, err = p.redisClient.XAdd(publishCtx, &redis.XAddArgs{
		Stream: streamKey,
		Values: map[string]interface{}{
			"event_type":     "cluster.synced",
			"correlation_id": result.OperationID,
			"payload":        string(data),
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
		},
	}).Result()

	if err != nil {
		return fmt.Errorf("failed to publish to stream %s: %w", streamKey, err)
	}

	logger.GetLogger().Debug("published sync result to Redis Stream",
		zap.String("stream", streamKey),
		zap.String("operation_id", result.OperationID),
		zap.String("cluster_id", result.ClusterID),
	)

	return nil
}

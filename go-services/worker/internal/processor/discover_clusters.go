// go-services/worker/internal/processor/discover_clusters.go
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

// StreamKeyClustersDiscovered is the Redis Stream key for cluster discovery results
const StreamKeyClustersDiscovered = "events:worker:clusters-discovered"

// DiscoverClustersPayload contains data for discover_clusters operation
type DiscoverClustersPayload struct {
	RASServer   string `json:"ras_server"`          // RAS server address (host:port)
	ClusterUser string `json:"cluster_user,omitempty"` // Optional cluster admin user
	ClusterPwd  string `json:"cluster_pwd,omitempty"`  // Optional cluster admin password
}

// DiscoverClustersResult contains the result of discover_clusters operation
type DiscoverClustersResult struct {
	OperationID string                   `json:"operation_id"`
	RASServer   string                   `json:"ras_server"`
	Clusters    []map[string]interface{} `json:"clusters"`
	Success     bool                     `json:"success"`
	Error       string                   `json:"error,omitempty"`
}

// processDiscoverClusters handles discover_clusters operation type.
// This operation discovers all clusters from a RAS server.
func (p *TaskProcessor) processDiscoverClusters(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()
	start := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	// Publish PROCESSING event
	if err := p.eventPublisher.PublishProcessing(ctx, msg.OperationID, "discovery", p.workerID); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	// Parse payload
	payload, err := parseDiscoverClustersPayload(msg.Payload.Data)
	if err != nil {
		return p.failDiscoverClusters(ctx, result, start, fmt.Sprintf("failed to parse payload: %v", err), "PAYLOAD_ERROR")
	}

	// Validate required fields
	if err := validateDiscoverClustersPayload(payload); err != nil {
		return p.failDiscoverClusters(ctx, result, start, err.Error(), "VALIDATION_ERROR")
	}

	log.Info("starting discover_clusters operation",
		zap.String("operation_id", msg.OperationID),
		zap.String("ras_server", payload.RASServer),
	)

	// Create RAS Adapter client
	rasClient, err := rasadapter.NewClient()
	if err != nil {
		return p.failDiscoverClusters(ctx, result, start, fmt.Sprintf("failed to create RAS client: %v", err), "CLIENT_ERROR")
	}

	// Fetch clusters from RAS server
	clustersResp, err := rasClient.ListClusters(ctx, payload.RASServer)
	if err != nil {
		return p.failDiscoverClusters(ctx, result, start, fmt.Sprintf("failed to list clusters: %v", err), "RAS_ERROR")
	}

	log.Info("discovered clusters from RAS server",
		zap.String("ras_server", payload.RASServer),
		zap.Int("count", clustersResp.Count),
	)

	// Convert clusters to generic format
	clusters := convertClustersToMap(clustersResp.Clusters)

	// Publish result to Redis Stream for Orchestrator
	discoverResult := DiscoverClustersResult{
		OperationID: msg.OperationID,
		RASServer:   payload.RASServer,
		Clusters:    clusters,
		Success:     true,
	}

	if err := p.publishDiscoverClustersResult(ctx, discoverResult); err != nil {
		log.Error("failed to publish discover result to Redis Stream", zap.Error(err))
		// Don't fail the operation - data was fetched successfully
	}

	// Publish SUCCESS event
	if err := p.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
		log.Error("failed to publish SUCCESS event", zap.Error(err))
	}

	// Build success result
	duration := time.Since(start).Seconds()
	result.Status = "completed"
	result.Results = append(result.Results, models.DatabaseResultV2{
		DatabaseID: "discovery:" + payload.RASServer,
		Success:    true,
		Data: map[string]interface{}{
			"ras_server":     payload.RASServer,
			"clusters_count": clustersResp.Count,
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

	log.Info("discover_clusters completed successfully",
		zap.String("operation_id", msg.OperationID),
		zap.String("ras_server", payload.RASServer),
		zap.Int("clusters_count", clustersResp.Count),
		zap.Float64("duration_seconds", duration),
	)

	return result
}

// failDiscoverClusters creates a failed result and publishes FAILED event
func (p *TaskProcessor) failDiscoverClusters(ctx context.Context, result *models.OperationResultV2, start time.Time, errorMsg, errorCode string) *models.OperationResultV2 {
	log := logger.GetLogger()
	duration := time.Since(start).Seconds()

	log.Error("discover_clusters failed",
		zap.String("operation_id", result.OperationID),
		zap.String("error", errorMsg),
		zap.String("error_code", errorCode),
	)

	// Publish FAILED event
	if err := p.eventPublisher.PublishFailed(ctx, result.OperationID, errorMsg); err != nil {
		log.Error("failed to publish FAILED event", zap.Error(err))
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

// parseDiscoverClustersPayload parses the payload data into DiscoverClustersPayload
func parseDiscoverClustersPayload(data map[string]interface{}) (*DiscoverClustersPayload, error) {
	// Marshal to JSON and unmarshal to struct for type-safe parsing
	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal payload data: %w", err)
	}

	var payload DiscoverClustersPayload
	if err := json.Unmarshal(jsonData, &payload); err != nil {
		return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
	}

	return &payload, nil
}

// validateDiscoverClustersPayload validates required fields in payload
func validateDiscoverClustersPayload(payload *DiscoverClustersPayload) error {
	if payload.RASServer == "" {
		return fmt.Errorf("ras_server is required")
	}
	return nil
}

// convertClustersToMap converts Cluster structs to generic maps
func convertClustersToMap(clusters []*rasadapter.Cluster) []map[string]interface{} {
	result := make([]map[string]interface{}, 0, len(clusters))

	for _, c := range clusters {
		item := map[string]interface{}{
			"uuid": c.UUID,
			"name": c.Name,
			"host": c.Host,
			"port": c.Port,
		}
		result = append(result, item)
	}

	return result
}

// publishDiscoverClustersResult publishes discover result to Redis Stream for Orchestrator
func (p *TaskProcessor) publishDiscoverClustersResult(ctx context.Context, result DiscoverClustersResult) error {
	if p.redisClient == nil {
		return fmt.Errorf("redis client not initialized")
	}

	// Serialize result to JSON
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	// Publish to Redis Stream
	_, err = p.redisClient.XAdd(ctx, &redis.XAddArgs{
		Stream: StreamKeyClustersDiscovered,
		Values: map[string]interface{}{
			"event_type":     "clusters.discovered",
			"correlation_id": result.OperationID,
			"payload":        string(data),
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
		},
	}).Result()

	if err != nil {
		return fmt.Errorf("failed to publish to stream %s: %w", StreamKeyClustersDiscovered, err)
	}

	logger.GetLogger().Debug("published discover result to Redis Stream",
		zap.String("stream", StreamKeyClustersDiscovered),
		zap.String("operation_id", result.OperationID),
		zap.String("ras_server", result.RASServer),
	)

	return nil
}

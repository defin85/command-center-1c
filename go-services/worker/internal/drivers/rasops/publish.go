package rasops

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/logger"
)

func publishSyncClusterResult(redisClient *redis.Client, result SyncClusterResult) error {
	if redisClient == nil {
		return fmt.Errorf("redis client not initialized")
	}

	// Decouple event publishing from operation timeout context.
	// Sync operations may run close to their deadline; publishing the cluster-synced
	// event is critical for Orchestrator to import databases.
	publishCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	_, err = redisClient.XAdd(publishCtx, &redis.XAddArgs{
		Stream: StreamKeyClusterSynced,
		Values: map[string]interface{}{
			"event_type":     streamEventTypeClusterSynced,
			"correlation_id": result.OperationID,
			"payload":        string(data),
			"timestamp":      time.Now().UTC().Format(time.RFC3339),
		},
	}).Result()
	if err != nil {
		return fmt.Errorf("failed to publish to stream %s: %w", StreamKeyClusterSynced, err)
	}

	logger.GetLogger().Debug("published sync result to Redis Stream",
		zap.String("stream", StreamKeyClusterSynced),
		zap.String("operation_id", result.OperationID),
		zap.String("cluster_id", result.ClusterID),
	)
	return nil
}

func publishDiscoverClustersResult(redisClient *redis.Client, ctx context.Context, result DiscoverClustersResult) error {
	if redisClient == nil {
		return fmt.Errorf("redis client not initialized")
	}

	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	_, err = redisClient.XAdd(ctx, &redis.XAddArgs{
		Stream: StreamKeyClustersDiscovered,
		Values: map[string]interface{}{
			"event_type":     streamEventTypeClustersDisc,
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

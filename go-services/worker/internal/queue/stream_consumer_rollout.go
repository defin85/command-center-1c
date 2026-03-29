package queue

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

const (
	defaultFactualPerDatabaseCap   = 1
	defaultFactualPerClusterCap    = 2
	defaultFactualGlobalCap        = 8
	factualRolloutAdmissionBackoff = 10 * time.Millisecond
	factualSyncOperationType       = "pool.factual.sync_source_slice"
	factualSyncDatabaseKeyFallback = "shared"
	factualSyncClusterKeyFallback  = "shared"
)

type factualRolloutLimits struct {
	perDatabase int
	perCluster  int
	global      int
}

type factualRolloutScope struct {
	databases []string
	clusters  []string
}

func (c *Consumer) acquireFactualRolloutAdmission(
	ctx context.Context,
	msg *models.OperationMessage,
) (release func(), ok bool) {
	if !isFactualSyncRolloutMessage(msg) {
		return nil, true
	}

	for {
		release, acquired := c.tryAcquireFactualRolloutAdmission(msg)
		if acquired {
			return release, true
		}

		select {
		case <-ctx.Done():
			return nil, false
		case <-time.After(factualRolloutAdmissionBackoff):
		}
	}
}

func (c *Consumer) tryAcquireFactualRolloutAdmission(
	msg *models.OperationMessage,
) (release func(), ok bool) {
	if !isFactualSyncRolloutMessage(msg) {
		return nil, true
	}

	limits := resolveFactualRolloutLimits(msg)
	scope := resolveFactualRolloutScope(msg)

	c.factualRolloutMu.Lock()
	defer c.factualRolloutMu.Unlock()

	if c.factualRolloutActiveByDatabase == nil {
		c.factualRolloutActiveByDatabase = map[string]int{}
	}
	if c.factualRolloutActiveByCluster == nil {
		c.factualRolloutActiveByCluster = map[string]int{}
	}

	for _, databaseKey := range scope.databases {
		if c.factualRolloutActiveByDatabase[databaseKey] >= limits.perDatabase {
			return nil, false
		}
	}
	for _, clusterKey := range scope.clusters {
		if c.factualRolloutActiveByCluster[clusterKey] >= limits.perCluster {
			return nil, false
		}
	}
	if c.factualRolloutActiveTotal >= limits.global {
		return nil, false
	}

	updatedDatabases := uniqueKeys(scope.databases)
	updatedClusters := uniqueKeys(scope.clusters)
	for _, databaseKey := range updatedDatabases {
		c.factualRolloutActiveByDatabase[databaseKey]++
	}
	for _, clusterKey := range updatedClusters {
		c.factualRolloutActiveByCluster[clusterKey]++
	}
	c.factualRolloutActiveTotal++

	return func() {
		c.factualRolloutMu.Lock()
		defer c.factualRolloutMu.Unlock()

		if c.factualRolloutActiveTotal > 0 {
			c.factualRolloutActiveTotal--
		}
		for _, databaseKey := range updatedDatabases {
			next := c.factualRolloutActiveByDatabase[databaseKey] - 1
			if next <= 0 {
				delete(c.factualRolloutActiveByDatabase, databaseKey)
				continue
			}
			c.factualRolloutActiveByDatabase[databaseKey] = next
		}
		for _, clusterKey := range updatedClusters {
			next := c.factualRolloutActiveByCluster[clusterKey] - 1
			if next <= 0 {
				delete(c.factualRolloutActiveByCluster, clusterKey)
				continue
			}
			c.factualRolloutActiveByCluster[clusterKey] = next
		}
	}, true
}

func isFactualSyncRolloutMessage(msg *models.OperationMessage) bool {
	return msg != nil && strings.EqualFold(strings.TrimSpace(msg.OperationType), factualSyncOperationType)
}

func resolveFactualRolloutLimits(msg *models.OperationMessage) factualRolloutLimits {
	payload := map[string]interface{}{}
	if msg != nil {
		payload = msg.Payload.Data
	}
	return factualRolloutLimits{
		perDatabase: readRolloutCap(payload, "per_database_cap", defaultFactualPerDatabaseCap),
		perCluster:  readRolloutCap(payload, "per_cluster_cap", defaultFactualPerClusterCap),
		global:      readRolloutCap(payload, "global_cap", defaultFactualGlobalCap),
	}
}

func resolveFactualRolloutScope(msg *models.OperationMessage) factualRolloutScope {
	scope := factualRolloutScope{
		databases: []string{factualSyncDatabaseKeyFallback},
		clusters:  []string{factualSyncClusterKeyFallback},
	}
	if msg == nil {
		return scope
	}

	databaseKeys := make([]string, 0, len(msg.TargetDatabases))
	clusterKeys := make([]string, 0, len(msg.TargetDatabases))
	for _, target := range msg.TargetDatabases {
		if databaseKey := normalizeFactualRolloutKey(target.ID); databaseKey != "" {
			databaseKeys = append(databaseKeys, databaseKey)
		}
		if clusterKey := normalizeFactualRolloutKey(target.ClusterID); clusterKey != "" {
			clusterKeys = append(clusterKeys, clusterKey)
		}
	}

	if len(databaseKeys) == 0 {
		if databaseKey := normalizeFactualRolloutKey(readMessagePayloadToken(msg.Payload.Data, "database_id")); databaseKey != "" {
			databaseKeys = append(databaseKeys, databaseKey)
		}
	}
	if len(clusterKeys) == 0 {
		if clusterKey := normalizeFactualRolloutKey(readMessagePayloadToken(msg.Payload.Data, "cluster_id")); clusterKey != "" {
			clusterKeys = append(clusterKeys, clusterKey)
		}
	}

	if len(databaseKeys) > 0 {
		scope.databases = databaseKeys
	}
	if len(clusterKeys) > 0 {
		scope.clusters = clusterKeys
	}
	return scope
}

func readRolloutCap(payload map[string]interface{}, key string, fallback int) int {
	if len(payload) == 0 {
		return fallback
	}
	raw, exists := payload[key]
	if !exists || raw == nil {
		return fallback
	}

	switch value := raw.(type) {
	case int:
		if value > 0 {
			return value
		}
	case int8:
		if value > 0 {
			return int(value)
		}
	case int16:
		if value > 0 {
			return int(value)
		}
	case int32:
		if value > 0 {
			return int(value)
		}
	case int64:
		if value > 0 {
			return int(value)
		}
	case float32:
		if value > 0 {
			return int(value)
		}
	case float64:
		if value > 0 {
			return int(value)
		}
	case string:
		if parsed, err := strconv.Atoi(strings.TrimSpace(value)); err == nil && parsed > 0 {
			return parsed
		}
	default:
		if parsed, err := strconv.Atoi(strings.TrimSpace(fmt.Sprint(value))); err == nil && parsed > 0 {
			return parsed
		}
	}

	return fallback
}

func normalizeFactualRolloutKey(value string) string {
	return strings.TrimSpace(strings.ToLower(value))
}

func uniqueKeys(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(values))
	keys := make([]string, 0, len(values))
	for _, value := range values {
		if value == "" {
			continue
		}
		if _, exists := seen[value]; exists {
			continue
		}
		seen[value] = struct{}{}
		keys = append(keys, value)
	}
	return keys
}

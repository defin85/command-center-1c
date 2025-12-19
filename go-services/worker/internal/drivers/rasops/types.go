package rasops

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

const (
	StreamKeyClusterSynced       = "events:worker:cluster-synced"
	StreamKeyClustersDiscovered  = "events:worker:clusters-discovered"
	streamEventTypeClusterSynced = "cluster.synced"
	streamEventTypeClustersDisc  = "clusters.discovered"
)

// SyncClusterPayload contains data for sync_cluster operation
type SyncClusterPayload struct {
	ClusterID         string `json:"cluster_id"`          // Django Cluster ID (UUID)
	RASServer         string `json:"ras_server"`          // RAS server address (host:port)
	RASClusterUUID    string `json:"ras_cluster_uuid"`    // RAS cluster UUID (may be empty)
	ClusterServiceURL string `json:"cluster_service_url"` // RAS Adapter URL (fallback path)
	ClusterName       string `json:"cluster_name"`        // Cluster name for lookup
	ClusterUser       string `json:"cluster_user"`        // Cluster admin user
	ClusterPwd        string `json:"cluster_pwd"`         // Cluster admin password
}

func parseSyncClusterPayload(data map[string]interface{}) (*SyncClusterPayload, error) {
	b, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal payload data: %w", err)
	}
	var payload SyncClusterPayload
	if err := json.Unmarshal(b, &payload); err != nil {
		return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
	}
	return &payload, nil
}

func validateSyncClusterPayload(payload *SyncClusterPayload) error {
	if payload == nil {
		return fmt.Errorf("payload is required")
	}
	if payload.ClusterID == "" {
		return fmt.Errorf("cluster_id is required")
	}
	if payload.RASServer == "" {
		return fmt.Errorf("ras_server is required")
	}
	if payload.ClusterName == "" && payload.RASClusterUUID == "" {
		return fmt.Errorf("cluster_name is required when ras_cluster_uuid is empty")
	}
	return nil
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

// DiscoverClustersPayload contains data for discover_clusters operation
type DiscoverClustersPayload struct {
	RASServer string `json:"ras_server"` // RAS server address (host:port)
}

func parseDiscoverClustersPayload(data map[string]interface{}) (*DiscoverClustersPayload, error) {
	b, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal payload data: %w", err)
	}
	var payload DiscoverClustersPayload
	if err := json.Unmarshal(b, &payload); err != nil {
		return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
	}
	return &payload, nil
}

func validateDiscoverClustersPayload(payload *DiscoverClustersPayload) error {
	if payload == nil || payload.RASServer == "" {
		return fmt.Errorf("ras_server is required")
	}
	return nil
}

// DiscoverClustersResult contains the result of discover_clusters operation
type DiscoverClustersResult struct {
	OperationID string                   `json:"operation_id"`
	RASServer   string                   `json:"ras_server"`
	Clusters    []map[string]interface{} `json:"clusters"`
	Success     bool                     `json:"success"`
	Error       string                   `json:"error,omitempty"`
}

func toRFC3339OrEmpty(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.UTC().Format(time.RFC3339)
}

var rasInfobaseOperationTypes = map[string]struct{}{
	"lock_scheduled_jobs":   {},
	"unlock_scheduled_jobs": {},
	"block_sessions":        {},
	"unblock_sessions":      {},
	"terminate_sessions":    {},
}

func InfobaseOperationTypes() []string {
	out := make([]string, 0, len(rasInfobaseOperationTypes))
	for t := range rasInfobaseOperationTypes {
		out = append(out, t)
	}
	sort.Strings(out)
	return out
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

func normalizeClusterName(name string) string {
	return strings.TrimSpace(name)
}

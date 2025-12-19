package statemachine

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// stateData represents persisted state
type stateData struct {
	State         InstallState `json:"state"`
	OperationID   string       `json:"operation_id"`
	DatabaseID    string       `json:"database_id"`
	CorrelationID string       `json:"correlation_id"`
	ClusterID     string       `json:"cluster_id"`
	InfobaseID    string       `json:"infobase_id"`
	ExtensionPath string       `json:"extension_path"`
	ExtensionName string       `json:"extension_name"`
	LastActivity  time.Time    `json:"last_activity"`
}

// saveState saves state to Redis (WITH lock for external callers)
func (sm *ExtensionInstallStateMachine) saveState(ctx context.Context) error {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.saveStateUnsafe(ctx)
}

// saveStateUnsafe saves state to Redis WITHOUT taking lock
// NOTE: Caller MUST hold sm.mu lock (either RLock or Lock)
// Used internally from transitionTo() which already holds lock
func (sm *ExtensionInstallStateMachine) saveStateUnsafe(ctx context.Context) error {
	// Skip if no Redis client (unit tests)
	if sm.redisClient == nil {
		return nil
	}

	data := stateData{
		State:         sm.State,
		OperationID:   sm.OperationID,
		DatabaseID:    sm.DatabaseID,
		CorrelationID: sm.CorrelationID,
		ClusterID:     sm.ClusterID,
		InfobaseID:    sm.InfobaseID,
		ExtensionPath: sm.ExtensionPath,
		ExtensionName: sm.ExtensionName,
		LastActivity:  sm.lastActivity,
	}

	bytes, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal state: %w", err)
	}

	key := fmt.Sprintf("workflow:%s:state", sm.CorrelationID)
	err = sm.redisClient.Set(ctx, key, bytes, sm.config.StateTTL).Err()
	if err != nil {
		return fmt.Errorf("failed to save state to Redis: %w", err)
	}

	return nil
}

// loadState loads state from Redis
func (sm *ExtensionInstallStateMachine) loadState(ctx context.Context) error {
	// Skip if no Redis client (unit tests)
	if sm.redisClient == nil {
		return fmt.Errorf("no redis client")
	}

	key := fmt.Sprintf("workflow:%s:state", sm.CorrelationID)

	bytes, err := sm.redisClient.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return fmt.Errorf("state not found")
	}
	if err != nil {
		return fmt.Errorf("failed to load state from Redis: %w", err)
	}

	var data stateData
	err = json.Unmarshal(bytes, &data)
	if err != nil {
		return fmt.Errorf("failed to unmarshal state: %w", err)
	}

	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.State = data.State
	sm.OperationID = data.OperationID
	sm.DatabaseID = data.DatabaseID
	sm.CorrelationID = data.CorrelationID
	sm.ClusterID = data.ClusterID
	sm.InfobaseID = data.InfobaseID
	sm.ExtensionPath = data.ExtensionPath
	sm.ExtensionName = data.ExtensionName
	sm.lastActivity = data.LastActivity

	fmt.Printf("[StateMachine] State loaded from Redis: %s\n", sm.State)

	return nil
}

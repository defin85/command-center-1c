package saga

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisStoreConfig holds configuration for RedisSagaStore.
type RedisStoreConfig struct {
	// KeyPrefix is the prefix for all saga keys.
	KeyPrefix string

	// StateTTL is the TTL for saga state (default: 7 days).
	StateTTL time.Duration

	// LockTTL is the default TTL for execution locks (default: 5 minutes).
	LockTTL time.Duration
}

// DefaultRedisStoreConfig returns default configuration.
func DefaultRedisStoreConfig() *RedisStoreConfig {
	return &RedisStoreConfig{
		KeyPrefix: "saga:",
		StateTTL:  7 * 24 * time.Hour,
		LockTTL:   5 * time.Minute,
	}
}

// RedisSagaStore implements SagaStore using Redis.
type RedisSagaStore struct {
	client  redis.Cmdable
	config  *RedisStoreConfig
	scripts struct {
		acquireLock *redis.Script
		releaseLock *redis.Script
	}
}

// NewRedisSagaStore creates a new Redis-based saga store.
func NewRedisSagaStore(client redis.Cmdable, config *RedisStoreConfig) *RedisSagaStore {
	if config == nil {
		config = DefaultRedisStoreConfig()
	}

	store := &RedisSagaStore{
		client: client,
		config: config,
	}

	// Lua script for atomic lock acquisition
	store.scripts.acquireLock = redis.NewScript(`
		local key = KEYS[1]
		local owner = ARGV[1]
		local ttl = tonumber(ARGV[2])

		local current = redis.call("GET", key)
		if current == false then
			redis.call("SET", key, owner, "PX", ttl)
			return 1
		elseif current == owner then
			redis.call("PEXPIRE", key, ttl)
			return 1
		end
		return 0
	`)

	// Lua script for safe lock release
	store.scripts.releaseLock = redis.NewScript(`
		local key = KEYS[1]
		local owner = ARGV[1]

		local current = redis.call("GET", key)
		if current == owner then
			redis.call("DEL", key)
			return 1
		end
		return 0
	`)

	return store
}

// stateKey returns the Redis key for saga state.
func (s *RedisSagaStore) stateKey(executionID string) string {
	return fmt.Sprintf("%sstate:%s", s.config.KeyPrefix, executionID)
}

// lockKey returns the Redis key for execution lock.
func (s *RedisSagaStore) lockKey(executionID string) string {
	return fmt.Sprintf("%slock:%s", s.config.KeyPrefix, executionID)
}

// statusIndexKey returns the Redis key for status index.
func (s *RedisSagaStore) statusIndexKey(status SagaStatus) string {
	return fmt.Sprintf("%sindex:status:%s", s.config.KeyPrefix, status)
}

// sagaIndexKey returns the Redis key for saga index (by saga ID).
func (s *RedisSagaStore) sagaIndexKey(sagaID string) string {
	return fmt.Sprintf("%sindex:saga:%s", s.config.KeyPrefix, sagaID)
}

// SaveState saves or updates saga state.
func (s *RedisSagaStore) SaveState(ctx context.Context, state *SagaState) error {
	if state == nil {
		return fmt.Errorf("state cannot be nil")
	}

	data, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("failed to marshal state: %w", err)
	}

	key := s.stateKey(state.ExecutionID)

	// Use pipeline for atomic operations
	pipe := s.client.TxPipeline()

	// Save state
	pipe.Set(ctx, key, data, s.config.StateTTL)

	// Update status index
	statusKey := s.statusIndexKey(state.Status)
	score := float64(state.UpdatedAt.UnixNano())
	pipe.ZAdd(ctx, statusKey, redis.Z{Score: score, Member: state.ExecutionID})

	// Update saga index
	sagaKey := s.sagaIndexKey(state.SagaID)
	pipe.ZAdd(ctx, sagaKey, redis.Z{Score: score, Member: state.ExecutionID})

	// Remove from old status indices if status changed
	// This is handled by scanning all status indices and removing the execution ID
	for _, status := range []SagaStatus{
		SagaStatusPending, SagaStatusRunning, SagaStatusCompleted,
		SagaStatusFailed, SagaStatusCompensating, SagaStatusCompensated,
		SagaStatusPartiallyCompensated,
	} {
		if status != state.Status {
			oldStatusKey := s.statusIndexKey(status)
			pipe.ZRem(ctx, oldStatusKey, state.ExecutionID)
		}
	}

	_, err = pipe.Exec(ctx)
	if err != nil {
		return fmt.Errorf("failed to save state: %w", err)
	}

	return nil
}

// LoadState loads saga state by execution ID.
func (s *RedisSagaStore) LoadState(ctx context.Context, executionID string) (*SagaState, error) {
	key := s.stateKey(executionID)

	data, err := s.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, ErrExecutionNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("failed to load state: %w", err)
	}

	state, err := SagaStateFromJSON(data)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal state: %w", err)
	}

	return state, nil
}

// DeleteState removes saga state.
func (s *RedisSagaStore) DeleteState(ctx context.Context, executionID string) error {
	// First load state to get saga ID and status for index cleanup
	state, err := s.LoadState(ctx, executionID)
	if err != nil {
		if err == ErrExecutionNotFound {
			return nil // Already deleted
		}
		return err
	}

	pipe := s.client.TxPipeline()

	// Delete state
	key := s.stateKey(executionID)
	pipe.Del(ctx, key)

	// Delete lock
	lockKey := s.lockKey(executionID)
	pipe.Del(ctx, lockKey)

	// Remove from status index
	statusKey := s.statusIndexKey(state.Status)
	pipe.ZRem(ctx, statusKey, executionID)

	// Remove from saga index
	sagaKey := s.sagaIndexKey(state.SagaID)
	pipe.ZRem(ctx, sagaKey, executionID)

	_, err = pipe.Exec(ctx)
	if err != nil {
		return fmt.Errorf("failed to delete state: %w", err)
	}

	return nil
}

// ListByStatus lists saga executions by status.
func (s *RedisSagaStore) ListByStatus(ctx context.Context, status SagaStatus, limit int) ([]*SagaState, error) {
	if limit <= 0 {
		limit = 100
	}

	statusKey := s.statusIndexKey(status)

	// Get execution IDs from index (ordered by update time, most recent first)
	executionIDs, err := s.client.ZRevRange(ctx, statusKey, 0, int64(limit-1)).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to list by status: %w", err)
	}

	if len(executionIDs) == 0 {
		return []*SagaState{}, nil
	}

	// Load states
	states := make([]*SagaState, 0, len(executionIDs))
	for _, execID := range executionIDs {
		state, err := s.LoadState(ctx, execID)
		if err != nil {
			if err == ErrExecutionNotFound {
				// State was deleted, remove from index
				s.client.ZRem(ctx, statusKey, execID)
				continue
			}
			return nil, err
		}
		states = append(states, state)
	}

	return states, nil
}

// ListBySaga lists saga executions by saga ID.
func (s *RedisSagaStore) ListBySaga(ctx context.Context, sagaID string, limit int) ([]*SagaState, error) {
	if limit <= 0 {
		limit = 100
	}

	sagaKey := s.sagaIndexKey(sagaID)

	executionIDs, err := s.client.ZRevRange(ctx, sagaKey, 0, int64(limit-1)).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to list by saga: %w", err)
	}

	if len(executionIDs) == 0 {
		return []*SagaState{}, nil
	}

	states := make([]*SagaState, 0, len(executionIDs))
	for _, execID := range executionIDs {
		state, err := s.LoadState(ctx, execID)
		if err != nil {
			if err == ErrExecutionNotFound {
				s.client.ZRem(ctx, sagaKey, execID)
				continue
			}
			return nil, err
		}
		states = append(states, state)
	}

	return states, nil
}

// AcquireLock acquires an execution lock.
func (s *RedisSagaStore) AcquireLock(ctx context.Context, executionID string, ttl time.Duration) (bool, error) {
	if ttl == 0 {
		ttl = s.config.LockTTL
	}

	key := s.lockKey(executionID)
	ttlMs := ttl.Milliseconds()

	result, err := s.scripts.acquireLock.Run(ctx, s.client, []string{key}, executionID, ttlMs).Int()
	if err != nil {
		return false, fmt.Errorf("failed to acquire lock: %w", err)
	}

	return result == 1, nil
}

// ReleaseLock releases an execution lock.
func (s *RedisSagaStore) ReleaseLock(ctx context.Context, executionID string) error {
	key := s.lockKey(executionID)

	_, err := s.scripts.releaseLock.Run(ctx, s.client, []string{key}, executionID).Int()
	if err != nil {
		return fmt.Errorf("failed to release lock: %w", err)
	}

	return nil
}

// ExtendLock extends the TTL of an existing lock.
func (s *RedisSagaStore) ExtendLock(ctx context.Context, executionID string, ttl time.Duration) error {
	if ttl == 0 {
		ttl = s.config.LockTTL
	}

	acquired, err := s.AcquireLock(ctx, executionID, ttl)
	if err != nil {
		return err
	}
	if !acquired {
		return fmt.Errorf("lock not held for execution: %s", executionID)
	}
	return nil
}

// Close releases resources.
func (s *RedisSagaStore) Close() error {
	// Don't close client as it may be shared
	return nil
}

// Cleanup removes expired saga states from indices.
func (s *RedisSagaStore) Cleanup(ctx context.Context, maxAge time.Duration) (int, error) {
	cutoff := time.Now().Add(-maxAge).UnixNano()
	removed := 0

	for _, status := range []SagaStatus{
		SagaStatusCompleted, SagaStatusCompensated, SagaStatusPartiallyCompensated,
	} {
		statusKey := s.statusIndexKey(status)

		// Get old entries
		entries, err := s.client.ZRangeByScore(ctx, statusKey, &redis.ZRangeBy{
			Min:   "-inf",
			Max:   fmt.Sprintf("%d", cutoff),
			Count: 100,
		}).Result()
		if err != nil {
			continue
		}

		for _, execID := range entries {
			if err := s.DeleteState(ctx, execID); err == nil {
				removed++
			}
		}
	}

	return removed, nil
}

// InMemorySagaStore is an in-memory implementation for testing.
type InMemorySagaStore struct {
	mu     sync.RWMutex
	states map[string]*SagaState
	locks  map[string]time.Time
}

// NewInMemorySagaStore creates an in-memory saga store for testing.
func NewInMemorySagaStore() *InMemorySagaStore {
	return &InMemorySagaStore{
		states: make(map[string]*SagaState),
		locks:  make(map[string]time.Time),
	}
}

// SaveState saves or updates saga state.
func (s *InMemorySagaStore) SaveState(_ context.Context, state *SagaState) error {
	if state == nil {
		return fmt.Errorf("state cannot be nil")
	}
	s.mu.Lock()
	defer s.mu.Unlock()

	// Deep copy to prevent external modifications
	data, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("failed to marshal state: %w", err)
	}
	var copy SagaState
	if err := json.Unmarshal(data, &copy); err != nil {
		return fmt.Errorf("failed to unmarshal state: %w", err)
	}
	s.states[state.ExecutionID] = &copy

	return nil
}

// LoadState loads saga state by execution ID.
func (s *InMemorySagaStore) LoadState(_ context.Context, executionID string) (*SagaState, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	state, exists := s.states[executionID]
	if !exists {
		return nil, ErrExecutionNotFound
	}

	// Deep copy to prevent external modifications
	data, err := json.Marshal(state)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal state: %w", err)
	}
	var copy SagaState
	if err := json.Unmarshal(data, &copy); err != nil {
		return nil, fmt.Errorf("failed to unmarshal state: %w", err)
	}

	return &copy, nil
}

// DeleteState removes saga state.
func (s *InMemorySagaStore) DeleteState(_ context.Context, executionID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.states, executionID)
	delete(s.locks, executionID)
	return nil
}

// ListByStatus lists saga executions by status.
func (s *InMemorySagaStore) ListByStatus(_ context.Context, status SagaStatus, limit int) ([]*SagaState, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if limit <= 0 {
		limit = 100
	}

	var results []*SagaState
	for _, state := range s.states {
		if state.Status == status {
			// Deep copy
			data, err := json.Marshal(state)
			if err != nil {
				return nil, fmt.Errorf("failed to marshal state: %w", err)
			}
			var copy SagaState
			if err := json.Unmarshal(data, &copy); err != nil {
				return nil, fmt.Errorf("failed to unmarshal state: %w", err)
			}
			results = append(results, &copy)

			if len(results) >= limit {
				break
			}
		}
	}

	return results, nil
}

// AcquireLock acquires an execution lock.
func (s *InMemorySagaStore) AcquireLock(_ context.Context, executionID string, ttl time.Duration) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if lockTime, exists := s.locks[executionID]; exists {
		// Check if lock is expired
		if time.Since(lockTime) < ttl {
			return false, nil
		}
	}

	s.locks[executionID] = time.Now()
	return true, nil
}

// ReleaseLock releases an execution lock.
func (s *InMemorySagaStore) ReleaseLock(_ context.Context, executionID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.locks, executionID)
	return nil
}

// Close releases resources.
func (s *InMemorySagaStore) Close() error {
	return nil
}

// GetAllStates returns all states (for testing).
func (s *InMemorySagaStore) GetAllStates() map[string]*SagaState {
	s.mu.RLock()
	defer s.mu.RUnlock()

	result := make(map[string]*SagaState, len(s.states))
	for k, v := range s.states {
		result[k] = v
	}
	return result
}

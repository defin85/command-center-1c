package state

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// StateStore defines the interface for workflow state persistence.
type StateStore interface {
	// SaveState saves the workflow state.
	SaveState(ctx context.Context, state *WorkflowState) error

	// LoadState loads the workflow state by execution ID.
	LoadState(ctx context.Context, executionID string) (*WorkflowState, error)

	// DeleteState removes the workflow state.
	DeleteState(ctx context.Context, executionID string) error

	// UpdateNodeState updates the state of a specific node.
	UpdateNodeState(ctx context.Context, executionID string, nodeState *NodeState) error

	// SaveCheckpoint saves a checkpoint for resume capability.
	SaveCheckpoint(ctx context.Context, executionID string, checkpoint *Checkpoint) error

	// LoadCheckpoint loads the latest checkpoint.
	LoadCheckpoint(ctx context.Context, executionID string) (*Checkpoint, error)

	// SetLock acquires a distributed lock for an execution.
	SetLock(ctx context.Context, executionID string, ttl time.Duration) (bool, error)

	// ReleaseLock releases the distributed lock.
	ReleaseLock(ctx context.Context, executionID string) error

	// Close closes the store connection.
	Close() error
}

// Checkpoint represents a resumable workflow checkpoint.
type Checkpoint struct {
	ExecutionID     string                 `json:"execution_id"`
	NodeID          string                 `json:"node_id"`
	Timestamp       time.Time              `json:"timestamp"`
	ContextSnapshot map[string]interface{} `json:"context_snapshot"`
	NodeStates      map[string]*NodeState  `json:"node_states"`
	CompletedNodes  []string               `json:"completed_nodes"`
}

// RedisStateStore implements StateStore using Redis.
type RedisStateStore struct {
	client       *redis.Client
	keyPrefix    string
	stateTTL     time.Duration
	checkpointTTL time.Duration
}

// RedisStateStoreConfig holds configuration for RedisStateStore.
type RedisStateStoreConfig struct {
	// KeyPrefix is the prefix for all keys (default: "wf:").
	KeyPrefix string
	// StateTTL is the TTL for state keys (default: 24h).
	StateTTL time.Duration
	// CheckpointTTL is the TTL for checkpoint keys (default: 7d).
	CheckpointTTL time.Duration
}

// DefaultRedisStateStoreConfig returns default configuration.
func DefaultRedisStateStoreConfig() *RedisStateStoreConfig {
	return &RedisStateStoreConfig{
		KeyPrefix:     "wf:",
		StateTTL:      24 * time.Hour,
		CheckpointTTL: 7 * 24 * time.Hour,
	}
}

// NewRedisStateStore creates a new Redis-based state store.
func NewRedisStateStore(client *redis.Client, config *RedisStateStoreConfig) *RedisStateStore {
	if config == nil {
		config = DefaultRedisStateStoreConfig()
	}
	return &RedisStateStore{
		client:        client,
		keyPrefix:     config.KeyPrefix,
		stateTTL:      config.StateTTL,
		checkpointTTL: config.CheckpointTTL,
	}
}

// stateKey returns the Redis key for workflow state.
func (s *RedisStateStore) stateKey(executionID string) string {
	return fmt.Sprintf("%sstate:%s", s.keyPrefix, executionID)
}

// nodeStateKey returns the Redis key for node state.
func (s *RedisStateStore) nodeStateKey(executionID, nodeID string) string {
	return fmt.Sprintf("%snode:%s:%s", s.keyPrefix, executionID, nodeID)
}

// checkpointKey returns the Redis key for checkpoint.
func (s *RedisStateStore) checkpointKey(executionID string) string {
	return fmt.Sprintf("%scheckpoint:%s", s.keyPrefix, executionID)
}

// lockKey returns the Redis key for distributed lock.
func (s *RedisStateStore) lockKey(executionID string) string {
	return fmt.Sprintf("%slock:%s", s.keyPrefix, executionID)
}

// SaveState saves the workflow state to Redis.
func (s *RedisStateStore) SaveState(ctx context.Context, state *WorkflowState) error {
	if state == nil {
		return fmt.Errorf("state cannot be nil")
	}

	data, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("failed to marshal state: %w", err)
	}

	key := s.stateKey(state.ExecutionID)
	if err := s.client.Set(ctx, key, data, s.stateTTL).Err(); err != nil {
		return fmt.Errorf("failed to save state to Redis: %w", err)
	}

	return nil
}

// LoadState loads the workflow state from Redis.
func (s *RedisStateStore) LoadState(ctx context.Context, executionID string) (*WorkflowState, error) {
	key := s.stateKey(executionID)

	data, err := s.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, &StateNotFoundError{ExecutionID: executionID}
	}
	if err != nil {
		return nil, fmt.Errorf("failed to load state from Redis: %w", err)
	}

	state, err := WorkflowStateFromJSON(data)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal state: %w", err)
	}

	return state, nil
}

// DeleteState removes the workflow state from Redis.
func (s *RedisStateStore) DeleteState(ctx context.Context, executionID string) error {
	// Delete main state
	stateKey := s.stateKey(executionID)
	if err := s.client.Del(ctx, stateKey).Err(); err != nil {
		return fmt.Errorf("failed to delete state: %w", err)
	}

	// Delete checkpoint
	checkpointKey := s.checkpointKey(executionID)
	s.client.Del(ctx, checkpointKey) // Ignore error for checkpoint

	// Delete lock if exists
	lockKey := s.lockKey(executionID)
	s.client.Del(ctx, lockKey) // Ignore error for lock

	return nil
}

// UpdateNodeState updates the state of a specific node using atomic operations.
func (s *RedisStateStore) UpdateNodeState(ctx context.Context, executionID string, nodeState *NodeState) error {
	if nodeState == nil {
		return fmt.Errorf("node state cannot be nil")
	}

	// Load current state
	state, err := s.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	// Update node state
	if state.NodeStates == nil {
		state.NodeStates = make(map[string]*NodeState)
	}
	state.NodeStates[nodeState.NodeID] = nodeState
	state.LastUpdated = time.Now()

	// Save back
	return s.SaveState(ctx, state)
}

// SaveCheckpoint saves a checkpoint to Redis.
func (s *RedisStateStore) SaveCheckpoint(ctx context.Context, executionID string, checkpoint *Checkpoint) error {
	if checkpoint == nil {
		return fmt.Errorf("checkpoint cannot be nil")
	}

	data, err := json.Marshal(checkpoint)
	if err != nil {
		return fmt.Errorf("failed to marshal checkpoint: %w", err)
	}

	key := s.checkpointKey(executionID)
	if err := s.client.Set(ctx, key, data, s.checkpointTTL).Err(); err != nil {
		return fmt.Errorf("failed to save checkpoint to Redis: %w", err)
	}

	return nil
}

// LoadCheckpoint loads the latest checkpoint from Redis.
func (s *RedisStateStore) LoadCheckpoint(ctx context.Context, executionID string) (*Checkpoint, error) {
	key := s.checkpointKey(executionID)

	data, err := s.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, &CheckpointNotFoundError{ExecutionID: executionID}
	}
	if err != nil {
		return nil, fmt.Errorf("failed to load checkpoint from Redis: %w", err)
	}

	var checkpoint Checkpoint
	if err := json.Unmarshal(data, &checkpoint); err != nil {
		return nil, fmt.Errorf("failed to unmarshal checkpoint: %w", err)
	}

	return &checkpoint, nil
}

// SetLock acquires a distributed lock for an execution.
// Returns true if lock was acquired, false if already locked.
func (s *RedisStateStore) SetLock(ctx context.Context, executionID string, ttl time.Duration) (bool, error) {
	key := s.lockKey(executionID)

	// Use SETNX for atomic lock acquisition
	result, err := s.client.SetNX(ctx, key, time.Now().Unix(), ttl).Result()
	if err != nil {
		return false, fmt.Errorf("failed to acquire lock: %w", err)
	}

	return result, nil
}

// ReleaseLock releases the distributed lock.
func (s *RedisStateStore) ReleaseLock(ctx context.Context, executionID string) error {
	key := s.lockKey(executionID)

	if err := s.client.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to release lock: %w", err)
	}

	return nil
}

// Close closes the Redis connection.
func (s *RedisStateStore) Close() error {
	// Don't close the client as it may be shared
	return nil
}

// StateNotFoundError indicates the state was not found.
type StateNotFoundError struct {
	ExecutionID string
}

func (e *StateNotFoundError) Error() string {
	return fmt.Sprintf("state not found for execution: %s", e.ExecutionID)
}

// IsNotFound returns true if the error is a StateNotFoundError.
func IsNotFound(err error) bool {
	_, ok := err.(*StateNotFoundError)
	return ok
}

// CheckpointNotFoundError indicates the checkpoint was not found.
type CheckpointNotFoundError struct {
	ExecutionID string
}

func (e *CheckpointNotFoundError) Error() string {
	return fmt.Sprintf("checkpoint not found for execution: %s", e.ExecutionID)
}

// IsCheckpointNotFound returns true if the error is a CheckpointNotFoundError.
func IsCheckpointNotFound(err error) bool {
	_, ok := err.(*CheckpointNotFoundError)
	return ok
}

// InMemoryStateStore is an in-memory implementation for testing.
type InMemoryStateStore struct {
	mu          sync.RWMutex
	states      map[string]*WorkflowState
	checkpoints map[string]*Checkpoint
	locks       map[string]time.Time
}

// NewInMemoryStateStore creates an in-memory state store for testing.
func NewInMemoryStateStore() *InMemoryStateStore {
	return &InMemoryStateStore{
		states:      make(map[string]*WorkflowState),
		checkpoints: make(map[string]*Checkpoint),
		locks:       make(map[string]time.Time),
	}
}

func (s *InMemoryStateStore) SaveState(_ context.Context, state *WorkflowState) error {
	if state == nil {
		return fmt.Errorf("state cannot be nil")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.states[state.ExecutionID] = state
	return nil
}

func (s *InMemoryStateStore) LoadState(_ context.Context, executionID string) (*WorkflowState, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	state, exists := s.states[executionID]
	if !exists {
		return nil, &StateNotFoundError{ExecutionID: executionID}
	}
	return state, nil
}

func (s *InMemoryStateStore) DeleteState(_ context.Context, executionID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.states, executionID)
	delete(s.checkpoints, executionID)
	delete(s.locks, executionID)
	return nil
}

func (s *InMemoryStateStore) UpdateNodeState(_ context.Context, executionID string, nodeState *NodeState) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	state, exists := s.states[executionID]
	if !exists {
		return &StateNotFoundError{ExecutionID: executionID}
	}
	if state.NodeStates == nil {
		state.NodeStates = make(map[string]*NodeState)
	}
	state.NodeStates[nodeState.NodeID] = nodeState
	state.LastUpdated = time.Now()
	return nil
}

func (s *InMemoryStateStore) SaveCheckpoint(_ context.Context, executionID string, checkpoint *Checkpoint) error {
	if checkpoint == nil {
		return fmt.Errorf("checkpoint cannot be nil")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.checkpoints[executionID] = checkpoint
	return nil
}

func (s *InMemoryStateStore) LoadCheckpoint(_ context.Context, executionID string) (*Checkpoint, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	checkpoint, exists := s.checkpoints[executionID]
	if !exists {
		return nil, &CheckpointNotFoundError{ExecutionID: executionID}
	}
	return checkpoint, nil
}

func (s *InMemoryStateStore) SetLock(_ context.Context, executionID string, ttl time.Duration) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if lockTime, exists := s.locks[executionID]; exists {
		if time.Since(lockTime) < ttl {
			return false, nil // Lock still valid
		}
	}
	s.locks[executionID] = time.Now()
	return true, nil
}

func (s *InMemoryStateStore) ReleaseLock(_ context.Context, executionID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.locks, executionID)
	return nil
}

func (s *InMemoryStateStore) Close() error {
	return nil
}

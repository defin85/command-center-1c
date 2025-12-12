package resourcemanager

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

// Redis key patterns for resource locks.
const (
	// LockKeyPattern is the pattern for lock hash keys.
	// Format: resource:lock:{database_id}
	LockKeyPattern = "resource:lock:%s"

	// QueueKeyPattern is the pattern for wait queue sorted set keys.
	// Format: resource:queue:{database_id}
	QueueKeyPattern = "resource:queue:%s"

	// HeartbeatKeyPattern is the pattern for heartbeat timestamp keys.
	// Format: resource:heartbeat:{database_id}
	HeartbeatKeyPattern = "resource:heartbeat:%s"

	// LockIndexKey is the key for tracking all active locks.
	LockIndexKey = "resource:locks:index"
)

// LockStore provides Redis storage operations for resource locks.
type LockStore struct {
	client redis.Cmdable

	// Lua scripts (compiled once, reused)
	acquireLockScript   *redis.Script
	releaseLockScript   *redis.Script
	extendLockScript    *redis.Script
	cleanupExpiredScript *redis.Script
}

// NewLockStore creates a new LockStore.
func NewLockStore(client redis.Cmdable) *LockStore {
	return &LockStore{
		client:              client,
		acquireLockScript:   redis.NewScript(acquireLockLua),
		releaseLockScript:   redis.NewScript(releaseLockLua),
		extendLockScript:    redis.NewScript(extendLockLua),
		cleanupExpiredScript: redis.NewScript(cleanupExpiredLua),
	}
}

// lockKey returns the Redis key for a database lock.
func lockKey(databaseID string) string {
	return fmt.Sprintf(LockKeyPattern, databaseID)
}

// queueKey returns the Redis key for a database wait queue.
func queueKey(databaseID string) string {
	return fmt.Sprintf(QueueKeyPattern, databaseID)
}

// heartbeatKey returns the Redis key for heartbeat tracking.
func heartbeatKey(databaseID string) string {
	return fmt.Sprintf(HeartbeatKeyPattern, databaseID)
}

// AcquireLock attempts to acquire a lock atomically.
// Returns (acquired, queue_position, error).
// If acquired is true, queue_position is 0.
// If acquired is false, queue_position indicates position in queue (1-based).
func (s *LockStore) AcquireLock(ctx context.Context, req *LockRequest) (bool, int, error) {
	keys := []string{
		lockKey(req.DatabaseID),
		queueKey(req.DatabaseID),
		LockIndexKey,
	}

	now := time.Now().Unix()
	ttlSeconds := int64(req.GetTTL().Seconds())

	args := []interface{}{
		req.OwnerID,
		req.Operation,
		req.CorrelationID,
		ttlSeconds,
		now,
		req.DatabaseID,
	}

	result, err := s.acquireLockScript.Run(ctx, s.client, keys, args...).Result()
	if err != nil {
		return false, 0, fmt.Errorf("failed to run acquire lock script: %w", err)
	}

	// Parse result - handle both real Redis and miniredis response formats
	acquired, position, parseErr := parseScriptResult(result)
	if parseErr != nil {
		return false, 0, parseErr
	}

	return acquired, position, nil
}

// parseScriptResult handles different response formats from Redis and miniredis.
func parseScriptResult(result interface{}) (bool, int, error) {
	switch v := result.(type) {
	case []interface{}:
		if len(v) != 2 {
			return false, 0, fmt.Errorf("unexpected script result length: %d", len(v))
		}
		acquired, _ := toInt64(v[0])
		position, _ := toInt64(v[1])
		return acquired == 1, int(position), nil
	default:
		return false, 0, fmt.Errorf("unexpected script result type: %T", result)
	}
}

// toInt64 converts various numeric types to int64.
func toInt64(v interface{}) (int64, bool) {
	switch n := v.(type) {
	case int64:
		return n, true
	case int:
		return int64(n), true
	case float64:
		return int64(n), true
	case string:
		i, err := strconv.ParseInt(n, 10, 64)
		return i, err == nil
	default:
		return 0, false
	}
}

// ReleaseLock releases a lock atomically.
// Only releases if the lock is held by the specified owner.
// Returns the next owner in queue (if any) for notification.
func (s *LockStore) ReleaseLock(ctx context.Context, databaseID, ownerID string) (string, error) {
	keys := []string{
		lockKey(databaseID),
		queueKey(databaseID),
		LockIndexKey,
	}

	args := []interface{}{
		ownerID,
		databaseID,
	}

	result, err := s.releaseLockScript.Run(ctx, s.client, keys, args...).Result()
	if err != nil {
		return "", fmt.Errorf("failed to run release lock script: %w", err)
	}

	// Parse result - handle both real Redis and miniredis response formats
	released, nextOwner, parseErr := parseReleaseResult(result)
	if parseErr != nil {
		return "", parseErr
	}

	if !released {
		return "", ErrLockNotHeld
	}

	return nextOwner, nil
}

// parseReleaseResult handles release lock script result.
// Note: miniredis truncates trailing nil values, so we handle both {1, owner} and {1}
func parseReleaseResult(result interface{}) (bool, string, error) {
	switch v := result.(type) {
	case []interface{}:
		if len(v) < 1 || len(v) > 2 {
			return false, "", fmt.Errorf("unexpected release result length: %d", len(v))
		}
		released, _ := toInt64(v[0])
		nextOwner := ""
		if len(v) > 1 && v[1] != nil {
			nextOwner, _ = v[1].(string)
		}
		return released == 1, nextOwner, nil
	default:
		return false, "", fmt.Errorf("unexpected release result type: %T", result)
	}
}

// ExtendLock extends the TTL of an existing lock.
// Only extends if the lock is held by the specified owner.
func (s *LockStore) ExtendLock(ctx context.Context, databaseID, ownerID string, ttl time.Duration) error {
	keys := []string{
		lockKey(databaseID),
		heartbeatKey(databaseID),
	}

	now := time.Now().Unix()
	ttlSeconds := int64(ttl.Seconds())

	args := []interface{}{
		ownerID,
		ttlSeconds,
		now,
	}

	result, err := s.extendLockScript.Run(ctx, s.client, keys, args...).Result()
	if err != nil {
		return fmt.Errorf("failed to run extend lock script: %w", err)
	}

	extendedInt, ok := result.(int64)
	if !ok {
		return fmt.Errorf("unexpected result type from Lua script: %T", result)
	}
	extended := extendedInt == 1
	if !extended {
		return ErrLockNotHeld
	}

	return nil
}

// GetLockInfo retrieves information about a lock.
func (s *LockStore) GetLockInfo(ctx context.Context, databaseID string) (*LockInfo, error) {
	key := lockKey(databaseID)

	data, err := s.client.HGetAll(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get lock info: %w", err)
	}

	if len(data) == 0 {
		return nil, nil // No lock exists
	}

	lockedAt, _ := strconv.ParseInt(data["locked_at"], 10, 64)
	expiresAt, _ := strconv.ParseInt(data["expires_at"], 10, 64)
	lastHeartbeat, _ := strconv.ParseInt(data["last_heartbeat"], 10, 64)

	// Get queue length
	queueLen, err := s.client.ZCard(ctx, queueKey(databaseID)).Result()
	if err != nil {
		queueLen = 0
	}

	info := &LockInfo{
		DatabaseID:    databaseID,
		OwnerID:       data["owner"],
		Operation:     data["operation"],
		CorrelationID: data["correlation_id"],
		LockedAt:      time.Unix(lockedAt, 0),
		ExpiresAt:     time.Unix(expiresAt, 0),
		QueueLength:   int(queueLen),
	}

	if lastHeartbeat > 0 {
		info.LastHeartbeat = time.Unix(lastHeartbeat, 0)
	}

	return info, nil
}

// GetQueuePosition returns the position of an owner in the wait queue.
// Returns 0 if not in queue, otherwise 1-based position.
func (s *LockStore) GetQueuePosition(ctx context.Context, databaseID, ownerID string) (int, error) {
	key := queueKey(databaseID)

	rank, err := s.client.ZRank(ctx, key, ownerID).Result()
	if err == redis.Nil {
		return 0, nil // Not in queue
	}
	if err != nil {
		return 0, fmt.Errorf("failed to get queue position: %w", err)
	}

	return int(rank) + 1, nil // Convert to 1-based
}

// AddToQueue adds an owner to the wait queue.
func (s *LockStore) AddToQueue(ctx context.Context, databaseID, ownerID string, timestamp time.Time) error {
	key := queueKey(databaseID)

	err := s.client.ZAdd(ctx, key, redis.Z{
		Score:  float64(timestamp.UnixNano()),
		Member: ownerID,
	}).Err()
	if err != nil {
		return fmt.Errorf("failed to add to queue: %w", err)
	}

	return nil
}

// RemoveFromQueue removes an owner from the wait queue.
func (s *LockStore) RemoveFromQueue(ctx context.Context, databaseID, ownerID string) error {
	key := queueKey(databaseID)

	removed, err := s.client.ZRem(ctx, key, ownerID).Result()
	if err != nil {
		return fmt.Errorf("failed to remove from queue: %w", err)
	}

	if removed == 0 {
		return ErrNotInQueue
	}

	return nil
}

// GetQueueEntries returns all entries in the wait queue.
func (s *LockStore) GetQueueEntries(ctx context.Context, databaseID string) ([]QueueEntry, error) {
	key := queueKey(databaseID)

	results, err := s.client.ZRangeWithScores(ctx, key, 0, -1).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get queue entries: %w", err)
	}

	entries := make([]QueueEntry, len(results))
	for i, z := range results {
		entries[i] = QueueEntry{
			OwnerID:    z.Member.(string),
			EnqueuedAt: time.Unix(0, int64(z.Score)),
		}
	}

	return entries, nil
}

// GetNextInQueue returns the first owner in the wait queue without removing them.
func (s *LockStore) GetNextInQueue(ctx context.Context, databaseID string) (string, error) {
	key := queueKey(databaseID)

	results, err := s.client.ZRange(ctx, key, 0, 0).Result()
	if err != nil {
		return "", fmt.Errorf("failed to get next in queue: %w", err)
	}

	if len(results) == 0 {
		return "", nil
	}

	return results[0], nil
}

// CleanupExpiredLocks removes expired locks and notifies waiting owners.
// Returns the list of database IDs that had locks cleaned up.
func (s *LockStore) CleanupExpiredLocks(ctx context.Context) ([]string, error) {
	// Get all tracked locks from the index
	lockIDs, err := s.client.SMembers(ctx, LockIndexKey).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get lock index: %w", err)
	}

	var cleanedUp []string
	now := time.Now().Unix()

	for _, databaseID := range lockIDs {
		key := lockKey(databaseID)

		// Check if lock exists and is expired
		expiresAtStr, err := s.client.HGet(ctx, key, "expires_at").Result()
		if err == redis.Nil {
			// Lock doesn't exist, remove from index
			s.client.SRem(ctx, LockIndexKey, databaseID)
			continue
		}
		if err != nil {
			continue
		}

		expiresAt, _ := strconv.ParseInt(expiresAtStr, 10, 64)
		if expiresAt > now {
			continue // Not expired
		}

		// Lock is expired, clean it up
		result, err := s.cleanupExpiredScript.Run(ctx, s.client, []string{
			key,
			queueKey(databaseID),
			LockIndexKey,
		}, databaseID, now).Result()

		if err != nil {
			continue
		}

		if result.(int64) == 1 {
			cleanedUp = append(cleanedUp, databaseID)
		}
	}

	return cleanedUp, nil
}

// GetAllLocks returns information about all currently held locks.
func (s *LockStore) GetAllLocks(ctx context.Context) ([]*LockInfo, error) {
	lockIDs, err := s.client.SMembers(ctx, LockIndexKey).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get lock index: %w", err)
	}

	locks := make([]*LockInfo, 0, len(lockIDs))
	for _, databaseID := range lockIDs {
		info, err := s.GetLockInfo(ctx, databaseID)
		if err != nil || info == nil {
			continue
		}
		locks = append(locks, info)
	}

	return locks, nil
}

// SubscribeToLockRelease subscribes to lock release events for a database.
// Returns a channel that receives the released database ID.
func (s *LockStore) SubscribeToLockRelease(ctx context.Context, databaseID string) (<-chan string, error) {
	// We need a *redis.Client for PubSub
	client, ok := s.client.(*redis.Client)
	if !ok {
		// Fallback for testing with other implementations
		ch := make(chan string, 1)
		return ch, nil
	}

	pubsub := client.Subscribe(ctx, lockReleaseChannel(databaseID))
	ch := make(chan string, 1)

	go func() {
		defer close(ch)
		defer pubsub.Close()

		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-pubsub.Channel():
				if !ok {
					return // Channel closed
				}
				if msg != nil {
					ch <- msg.Payload
				}
				return
			}
		}
	}()

	return ch, nil
}

// NotifyLockRelease publishes a lock release event.
func (s *LockStore) NotifyLockRelease(ctx context.Context, databaseID, nextOwner string) error {
	payload, _ := json.Marshal(map[string]string{
		"database_id": databaseID,
		"next_owner":  nextOwner,
	})

	err := s.client.Publish(ctx, lockReleaseChannel(databaseID), string(payload)).Err()
	if err != nil {
		return fmt.Errorf("failed to publish lock release: %w", err)
	}

	return nil
}

// lockReleaseChannel returns the pub/sub channel for lock release events.
func lockReleaseChannel(databaseID string) string {
	return fmt.Sprintf("resource:released:%s", databaseID)
}

// Lua Scripts
// All scripts are designed for atomicity and to minimize round-trips.

// acquireLockLua tries to acquire a lock or add to queue.
// KEYS[1] = lock key, KEYS[2] = queue key, KEYS[3] = index key
// ARGV[1] = owner_id, ARGV[2] = operation, ARGV[3] = correlation_id
// ARGV[4] = ttl_seconds, ARGV[5] = timestamp, ARGV[6] = database_id
// Returns {acquired (0/1), position (0 if acquired)}
const acquireLockLua = `
local lock_key = KEYS[1]
local queue_key = KEYS[2]
local index_key = KEYS[3]
local owner_id = ARGV[1]
local operation = ARGV[2]
local correlation_id = ARGV[3]
local ttl_seconds = tonumber(ARGV[4])
local timestamp = tonumber(ARGV[5])
local database_id = ARGV[6]

-- Check current lock
local current_owner = redis.call('HGET', lock_key, 'owner')

if current_owner == false then
    -- Lock is free - acquire it
    redis.call('HMSET', lock_key,
        'owner', owner_id,
        'operation', operation,
        'correlation_id', correlation_id,
        'locked_at', timestamp,
        'expires_at', timestamp + ttl_seconds,
        'last_heartbeat', timestamp)
    redis.call('EXPIRE', lock_key, ttl_seconds)

    -- Remove from queue if was waiting
    redis.call('ZREM', queue_key, owner_id)

    -- Add to lock index
    redis.call('SADD', index_key, database_id)

    return {1, 0}  -- acquired, position 0
elseif current_owner == owner_id then
    -- Re-entrant: already our lock - extend it
    redis.call('HSET', lock_key, 'expires_at', timestamp + ttl_seconds)
    redis.call('HSET', lock_key, 'last_heartbeat', timestamp)
    redis.call('EXPIRE', lock_key, ttl_seconds)
    return {1, 0}  -- acquired (re-entrant), position 0
else
    -- Check if lock is expired
    local expires_at = tonumber(redis.call('HGET', lock_key, 'expires_at'))
    if expires_at and expires_at < timestamp then
        -- Lock expired - clean it up and acquire
        redis.call('DEL', lock_key)
        redis.call('HMSET', lock_key,
            'owner', owner_id,
            'operation', operation,
            'correlation_id', correlation_id,
            'locked_at', timestamp,
            'expires_at', timestamp + ttl_seconds,
            'last_heartbeat', timestamp)
        redis.call('EXPIRE', lock_key, ttl_seconds)
        redis.call('ZREM', queue_key, owner_id)
        redis.call('SADD', index_key, database_id)
        return {1, 0}  -- acquired after cleanup
    end

    -- Lock is held by someone else - check queue position
    local pos = redis.call('ZRANK', queue_key, owner_id)
    if pos == false then
        -- Not in queue - add with timestamp as score for fair ordering
        redis.call('ZADD', queue_key, timestamp * 1000000000, owner_id)
        pos = redis.call('ZRANK', queue_key, owner_id)
    end
    return {0, pos + 1}  -- not acquired, 1-based position
end
`

// releaseLockLua releases a lock and returns next owner.
// KEYS[1] = lock key, KEYS[2] = queue key, KEYS[3] = index key
// ARGV[1] = owner_id, ARGV[2] = database_id
// Returns {released (0/1), next_owner_id or nil}
const releaseLockLua = `
local lock_key = KEYS[1]
local queue_key = KEYS[2]
local index_key = KEYS[3]
local owner_id = ARGV[1]
local database_id = ARGV[2]

-- Verify owner
local current_owner = redis.call('HGET', lock_key, 'owner')
if current_owner ~= owner_id then
    return {0, nil}  -- Not the owner
end

-- Delete the lock
redis.call('DEL', lock_key)

-- Get next in queue
local next_owners = redis.call('ZRANGE', queue_key, 0, 0)
local next_owner = nil
if #next_owners > 0 then
    next_owner = next_owners[1]
end

-- If no one waiting, remove from index
if next_owner == nil then
    redis.call('SREM', index_key, database_id)
end

return {1, next_owner}
`

// extendLockLua extends the TTL of a lock.
// KEYS[1] = lock key, KEYS[2] = heartbeat key
// ARGV[1] = owner_id, ARGV[2] = ttl_seconds, ARGV[3] = timestamp
// Returns 1 if extended, 0 if not owner
const extendLockLua = `
local lock_key = KEYS[1]
local owner_id = ARGV[1]
local ttl_seconds = tonumber(ARGV[2])
local timestamp = tonumber(ARGV[3])

-- Verify owner
local current_owner = redis.call('HGET', lock_key, 'owner')
if current_owner ~= owner_id then
    return 0
end

-- Extend TTL
redis.call('HSET', lock_key, 'expires_at', timestamp + ttl_seconds)
redis.call('HSET', lock_key, 'last_heartbeat', timestamp)
redis.call('EXPIRE', lock_key, ttl_seconds)

return 1
`

// cleanupExpiredLua cleans up an expired lock.
// KEYS[1] = lock key, KEYS[2] = queue key, KEYS[3] = index key
// ARGV[1] = database_id, ARGV[2] = timestamp
// Returns 1 if cleaned up, 0 otherwise
const cleanupExpiredLua = `
local lock_key = KEYS[1]
local queue_key = KEYS[2]
local index_key = KEYS[3]
local database_id = ARGV[1]
local timestamp = tonumber(ARGV[2])

-- Check if lock exists and is expired
local expires_at = tonumber(redis.call('HGET', lock_key, 'expires_at'))
if not expires_at or expires_at > timestamp then
    return 0  -- Not expired or doesn't exist
end

-- Delete expired lock
redis.call('DEL', lock_key)

-- Check if anyone waiting
local queue_len = redis.call('ZCARD', queue_key)
if queue_len == 0 then
    -- No one waiting, remove from index
    redis.call('SREM', index_key, database_id)
end

return 1
`

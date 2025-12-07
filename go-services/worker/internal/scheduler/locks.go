package scheduler

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	// LockKeyPrefix is the prefix for all scheduler lock keys in Redis
	LockKeyPrefix = "scheduler:lock:"
)

var (
	// ErrLockNotAcquired indicates that the lock could not be acquired
	ErrLockNotAcquired = errors.New("lock not acquired")
	// ErrLockNotHeld indicates that the lock is not held by this instance
	ErrLockNotHeld = errors.New("lock not held")
)

// DistributedLock represents a distributed lock in Redis
type DistributedLock struct {
	redis   redis.Cmdable
	key     string
	value   string // unique identifier for this lock holder
	ttl     time.Duration
}

// NewDistributedLock creates a new distributed lock instance
func NewDistributedLock(redis redis.Cmdable, jobName string, workerID string, ttl time.Duration) *DistributedLock {
	return &DistributedLock{
		redis: redis,
		key:   LockKeyPrefix + jobName,
		value: workerID,
		ttl:   ttl,
	}
}

// AcquireLock attempts to acquire a distributed lock using SETNX
// Returns true if lock was acquired, false otherwise
func AcquireLock(ctx context.Context, redis redis.Cmdable, jobName string, workerID string, ttl time.Duration) (bool, error) {
	key := LockKeyPrefix + jobName

	// Use SET with NX and EX for atomic lock acquisition
	// NX = only set if not exists
	// EX = set expiration in seconds
	result, err := redis.SetNX(ctx, key, workerID, ttl).Result()
	if err != nil {
		return false, fmt.Errorf("failed to acquire lock: %w", err)
	}

	return result, nil
}

// Lua script for atomic check-and-delete (release lock)
var releaseLockScript = redis.NewScript(`
	if redis.call("GET", KEYS[1]) == ARGV[1] then
		return redis.call("DEL", KEYS[1])
	else
		return 0
	end
`)

// Lua script for atomic check-and-extend (extend lock TTL)
var extendLockScript = redis.NewScript(`
	if redis.call("GET", KEYS[1]) == ARGV[1] then
		return redis.call("PEXPIRE", KEYS[1], ARGV[2])
	else
		return 0
	end
`)

// ReleaseLock releases a distributed lock
// Only releases if the lock is held by the specified workerID (to prevent releasing someone else's lock)
func ReleaseLock(ctx context.Context, rdb redis.Cmdable, jobName string, workerID string) error {
	key := LockKeyPrefix + jobName

	result, err := releaseLockScript.Run(ctx, rdb, []string{key}, workerID).Result()
	if err != nil {
		return fmt.Errorf("failed to release lock: %w", err)
	}

	if result.(int64) == 0 {
		return ErrLockNotHeld
	}

	return nil
}

// ExtendLock extends the TTL of an existing lock
// Only extends if the lock is held by the specified workerID
func ExtendLock(ctx context.Context, rdb redis.Cmdable, jobName string, workerID string, ttl time.Duration) error {
	key := LockKeyPrefix + jobName

	result, err := extendLockScript.Run(ctx, rdb, []string{key}, workerID, ttl.Milliseconds()).Result()
	if err != nil {
		return fmt.Errorf("failed to extend lock: %w", err)
	}

	if result.(int64) == 0 {
		return ErrLockNotHeld
	}

	return nil
}

// AcquireLockWithRetry attempts to acquire a lock with retries
func AcquireLockWithRetry(ctx context.Context, redis redis.Cmdable, jobName string, workerID string, ttl time.Duration, maxRetries int, retryDelay time.Duration) (bool, error) {
	for i := 0; i <= maxRetries; i++ {
		acquired, err := AcquireLock(ctx, redis, jobName, workerID, ttl)
		if err != nil {
			return false, err
		}
		if acquired {
			return true, nil
		}

		// Don't sleep on the last iteration
		if i < maxRetries {
			select {
			case <-ctx.Done():
				return false, ctx.Err()
			case <-time.After(retryDelay):
				// Continue to next retry
			}
		}
	}

	return false, nil
}

// LockGuard is a helper that acquires a lock, executes a function, and releases the lock
type LockGuard struct {
	redis     redis.Cmdable
	jobName   string
	workerID  string
	ttl       time.Duration
	acquired  bool
}

// NewLockGuard creates a new lock guard
func NewLockGuard(redis redis.Cmdable, jobName string, workerID string, ttl time.Duration) *LockGuard {
	return &LockGuard{
		redis:    redis,
		jobName:  jobName,
		workerID: workerID,
		ttl:      ttl,
		acquired: false,
	}
}

// Acquire attempts to acquire the lock
func (lg *LockGuard) Acquire(ctx context.Context) (bool, error) {
	acquired, err := AcquireLock(ctx, lg.redis, lg.jobName, lg.workerID, lg.ttl)
	if err != nil {
		return false, err
	}
	lg.acquired = acquired
	return acquired, nil
}

// Release releases the lock if it was acquired
func (lg *LockGuard) Release(ctx context.Context) error {
	if !lg.acquired {
		return nil
	}
	err := ReleaseLock(ctx, lg.redis, lg.jobName, lg.workerID)
	if err != nil && !errors.Is(err, ErrLockNotHeld) {
		return err
	}
	lg.acquired = false
	return nil
}

// WithLock executes a function while holding the lock
// Automatically acquires and releases the lock
func WithLock(ctx context.Context, redis redis.Cmdable, jobName string, workerID string, ttl time.Duration, fn func(ctx context.Context) error) error {
	acquired, err := AcquireLock(ctx, redis, jobName, workerID, ttl)
	if err != nil {
		return fmt.Errorf("failed to acquire lock for %s: %w", jobName, err)
	}
	if !acquired {
		return ErrLockNotAcquired
	}

	// Ensure lock is released
	defer func() {
		// Use background context for cleanup to ensure lock is released
		// even if the original context was cancelled
		releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = ReleaseLock(releaseCtx, redis, jobName, workerID)
	}()

	return fn(ctx)
}

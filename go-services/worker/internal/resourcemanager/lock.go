// Package resourcemanager provides distributed locking for 1C database resources.
// It ensures exclusive access to databases during workflow execution with fair
// queueing support for waiting workflows.
package resourcemanager

import (
	"errors"
	"time"
)

// Default configuration values.
const (
	// DefaultLockTTL is the default time-to-live for locks (15 minutes).
	DefaultLockTTL = 15 * time.Minute

	// DefaultWaitTimeout is the default maximum time to wait in queue (5 minutes).
	DefaultWaitTimeout = 5 * time.Minute

	// DefaultHeartbeatInterval is the default interval for lock heartbeat (1 minute).
	DefaultHeartbeatInterval = 1 * time.Minute

	// MinLockTTL is the minimum allowed lock TTL.
	MinLockTTL = 30 * time.Second

	// MaxLockTTL is the maximum allowed lock TTL.
	MaxLockTTL = 1 * time.Hour
)

// Errors returned by ResourceManager.
var (
	// ErrLockNotAcquired indicates that the lock could not be acquired.
	ErrLockNotAcquired = errors.New("lock not acquired")

	// ErrLockNotHeld indicates that the lock is not held by this owner.
	ErrLockNotHeld = errors.New("lock not held by owner")

	// ErrLockExpired indicates that the lock has expired.
	ErrLockExpired = errors.New("lock expired")

	// ErrWaitTimeout indicates that waiting in queue timed out.
	ErrWaitTimeout = errors.New("wait timeout exceeded")

	// ErrNotInQueue indicates that the owner is not in the wait queue.
	ErrNotInQueue = errors.New("owner not in queue")

	// ErrInvalidRequest indicates that the lock request is invalid.
	ErrInvalidRequest = errors.New("invalid lock request")

	// ErrContextCancelled indicates that the context was cancelled while waiting.
	ErrContextCancelled = errors.New("context cancelled")
)

// LockRequest represents a request to acquire a lock on a database resource.
type LockRequest struct {
	// DatabaseID is the unique identifier of the 1C database to lock.
	DatabaseID string

	// OwnerID is the unique identifier of the lock owner (typically workflow_id).
	OwnerID string

	// Operation describes what operation is being performed (e.g., "extension_install").
	Operation string

	// CorrelationID is used for tracing and correlation across services.
	CorrelationID string

	// TTL is the time-to-live for the lock. If zero, DefaultLockTTL is used.
	TTL time.Duration

	// WaitTimeout is the maximum time to wait in queue if the lock is held.
	// If zero, the method returns immediately without waiting.
	// Use a negative value to wait indefinitely (not recommended).
	WaitTimeout time.Duration
}

// Validate checks if the lock request is valid.
func (r *LockRequest) Validate() error {
	if r.DatabaseID == "" {
		return errors.New("database_id is required")
	}
	if r.OwnerID == "" {
		return errors.New("owner_id is required")
	}
	if r.TTL < 0 {
		return errors.New("ttl cannot be negative")
	}
	if r.TTL > 0 && r.TTL < MinLockTTL {
		return errors.New("ttl is below minimum allowed value")
	}
	if r.TTL > MaxLockTTL {
		return errors.New("ttl exceeds maximum allowed value")
	}
	return nil
}

// GetTTL returns the TTL to use, applying default if not set.
func (r *LockRequest) GetTTL() time.Duration {
	if r.TTL == 0 {
		return DefaultLockTTL
	}
	return r.TTL
}

// LockResult represents the result of a lock acquisition attempt.
type LockResult struct {
	// Acquired indicates whether the lock was successfully acquired.
	Acquired bool

	// QueuePosition is the position in the wait queue (1-based).
	// Only set if Acquired is false and the owner is in the queue.
	// 0 means not in queue.
	QueuePosition int

	// LockInfo contains information about the current lock.
	// If Acquired is true, this is info about the acquired lock.
	// If Acquired is false, this is info about the lock that is blocking.
	LockInfo *LockInfo
}

// LockInfo contains information about a lock on a database resource.
type LockInfo struct {
	// DatabaseID is the unique identifier of the locked database.
	DatabaseID string `json:"database_id"`

	// OwnerID is the unique identifier of the lock owner.
	OwnerID string `json:"owner_id"`

	// Operation describes what operation is being performed.
	Operation string `json:"operation"`

	// CorrelationID is used for tracing and correlation.
	CorrelationID string `json:"correlation_id"`

	// LockedAt is the time when the lock was acquired.
	LockedAt time.Time `json:"locked_at"`

	// ExpiresAt is the time when the lock will expire.
	ExpiresAt time.Time `json:"expires_at"`

	// QueueLength is the number of owners waiting in the queue.
	QueueLength int `json:"queue_length"`

	// LastHeartbeat is the last time the lock was extended via heartbeat.
	LastHeartbeat time.Time `json:"last_heartbeat,omitempty"`
}

// IsExpired returns true if the lock has expired.
func (l *LockInfo) IsExpired() bool {
	return time.Now().After(l.ExpiresAt)
}

// RemainingTTL returns the remaining time before the lock expires.
func (l *LockInfo) RemainingTTL() time.Duration {
	remaining := time.Until(l.ExpiresAt)
	if remaining < 0 {
		return 0
	}
	return remaining
}

// QueueEntry represents an entry in the wait queue.
type QueueEntry struct {
	// OwnerID is the unique identifier of the waiting owner.
	OwnerID string `json:"owner_id"`

	// EnqueuedAt is the time when the owner was added to the queue.
	EnqueuedAt time.Time `json:"enqueued_at"`

	// Operation describes what operation the owner wants to perform.
	Operation string `json:"operation,omitempty"`

	// CorrelationID is used for tracing.
	CorrelationID string `json:"correlation_id,omitempty"`
}

// WaitDuration returns how long the entry has been waiting.
func (e *QueueEntry) WaitDuration() time.Duration {
	return time.Since(e.EnqueuedAt)
}

// LockStats contains statistics about resource locks.
type LockStats struct {
	// TotalLocks is the total number of currently held locks.
	TotalLocks int64 `json:"total_locks"`

	// TotalWaiting is the total number of owners waiting across all queues.
	TotalWaiting int64 `json:"total_waiting"`

	// AvgLockDuration is the average duration locks are held.
	AvgLockDuration time.Duration `json:"avg_lock_duration"`

	// AvgWaitTime is the average time owners spend waiting in queues.
	AvgWaitTime time.Duration `json:"avg_wait_time"`
}

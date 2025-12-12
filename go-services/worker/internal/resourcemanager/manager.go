package resourcemanager

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/redis/go-redis/v9"
)

// ResourceManager defines the interface for managing distributed locks on 1C database resources.
type ResourceManager interface {
	// AcquireLock attempts to acquire a lock on a database.
	// If the lock is held by another owner and WaitTimeout > 0, it waits in a fair queue.
	// Returns the result of the acquisition attempt.
	AcquireLock(ctx context.Context, req *LockRequest) (*LockResult, error)

	// ReleaseLock releases a lock on a database.
	// Only succeeds if the lock is held by the specified owner.
	ReleaseLock(ctx context.Context, databaseID, ownerID string) error

	// ExtendLock extends the TTL of an existing lock (heartbeat).
	// Only succeeds if the lock is held by the specified owner.
	ExtendLock(ctx context.Context, databaseID, ownerID string, ttl time.Duration) error

	// GetLockInfo returns information about a lock, or nil if no lock exists.
	GetLockInfo(ctx context.Context, databaseID string) (*LockInfo, error)

	// GetQueuePosition returns the position of an owner in the wait queue.
	// Returns 0 if not in queue, otherwise 1-based position.
	GetQueuePosition(ctx context.Context, databaseID, ownerID string) (int, error)

	// CancelWait removes an owner from the wait queue.
	CancelWait(ctx context.Context, databaseID, ownerID string) error

	// GetAllLocks returns information about all currently held locks.
	GetAllLocks(ctx context.Context) ([]*LockInfo, error)

	// ReleaseAllByOwner releases all locks held by a specific owner.
	// Used during graceful shutdown.
	ReleaseAllByOwner(ctx context.Context, ownerID string) (int, error)

	// StartCleanupWorker starts a background worker that cleans up expired locks.
	StartCleanupWorker(ctx context.Context, interval time.Duration)

	// Close stops background workers and releases resources.
	Close() error
}

// Config holds configuration for the resource manager.
type Config struct {
	// DefaultTTL is the default lock TTL if not specified in request.
	DefaultTTL time.Duration

	// DefaultWaitTimeout is the default wait timeout if not specified in request.
	DefaultWaitTimeout time.Duration

	// CleanupInterval is the interval for the cleanup worker.
	CleanupInterval time.Duration

	// WorkerID is the unique identifier for this worker instance.
	// Used for tracking which worker holds which locks.
	WorkerID string
}

// DefaultConfig returns default configuration.
func DefaultConfig() *Config {
	return &Config{
		DefaultTTL:         DefaultLockTTL,
		DefaultWaitTimeout: DefaultWaitTimeout,
		CleanupInterval:    30 * time.Second,
		WorkerID:           "",
	}
}

// resourceManager implements ResourceManager.
type resourceManager struct {
	store   *LockStore
	config  *Config
	metrics *Metrics

	// Background worker management
	cleanupCancel context.CancelFunc
	cleanupWg     sync.WaitGroup

	// Track locks held by this manager for graceful shutdown
	mu        sync.RWMutex
	heldLocks map[string]string // databaseID -> ownerID
}

// NewResourceManager creates a new ResourceManager.
func NewResourceManager(client redis.Cmdable, config *Config) ResourceManager {
	if config == nil {
		config = DefaultConfig()
	}

	rm := &resourceManager{
		store:     NewLockStore(client),
		config:    config,
		metrics:   NewMetrics(),
		heldLocks: make(map[string]string),
	}

	return rm
}

// AcquireLock implements ResourceManager.AcquireLock.
func (rm *resourceManager) AcquireLock(ctx context.Context, req *LockRequest) (*LockResult, error) {
	if err := req.Validate(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrInvalidRequest, err)
	}

	start := time.Now()
	defer func() {
		rm.metrics.LockAcquisitionDuration.Observe(time.Since(start).Seconds())
	}()

	// First attempt to acquire
	acquired, position, err := rm.store.AcquireLock(ctx, req)
	if err != nil {
		rm.metrics.LockAcquisitionTotal.WithLabelValues("error").Inc()
		return nil, err
	}

	if acquired {
		rm.trackLock(req.DatabaseID, req.OwnerID)
		rm.metrics.LockAcquisitionTotal.WithLabelValues("acquired").Inc()
		rm.metrics.ActiveLocks.Inc()

		info, _ := rm.store.GetLockInfo(ctx, req.DatabaseID)
		return &LockResult{
			Acquired:      true,
			QueuePosition: 0,
			LockInfo:      info,
		}, nil
	}

	// Lock not acquired - check if we should wait
	if req.WaitTimeout == 0 {
		rm.metrics.LockAcquisitionTotal.WithLabelValues("busy").Inc()
		info, _ := rm.store.GetLockInfo(ctx, req.DatabaseID)
		return &LockResult{
			Acquired:      false,
			QueuePosition: position,
			LockInfo:      info,
		}, nil
	}

	// Wait for lock with timeout
	rm.metrics.WaitingInQueue.Inc()
	defer rm.metrics.WaitingInQueue.Dec()

	result, err := rm.waitForLock(ctx, req, position)
	if err != nil {
		if err == ErrWaitTimeout {
			rm.metrics.LockAcquisitionTotal.WithLabelValues("timeout").Inc()
		} else if err == ErrContextCancelled {
			rm.metrics.LockAcquisitionTotal.WithLabelValues("cancelled").Inc()
		}
		return result, err
	}

	if result.Acquired {
		rm.trackLock(req.DatabaseID, req.OwnerID)
		rm.metrics.LockAcquisitionTotal.WithLabelValues("acquired_after_wait").Inc()
		rm.metrics.ActiveLocks.Inc()
	}

	return result, nil
}

// waitForLock waits for a lock to become available.
func (rm *resourceManager) waitForLock(ctx context.Context, req *LockRequest, initialPosition int) (*LockResult, error) {
	waitTimeout := req.WaitTimeout
	if waitTimeout < 0 {
		waitTimeout = 24 * time.Hour // Effectively infinite
	}

	deadline := time.Now().Add(waitTimeout)

	// Subscribe to lock release notifications
	releaseCh, err := rm.store.SubscribeToLockRelease(ctx, req.DatabaseID)
	if err != nil {
		return nil, fmt.Errorf("failed to subscribe to lock release: %w", err)
	}

	// Polling interval as fallback (in case pubsub misses messages)
	pollInterval := 100 * time.Millisecond
	pollTicker := time.NewTicker(pollInterval)
	defer pollTicker.Stop()

	for {
		select {
		case <-ctx.Done():
			// Context cancelled - remove from queue
			rm.store.RemoveFromQueue(ctx, req.DatabaseID, req.OwnerID)
			return &LockResult{
				Acquired:      false,
				QueuePosition: 0,
			}, ErrContextCancelled

		case <-releaseCh:
			// Lock was released - try to acquire
			acquired, position, err := rm.store.AcquireLock(ctx, req)
			if err != nil {
				return nil, err
			}
			if acquired {
				info, _ := rm.store.GetLockInfo(ctx, req.DatabaseID)
				return &LockResult{
					Acquired:      true,
					QueuePosition: 0,
					LockInfo:      info,
				}, nil
			}
			// Still not first in queue, continue waiting
			if time.Now().After(deadline) {
				rm.store.RemoveFromQueue(ctx, req.DatabaseID, req.OwnerID)
				info, _ := rm.store.GetLockInfo(ctx, req.DatabaseID)
				return &LockResult{
					Acquired:      false,
					QueuePosition: position,
					LockInfo:      info,
				}, ErrWaitTimeout
			}

		case <-pollTicker.C:
			// Periodic poll as fallback
			acquired, position, err := rm.store.AcquireLock(ctx, req)
			if err != nil {
				return nil, err
			}
			if acquired {
				info, _ := rm.store.GetLockInfo(ctx, req.DatabaseID)
				return &LockResult{
					Acquired:      true,
					QueuePosition: 0,
					LockInfo:      info,
				}, nil
			}
			// Check timeout
			if time.Now().After(deadline) {
				rm.store.RemoveFromQueue(ctx, req.DatabaseID, req.OwnerID)
				info, _ := rm.store.GetLockInfo(ctx, req.DatabaseID)
				return &LockResult{
					Acquired:      false,
					QueuePosition: position,
					LockInfo:      info,
				}, ErrWaitTimeout
			}
		}
	}
}

// ReleaseLock implements ResourceManager.ReleaseLock.
func (rm *resourceManager) ReleaseLock(ctx context.Context, databaseID, ownerID string) error {
	start := time.Now()

	nextOwner, err := rm.store.ReleaseLock(ctx, databaseID, ownerID)
	if err != nil {
		return err
	}

	rm.untrackLock(databaseID)
	rm.metrics.ActiveLocks.Dec()
	rm.metrics.LockHoldDuration.Observe(time.Since(start).Seconds())

	// Notify next owner if any
	if nextOwner != "" {
		rm.store.NotifyLockRelease(ctx, databaseID, nextOwner)
	}

	return nil
}

// ExtendLock implements ResourceManager.ExtendLock.
func (rm *resourceManager) ExtendLock(ctx context.Context, databaseID, ownerID string, ttl time.Duration) error {
	if ttl < MinLockTTL {
		ttl = MinLockTTL
	}
	if ttl > MaxLockTTL {
		ttl = MaxLockTTL
	}

	err := rm.store.ExtendLock(ctx, databaseID, ownerID, ttl)
	if err != nil {
		rm.metrics.HeartbeatTotal.WithLabelValues("failed").Inc()
		return err
	}

	rm.metrics.HeartbeatTotal.WithLabelValues("success").Inc()
	return nil
}

// GetLockInfo implements ResourceManager.GetLockInfo.
func (rm *resourceManager) GetLockInfo(ctx context.Context, databaseID string) (*LockInfo, error) {
	return rm.store.GetLockInfo(ctx, databaseID)
}

// GetQueuePosition implements ResourceManager.GetQueuePosition.
func (rm *resourceManager) GetQueuePosition(ctx context.Context, databaseID, ownerID string) (int, error) {
	return rm.store.GetQueuePosition(ctx, databaseID, ownerID)
}

// CancelWait implements ResourceManager.CancelWait.
func (rm *resourceManager) CancelWait(ctx context.Context, databaseID, ownerID string) error {
	return rm.store.RemoveFromQueue(ctx, databaseID, ownerID)
}

// GetAllLocks implements ResourceManager.GetAllLocks.
func (rm *resourceManager) GetAllLocks(ctx context.Context) ([]*LockInfo, error) {
	return rm.store.GetAllLocks(ctx)
}

// ReleaseAllByOwner implements ResourceManager.ReleaseAllByOwner.
func (rm *resourceManager) ReleaseAllByOwner(ctx context.Context, ownerID string) (int, error) {
	rm.mu.RLock()
	locksToRelease := make([]string, 0)
	for dbID, owner := range rm.heldLocks {
		if owner == ownerID {
			locksToRelease = append(locksToRelease, dbID)
		}
	}
	rm.mu.RUnlock()

	released := 0
	for _, dbID := range locksToRelease {
		if err := rm.ReleaseLock(ctx, dbID, ownerID); err == nil {
			released++
		}
	}

	return released, nil
}

// StartCleanupWorker implements ResourceManager.StartCleanupWorker.
func (rm *resourceManager) StartCleanupWorker(ctx context.Context, interval time.Duration) {
	if interval == 0 {
		interval = rm.config.CleanupInterval
	}

	cleanupCtx, cancel := context.WithCancel(ctx)
	rm.cleanupCancel = cancel

	rm.cleanupWg.Add(1)
	go func() {
		defer rm.cleanupWg.Done()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-cleanupCtx.Done():
				return
			case <-ticker.C:
				cleanedUp, err := rm.store.CleanupExpiredLocks(cleanupCtx)
				if err == nil && len(cleanedUp) > 0 {
					rm.metrics.ExpiredLocksCleanedUp.Add(float64(len(cleanedUp)))
					// Notify waiting owners for cleaned up locks
					for _, dbID := range cleanedUp {
						nextOwner, _ := rm.store.GetNextInQueue(cleanupCtx, dbID)
						if nextOwner != "" {
							rm.store.NotifyLockRelease(cleanupCtx, dbID, nextOwner)
						}
					}
				}
			}
		}
	}()
}

// Close implements ResourceManager.Close.
func (rm *resourceManager) Close() error {
	if rm.cleanupCancel != nil {
		rm.cleanupCancel()
	}
	rm.cleanupWg.Wait()
	return nil
}

// trackLock records that this manager holds a lock.
func (rm *resourceManager) trackLock(databaseID, ownerID string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	rm.heldLocks[databaseID] = ownerID
}

// untrackLock removes a lock from tracking.
func (rm *resourceManager) untrackLock(databaseID string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	delete(rm.heldLocks, databaseID)
}

// Metrics for ResourceManager.
type Metrics struct {
	// LockAcquisitionTotal counts lock acquisition attempts by result.
	LockAcquisitionTotal *prometheus.CounterVec

	// LockAcquisitionDuration measures time to acquire a lock.
	LockAcquisitionDuration prometheus.Histogram

	// LockHoldDuration measures how long locks are held.
	LockHoldDuration prometheus.Histogram

	// ActiveLocks shows current number of held locks.
	ActiveLocks prometheus.Gauge

	// WaitingInQueue shows current number of owners waiting.
	WaitingInQueue prometheus.Gauge

	// HeartbeatTotal counts heartbeat operations by result.
	HeartbeatTotal *prometheus.CounterVec

	// ExpiredLocksCleanedUp counts expired locks that were cleaned up.
	ExpiredLocksCleanedUp prometheus.Counter
}

var (
	globalMetrics     *Metrics
	globalMetricsOnce sync.Once
)

// NewMetrics returns the singleton Prometheus metrics for ResourceManager.
// Uses sync.Once to ensure metrics are registered only once.
func NewMetrics() *Metrics {
	globalMetricsOnce.Do(func() {
		globalMetrics = &Metrics{
			LockAcquisitionTotal: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "lock_acquisition_total",
					Help:      "Total number of lock acquisition attempts by result",
				},
				[]string{"result"}, // acquired, acquired_after_wait, busy, timeout, cancelled, error
			),

			LockAcquisitionDuration: promauto.NewHistogram(
				prometheus.HistogramOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "lock_acquisition_duration_seconds",
					Help:      "Time to acquire a lock (including wait time)",
					Buckets:   []float64{0.001, 0.01, 0.1, 0.5, 1, 5, 10, 30, 60, 120, 300},
				},
			),

			LockHoldDuration: promauto.NewHistogram(
				prometheus.HistogramOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "lock_hold_duration_seconds",
					Help:      "Duration locks are held",
					Buckets:   []float64{1, 5, 10, 30, 60, 120, 300, 600, 900},
				},
			),

			ActiveLocks: promauto.NewGauge(
				prometheus.GaugeOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "active_locks",
					Help:      "Current number of active locks",
				},
			),

			WaitingInQueue: promauto.NewGauge(
				prometheus.GaugeOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "waiting_in_queue",
					Help:      "Current number of owners waiting in queues",
				},
			),

			HeartbeatTotal: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "heartbeat_total",
					Help:      "Total number of heartbeat operations by result",
				},
				[]string{"result"}, // success, failed
			),

			ExpiredLocksCleanedUp: promauto.NewCounter(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "resourcemanager",
					Name:      "expired_locks_cleaned_up_total",
					Help:      "Total number of expired locks cleaned up",
				},
			),
		}
	})
	return globalMetrics
}

// LockGuard provides a convenient way to acquire and release a lock.
// It implements the context.Context-aware locking pattern.
type LockGuard struct {
	rm         ResourceManager
	databaseID string
	ownerID    string
	acquired   bool
}

// NewLockGuard creates a new lock guard.
func NewLockGuard(rm ResourceManager, databaseID, ownerID string) *LockGuard {
	return &LockGuard{
		rm:         rm,
		databaseID: databaseID,
		ownerID:    ownerID,
		acquired:   false,
	}
}

// Acquire attempts to acquire the lock.
func (lg *LockGuard) Acquire(ctx context.Context, req *LockRequest) (*LockResult, error) {
	if req.DatabaseID == "" {
		req.DatabaseID = lg.databaseID
	}
	if req.OwnerID == "" {
		req.OwnerID = lg.ownerID
	}

	result, err := lg.rm.AcquireLock(ctx, req)
	if err != nil {
		return nil, err
	}

	lg.acquired = result.Acquired
	return result, nil
}

// Release releases the lock if it was acquired.
func (lg *LockGuard) Release(ctx context.Context) error {
	if !lg.acquired {
		return nil
	}

	err := lg.rm.ReleaseLock(ctx, lg.databaseID, lg.ownerID)
	if err != nil && err != ErrLockNotHeld {
		return err
	}

	lg.acquired = false
	return nil
}

// IsAcquired returns true if the lock is currently acquired.
func (lg *LockGuard) IsAcquired() bool {
	return lg.acquired
}

// WithLock executes a function while holding a lock.
// Automatically acquires and releases the lock.
func WithLock(ctx context.Context, rm ResourceManager, req *LockRequest, fn func(ctx context.Context) error) error {
	result, err := rm.AcquireLock(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !result.Acquired {
		return ErrLockNotAcquired
	}

	// Ensure lock is released
	defer func() {
		releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		rm.ReleaseLock(releaseCtx, req.DatabaseID, req.OwnerID)
	}()

	return fn(ctx)
}

// HeartbeatLoop runs a heartbeat loop to keep a lock alive.
// It extends the lock TTL at regular intervals.
// Stops when the context is cancelled.
func HeartbeatLoop(ctx context.Context, rm ResourceManager, databaseID, ownerID string, interval, ttl time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := rm.ExtendLock(ctx, databaseID, ownerID, ttl); err != nil {
				// Lock lost, stop heartbeat
				return
			}
		}
	}
}

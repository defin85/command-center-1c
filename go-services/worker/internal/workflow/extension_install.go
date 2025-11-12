package workflow

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/clusterclient"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/redis/go-redis/v9"
)

type ExtensionInstallWorkflow struct {
	clusterClient *clusterclient.Client
	redisClient   *redis.Client
	pubSubEnabled bool
}

func NewExtensionInstallWorkflow(clusterServiceURL, redisAddr string, pubSubEnabled bool) *ExtensionInstallWorkflow {
	log := logger.GetLogger()
	var redisClient *redis.Client

	log.Infof("Initializing ExtensionInstallWorkflow: redis_addr=%s, pubsub_enabled=%v", redisAddr, pubSubEnabled)

	if pubSubEnabled && redisAddr != "" {
		redisClient = redis.NewClient(&redis.Options{
			Addr: redisAddr,
			DB:   0,
		})

		// Test connection
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()

		if err := redisClient.Ping(ctx).Err(); err != nil {
			log.Warnf("Redis connection failed, Pub/Sub disabled: %v", err)
			redisClient = nil
			pubSubEnabled = false
		} else {
			log.Infof("Redis client initialized successfully for Pub/Sub (addr=%s)", redisAddr)
		}
	} else {
		log.Infof("Redis Pub/Sub disabled by configuration (enabled=%v, addr=%s)", pubSubEnabled, redisAddr)
	}

	workflow := &ExtensionInstallWorkflow{
		clusterClient: clusterclient.NewClient(clusterServiceURL),
		redisClient:   redisClient,
		pubSubEnabled: pubSubEnabled && redisClient != nil,
	}

	log.Infof("ExtensionInstallWorkflow initialized: pubsub_enabled=%v, redis_client_set=%v", workflow.pubSubEnabled, workflow.redisClient != nil)

	return workflow
}

type WorkflowParams struct {
	ClusterID  string
	InfobaseID string
}

// PreInstall выполняет шаги ДО установки: lock jobs + terminate sessions + wait
func (w *ExtensionInstallWorkflow) PreInstall(ctx context.Context, params WorkflowParams) error {
	log := logger.GetLogger()

	// Step 1: Block scheduled jobs
	log.Infof("Workflow Step 1/3: Blocking scheduled jobs for infobase %s", params.InfobaseID)
	if err := w.clusterClient.LockInfobase(ctx, params.ClusterID, params.InfobaseID); err != nil {
		return fmt.Errorf("failed to lock scheduled jobs: %w", err)
	}

	// Step 2: Terminate all sessions
	log.Infof("Workflow Step 2/3: Terminating all active sessions")
	terminated, err := w.clusterClient.TerminateSessions(ctx, params.ClusterID, params.InfobaseID)
	if err != nil {
		// Rollback: unlock если terminate failed
		w.clusterClient.UnlockInfobase(context.Background(), params.ClusterID, params.InfobaseID)
		return fmt.Errorf("failed to terminate sessions: %w", err)
	}
	log.Infof("Terminated %d sessions", terminated)

	// Step 3: Wait for sessions=0 (polling max 30 sec)
	log.Infof("Workflow Step 3/3: Waiting for all sessions to close (max 30s)")
	if err := w.waitForNoSessions(ctx, params.ClusterID, params.InfobaseID, 30*time.Second); err != nil {
		// Rollback: unlock
		w.clusterClient.UnlockInfobase(context.Background(), params.ClusterID, params.InfobaseID)
		return fmt.Errorf("timeout waiting for sessions: %w", err)
	}

	log.Infof("Pre-install workflow completed: scheduled jobs blocked, no active sessions")
	return nil
}

// PostInstall выполняет шаги ПОСЛЕ установки: unlock jobs
func (w *ExtensionInstallWorkflow) PostInstall(ctx context.Context, params WorkflowParams) error {
	log := logger.GetLogger()

	log.Infof("Workflow: Unlocking scheduled jobs for infobase %s", params.InfobaseID)
	if err := w.clusterClient.UnlockInfobase(ctx, params.ClusterID, params.InfobaseID); err != nil {
		log.Errorf("CRITICAL: Failed to unlock scheduled jobs: %v", err)
		log.Errorf("MANUAL ACTION REQUIRED: Unlock infobase %s in cluster %s", params.InfobaseID, params.ClusterID)
		return fmt.Errorf("failed to unlock (MANUAL UNLOCK REQUIRED): %w", err)
	}

	log.Infof("Post-install workflow completed: scheduled jobs unlocked")
	return nil
}

// Rollback разблокирует jobs (для defer в случае ошибки)
func (w *ExtensionInstallWorkflow) Rollback(ctx context.Context, params WorkflowParams) {
	log := logger.GetLogger()

	log.Warnf("Workflow Rollback: Unlocking scheduled jobs for infobase %s", params.InfobaseID)
	if err := w.clusterClient.UnlockInfobase(ctx, params.ClusterID, params.InfobaseID); err != nil {
		log.Errorf("Rollback failed: %v", err)
	}
}

// SessionsClosedEvent represents the event from cluster-service
type SessionsClosedEvent struct {
	InfobaseID    string `json:"infobase_id"`
	ClusterID     string `json:"cluster_id"`
	Timestamp     int64  `json:"timestamp"`
	SessionsCount int    `json:"sessions_count"`
}

func (w *ExtensionInstallWorkflow) waitForNoSessions(ctx context.Context, clusterID, infobaseID string, maxWait time.Duration) error {
	log := logger.GetLogger()

	// Try event-driven approach first if Pub/Sub is enabled
	if w.pubSubEnabled && w.redisClient != nil {
		log.Infof("Using event-driven approach (Redis Pub/Sub) for waiting sessions to close")
		err := w.waitForSessionsEventDriven(ctx, clusterID, infobaseID, maxWait)
		if err != nil {
			log.Warnf("Event-driven wait failed: %v, falling back to polling", err)
			// Fallback to polling
			return w.waitForSessionsPolling(ctx, clusterID, infobaseID, maxWait)
		}
		return nil
	}

	// Use polling approach (default or fallback)
	log.Infof("Using polling approach for waiting sessions to close")
	return w.waitForSessionsPolling(ctx, clusterID, infobaseID, maxWait)
}

// waitForSessionsEventDriven subscribes to Redis Pub/Sub and waits for sessions closed event
func (w *ExtensionInstallWorkflow) waitForSessionsEventDriven(ctx context.Context, clusterID, infobaseID string, maxWait time.Duration) error {
	log := logger.GetLogger()
	channel := fmt.Sprintf("sessions:%s:closed", infobaseID)

	log.Infof("Subscribing to Redis channel: %s (max wait: %v)", channel, maxWait)

	// Subscribe to channel
	pubsub := w.redisClient.Subscribe(ctx, channel)
	defer pubsub.Close()

	// Create timeout context
	timeoutCtx, cancel := context.WithTimeout(ctx, maxWait)
	defer cancel()

	// Wait for message
	ch := pubsub.Channel()

	for {
		select {
		case <-timeoutCtx.Done():
			// Timeout!
			log.Errorf("Timeout waiting for sessions closed event after %v", maxWait)
			return fmt.Errorf("timeout: sessions still active after %v (event-driven)", maxWait)

		case msg := <-ch:
			// Event received!
			log.Infof("Received message on channel %s: %s", channel, msg.Payload)

			// Parse event
			var event SessionsClosedEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				log.Warnf("Failed to parse event: %v", err)
				continue
			}

			// Verify this is our infobase
			if event.InfobaseID == infobaseID && event.SessionsCount == 0 {
				log.Infof("All sessions closed for infobase %s (event-driven, ~0ms latency!)", infobaseID)
				return nil // Success!
			}
		}
	}
}

// waitForSessionsPolling polls sessions count periodically (fallback approach)
func (w *ExtensionInstallWorkflow) waitForSessionsPolling(ctx context.Context, clusterID, infobaseID string, maxWait time.Duration) error {
	log := logger.GetLogger()
	deadline := time.Now().Add(maxWait)
	pollInterval := 2 * time.Second
	attempt := 0

	for time.Now().Before(deadline) {
		attempt++
		count, err := w.clusterClient.GetSessionsCount(ctx, clusterID, infobaseID)
		if err != nil {
			log.Warnf("Failed to get sessions count (attempt %d): %v", attempt, err)
			// Continue trying
		} else if count == 0 {
			log.Infof("All sessions closed after %d attempts (polling)", attempt)
			return nil // Success!
		} else {
			log.Infof("Waiting for sessions to close: %d active (attempt %d)", count, attempt)
		}

		// Wait before next poll
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(pollInterval):
			// Continue polling
		}
	}

	return fmt.Errorf("timeout: sessions still active after %v (polling)", maxWait)
}

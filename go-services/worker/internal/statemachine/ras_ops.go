// go-services/worker/internal/statemachine/ras_ops.go
package statemachine

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/rasdirect"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
)

func (sm *ExtensionInstallStateMachine) lockScheduledJobs(ctx context.Context) error {
	start := time.Now()
	log := logger.GetLogger()
	sm.timeline.Record(ctx, sm.OperationID, "ras.lock_scheduled_jobs.started", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"cluster_id":  sm.ClusterID,
		"infobase_id": sm.InfobaseID,
	})

	if err := sm.executeRasOp(ctx, "lock_scheduled_jobs"); err != nil {
		sm.timeline.Record(ctx, sm.OperationID, "ras.lock_scheduled_jobs.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       err.Error(),
			"duration_ms": time.Since(start).Milliseconds(),
		})
		return err
	}

	sm.timeline.Record(ctx, sm.OperationID, "ras.lock_scheduled_jobs.completed", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"duration_ms": time.Since(start).Milliseconds(),
	})
	log.Infof("[StateMachine] RAS scheduled jobs locked: db=%s", sm.DatabaseID)
	return nil
}

func (sm *ExtensionInstallStateMachine) terminateSessions(ctx context.Context) error {
	start := time.Now()
	log := logger.GetLogger()
	sm.timeline.Record(ctx, sm.OperationID, "ras.terminate_sessions.started", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"cluster_id":  sm.ClusterID,
		"infobase_id": sm.InfobaseID,
	})

	if err := sm.executeRasOp(ctx, "terminate_sessions"); err != nil {
		sm.timeline.Record(ctx, sm.OperationID, "ras.terminate_sessions.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       err.Error(),
			"duration_ms": time.Since(start).Milliseconds(),
		})
		return err
	}

	if err := sm.waitForSessionsClosed(ctx, sm.config.TimeoutTerminate); err != nil {
		sm.timeline.Record(ctx, sm.OperationID, "ras.sessions_wait.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       err.Error(),
		})
		return err
	}

	sm.timeline.Record(ctx, sm.OperationID, "ras.terminate_sessions.completed", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"duration_ms": time.Since(start).Milliseconds(),
	})
	log.Infof("[StateMachine] RAS sessions terminated: db=%s", sm.DatabaseID)
	return nil
}

func (sm *ExtensionInstallStateMachine) unlockScheduledJobs(ctx context.Context) error {
	start := time.Now()
	log := logger.GetLogger()
	sm.timeline.Record(ctx, sm.OperationID, "ras.unlock_scheduled_jobs.started", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"cluster_id":  sm.ClusterID,
		"infobase_id": sm.InfobaseID,
	})

	if err := sm.executeRasOp(ctx, "unlock_scheduled_jobs"); err != nil {
		sm.timeline.Record(ctx, sm.OperationID, "ras.unlock_scheduled_jobs.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       err.Error(),
			"duration_ms": time.Since(start).Milliseconds(),
		})
		return err
	}

	sm.timeline.Record(ctx, sm.OperationID, "ras.unlock_scheduled_jobs.completed", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"duration_ms": time.Since(start).Milliseconds(),
	})
	log.Infof("[StateMachine] RAS scheduled jobs unlocked: db=%s", sm.DatabaseID)
	return nil
}

func (sm *ExtensionInstallStateMachine) executeRasOp(ctx context.Context, op string) error {
	useDirect := os.Getenv("USE_DIRECT_RAS") != "false" && sm.RASServer != ""

	if useDirect {
		dc, err := rasdirect.NewClient(sm.RASServer)
		if err != nil {
			return err
		}
		defer dc.Close()

		switch op {
		case "lock_scheduled_jobs":
			return dc.LockScheduledJobs(ctx, sm.ClusterID, sm.InfobaseID, sm.ClusterUser, sm.ClusterPwd)
		case "unlock_scheduled_jobs":
			return dc.UnlockScheduledJobs(ctx, sm.ClusterID, sm.InfobaseID, sm.ClusterUser, sm.ClusterPwd)
		case "terminate_sessions":
			return dc.TerminateAllSessions(ctx, sm.ClusterID, sm.InfobaseID, sm.ClusterUser, sm.ClusterPwd)
		default:
			return fmt.Errorf("unsupported ras op: %s", op)
		}
	}

	client, err := rasadapter.NewClient()
	if err != nil {
		return err
	}

	switch op {
	case "lock_scheduled_jobs":
		_, err = client.LockScheduledJobs(ctx, sm.ClusterID, sm.InfobaseID, &rasadapter.LockInfobaseRequest{})
	case "unlock_scheduled_jobs":
		_, err = client.UnlockScheduledJobs(ctx, sm.ClusterID, sm.InfobaseID, &rasadapter.UnlockInfobaseRequest{})
	case "terminate_sessions":
		_, err = client.TerminateAllSessions(ctx, sm.ClusterID, sm.InfobaseID)
	default:
		return fmt.Errorf("unsupported ras op: %s", op)
	}
	return err
}

func (sm *ExtensionInstallStateMachine) waitForSessionsClosed(ctx context.Context, timeout time.Duration) error {
	if sm.RASServer == "" {
		return nil
	}

	client, err := rasadapter.NewClient()
	if err != nil {
		return nil
	}

	deadline := time.Now().Add(timeout)
	for {
		if time.Now().After(deadline) {
			return fmt.Errorf("timeout waiting for sessions to close")
		}

		resp, err := client.ListSessions(ctx, sm.RASServer, sm.ClusterID, sm.InfobaseID)
		if err != nil {
			return err
		}
		if resp == nil || resp.Count == 0 || len(resp.Sessions) == 0 {
			return nil
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(2 * time.Second):
		}
	}
}

package statemachine

import (
	"context"
	"fmt"
)

// handleInit handles initial state
func (sm *ExtensionInstallStateMachine) handleInit(ctx context.Context) error {
	fmt.Printf("[StateMachine] Handling Init state\n")

	if err := sm.lockScheduledJobs(ctx); err != nil {
		return fmt.Errorf("failed to lock scheduled jobs: %w", err)
	}

	// Add compensation for unlock
	sm.pushCompensation("unlock_infobase", func(ctx context.Context) error {
		return sm.unlockInfobase(ctx)
	})

	// Transition to next state
	return sm.transitionTo(StateJobsLocked)
}

// handleJobsLocked handles jobs locked state
func (sm *ExtensionInstallStateMachine) handleJobsLocked(ctx context.Context) error {
	fmt.Printf("[StateMachine] Handling JobsLocked state\n")

	if err := sm.terminateSessions(ctx); err != nil {
		return fmt.Errorf("failed to terminate sessions: %w", err)
	}

	// Transition to next state
	return sm.transitionTo(StateSessionsClosed)
}

// handleSessionsClosed handles sessions closed state
func (sm *ExtensionInstallStateMachine) handleSessionsClosed(ctx context.Context) error {
	fmt.Printf("[StateMachine] Handling SessionsClosed state\n")

	if sm.extensionInstaller != nil {
		defer sm.clearDesignerCredentials()

		server := sm.ServerAddress
		if sm.ServerPort > 0 {
			server = fmt.Sprintf("%s:%d", sm.ServerAddress, sm.ServerPort)
		}

		if server == "" || sm.InfobaseName == "" || sm.Username == "" {
			return fmt.Errorf("direct install requires server, infobase_name, and username")
		}

		sm.timeline.Record(ctx, sm.OperationID, "cli.install_extension.started", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"server":      server,
			"infobase":    sm.InfobaseName,
		})

		res, err := sm.extensionInstaller.InstallExtension(ctx, ExtensionInstallRequest{
			Server:        server,
			InfobaseName:  sm.InfobaseName,
			Username:      sm.Username,
			Password:      sm.Password,
			ExtensionName: sm.ExtensionName,
			ExtensionPath: sm.ExtensionPath,
		})
		if err != nil {
			sm.timeline.Record(ctx, sm.OperationID, "cli.install_extension.failed", map[string]interface{}{
				"database_id": sm.DatabaseID,
				"error":       err.Error(),
			})
			return fmt.Errorf("direct install failed: %w", err)
		}

		if res != nil {
			sm.timeline.Record(ctx, sm.OperationID, "cli.install_extension.completed", map[string]interface{}{
				"database_id": sm.DatabaseID,
				"duration_ms": res.Duration.Milliseconds(),
			})
		}

		return sm.transitionTo(StateExtensionInstalled)
	}

	return fmt.Errorf("direct installer is required for extension install")
}

// handleExtensionInstalled handles extension installed state
func (sm *ExtensionInstallStateMachine) handleExtensionInstalled(ctx context.Context) error {
	fmt.Printf("[StateMachine] Handling ExtensionInstalled state\n")

	if err := sm.unlockScheduledJobs(ctx); err != nil {
		// Unlock failed - critical, need manual intervention
		sm.publishManualActionRequired(ctx, "unlock_failed")
		return fmt.Errorf("failed to unlock scheduled jobs: %w", err)
	}

	// Transition to completed
	return sm.transitionTo(StateCompleted)
}

// unlockInfobase unlocks infobase (compensation action)
func (sm *ExtensionInstallStateMachine) unlockInfobase(ctx context.Context) error {
	return sm.unlockScheduledJobs(ctx)
}

// publishManualActionRequired publishes manual action event
func (sm *ExtensionInstallStateMachine) publishManualActionRequired(ctx context.Context, reason string) {
	payload := map[string]interface{}{
		"operation_id":   sm.OperationID,
		"database_id":    sm.DatabaseID,
		"correlation_id": sm.CorrelationID,
		"reason":         reason,
		"state":          sm.State.String(),
	}

	sm.publishCommand(ctx,
		"events:orchestrator:manual-action",
		"orchestrator.manual-action.required",
		payload,
	)
}

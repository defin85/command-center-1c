package jobs

import (
	"context"
	"errors"
	"testing"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

type stubPoolFactualSyncClient struct {
	activeResponse    *orchestrator.PoolFactualSyncWindowResponse
	activeError       error
	activeCalls       int
	reconcileResponse *orchestrator.PoolFactualSyncWindowResponse
	reconcileError    error
	reconcileCalls    int
}

func (s *stubPoolFactualSyncClient) TriggerPoolFactualActiveSyncWindow(ctx context.Context) (*orchestrator.PoolFactualSyncWindowResponse, error) {
	s.activeCalls++
	return s.activeResponse, s.activeError
}

func (s *stubPoolFactualSyncClient) TriggerPoolFactualClosedQuarterReconcileWindow(ctx context.Context) (*orchestrator.PoolFactualSyncWindowResponse, error) {
	s.reconcileCalls++
	return s.reconcileResponse, s.reconcileError
}

func TestPoolFactualJobs_Name(t *testing.T) {
	logger := zap.NewNop()

	activeJob := NewPoolFactualActiveSyncJob(&stubPoolFactualSyncClient{}, logger)
	if activeJob.Name() != PoolFactualActiveSyncJobName {
		t.Fatalf("expected active job name %s, got %s", PoolFactualActiveSyncJobName, activeJob.Name())
	}

	reconcileJob := NewPoolFactualClosedQuarterReconcileJob(&stubPoolFactualSyncClient{}, logger)
	if reconcileJob.Name() != PoolFactualClosedQuarterReconcileJobName {
		t.Fatalf("expected reconcile job name %s, got %s", PoolFactualClosedQuarterReconcileJobName, reconcileJob.Name())
	}
}

func TestPoolFactualActiveSyncJob_Execute(t *testing.T) {
	t.Run("fails closed without client", func(t *testing.T) {
		job := NewPoolFactualActiveSyncJob(nil, zap.NewNop())
		err := job.Execute(context.Background())
		if err == nil || err.Error() != "pool factual active sync client is not configured" {
			t.Fatalf("expected fail-closed client error, got %v", err)
		}
	})

	t.Run("calls orchestrator client", func(t *testing.T) {
		client := &stubPoolFactualSyncClient{
			activeResponse: &orchestrator.PoolFactualSyncWindowResponse{
				QuarterStart:       "2026-01-01",
				PoolsScanned:       2,
				CheckpointsTouched: 2,
				CheckpointsRunning: 1,
			},
		}
		job := NewPoolFactualActiveSyncJob(client, zap.NewNop())
		if err := job.Execute(context.Background()); err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if client.activeCalls != 1 {
			t.Fatalf("expected 1 active sync call, got %d", client.activeCalls)
		}
	})

	t.Run("wraps orchestrator errors", func(t *testing.T) {
		client := &stubPoolFactualSyncClient{activeError: errors.New("boom")}
		job := NewPoolFactualActiveSyncJob(client, zap.NewNop())
		err := job.Execute(context.Background())
		if err == nil || err.Error() != "failed to trigger pool factual active sync window: boom" {
			t.Fatalf("expected wrapped error, got %v", err)
		}
	})
}

func TestPoolFactualClosedQuarterReconcileJob_Execute(t *testing.T) {
	t.Run("fails closed without client", func(t *testing.T) {
		job := NewPoolFactualClosedQuarterReconcileJob(nil, zap.NewNop())
		err := job.Execute(context.Background())
		if err == nil || err.Error() != "pool factual closed-quarter reconcile client is not configured" {
			t.Fatalf("expected fail-closed client error, got %v", err)
		}
	})

	t.Run("calls orchestrator client", func(t *testing.T) {
		client := &stubPoolFactualSyncClient{
			reconcileResponse: &orchestrator.PoolFactualSyncWindowResponse{
				QuarterCutoffStart:          "2025-10-01",
				ReadCheckpointsScanned:      4,
				ReconcileCheckpointsTouched: 2,
				ReconcileCheckpointsCreated: 1,
				ReconcileCheckpointsRunning: 1,
			},
		}
		job := NewPoolFactualClosedQuarterReconcileJob(client, zap.NewNop())
		if err := job.Execute(context.Background()); err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if client.reconcileCalls != 1 {
			t.Fatalf("expected 1 reconcile call, got %d", client.reconcileCalls)
		}
	})

	t.Run("wraps orchestrator errors", func(t *testing.T) {
		client := &stubPoolFactualSyncClient{reconcileError: errors.New("boom")}
		job := NewPoolFactualClosedQuarterReconcileJob(client, zap.NewNop())
		err := job.Execute(context.Background())
		if err == nil || err.Error() != "failed to trigger pool factual closed-quarter reconcile window: boom" {
			t.Fatalf("expected wrapped error, got %v", err)
		}
	})
}

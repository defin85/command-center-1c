package runtime_settings

import (
	"context"
	"testing"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/scheduler"
)

type syncStubJob struct {
	name string
}

func (j *syncStubJob) Name() string { return j.name }

func (j *syncStubJob) Execute(ctx context.Context) error {
	_ = ctx
	return nil
}

func TestSchedulerSettingsSyncerApplySettingsUpdatesDesiredState(t *testing.T) {
	cfg := scheduler.DefaultConfig()
	cfg.Enabled = true
	s := scheduler.NewWithConfig(nil, cfg, "worker-test", zap.NewNop())

	activeJob := &syncStubJob{name: "pool_factual_active_sync"}
	reconcileJob := &syncStubJob{name: "pool_factual_closed_quarter_reconcile"}
	if err := s.RegisterJob("@every 1h", activeJob); err != nil {
		t.Fatalf("failed to register active job: %v", err)
	}
	if err := s.RegisterJob("@every 1h", reconcileJob); err != nil {
		t.Fatalf("failed to register reconcile job: %v", err)
	}

	syncer := NewSchedulerSettingsSyncer(nil, s, zap.NewNop(), 0)
	syncer.applySettings([]orchestrator.RuntimeSetting{
		{Key: schedulerEnabledRuntimeKey, Value: false},
		{Key: poolFactualActiveSyncEnabledRuntimeKey, Value: false},
		{Key: poolFactualClosedQuarterEnabledRuntimeKey, Value: true},
	})

	if s.IsEnabled() {
		t.Fatalf("expected scheduler to be disabled after sync")
	}
	if s.IsJobEnabled(activeJob.Name()) {
		t.Fatalf("expected active sync job to be disabled after sync")
	}
	if !s.IsJobEnabled(reconcileJob.Name()) {
		t.Fatalf("expected reconcile job to remain enabled after sync")
	}
}

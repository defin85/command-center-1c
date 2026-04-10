package runtime_settings

import (
	"context"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/scheduler"
)

const (
	schedulerEnabledRuntimeKey                      = "runtime.scheduler.enabled"
	poolFactualActiveSyncEnabledRuntimeKey          = "runtime.scheduler.job.pool_factual_active_sync.enabled"
	poolFactualActiveSyncScheduleRuntimeKey         = "runtime.scheduler.job.pool_factual_active_sync.schedule"
	poolFactualClosedQuarterEnabledRuntimeKey       = "runtime.scheduler.job.pool_factual_closed_quarter_reconcile.enabled"
	poolFactualClosedQuarterScheduleRuntimeKey      = "runtime.scheduler.job.pool_factual_closed_quarter_reconcile.schedule"
	defaultSchedulerSettingsSyncInterval time.Duration = time.Minute
)

type SchedulerSettingsSyncer struct {
	client   *orchestrator.Client
	scheduler *scheduler.Scheduler
	interval time.Duration
	logger   *zap.Logger
	state    *schedulerSettingsState
}

type schedulerSettingsState struct {
	lastSchedules map[string]string
}

func NewSchedulerSettingsSyncer(
	client *orchestrator.Client,
	schedulerInstance *scheduler.Scheduler,
	logger *zap.Logger,
	interval time.Duration,
) *SchedulerSettingsSyncer {
	if interval <= 0 {
		interval = defaultSchedulerSettingsSyncInterval
	}
	return &SchedulerSettingsSyncer{
		client:    client,
		scheduler: schedulerInstance,
		interval:  interval,
		logger:    logger,
		state: &schedulerSettingsState{
			lastSchedules: map[string]string{},
		},
	}
}

func (s *SchedulerSettingsSyncer) Start(ctx context.Context) {
	if s == nil || s.client == nil || s.scheduler == nil {
		return
	}

	s.syncOnce(ctx)

	ticker := time.NewTicker(s.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.syncOnce(ctx)
		}
	}
}

func (s *SchedulerSettingsSyncer) syncOnce(ctx context.Context) {
	settings, err := s.client.GetRuntimeSettings(ctx)
	if err != nil {
		if s.logger != nil {
			s.logger.Warn("failed to fetch runtime settings for scheduler desired-state sync", zap.Error(err))
		}
		return
	}
	s.applySettings(settings)
}

func (s *SchedulerSettingsSyncer) applySettings(settings []orchestrator.RuntimeSetting) {
	if s == nil || s.scheduler == nil {
		return
	}

	values := map[string]orchestrator.RuntimeSetting{}
	for _, item := range settings {
		values[item.Key] = item
	}

	s.scheduler.SetEnabled(getBoolValue(values, schedulerEnabledRuntimeKey, s.scheduler.IsEnabled()))

	_ = s.scheduler.SetJobEnabled(
		"pool_factual_active_sync",
		getBoolValue(values, poolFactualActiveSyncEnabledRuntimeKey, s.scheduler.IsJobEnabled("pool_factual_active_sync")),
	)
	_ = s.scheduler.SetJobEnabled(
		"pool_factual_closed_quarter_reconcile",
		getBoolValue(
			values,
			poolFactualClosedQuarterEnabledRuntimeKey,
			s.scheduler.IsJobEnabled("pool_factual_closed_quarter_reconcile"),
		),
	)

	s.logScheduleChange("pool_factual_active_sync", getStringValue(values, poolFactualActiveSyncScheduleRuntimeKey, ""))
	s.logScheduleChange(
		"pool_factual_closed_quarter_reconcile",
		getStringValue(values, poolFactualClosedQuarterScheduleRuntimeKey, ""),
	)
}

func (s *SchedulerSettingsSyncer) logScheduleChange(jobName string, schedule string) {
	if s == nil || s.logger == nil || schedule == "" {
		return
	}
	previous := s.state.lastSchedules[jobName]
	if previous == schedule {
		return
	}
	s.state.lastSchedules[jobName] = schedule
	s.logger.Info(
		"scheduler cadence updated in runtime settings; controlled apply path still requires restart/reconcile",
		zap.String("job", jobName),
		zap.String("schedule", schedule),
	)
}

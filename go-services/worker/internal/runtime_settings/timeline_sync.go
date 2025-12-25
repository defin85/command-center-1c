package runtime_settings

import (
	"context"
	"strconv"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

type TimelineSettingsSyncer struct {
	client   *orchestrator.Client
	timeline *tracing.RedisTimeline
	interval time.Duration
	logger   *zap.Logger
	state    *timelineSettingsState
}

type timelineSettingsState struct {
	mu                sync.Mutex
	appliedQueueSize   int
	desiredQueueSize   int
	appliedWorkerCount int
	desiredWorkerCount int
	appliedDropOnFull  bool
	appliedResetToken  string
	synced            bool
}

func NewTimelineSettingsSyncer(
	client *orchestrator.Client,
	timeline *tracing.RedisTimeline,
	logger *zap.Logger,
	queueSize int,
	workerCount int,
	dropOnFull bool,
	interval time.Duration,
) *TimelineSettingsSyncer {
	if interval <= 0 {
		interval = time.Minute
	}
	return &TimelineSettingsSyncer{
		client:   client,
		timeline: timeline,
		interval: interval,
		logger:   logger,
		state: &timelineSettingsState{
			appliedQueueSize:   queueSize,
			desiredQueueSize:   queueSize,
			appliedWorkerCount: workerCount,
			desiredWorkerCount: workerCount,
			appliedDropOnFull:  dropOnFull,
			appliedResetToken:  "",
		},
	}
}

func (s *TimelineSettingsSyncer) Start(ctx context.Context) {
	if s == nil || s.client == nil || s.timeline == nil {
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

func (s *TimelineSettingsSyncer) ResetQueue() {
	if s == nil || s.timeline == nil {
		return
	}
	s.state.mu.Lock()
	queueSize := s.state.desiredQueueSize
	workerCount := s.state.desiredWorkerCount
	s.state.mu.Unlock()
	if queueSize <= 0 || workerCount <= 0 {
		return
	}
	s.timeline.ResetQueue(queueSize, workerCount)
	s.state.mu.Lock()
	s.state.appliedQueueSize = queueSize
	s.state.appliedWorkerCount = workerCount
	s.state.mu.Unlock()
	if s.logger != nil {
		s.logger.Info("timeline queue reset",
			zap.Int("queue_size", queueSize),
			zap.Int("worker_count", workerCount),
		)
	}
}

func (s *TimelineSettingsSyncer) syncOnce(ctx context.Context) {
	settings, err := s.client.GetRuntimeSettings(ctx)
	if err != nil {
		if s.logger != nil {
			s.logger.Warn("failed to fetch runtime settings", zap.Error(err))
		}
		return
	}
	s.applySettings(settings)
}

func (s *TimelineSettingsSyncer) applySettings(settings []orchestrator.RuntimeSetting) {
	if s == nil || s.timeline == nil {
		return
	}
	s.state.mu.Lock()
	shouldReset := false
	defer func() {
		s.state.mu.Unlock()
		if shouldReset {
			s.ResetQueue()
		}
	}()
	values := map[string]orchestrator.RuntimeSetting{}
	for _, item := range settings {
		values[item.Key] = item
	}

	queueSize := getIntValue(values, "observability.timeline.queue_size", s.state.desiredQueueSize)
	workerCount := getIntValue(values, "observability.timeline.worker_count", s.state.desiredWorkerCount)
	dropOnFull := getBoolValue(values, "observability.timeline.drop_on_full", s.state.appliedDropOnFull)
	resetToken := getStringValue(values, "observability.timeline.reset_token", "")

	if queueSize > 0 && queueSize != s.state.desiredQueueSize {
		s.state.desiredQueueSize = queueSize
		if s.logger != nil && queueSize != s.state.appliedQueueSize {
			s.logger.Info("timeline queue size pending reset",
				zap.Int("current", s.state.appliedQueueSize),
				zap.Int("desired", queueSize),
			)
		}
	}

	if workerCount > 0 && workerCount != s.state.desiredWorkerCount {
		s.state.desiredWorkerCount = workerCount
	}

	if workerCount > s.state.appliedWorkerCount {
		s.timeline.UpdateWorkerCount(workerCount)
		if s.logger != nil {
			s.logger.Info("timeline worker count updated",
				zap.Int("previous", s.state.appliedWorkerCount),
				zap.Int("current", workerCount),
			)
		}
		s.state.appliedWorkerCount = workerCount
	} else if workerCount > 0 && workerCount < s.state.appliedWorkerCount {
		if s.logger != nil {
			s.logger.Info("timeline worker count decrease pending reset",
				zap.Int("current", s.state.appliedWorkerCount),
				zap.Int("desired", workerCount),
			)
		}
	}

	if dropOnFull != s.state.appliedDropOnFull {
		s.timeline.UpdateDropOnFull(dropOnFull)
		if s.logger != nil {
			s.logger.Info("timeline drop_on_full updated",
				zap.Bool("previous", s.state.appliedDropOnFull),
				zap.Bool("current", dropOnFull),
			)
		}
		s.state.appliedDropOnFull = dropOnFull
	}

	if resetToken != "" && resetToken != s.state.appliedResetToken {
		if s.state.synced {
			s.state.appliedResetToken = resetToken
			shouldReset = true
		} else {
			s.state.appliedResetToken = resetToken
		}
	}
	s.state.synced = true
}

func getIntValue(values map[string]orchestrator.RuntimeSetting, key string, fallback int) int {
	setting, ok := values[key]
	if !ok {
		return fallback
	}
	switch val := setting.Value.(type) {
	case float64:
		return int(val)
	case int:
		return val
	case int64:
		return int(val)
	case string:
		parsed, err := strconv.Atoi(val)
		if err == nil {
			return parsed
		}
	}
	return fallback
}

func getBoolValue(values map[string]orchestrator.RuntimeSetting, key string, fallback bool) bool {
	setting, ok := values[key]
	if !ok {
		return fallback
	}
	switch val := setting.Value.(type) {
	case bool:
		return val
	case string:
		parsed, err := strconv.ParseBool(val)
		if err == nil {
			return parsed
		}
	}
	return fallback
}

func getStringValue(values map[string]orchestrator.RuntimeSetting, key string, fallback string) string {
	setting, ok := values[key]
	if !ok {
		return fallback
	}
	switch val := setting.Value.(type) {
	case string:
		return val
	}
	return fallback
}

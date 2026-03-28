package jobs

import (
	"context"
	"fmt"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

const (
	PoolFactualActiveSyncJobName             = "pool_factual_active_sync"
	PoolFactualClosedQuarterReconcileJobName = "pool_factual_closed_quarter_reconcile"
)

// PoolFactualSyncClient is the subset of orchestrator client needed by factual scheduler jobs.
type PoolFactualSyncClient interface {
	TriggerPoolFactualActiveSyncWindow(ctx context.Context) (*orchestrator.PoolFactualSyncWindowResponse, error)
	TriggerPoolFactualClosedQuarterReconcileWindow(ctx context.Context) (*orchestrator.PoolFactualSyncWindowResponse, error)
}

type PoolFactualActiveSyncJob struct {
	client PoolFactualSyncClient
	logger *zap.Logger
}

type PoolFactualClosedQuarterReconcileJob struct {
	client PoolFactualSyncClient
	logger *zap.Logger
}

func NewPoolFactualActiveSyncJob(client PoolFactualSyncClient, logger *zap.Logger) *PoolFactualActiveSyncJob {
	return &PoolFactualActiveSyncJob{
		client: client,
		logger: logger.With(zap.String("job", PoolFactualActiveSyncJobName)),
	}
}

func NewPoolFactualClosedQuarterReconcileJob(
	client PoolFactualSyncClient,
	logger *zap.Logger,
) *PoolFactualClosedQuarterReconcileJob {
	return &PoolFactualClosedQuarterReconcileJob{
		client: client,
		logger: logger.With(zap.String("job", PoolFactualClosedQuarterReconcileJobName)),
	}
}

func (j *PoolFactualActiveSyncJob) Name() string {
	return PoolFactualActiveSyncJobName
}

func (j *PoolFactualClosedQuarterReconcileJob) Name() string {
	return PoolFactualClosedQuarterReconcileJobName
}

func (j *PoolFactualActiveSyncJob) Execute(ctx context.Context) error {
	if j.client == nil {
		return fmt.Errorf("pool factual active sync client is not configured")
	}
	response, err := j.client.TriggerPoolFactualActiveSyncWindow(ctx)
	if err != nil {
		return fmt.Errorf("failed to trigger pool factual active sync window: %w", err)
	}
	j.logger.Info(
		"triggered pool factual active sync window",
		zap.String("quarter_start", response.QuarterStart),
		zap.Int("pools_scanned", response.PoolsScanned),
		zap.Int("checkpoints_touched", response.CheckpointsTouched),
		zap.Int("checkpoints_running", response.CheckpointsRunning),
	)
	return nil
}

func (j *PoolFactualClosedQuarterReconcileJob) Execute(ctx context.Context) error {
	if j.client == nil {
		return fmt.Errorf("pool factual closed-quarter reconcile client is not configured")
	}
	response, err := j.client.TriggerPoolFactualClosedQuarterReconcileWindow(ctx)
	if err != nil {
		return fmt.Errorf("failed to trigger pool factual closed-quarter reconcile window: %w", err)
	}
	j.logger.Info(
		"triggered pool factual closed-quarter reconcile window",
		zap.String("quarter_cutoff_start", response.QuarterCutoffStart),
		zap.Int("read_checkpoints_scanned", response.ReadCheckpointsScanned),
		zap.Int("reconcile_checkpoints_touched", response.ReconcileCheckpointsTouched),
		zap.Int("reconcile_checkpoints_created", response.ReconcileCheckpointsCreated),
		zap.Int("reconcile_checkpoints_running", response.ReconcileCheckpointsRunning),
	)
	return nil
}

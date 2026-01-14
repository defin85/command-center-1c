package jobs

import (
	"context"
	"fmt"
	"time"

	"go.uber.org/zap"

	crartifacts "github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/artifacts"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

const (
	ArtifactsPurgeJobName = "purge_artifacts"

	storageDeleteMaxRetries     = 3
	storageDeleteInitialBackoff = 200 * time.Millisecond
	storageDeleteMaxBackoff     = 5 * time.Second
)

type ArtifactsPurgeJob struct {
	client         *orchestrator.Client
	storage        *crartifacts.Storage
	workerInstance string
	maxJobsPerRun  int
	batchSize      int
	progressEvery  int
	logger         *zap.Logger
}

func NewArtifactsPurgeJob(
	client *orchestrator.Client,
	workerInstance string,
	logger *zap.Logger,
	maxJobsPerRun int,
) (*ArtifactsPurgeJob, error) {
	storage, err := crartifacts.NewStorageFromMinioEnv()
	if err != nil {
		return nil, err
	}

	if maxJobsPerRun <= 0 {
		maxJobsPerRun = 3
	}

	return &ArtifactsPurgeJob{
		client:         client,
		storage:        storage,
		workerInstance: workerInstance,
		maxJobsPerRun:  maxJobsPerRun,
		batchSize:      1000,
		progressEvery:  50,
		logger:         logger.With(zap.String("job", ArtifactsPurgeJobName)),
	}, nil
}

func (j *ArtifactsPurgeJob) Name() string {
	return ArtifactsPurgeJobName
}

func (j *ArtifactsPurgeJob) Execute(ctx context.Context) error {
	start := time.Now()

	processed := 0
	var lastErr error

	for processed < j.maxJobsPerRun {
		claimed, err := j.client.ClaimArtifactPurgeJob(ctx, j.workerInstance)
		if err != nil {
			return fmt.Errorf("claim purge job: %w", err)
		}
		if claimed == nil {
			break
		}

		processed++
		if err := j.runOne(ctx, claimed); err != nil {
			lastErr = err
		}
	}

	if lastErr != nil {
		j.logger.Error("purge run finished with errors",
			zap.Int("processed_jobs", processed),
			zap.Duration("duration", time.Since(start)),
			zap.Error(lastErr),
		)
		return lastErr
	}

	j.logger.Info("purge run finished",
		zap.Int("processed_jobs", processed),
		zap.Duration("duration", time.Since(start)),
	)
	return nil
}

func (j *ArtifactsPurgeJob) runOne(ctx context.Context, job *orchestrator.ArtifactPurgeJobClaim) error {
	logger := j.logger.With(
		zap.String("purge_job_id", job.JobID),
		zap.String("artifact_id", job.ArtifactID),
		zap.String("mode", job.Mode),
	)

	logger.Info("starting artifact purge",
		zap.Int("total_objects", job.TotalObjects),
		zap.Int64("total_bytes", job.TotalBytes),
	)

	deletedObjects := 0
	deletedBytes := int64(0)

	updateProgress := func() {
		if err := j.client.UpdateArtifactPurgeJob(ctx, job.JobID, deletedObjects, deletedBytes); err != nil {
			logger.Warn("failed to update purge progress", zap.Error(err))
		}
	}

	failJob := func(code string, err error) error {
		message := ""
		if err != nil {
			message = err.Error()
		}
		if completeErr := j.client.CompleteArtifactPurgeJob(ctx, job.JobID, "failed", deletedObjects, deletedBytes, code, message); completeErr != nil {
			logger.Error("failed to report purge failure", zap.Error(completeErr))
		}
		if err != nil {
			return err
		}
		return fmt.Errorf("purge failed (code=%s)", code)
	}

	sleepWithBackoff := func(attempt int) error {
		delay := storageDeleteInitialBackoff * time.Duration(1<<attempt)
		if delay > storageDeleteMaxBackoff {
			delay = storageDeleteMaxBackoff
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(delay):
			return nil
		}
	}

	keys := job.StorageKeys
	for idx := 0; idx < len(keys); idx += j.batchSize {
		end := idx + j.batchSize
		if end > len(keys) {
			end = len(keys)
		}
		batch := keys[idx:end]
		pending := batch
		for attempt := 0; attempt <= storageDeleteMaxRetries; attempt++ {
			d, failedKeys, err := j.storage.DeleteObjects(ctx, pending)
			deletedObjects += d
			deletedBytes = estimateDeletedBytes(job.TotalBytes, deletedObjects, job.TotalObjects)

			if err == nil {
				break
			}
			if attempt >= storageDeleteMaxRetries || len(failedKeys) == 0 {
				return failJob("STORAGE_DELETE_ERROR", err)
			}

			logger.Warn("storage delete failed, retrying",
				zap.Int("attempt", attempt+1),
				zap.Int("failed_keys", len(failedKeys)),
				zap.Error(err),
			)
			updateProgress()
			if sleepErr := sleepWithBackoff(attempt); sleepErr != nil {
				return failJob("STORAGE_DELETE_ERROR", sleepErr)
			}
			pending = failedKeys
		}

		if deletedObjects%j.progressEvery == 0 || end == len(keys) {
			updateProgress()
		}
	}

	if prefix := job.Prefix; prefix != "" {
		for attempt := 0; attempt <= storageDeleteMaxRetries; attempt++ {
			d, _, err := j.storage.DeleteByPrefix(ctx, prefix, j.batchSize)
			deletedObjects += d
			deletedBytes = job.TotalBytes
			updateProgress()

			if err == nil {
				break
			}
			if attempt >= storageDeleteMaxRetries {
				return failJob("STORAGE_PREFIX_DELETE_ERROR", err)
			}

			logger.Warn("storage prefix delete failed, retrying",
				zap.Int("attempt", attempt+1),
				zap.Error(err),
			)
			if sleepErr := sleepWithBackoff(attempt); sleepErr != nil {
				return failJob("STORAGE_PREFIX_DELETE_ERROR", sleepErr)
			}
		}
	}

	if err := j.client.CompleteArtifactPurgeJob(ctx, job.JobID, "success", deletedObjects, job.TotalBytes, "", ""); err != nil {
		return fmt.Errorf("complete purge job: %w", err)
	}

	logger.Info("artifact purge completed",
		zap.Int("deleted_objects", deletedObjects),
		zap.Int64("deleted_bytes", deletedBytes),
	)
	return nil
}

func estimateDeletedBytes(totalBytes int64, deletedObjects int, totalObjects int) int64 {
	if totalBytes <= 0 || deletedObjects <= 0 || totalObjects <= 0 {
		return 0
	}
	if deletedObjects >= totalObjects {
		return totalBytes
	}
	return int64(float64(totalBytes) * (float64(deletedObjects) / float64(totalObjects)))
}

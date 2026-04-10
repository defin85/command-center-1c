package scheduler

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

type countingJob struct {
	name      string
	executions atomic.Int32
}

func (j *countingJob) Name() string {
	return j.name
}

func (j *countingJob) Execute(ctx context.Context) error {
	_ = ctx
	j.executions.Add(1)
	return nil
}

func TestSchedulerJobDesiredStateCanDisableAndReenableExecution(t *testing.T) {
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("failed to start miniredis: %v", err)
	}
	defer mr.Close()

	redisClient := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	defer redisClient.Close()

	cfg := DefaultConfig()
	cfg.Enabled = true
	cfg.LockTTL = 2 * time.Second

	s := NewWithConfig(redisClient, cfg, "worker-test", zap.NewNop())
	job := &countingJob{name: "test_job"}
	if err := s.RegisterJob("@every 1h", job); err != nil {
		t.Fatalf("failed to register job: %v", err)
	}
	if err := s.Start(); err != nil {
		t.Fatalf("failed to start scheduler: %v", err)
	}
	defer func() { _ = s.Stop() }()

	if err := s.SetJobEnabled(job.Name(), false); err != nil {
		t.Fatalf("failed to disable job: %v", err)
	}
	if err := s.RunJobNow(job.Name()); err != nil {
		t.Fatalf("failed to run job immediately: %v", err)
	}
	time.Sleep(200 * time.Millisecond)
	if got := job.executions.Load(); got != 0 {
		t.Fatalf("expected disabled job to be skipped, got executions=%d", got)
	}

	if err := s.SetJobEnabled(job.Name(), true); err != nil {
		t.Fatalf("failed to reenable job: %v", err)
	}
	if err := s.RunJobNow(job.Name()); err != nil {
		t.Fatalf("failed to run job immediately after reenabling: %v", err)
	}
	time.Sleep(200 * time.Millisecond)
	if got := job.executions.Load(); got != 1 {
		t.Fatalf("expected reenbled job to execute once, got executions=%d", got)
	}
}

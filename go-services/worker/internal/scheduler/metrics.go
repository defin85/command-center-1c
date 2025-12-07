package scheduler

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	// MetricsNamespace is the namespace for scheduler metrics
	MetricsNamespace = "cc1c"
	// MetricsSubsystem is the subsystem for scheduler metrics
	MetricsSubsystem = "scheduler"
)

// SchedulerMetrics holds all scheduler-related Prometheus metrics
type SchedulerMetrics struct {
	// JobsTotal counts the total number of job executions
	// Labels: job (job name), status (success, failure, skipped)
	JobsTotal *prometheus.CounterVec

	// JobDurationSeconds measures job execution duration
	// Labels: job (job name)
	JobDurationSeconds *prometheus.HistogramVec

	// JobLastRunTimestamp records the timestamp of the last job run
	// Labels: job (job name)
	JobLastRunTimestamp *prometheus.GaugeVec

	// LockAcquisitionTotal counts lock acquisition attempts
	// Labels: job (job name), status (acquired, failed, timeout)
	LockAcquisitionTotal *prometheus.CounterVec

	// LockHoldDurationSeconds measures how long locks are held
	// Labels: job (job name)
	LockHoldDurationSeconds *prometheus.HistogramVec

	// ActiveJobs shows the number of currently running jobs
	ActiveJobs prometheus.Gauge

	// SchedulerEnabled indicates if the scheduler is enabled (1) or disabled (0)
	SchedulerEnabled prometheus.Gauge
}

// NewSchedulerMetrics creates and registers scheduler metrics
func NewSchedulerMetrics() *SchedulerMetrics {
	return &SchedulerMetrics{
		JobsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "jobs_total",
				Help:      "Total number of scheduled job executions",
			},
			[]string{"job", "status"},
		),

		JobDurationSeconds: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "job_duration_seconds",
				Help:      "Duration of scheduled job executions in seconds",
				Buckets:   []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300},
			},
			[]string{"job"},
		),

		JobLastRunTimestamp: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "job_last_run_timestamp",
				Help:      "Unix timestamp of the last job run",
			},
			[]string{"job"},
		),

		LockAcquisitionTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "lock_acquisition_total",
				Help:      "Total number of lock acquisition attempts",
			},
			[]string{"job", "status"},
		),

		LockHoldDurationSeconds: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "lock_hold_duration_seconds",
				Help:      "Duration of lock holds in seconds",
				Buckets:   []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300},
			},
			[]string{"job"},
		),

		ActiveJobs: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "active_jobs",
				Help:      "Number of currently running scheduled jobs",
			},
		),

		SchedulerEnabled: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: MetricsNamespace,
				Subsystem: MetricsSubsystem,
				Name:      "enabled",
				Help:      "Whether the scheduler is enabled (1) or disabled (0)",
			},
		),
	}
}

// JobStatus represents the status of a job execution
type JobStatus string

const (
	// JobStatusSuccess indicates successful job completion
	JobStatusSuccess JobStatus = "success"
	// JobStatusFailure indicates job failure
	JobStatusFailure JobStatus = "failure"
	// JobStatusSkipped indicates job was skipped (e.g., couldn't acquire lock)
	JobStatusSkipped JobStatus = "skipped"
)

// LockStatus represents the status of a lock acquisition attempt
type LockStatus string

const (
	// LockStatusAcquired indicates lock was successfully acquired
	LockStatusAcquired LockStatus = "acquired"
	// LockStatusFailed indicates lock acquisition failed
	LockStatusFailed LockStatus = "failed"
	// LockStatusTimeout indicates lock acquisition timed out
	LockStatusTimeout LockStatus = "timeout"
)

// RecordJobExecution records a job execution with its status and duration
func (m *SchedulerMetrics) RecordJobExecution(jobName string, status JobStatus, durationSeconds float64) {
	m.JobsTotal.WithLabelValues(jobName, string(status)).Inc()
	if status == JobStatusSuccess || status == JobStatusFailure {
		m.JobDurationSeconds.WithLabelValues(jobName).Observe(durationSeconds)
	}
}

// RecordJobStart records when a job starts
func (m *SchedulerMetrics) RecordJobStart(jobName string) {
	m.ActiveJobs.Inc()
}

// RecordJobEnd records when a job ends
func (m *SchedulerMetrics) RecordJobEnd(jobName string) {
	m.ActiveJobs.Dec()
}

// UpdateLastRunTimestamp updates the last run timestamp for a job
func (m *SchedulerMetrics) UpdateLastRunTimestamp(jobName string, timestamp float64) {
	m.JobLastRunTimestamp.WithLabelValues(jobName).Set(timestamp)
}

// RecordLockAcquisition records a lock acquisition attempt
func (m *SchedulerMetrics) RecordLockAcquisition(jobName string, status LockStatus) {
	m.LockAcquisitionTotal.WithLabelValues(jobName, string(status)).Inc()
}

// RecordLockHoldDuration records how long a lock was held
func (m *SchedulerMetrics) RecordLockHoldDuration(jobName string, durationSeconds float64) {
	m.LockHoldDurationSeconds.WithLabelValues(jobName).Observe(durationSeconds)
}

// SetSchedulerEnabled sets the scheduler enabled gauge
func (m *SchedulerMetrics) SetSchedulerEnabled(enabled bool) {
	if enabled {
		m.SchedulerEnabled.Set(1)
	} else {
		m.SchedulerEnabled.Set(0)
	}
}

// Global metrics instance
var globalMetrics *SchedulerMetrics

// GetMetrics returns the global scheduler metrics instance
func GetMetrics() *SchedulerMetrics {
	if globalMetrics == nil {
		globalMetrics = NewSchedulerMetrics()
	}
	return globalMetrics
}

// go-services/worker/internal/drivers/ibcmd/executor.go
package ibcmd

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/process"
)

// ExecutionResult contains the result of subprocess execution.
type ExecutionResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
	Duration time.Duration

	StdoutTruncated bool
	StderrTruncated bool
	WaitDelayHit    bool
}

// CombinedOutput returns stdout+stderr as a single string.
func (r *ExecutionResult) CombinedOutput() string {
	if r == nil {
		return ""
	}
	if r.Stderr == "" {
		return r.Stdout
	}
	if r.Stdout == "" {
		return r.Stderr
	}
	return r.Stdout + "\n" + r.Stderr
}

// Executor handles execution of ibcmd subprocess.
type Executor struct {
	exePath string
	timeout time.Duration
}

// NewExecutor creates a new ibcmd executor.
func NewExecutor(exePath string, timeout time.Duration) *Executor {
	if timeout == 0 {
		timeout = 10 * time.Minute
	}
	return &Executor{
		exePath: exePath,
		timeout: timeout,
	}
}

// NewExecutorFromEnv creates executor from environment configuration.
// Requires IBCMD_PATH to be set.
func NewExecutorFromEnv() (*Executor, error) {
	exePath := os.Getenv("IBCMD_PATH")
	if exePath == "" {
		return nil, fmt.Errorf("IBCMD_PATH is not configured")
	}

	timeout := 10 * time.Minute
	if raw := os.Getenv("IBCMD_TIMEOUT"); raw != "" {
		if parsed, err := time.ParseDuration(raw); err == nil {
			timeout = parsed
		}
	}

	return NewExecutor(exePath, timeout), nil
}

// Execute runs a subprocess with the given arguments and optional stdin.
// Uses async stdout/stderr reading to prevent deadlocks on large output.
func (e *Executor) Execute(ctx context.Context, args []string, stdin string) (*ExecutionResult, error) {
	runResult, err := process.Run(ctx, process.Spec{
		ExePath:   e.exePath,
		Args:      args,
		Stdin:     stdin,
		Timeout:   e.timeout,
		WaitDelay: 0,
	})

	result := &ExecutionResult{
		Stdout:          runResult.Stdout,
		Stderr:          runResult.Stderr,
		ExitCode:        runResult.ExitCode,
		Duration:        runResult.Duration,
		StdoutTruncated: runResult.StdoutTruncated,
		StderrTruncated: runResult.StderrTruncated,
		WaitDelayHit:    runResult.WaitDelayHit,
	}

	return result, err
}

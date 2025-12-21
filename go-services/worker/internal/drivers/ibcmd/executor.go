// go-services/worker/internal/drivers/ibcmd/executor.go
package ibcmd

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
	"time"
)

// ExecutionResult contains the result of subprocess execution.
type ExecutionResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
	Duration time.Duration
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
	startTime := time.Now()

	if e.exePath == "" {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("ibcmd path is not configured")
	}

	if _, err := os.Stat(e.exePath); os.IsNotExist(err) {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("ibcmd not found at path: %s", e.exePath)
	}

	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, e.exePath, args...)
	if stdin != "" {
		cmd.Stdin = bytes.NewBufferString(stdin)
	}

	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("failed to create stdout pipe: %w", err)
	}
	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("failed to start subprocess: %w", err)
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		io.Copy(&stdoutBuf, stdoutPipe)
	}()

	go func() {
		defer wg.Done()
		io.Copy(&stderrBuf, stderrPipe)
	}()

	errChan := make(chan error, 1)
	go func() {
		errChan <- cmd.Wait()
	}()

	var cmdErr error
	select {
	case cmdErr = <-errChan:
	case <-ctx.Done():
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		<-errChan
		wg.Wait()
		return &ExecutionResult{
			Stdout:   stdoutBuf.String(),
			Stderr:   stderrBuf.String(),
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("operation cancelled: %w", ctx.Err())
	}

	wg.Wait()

	duration := time.Since(startTime)
	result := &ExecutionResult{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: 0,
		Duration: duration,
	}

	if cmdErr != nil {
		if exitErr, ok := cmdErr.(*exec.ExitError); ok {
			result.ExitCode = exitErr.ExitCode()
		} else {
			return result, cmdErr
		}
	}

	return result, cmdErr
}

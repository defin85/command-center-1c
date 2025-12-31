// go-services/worker/internal/drivers/cli/v8executor.go
package cli

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
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

// V8Executor handles execution of 1cv8.exe subprocess with async stdout/stderr reading.
type V8Executor struct {
	exe1cv8Path string
	timeout     time.Duration
}

// CommandOptions configures default flags for DESIGNER commands.
type CommandOptions struct {
	DisableStartupMessages bool
	DisableStartupDialogs  bool
}

// DefaultCommandOptions returns default CLI flags for silent execution.
func DefaultCommandOptions() CommandOptions {
	return CommandOptions{
		DisableStartupMessages: true,
		DisableStartupDialogs:  true,
	}
}

// NewV8ExecutorFromEnv creates a V8Executor using environment configuration.
// Requires EXE_1CV8_PATH to be set.
func NewV8ExecutorFromEnv() (*V8Executor, error) {
	exePath := os.Getenv("EXE_1CV8_PATH")
	if exePath == "" {
		return nil, fmt.Errorf("EXE_1CV8_PATH is not configured")
	}

	timeout := 5 * time.Minute
	if raw := os.Getenv("CLI_1CV8_TIMEOUT"); raw != "" {
		if parsed, err := time.ParseDuration(raw); err == nil {
			timeout = parsed
		}
	}

	return NewV8Executor(exePath, timeout), nil
}

// NewV8Executor creates a new V8Executor instance.
// exe1cv8Path must be explicitly provided - no default path is assumed.
func NewV8Executor(exe1cv8Path string, timeout time.Duration) *V8Executor {
	if timeout == 0 {
		timeout = 5 * time.Minute
	}
	return &V8Executor{
		exe1cv8Path: exe1cv8Path,
		timeout:     timeout,
	}
}

// Execute runs a subprocess with the given arguments and returns the result.
// Uses async stdout/stderr reading to prevent deadlocks on large output.
func (e *V8Executor) Execute(ctx context.Context, args []string) (*ExecutionResult, error) {
	startTime := time.Now()

	if e.exe1cv8Path == "" {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("1cv8.exe path is not configured")
	}

	if _, err := os.Stat(e.exe1cv8Path); os.IsNotExist(err) {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("1cv8.exe not found at path: %s", e.exe1cv8Path)
	}

	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, e.exe1cv8Path, args...)

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

// BuildDesignerCommandArgs builds full DESIGNER command arguments.
func BuildDesignerCommandArgs(
	server string,
	infobase string,
	username string,
	password string,
	command string,
	args []string,
	options CommandOptions,
) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}

	cmd := strings.TrimSpace(command)
	cmd = strings.TrimPrefix(cmd, "/")
	if cmd == "" {
		return nil, fmt.Errorf("command cannot be empty")
	}

	cmdArgs := []string{"DESIGNER"}
	if options.DisableStartupMessages {
		cmdArgs = append(cmdArgs, "/DisableStartupMessages")
	}
	if options.DisableStartupDialogs {
		cmdArgs = append(cmdArgs, "/DisableStartupDialogs")
	}
	cmdArgs = append(cmdArgs,
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		fmt.Sprintf("/%s", cmd),
	)
	cmdArgs = append(cmdArgs, args...)
	return cmdArgs, nil
}

// MaskSensitiveArgs replaces password arguments with placeholder.
func MaskSensitiveArgs(args []string) []string {
	masked := make([]string, 0, len(args))
	for _, arg := range args {
		if strings.HasPrefix(arg, "/P") {
			masked = append(masked, "/P***")
			continue
		}
		masked = append(masked, arg)
	}
	return masked
}

// go-services/worker/internal/drivers/cli/v8executor.go
package cli

import (
	"context"
	"fmt"
	"os"
	"strings"
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
// Requires PLATFORM_1C_BIN_PATH to be set.
func NewV8ExecutorFromEnv() (*V8Executor, error) {
	exePath, err := Resolve1cv8PathFromEnv()
	if err != nil {
		return nil, err
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
	runResult, err := process.Run(ctx, process.Spec{
		ExePath:   e.exe1cv8Path,
		Args:      args,
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

// BuildDesignerCommandArgs builds full DESIGNER command arguments.
func BuildDesignerCommandArgs(
	server string,
	infobase string,
	username string,
	password string,
	command string,
	args []string,
	options CommandOptions,
	preArgs []string,
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
	if strings.TrimSpace(password) != "" && strings.TrimSpace(username) == "" {
		return nil, fmt.Errorf("username is required when password is provided")
	}
	cmdArgs = append(cmdArgs, fmt.Sprintf("/S%s\\%s", server, infobase))
	if strings.TrimSpace(username) != "" {
		cmdArgs = append(cmdArgs, fmt.Sprintf("/N%s", username))
	}
	if strings.TrimSpace(password) != "" {
		cmdArgs = append(cmdArgs, fmt.Sprintf("/P%s", password))
	}
	if len(preArgs) > 0 {
		cmdArgs = append(cmdArgs, preArgs...)
	}
	cmdArgs = append(cmdArgs, fmt.Sprintf("/%s", cmd))
	cmdArgs = append(cmdArgs, args...)
	return cmdArgs, nil
}

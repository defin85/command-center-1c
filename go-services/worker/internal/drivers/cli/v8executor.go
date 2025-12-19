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

// BuildInstallLoadCommand builds command arguments for loading extension (step 1 of install).
func BuildInstallLoadCommand(server, infobase, username, password, extensionName, extensionPath string) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}
	if strings.TrimSpace(extensionPath) == "" {
		return nil, fmt.Errorf("extension path cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/LoadCfg", extensionPath,
		"-Extension", extensionName,
	}, nil
}

// BuildInstallUpdateCommand builds command arguments for updating DB config (step 2 of install).
func BuildInstallUpdateCommand(server, infobase, username, password, extensionName string) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/UpdateDBCfg",
		"-Extension", extensionName,
	}, nil
}

// BuildDeleteCommand builds command arguments for deleting an extension.
func BuildDeleteCommand(server, infobase, username, password, extensionName string) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(extensionName) == "" {
		return nil, fmt.Errorf("extension name cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/DeleteCfg",
		"-Extension", extensionName,
	}, nil
}

// BuildUpdateDBCfgCommand builds command arguments for updating DB configuration (no extension).
func BuildUpdateDBCfgCommand(server, infobase, username, password string) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/UpdateDBCfg",
	}, nil
}

// BuildLoadConfigCommand builds command arguments for loading configuration from file (.cf).
func BuildLoadConfigCommand(server, infobase, username, password, configPath string) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(configPath) == "" {
		return nil, fmt.Errorf("config path cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/LoadCfg", configPath,
	}, nil
}

// BuildDumpConfigCommand builds command arguments for dumping configuration to file (.cf).
func BuildDumpConfigCommand(server, infobase, username, password, targetPath string) ([]string, error) {
	if strings.TrimSpace(server) == "" {
		return nil, fmt.Errorf("server cannot be empty")
	}
	if strings.TrimSpace(infobase) == "" {
		return nil, fmt.Errorf("infobase cannot be empty")
	}
	if strings.TrimSpace(targetPath) == "" {
		return nil, fmt.Errorf("target path cannot be empty")
	}

	return []string{
		"DESIGNER",
		"/DisableStartupMessages",
		"/DisableStartupDialogs",
		fmt.Sprintf("/S%s\\%s", server, infobase),
		fmt.Sprintf("/N%s", username),
		fmt.Sprintf("/P%s", password),
		"/DumpCfg", targetPath,
	}, nil
}

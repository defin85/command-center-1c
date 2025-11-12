package v8executor

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

// ExecutionResult contains the result of subprocess execution
type ExecutionResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
	Duration time.Duration
}

// V8Executor handles execution of 1cv8.exe subprocess with async stdout/stderr reading
type V8Executor struct {
	exe1cv8Path string
	timeout     time.Duration
}

// InstallRequest contains parameters for installing an extension
type InstallRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
	ExtensionPath string // Path to .cfe file
}

// DumpRequest contains parameters for dumping an extension
type DumpRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
	OutputPath    string // Where to save .cfe
}

// RollbackRequest contains parameters for rolling back an extension
type RollbackRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
}

// UpdateRequest contains parameters for updating extension DB config
type UpdateRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
}

// NewV8Executor creates a new V8Executor instance
// exe1cv8Path must be explicitly provided - no default path is assumed
// This prevents attempting to run potentially invalid or non-existent executables
func NewV8Executor(exe1cv8Path string, timeout time.Duration) *V8Executor {
	// DO NOT set default path - require explicit configuration
	// This prevents deadlock issues when default path exists but shouldn't be used

	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	return &V8Executor{
		exe1cv8Path: exe1cv8Path,
		timeout:     timeout,
	}
}

// Execute runs a subprocess with the given arguments and returns the result
// CRITICAL: Uses async stdout/stderr reading to prevent deadlock when subprocess
// produces large output (> 64KB buffer on Windows)
func (e *V8Executor) Execute(ctx context.Context, args []string) (*ExecutionResult, error) {
	startTime := time.Now()

	// Validate exe1cv8Path before attempting to run
	if e.exe1cv8Path == "" {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("1cv8.exe path is not configured")
	}

	// Check if executable exists before attempting to run
	// This prevents deadlock issues on Windows when trying to run non-existent files
	if _, err := os.Stat(e.exe1cv8Path); os.IsNotExist(err) {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("1cv8.exe not found at path: %s", e.exe1cv8Path)
	}

	// Apply timeout to context
	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	// Create command with context for cancellation support
	cmd := exec.CommandContext(ctx, e.exe1cv8Path, args...)

	// CRITICAL FIX: Use pipes for async reading to avoid deadlock
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

	// Start the subprocess
	if err := cmd.Start(); err != nil {
		return &ExecutionResult{
			ExitCode: -1,
			Duration: time.Since(startTime),
		}, fmt.Errorf("failed to start subprocess: %w", err)
	}

	// Read stdout and stderr asynchronously in separate goroutines
	// This prevents deadlock when subprocess produces large output
	var stdoutBuf, stderrBuf bytes.Buffer
	var wg sync.WaitGroup

	wg.Add(2)

	// Read stdout in goroutine with panic recovery
	go func() {
		defer func() {
			if r := recover(); r != nil {
				// Log panic but ensure WaitGroup is decremented
				// This prevents deadlock if io.Copy panics
			}
			wg.Done()
		}()
		io.Copy(&stdoutBuf, stdoutPipe)
	}()

	// Read stderr in goroutine with panic recovery
	go func() {
		defer func() {
			if r := recover(); r != nil {
				// Log panic but ensure WaitGroup is decremented
			}
			wg.Done()
		}()
		io.Copy(&stderrBuf, stderrPipe)
	}()

	// Wait for subprocess to complete in a separate goroutine
	errChan := make(chan error, 1)
	go func() {
		errChan <- cmd.Wait()
	}()

	// Handle completion or context cancellation
	var cmdErr error
	select {
	case cmdErr = <-errChan:
		// Process completed normally (or failed) - NO KILL needed
		// Process already exited gracefully
	case <-ctx.Done():
		// Context cancelled (timeout or explicit cancellation)
		// ONLY HERE we kill the process
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		<-errChan // Wait for Wait() to return
		wg.Wait() // Wait for readers to complete

		// Return result with partial output captured before cancellation
		return &ExecutionResult{
			Stdout:   stdoutBuf.String(),
			Stderr:   stderrBuf.String(),
			ExitCode: -1, // Cancelled
			Duration: time.Since(startTime),
		}, fmt.Errorf("operation cancelled: %w", ctx.Err())
	}

	// Wait for stdout/stderr readers to complete
	wg.Wait()

	duration := time.Since(startTime)

	// Build result
	result := &ExecutionResult{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: 0,
		Duration: duration,
	}

	// Extract exit code from error if available
	if cmdErr != nil {
		if exitErr, ok := cmdErr.(*exec.ExitError); ok {
			result.ExitCode = exitErr.ExitCode()
		} else {
			// Non-exit error (e.g., failed to start)
			return result, cmdErr
		}
	}

	return result, cmdErr
}

// InstallExtension installs an extension into a 1C infobase (2-step process)
// Step 1: LoadCfg -Extension (load .cfe file)
// Step 2: UpdateDBCfg -Extension (apply to database)
func (e *V8Executor) InstallExtension(ctx context.Context, req InstallRequest) error {
	// ✅ ADD: Log request details
	fmt.Printf("[DEBUG] InstallExtension called: server=%s, infobase=%s, user=%s, extension=%s, path=%s\n",
		req.Server, req.InfobaseName, req.Username, req.ExtensionName, req.ExtensionPath)

	// Step 1: Load extension from .cfe file
	loadArgs, err := BuildInstallLoadCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
		req.ExtensionPath,
	)
	if err != nil {
		return fmt.Errorf("failed to build LoadCfg command: %w", err)
	}

	// ✅ ADD: Log command that will be executed
	fmt.Printf("[DEBUG] Executing LoadCfg command: %v\n", loadArgs)

	result1, err := e.Execute(ctx, loadArgs)

	// ✅ ADD: Log result
	fmt.Printf("[DEBUG] LoadCfg result: exitCode=%d, stdout=%s, stderr=%s, err=%v\n",
		result1.ExitCode, result1.Stdout, result1.Stderr, err)

	if err != nil {
		return fmt.Errorf("LoadCfg failed: %w (stderr: %s)", err, result1.Stderr)
	}
	if result1.ExitCode != 0 {
		return fmt.Errorf("LoadCfg failed with exit code %d: %s", result1.ExitCode, result1.Stderr)
	}

	// Step 2: Update DB configuration
	updateArgs, err := BuildInstallUpdateCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
	)
	if err != nil {
		return fmt.Errorf("failed to build UpdateDBCfg command: %w", err)
	}

	// ✅ ADD: Log command that will be executed
	fmt.Printf("[DEBUG] Executing UpdateDBCfg command: %v\n", updateArgs)

	result2, err := e.Execute(ctx, updateArgs)

	// ✅ ADD: Log result
	fmt.Printf("[DEBUG] UpdateDBCfg result: exitCode=%d, stdout=%s, stderr=%s, err=%v\n",
		result2.ExitCode, result2.Stdout, result2.Stderr, err)

	if err != nil {
		return fmt.Errorf("UpdateDBCfg failed: %w (stderr: %s)", err, result2.Stderr)
	}
	if result2.ExitCode != 0 {
		return fmt.Errorf("UpdateDBCfg failed with exit code %d: %s", result2.ExitCode, result2.Stderr)
	}

	return nil
}

// UpdateExtension updates extension DB configuration
// This is typically called after modifying an extension
func (e *V8Executor) UpdateExtension(ctx context.Context, req UpdateRequest) error {
	updateArgs, err := BuildUpdateCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
	)
	if err != nil {
		return fmt.Errorf("failed to build UpdateDBCfg command: %w", err)
	}

	result, err := e.Execute(ctx, updateArgs)
	if err != nil {
		return fmt.Errorf("UpdateDBCfg failed: %w (stderr: %s)", err, result.Stderr)
	}
	if result.ExitCode != 0 {
		return fmt.Errorf("UpdateDBCfg failed with exit code %d: %s", result.ExitCode, result.Stderr)
	}

	return nil
}

// DumpExtension exports an extension to a .cfe file
func (e *V8Executor) DumpExtension(ctx context.Context, req DumpRequest) error {
	dumpArgs, err := BuildDumpCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
		req.OutputPath,
	)
	if err != nil {
		return fmt.Errorf("failed to build DumpCfg command: %w", err)
	}

	result, err := e.Execute(ctx, dumpArgs)
	if err != nil {
		return fmt.Errorf("DumpCfg failed: %w (stderr: %s)", err, result.Stderr)
	}
	if result.ExitCode != 0 {
		return fmt.Errorf("DumpCfg failed with exit code %d: %s", result.ExitCode, result.Stderr)
	}

	return nil
}

// RollbackExtension rolls back extension to main configuration
func (e *V8Executor) RollbackExtension(ctx context.Context, req RollbackRequest) error {
	rollbackArgs, err := BuildRollbackCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
	)
	if err != nil {
		return fmt.Errorf("failed to build RollbackCfg command: %w", err)
	}

	result, err := e.Execute(ctx, rollbackArgs)
	if err != nil {
		return fmt.Errorf("RollbackCfg failed: %w (stderr: %s)", err, result.Stderr)
	}
	if result.ExitCode != 0 {
		return fmt.Errorf("RollbackCfg failed with exit code %d: %s", result.ExitCode, result.Stderr)
	}

	return nil
}

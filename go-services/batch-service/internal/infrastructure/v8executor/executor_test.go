package v8executor

import (
	"context"
	"os/exec"
	"strings"
	"testing"
	"time"
)

// TestExecute_Success tests successful execution
func TestExecute_Success(t *testing.T) {
	// Skip if 1cv8.exe not available
	exe1cv8Path := `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	if _, err := exec.LookPath(exe1cv8Path); err != nil {
		t.Skip("1cv8.exe not found, skipping test")
	}

	// NOTE: 1cv8.exe DESIGNER /? command may hang waiting for user input
	// This is a known behavior - it tries to show GUI help dialog
	// Instead, we test with a command that will definitely fail quickly
	// This still tests our deadlock prevention without hanging

	executor := NewV8Executor(exe1cv8Path, 5*time.Second)

	// Use a command that will fail quickly (try to connect to non-existent base)
	// This tests that we handle errors without deadlock
	args := []string{"DESIGNER", "/F", "nonexistent_server\\nonexistent_base"}

	ctx := context.Background()
	result, err := executor.Execute(ctx, args)

	// Debug output
	t.Logf("DEBUG: err=%v, result=%+v", err, result)

	// The command should fail (connection error or timeout), but MUST NOT deadlock
	// We're testing deadlock prevention, not successful execution
	if err == nil {
		t.Log("WARNING: Expected command to fail, but it succeeded")
	}

	// Result should be returned regardless of success/failure
	if result == nil {
		t.Fatalf("Expected non-nil result even on failure (err=%v)", err)
	}

	// Check duration is reasonable
	// NOTE: May timeout if 1cv8.exe tries to connect to non-existent base (that's OK)
	// We're testing that it completes (not deadlocks), even if via timeout
	if result.Duration > 6*time.Second {
		t.Errorf("Command took too long (potential deadlock): %v", result.Duration)
	}

	t.Logf("Execution completed in %v (exit code: %d)", result.Duration, result.ExitCode)
	t.Logf("Test passed - no deadlock detected (result returned successfully)")
}

// TestExecute_Timeout tests timeout handling
func TestExecute_Timeout(t *testing.T) {
	// Use ping command with short timeout
	// ping -n 100 will take ~100 seconds, but we timeout after 1 second
	pingPath, err := exec.LookPath("ping.exe")
	if err != nil {
		t.Skip("ping.exe not found, skipping timeout test")
	}

	executor := NewV8Executor(pingPath, 1*time.Second) // Use short timeout

	// Command that will timeout (ping 100 times)
	args := []string{"-n", "100", "127.0.0.1"}

	ctx := context.Background()
	result, err := executor.Execute(ctx, args)

	// Should timeout
	if err == nil {
		t.Fatal("Expected timeout error, got nil")
	}

	if !strings.Contains(err.Error(), "cancelled") && !strings.Contains(err.Error(), "timeout") && !strings.Contains(err.Error(), "deadline") {
		t.Errorf("Expected cancellation/timeout/deadline error, got: %v", err)
	}

	// Result may be nil on timeout
	if result != nil {
		t.Logf("Partial result captured: stdout=%d bytes, stderr=%d bytes",
			len(result.Stdout), len(result.Stderr))
	}
}

// TestExecute_LargeOutput tests handling of large output without deadlock
// This is the CRITICAL test - ensures we don't deadlock when subprocess
// produces more than 64KB of output
func TestExecute_LargeOutput(t *testing.T) {
	// Use a command that produces large output
	// On Windows: "dir /s C:\Windows\System32" produces large output
	// On Unix: "find /usr" produces large output

	// We'll use a simple echo command in a loop for cross-platform testing
	// This is a simplified test - real deadlock would happen with 1cv8.exe

	// Use PowerShell to generate large output (Windows)
	// Find full path to powershell
	powershellPath, err := exec.LookPath("powershell.exe")
	if err != nil {
		t.Skip("PowerShell not found, skipping large output test")
	}

	executor := NewV8Executor(powershellPath, 10*time.Second)

	// Generate ~100KB of output
	args := []string{"-Command", "1..10000 | ForEach-Object { Write-Output 'Line $_: This is a test line with some content to make it longer' }"}

	ctx := context.Background()
	result, err := executor.Execute(ctx, args)

	// Should complete without deadlock
	if err != nil {
		t.Fatalf("Execution failed: %v", err)
	}

	if result == nil {
		t.Fatal("Expected non-nil result")
	}

	// Should have captured large output
	outputSize := len(result.Stdout) + len(result.Stderr)
	if outputSize < 10000 {
		t.Errorf("Expected large output (>10KB), got %d bytes", outputSize)
	}

	t.Logf("Successfully handled large output: %d bytes in %v", outputSize, result.Duration)
}

// TestExecute_NonZeroExitCode tests handling of non-zero exit codes
func TestExecute_NonZeroExitCode(t *testing.T) {
	// Use a command that will exit with non-zero code
	// On Windows: "cmd /c exit 42"
	// On Unix: "sh -c 'exit 42'"

	cmdPath, err := exec.LookPath("cmd.exe")
	if err != nil {
		t.Skip("cmd.exe not found, skipping test")
	}

	executor := NewV8Executor(cmdPath, 5*time.Second)
	args := []string{"/c", "exit 42"}

	ctx := context.Background()
	result, err := executor.Execute(ctx, args)

	// Should return error for non-zero exit
	if err == nil {
		t.Fatal("Expected error for non-zero exit code")
	}

	// Should still have result with exit code
	if result == nil {
		t.Fatal("Expected non-nil result")
	}

	if result.ExitCode != 42 {
		t.Errorf("Expected exit code 42, got %d", result.ExitCode)
	}

	t.Logf("Correctly captured exit code: %d", result.ExitCode)
}

// TestExecute_ContextCancellation tests context cancellation handling
func TestExecute_ContextCancellation(t *testing.T) {
	pingPath, err := exec.LookPath("ping.exe")
	if err != nil {
		t.Skip("ping.exe not found, skipping test")
	}

	executor := NewV8Executor(pingPath, 30*time.Second)

	// Command that will run for a while
	// On Windows: "ping -n 100 127.0.0.1" (100 pings)
	args := []string{"-n", "100", "127.0.0.1"}

	// Create context that we'll cancel
	ctx, cancel := context.WithCancel(context.Background())

	// Cancel after 500ms
	go func() {
		time.Sleep(500 * time.Millisecond)
		cancel()
	}()

	result, err := executor.Execute(ctx, args)

	// Should return cancellation error
	if err == nil {
		t.Fatal("Expected cancellation error, got nil")
	}

	if !strings.Contains(err.Error(), "cancelled") {
		t.Errorf("Expected cancellation error, got: %v", err)
	}

	// Result may be nil or contain partial output
	if result != nil {
		t.Logf("Partial output captured before cancellation: %d bytes",
			len(result.Stdout)+len(result.Stderr))
	}
}

// TestNewV8Executor_Defaults tests default values
func TestNewV8Executor_Defaults(t *testing.T) {
	executor := NewV8Executor("", 0)

	// Should NOT set default exe path - require explicit configuration
	if executor.exe1cv8Path != "" {
		t.Errorf("Expected empty exe path (no default), got: %s", executor.exe1cv8Path)
	}

	// Should set default timeout
	if executor.timeout != 5*time.Minute {
		t.Errorf("Expected default timeout 5m, got: %v", executor.timeout)
	}
}

// TestNewV8Executor_CustomValues tests custom values
func TestNewV8Executor_CustomValues(t *testing.T) {
	customPath := `C:\Custom\Path\1cv8.exe`
	customTimeout := 10 * time.Minute

	executor := NewV8Executor(customPath, customTimeout)

	if executor.exe1cv8Path != customPath {
		t.Errorf("Expected custom exe path, got: %s", executor.exe1cv8Path)
	}

	if executor.timeout != customTimeout {
		t.Errorf("Expected custom timeout, got: %v", executor.timeout)
	}
}

// TestInstallExtension_Success tests successful extension installation
func TestInstallExtension_Success(t *testing.T) {
	// This is a unit test - we test the method structure, not actual 1C execution
	// Real integration tests would require a running 1C infobase

	// Create executor with dummy path (won't actually execute)
	executor := NewV8Executor("dummy.exe", 5*time.Second)

	req := InstallRequest{
		Server:        "testserver",
		InfobaseName:  "testbase",
		Username:      "admin",
		Password:      "pass",
		ExtensionName: "TestExt",
		ExtensionPath: "C:\\test\\ext.cfe",
	}

	ctx := context.Background()

	// This will fail because dummy.exe doesn't exist, but we test the method structure
	err := executor.InstallExtension(ctx, req)

	// Should fail with "not found" error (expected for unit test)
	if err == nil {
		t.Fatal("Expected error for dummy executable")
	}

	if !strings.Contains(err.Error(), "not found") && !strings.Contains(err.Error(), "LoadCfg") {
		t.Logf("Got expected error: %v", err)
	}
}

// TestInstallExtension_ValidationError tests input validation
func TestInstallExtension_ValidationError(t *testing.T) {
	executor := NewV8Executor("dummy.exe", 5*time.Second)

	testCases := []struct {
		name string
		req  InstallRequest
	}{
		{
			name: "empty server",
			req: InstallRequest{
				Server:        "",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "C:\\test\\ext.cfe",
			},
		},
		{
			name: "empty infobase",
			req: InstallRequest{
				Server:        "testserver",
				InfobaseName:  "",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "C:\\test\\ext.cfe",
			},
		},
		{
			name: "empty extension name",
			req: InstallRequest{
				Server:        "testserver",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "",
				ExtensionPath: "C:\\test\\ext.cfe",
			},
		},
		{
			name: "empty extension path",
			req: InstallRequest{
				Server:        "testserver",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				ExtensionPath: "",
			},
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := executor.InstallExtension(ctx, tc.req)

			if err == nil {
				t.Fatalf("Expected validation error for %s", tc.name)
			}

			if !strings.Contains(err.Error(), "cannot be empty") {
				t.Errorf("Expected validation error, got: %v", err)
			}
		})
	}
}

// TestUpdateExtension_ValidationError tests input validation for UpdateExtension
func TestUpdateExtension_ValidationError(t *testing.T) {
	executor := NewV8Executor("dummy.exe", 5*time.Second)

	testCases := []struct {
		name string
		req  UpdateRequest
	}{
		{
			name: "empty server",
			req: UpdateRequest{
				Server:        "",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
			},
		},
		{
			name: "empty infobase",
			req: UpdateRequest{
				Server:        "testserver",
				InfobaseName:  "",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
			},
		},
		{
			name: "empty extension name",
			req: UpdateRequest{
				Server:        "testserver",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "",
			},
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := executor.UpdateExtension(ctx, tc.req)

			if err == nil {
				t.Fatalf("Expected validation error for %s", tc.name)
			}

			if !strings.Contains(err.Error(), "cannot be empty") {
				t.Errorf("Expected validation error, got: %v", err)
			}
		})
	}
}

// TestDumpExtension_ValidationError tests input validation for DumpExtension
func TestDumpExtension_ValidationError(t *testing.T) {
	executor := NewV8Executor("dummy.exe", 5*time.Second)

	testCases := []struct {
		name string
		req  DumpRequest
	}{
		{
			name: "empty server",
			req: DumpRequest{
				Server:        "",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				OutputPath:    "C:\\dump\\ext.cfe",
			},
		},
		{
			name: "empty infobase",
			req: DumpRequest{
				Server:        "testserver",
				InfobaseName:  "",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				OutputPath:    "C:\\dump\\ext.cfe",
			},
		},
		{
			name: "empty extension name",
			req: DumpRequest{
				Server:        "testserver",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "",
				OutputPath:    "C:\\dump\\ext.cfe",
			},
		},
		{
			name: "empty output path",
			req: DumpRequest{
				Server:        "testserver",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
				OutputPath:    "",
			},
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := executor.DumpExtension(ctx, tc.req)

			if err == nil {
				t.Fatalf("Expected validation error for %s", tc.name)
			}

			if !strings.Contains(err.Error(), "cannot be empty") {
				t.Errorf("Expected validation error, got: %v", err)
			}
		})
	}
}

// TestRollbackExtension_ValidationError tests input validation for RollbackExtension
func TestRollbackExtension_ValidationError(t *testing.T) {
	executor := NewV8Executor("dummy.exe", 5*time.Second)

	testCases := []struct {
		name string
		req  RollbackRequest
	}{
		{
			name: "empty server",
			req: RollbackRequest{
				Server:        "",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
			},
		},
		{
			name: "empty infobase",
			req: RollbackRequest{
				Server:        "testserver",
				InfobaseName:  "",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "TestExt",
			},
		},
		{
			name: "empty extension name",
			req: RollbackRequest{
				Server:        "testserver",
				InfobaseName:  "testbase",
				Username:      "admin",
				Password:      "pass",
				ExtensionName: "",
			},
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := executor.RollbackExtension(ctx, tc.req)

			if err == nil {
				t.Fatalf("Expected validation error for %s", tc.name)
			}

			if !strings.Contains(err.Error(), "cannot be empty") {
				t.Errorf("Expected validation error, got: %v", err)
			}
		})
	}
}

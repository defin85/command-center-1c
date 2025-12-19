// go-services/worker/internal/drivers/cli/extension_installer.go
package cli

import (
	"context"
	"fmt"
	"os"
	"time"
)

// InstallRequest contains parameters for installing an extension.
type InstallRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
	ExtensionPath string
}

// InstallResult contains execution metadata for install.
type InstallResult struct {
	Duration time.Duration
	Output   string
}

// ExtensionInstaller installs extensions via 1cv8.exe DESIGNER.
type ExtensionInstaller struct {
	executor *V8Executor
}

// NewExtensionInstallerFromEnv creates installer from environment configuration.
// Requires EXE_1CV8_PATH to be set.
func NewExtensionInstallerFromEnv() (*ExtensionInstaller, error) {
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

	return NewExtensionInstaller(exePath, timeout), nil
}

// NewExtensionInstaller creates a new ExtensionInstaller with explicit configuration.
func NewExtensionInstaller(exePath string, timeout time.Duration) *ExtensionInstaller {
	return &ExtensionInstaller{
		executor: NewV8Executor(exePath, timeout),
	}
}

// InstallExtension installs extension using two-step DESIGNER commands.
func (i *ExtensionInstaller) InstallExtension(ctx context.Context, req InstallRequest) (*InstallResult, error) {
	start := time.Now()

	loadArgs, err := BuildInstallLoadCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
		req.ExtensionPath,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to build LoadCfg command: %w", err)
	}

	loadRes, err := i.executor.Execute(ctx, loadArgs)
	if err != nil {
		return &InstallResult{Duration: time.Since(start), Output: loadRes.CombinedOutput()},
			fmt.Errorf("LoadCfg failed: %w (stderr: %s)", err, loadRes.Stderr)
	}
	if loadRes.ExitCode != 0 {
		return &InstallResult{Duration: time.Since(start), Output: loadRes.CombinedOutput()},
			fmt.Errorf("LoadCfg failed with exit code %d: %s", loadRes.ExitCode, loadRes.Stderr)
	}

	updateArgs, err := BuildInstallUpdateCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to build UpdateDBCfg command: %w", err)
	}

	updateRes, err := i.executor.Execute(ctx, updateArgs)
	if err != nil {
		return &InstallResult{Duration: time.Since(start), Output: updateRes.CombinedOutput()},
			fmt.Errorf("UpdateDBCfg failed: %w (stderr: %s)", err, updateRes.Stderr)
	}
	if updateRes.ExitCode != 0 {
		return &InstallResult{Duration: time.Since(start), Output: updateRes.CombinedOutput()},
			fmt.Errorf("UpdateDBCfg failed with exit code %d: %s", updateRes.ExitCode, updateRes.Stderr)
	}

	return &InstallResult{
		Duration: time.Since(start),
		Output:   updateRes.CombinedOutput(),
	}, nil
}

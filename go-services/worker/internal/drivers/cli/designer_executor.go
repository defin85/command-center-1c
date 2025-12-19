// go-services/worker/internal/drivers/cli/designer_executor.go
package cli

import (
	"context"
	"fmt"
	"os"
	"time"
)

// DesignerExecutor executes 1cv8 DESIGNER commands for configuration operations.
type DesignerExecutor struct {
	executor *V8Executor
}

// NewDesignerExecutorFromEnv creates executor from environment configuration.
// Requires EXE_1CV8_PATH to be set.
func NewDesignerExecutorFromEnv() (*DesignerExecutor, error) {
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

	return NewDesignerExecutor(exePath, timeout), nil
}

// NewDesignerExecutor creates a new executor with explicit configuration.
func NewDesignerExecutor(exePath string, timeout time.Duration) *DesignerExecutor {
	return &DesignerExecutor{
		executor: NewV8Executor(exePath, timeout),
	}
}

// RemoveExtension removes an extension from infobase.
func (e *DesignerExecutor) RemoveExtension(ctx context.Context, server, infobase, username, password, extensionName string) (*ExecutionResult, error) {
	args, err := BuildDeleteCommand(server, infobase, username, password, extensionName)
	if err != nil {
		return nil, err
	}
	return e.executor.Execute(ctx, args)
}

// UpdateDBCfg updates database configuration.
func (e *DesignerExecutor) UpdateDBCfg(ctx context.Context, server, infobase, username, password string) (*ExecutionResult, error) {
	args, err := BuildUpdateDBCfgCommand(server, infobase, username, password)
	if err != nil {
		return nil, err
	}
	return e.executor.Execute(ctx, args)
}

// LoadConfig loads configuration from file (.cf).
func (e *DesignerExecutor) LoadConfig(ctx context.Context, server, infobase, username, password, configPath string) (*ExecutionResult, error) {
	args, err := BuildLoadConfigCommand(server, infobase, username, password, configPath)
	if err != nil {
		return nil, err
	}
	return e.executor.Execute(ctx, args)
}

// DumpConfig dumps configuration to file (.cf).
func (e *DesignerExecutor) DumpConfig(ctx context.Context, server, infobase, username, password, targetPath string) (*ExecutionResult, error) {
	args, err := BuildDumpConfigCommand(server, infobase, username, password, targetPath)
	if err != nil {
		return nil, err
	}
	return e.executor.Execute(ctx, args)
}

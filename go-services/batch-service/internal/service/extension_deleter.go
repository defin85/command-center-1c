package service

import (
	"context"
	"time"

	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/pkg/v8errors"
)

// ExtensionDeleter handles deletion of 1C extensions
type ExtensionDeleter struct {
	executor *v8executor.V8Executor
}

// NewExtensionDeleter creates a new ExtensionDeleter
func NewExtensionDeleter(exe1cv8Path string, timeout time.Duration) *ExtensionDeleter {
	executor := v8executor.NewV8Executor(exe1cv8Path, timeout)

	return &ExtensionDeleter{
		executor: executor,
	}
}

// DeleteRequest contains parameters for extension deletion
type DeleteRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
}

// DeleteExtension deletes an extension from a 1C infobase
func (d *ExtensionDeleter) DeleteExtension(ctx context.Context, req DeleteRequest) error {
	// Build command arguments
	args := v8executor.BuildDeleteCommand(
		req.Server,
		req.InfobaseName,
		req.Username,
		req.Password,
		req.ExtensionName,
	)

	// Execute command using V8Executor with async stdout/stderr reading
	result, err := d.executor.Execute(ctx, args)
	if err != nil {
		// Parse V8 error from stdout/stderr
		stdout := ""
		stderr := ""
		if result != nil {
			stdout = result.Stdout
			stderr = result.Stderr
		}
		return v8errors.ParseV8Error(stdout, stderr, err)
	}

	return nil
}

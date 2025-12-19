// go-services/worker/internal/statemachine/installer.go
package statemachine

import (
	"context"
	"time"
)

// ExtensionInstallRequest contains input for direct CLI installation.
type ExtensionInstallRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
	ExtensionPath string
}

// ExtensionInstallResult contains metadata from direct CLI installation.
type ExtensionInstallResult struct {
	Duration time.Duration
	Output   string
}

// ExtensionInstaller executes extension install directly (without batch-service).
type ExtensionInstaller interface {
	InstallExtension(ctx context.Context, req ExtensionInstallRequest) (*ExtensionInstallResult, error)
}

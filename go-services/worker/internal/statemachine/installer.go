// go-services/worker/internal/statemachine/installer.go
package statemachine

import (
	"context"
	"time"
)

// DesignerCredentials contains credentials for direct CLI operations.
type DesignerCredentials struct {
	ServerAddress string
	ServerPort    int
	InfobaseName  string
	Username      string
	Password      string
}

// DesignerCredentialsProvider fetches designer credentials when needed.
type DesignerCredentialsProvider interface {
	Fetch(ctx context.Context, databaseID string) (*DesignerCredentials, error)
}

// ClusterInfo contains RAS connection info for direct operations.
type ClusterInfo struct {
	ClusterID   string
	InfobaseID  string
	RASServer   string
	ClusterUser string
	ClusterPwd  string
}

// ClusterInfoProvider fetches cluster info when needed.
type ClusterInfoProvider interface {
	Fetch(ctx context.Context, databaseID string) (*ClusterInfo, error)
}

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

// go-services/worker/internal/statemachine/installer.go
package statemachine

import "context"

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

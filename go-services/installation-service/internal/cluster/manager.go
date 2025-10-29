package cluster

import "context"

// ClusterManager defines the interface for managing 1C clusters and infobases
type ClusterManager interface {
	// GetClusterInfo retrieves information about the 1C cluster
	GetClusterInfo(ctx context.Context) (*ClusterInfo, error)

	// GetInfobaseList retrieves the list of infobases in the cluster
	// If detailed is true, fetches detailed information for each infobase
	GetInfobaseList(ctx context.Context, detailed bool) ([]InfobaseInfo, error)

	// Close releases any resources held by the manager
	Close() error
}

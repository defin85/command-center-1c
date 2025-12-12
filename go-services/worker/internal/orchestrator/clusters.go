package orchestrator

import (
	"context"
	"fmt"
	"time"
)

const (
	// API paths for cluster endpoints
	pathClusterHealth = "/api/v2/internal/update-cluster-health"
)

// UpdateClusterHealth updates the health status of a cluster.
func (c *Client) UpdateClusterHealth(ctx context.Context, clusterID string, req *HealthUpdateRequest) error {
	if clusterID == "" {
		return fmt.Errorf("cluster ID is required")
	}
	if req == nil {
		return fmt.Errorf("health update request is required")
	}

	path := fmt.Sprintf("%s?cluster_id=%s", pathClusterHealth, clusterID)

	var resp HealthUpdateResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return fmt.Errorf("failed to update cluster health: %w", err)
	}

	return nil
}

// SetClusterHealthy is a convenience method to mark a cluster as healthy.
func (c *Client) SetClusterHealthy(ctx context.Context, clusterID string, responseTimeMs int) error {
	now := time.Now()
	return c.UpdateClusterHealth(ctx, clusterID, &HealthUpdateRequest{
		Healthy:        true,
		LastCheckAt:    &now,
		ResponseTimeMs: responseTimeMs,
	})
}

// SetClusterUnhealthy is a convenience method to mark a cluster as unhealthy.
func (c *Client) SetClusterUnhealthy(ctx context.Context, clusterID string, errorMessage, errorCode string) error {
	now := time.Now()
	return c.UpdateClusterHealth(ctx, clusterID, &HealthUpdateRequest{
		Healthy:      false,
		ErrorMessage: errorMessage,
		ErrorCode:    errorCode,
		LastCheckAt:  &now,
	})
}

// SetClusterHealthWithDetails updates cluster health with detailed information.
func (c *Client) SetClusterHealthWithDetails(ctx context.Context, clusterID string, healthy bool, responseTimeMs int, details map[string]interface{}) error {
	now := time.Now()
	return c.UpdateClusterHealth(ctx, clusterID, &HealthUpdateRequest{
		Healthy:        healthy,
		LastCheckAt:    &now,
		ResponseTimeMs: responseTimeMs,
		Details:        details,
	})
}

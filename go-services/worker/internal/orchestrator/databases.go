package orchestrator

import (
	"context"
	"fmt"
	"time"
)

const (
	// API paths for database endpoints
	pathDatabaseCredentials = "/api/internal/databases/%s/credentials"
	pathDatabaseHealth      = "/api/internal/databases/%s/health"
)

// GetDatabaseCredentials fetches credentials for a database by ID.
func (c *Client) GetDatabaseCredentials(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	if databaseID == "" {
		return nil, fmt.Errorf("database ID is required")
	}

	path := fmt.Sprintf(pathDatabaseCredentials, databaseID)

	var creds DatabaseCredentials
	if err := c.get(ctx, path, &creds); err != nil {
		return nil, fmt.Errorf("failed to get database credentials: %w", err)
	}

	return &creds, nil
}

// UpdateDatabaseHealth updates the health status of a database.
func (c *Client) UpdateDatabaseHealth(ctx context.Context, databaseID string, req *HealthUpdateRequest) error {
	if databaseID == "" {
		return fmt.Errorf("database ID is required")
	}
	if req == nil {
		return fmt.Errorf("health update request is required")
	}

	path := fmt.Sprintf(pathDatabaseHealth, databaseID)

	var resp HealthUpdateResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return fmt.Errorf("failed to update database health: %w", err)
	}

	return nil
}

// SetDatabaseHealthy is a convenience method to mark a database as healthy.
func (c *Client) SetDatabaseHealthy(ctx context.Context, databaseID string, responseTimeMs int) error {
	now := time.Now()
	return c.UpdateDatabaseHealth(ctx, databaseID, &HealthUpdateRequest{
		Healthy:        true,
		LastCheckAt:    &now,
		ResponseTimeMs: responseTimeMs,
	})
}

// SetDatabaseUnhealthy is a convenience method to mark a database as unhealthy.
func (c *Client) SetDatabaseUnhealthy(ctx context.Context, databaseID string, errorMessage, errorCode string) error {
	now := time.Now()
	return c.UpdateDatabaseHealth(ctx, databaseID, &HealthUpdateRequest{
		Healthy:      false,
		ErrorMessage: errorMessage,
		ErrorCode:    errorCode,
		LastCheckAt:  &now,
	})
}

// SetDatabaseHealthWithDetails updates database health with detailed information.
func (c *Client) SetDatabaseHealthWithDetails(ctx context.Context, databaseID string, healthy bool, responseTimeMs int, details map[string]interface{}) error {
	now := time.Now()
	return c.UpdateDatabaseHealth(ctx, databaseID, &HealthUpdateRequest{
		Healthy:        healthy,
		LastCheckAt:    &now,
		ResponseTimeMs: responseTimeMs,
		Details:        details,
	})
}

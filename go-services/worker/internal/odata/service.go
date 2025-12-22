package odata

import (
	"context"
	"fmt"
	"time"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

// Service provides shared OData operations for worker subsystems.
type Service struct {
	pool *ClientPool
}

// NewService creates a shared OData service backed by a client pool.
func NewService(pool *ClientPool) *Service {
	return &Service{pool: pool}
}

// Query executes OData query and returns results.
func (s *Service) Query(ctx context.Context, creds sharedodata.ODataCredentials, entity string, query *sharedodata.QueryParams) ([]map[string]interface{}, error) {
	client := s.getClient(creds)
	if client == nil {
		return nil, fmt.Errorf("odata service not configured")
	}
	req := QueryRequest{
		Entity: entity,
	}
	if query != nil {
		req.Filter = query.Filter
		req.Select = query.Select
		req.OrderBy = query.OrderBy
		req.Top = query.Top
		req.Skip = query.Skip
		req.Expand = query.Expand
	}
	return client.Query(ctx, req)
}

// Create creates a new entity record.
func (s *Service) Create(ctx context.Context, creds sharedodata.ODataCredentials, entity string, data map[string]interface{}) (map[string]interface{}, error) {
	client := s.getClient(creds)
	if client == nil {
		return nil, fmt.Errorf("odata service not configured")
	}
	return client.Create(ctx, entity, data)
}

// Update updates an existing entity record.
func (s *Service) Update(ctx context.Context, creds sharedodata.ODataCredentials, entity, entityID string, data map[string]interface{}) error {
	client := s.getClient(creds)
	if client == nil {
		return fmt.Errorf("odata service not configured")
	}
	return client.Update(ctx, entity, entityID, data)
}

// Delete deletes an entity record.
func (s *Service) Delete(ctx context.Context, creds sharedodata.ODataCredentials, entity, entityID string) error {
	client := s.getClient(creds)
	if client == nil {
		return fmt.Errorf("odata service not configured")
	}
	return client.Delete(ctx, entity, entityID)
}

// ExecuteBatch executes multiple operations in a single batch request.
func (s *Service) ExecuteBatch(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
	client := s.getClient(creds)
	if client == nil {
		return nil, fmt.Errorf("odata service not configured")
	}
	return client.ExecuteBatch(ctx, items)
}

// CacheSize returns number of cached clients.
func (s *Service) CacheSize() int {
	if s == nil || s.pool == nil {
		return 0
	}
	return s.pool.CacheSize()
}

// HealthCheck checks connectivity for the OData endpoint and returns response time in ms.
func (s *Service) HealthCheck(ctx context.Context, creds sharedodata.ODataCredentials) (int64, error) {
	client := s.getClient(creds)
	if client == nil {
		return 0, fmt.Errorf("odata service not configured")
	}
	start := time.Now()
	err := client.HealthCheck(ctx)
	return time.Since(start).Milliseconds(), err
}

func (s *Service) getClient(creds sharedodata.ODataCredentials) *Client {
	if s == nil || s.pool == nil {
		return nil
	}
	return s.pool.Get(creds.BaseURL, creds.Username, creds.Password)
}

// go-services/worker/internal/credentials/mock.go
//go:build integration || test
// +build integration test

package credentials

import (
	"context"
	"fmt"
)

// MockCredentialsClient is a mock implementation for testing
type MockCredentialsClient struct {
	Credentials *DatabaseCredentials
	Error       error
}

// Fetch returns mock credentials
func (m *MockCredentialsClient) Fetch(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	if m.Error != nil {
		return nil, m.Error
	}

	if m.Credentials == nil {
		return nil, fmt.Errorf("no mock credentials configured")
	}

	// Clone credentials with correct database_id
	creds := *m.Credentials
	creds.DatabaseID = databaseID

	return &creds, nil
}

package mocks

import (
	"context"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/stretchr/testify/mock"
)

// MockRASClient is a mock implementation of RAS client for testing
type MockRASClient struct {
	mock.Mock
}

// GetClusters mocks the GetClusters method
func (m *MockRASClient) GetClusters(ctx context.Context) ([]*models.Cluster, error) {
	args := m.Called(ctx)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Cluster), args.Error(1)
}

// GetInfobases mocks the GetInfobases method
func (m *MockRASClient) GetInfobases(ctx context.Context, clusterID string) ([]*models.Infobase, error) {
	args := m.Called(ctx, clusterID)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Infobase), args.Error(1)
}

// GetSessions mocks the GetSessions method
func (m *MockRASClient) GetSessions(ctx context.Context, clusterID, infobaseID string) ([]*models.Session, error) {
	args := m.Called(ctx, clusterID, infobaseID)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Session), args.Error(1)
}

// TerminateSession mocks the TerminateSession method
func (m *MockRASClient) TerminateSession(ctx context.Context, clusterID, sessionID string) error {
	args := m.Called(ctx, clusterID, sessionID)
	return args.Error(0)
}

// Close mocks the Close method
func (m *MockRASClient) Close() error {
	args := m.Called()
	return args.Error(0)
}

package mocks

import (
	"context"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/stretchr/testify/mock"
)

// MockSessionService is a mock implementation of SessionService for testing
type MockSessionService struct {
	mock.Mock
}

// GetSessions mocks the GetSessions method
func (m *MockSessionService) GetSessions(ctx context.Context, clusterID, infobaseID string) ([]*models.Session, error) {
	args := m.Called(ctx, clusterID, infobaseID)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*models.Session), args.Error(1)
}

// TerminateSessions mocks the TerminateSessions method
func (m *MockSessionService) TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error) {
	args := m.Called(ctx, clusterID, infobaseID)
	return args.Int(0), args.Error(1)
}

// GetSessionsCount mocks the GetSessionsCount method
func (m *MockSessionService) GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error) {
	args := m.Called(ctx, clusterID, infobaseID)
	return args.Int(0), args.Error(1)
}

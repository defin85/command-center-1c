package mocks

import (
	"context"
	"github.com/stretchr/testify/mock"
)

// MockEventPublisher is a mock implementation of EventPublisher for testing
type MockEventPublisher struct {
	mock.Mock
}

// Publish mocks the Publish method
func (m *MockEventPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	args := m.Called(ctx, channel, eventType, payload, correlationID)
	return args.Error(0)
}

// Close mocks the Close method
func (m *MockEventPublisher) Close() error {
	args := m.Called()
	return args.Error(0)
}

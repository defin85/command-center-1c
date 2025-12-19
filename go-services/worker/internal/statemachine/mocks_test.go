package statemachine

import (
	"context"
	"sync"
)

// MockPublisher is a mock implementation of EventPublisher for testing
type MockPublisher struct {
	mu             sync.Mutex
	PublishedCalls []PublishCall
	PublishError   error
	Closed         bool
}

type PublishCall struct {
	Channel       string
	EventType     string
	Payload       interface{}
	CorrelationID string
}

func NewMockPublisher() *MockPublisher {
	return &MockPublisher{
		PublishedCalls: make([]PublishCall, 0),
	}
}

func (m *MockPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.PublishError != nil {
		return m.PublishError
	}

	m.PublishedCalls = append(m.PublishedCalls, PublishCall{
		Channel:       channel,
		EventType:     eventType,
		Payload:       payload,
		CorrelationID: correlationID,
	})

	return nil
}

func (m *MockPublisher) Close() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.Closed = true
	return nil
}

func (m *MockPublisher) GetPublishedCount() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return len(m.PublishedCalls)
}

func (m *MockPublisher) GetLastPublished() *PublishCall {
	m.mu.Lock()
	defer m.mu.Unlock()

	if len(m.PublishedCalls) == 0 {
		return nil
	}

	return &m.PublishedCalls[len(m.PublishedCalls)-1]
}

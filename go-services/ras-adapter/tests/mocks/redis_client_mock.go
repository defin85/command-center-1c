package mocks

import (
	"context"
	"time"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/mock"
)

// MockRedisClient is a mock implementation of RedisClient for testing
type MockRedisClient struct {
	mock.Mock
}

// SetNX mocks the SetNX method
func (m *MockRedisClient) SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
	args := m.Called(ctx, key, value, expiration)
	return args.Get(0).(*redis.BoolCmd)
}

// MockBoolCmd is a mock implementation of redis.BoolCmd
type MockBoolCmd struct {
	val bool
	err error
}

// SetVal sets the result value
func (m *MockBoolCmd) SetVal(val bool) {
	m.val = val
}

// SetErr sets the error
func (m *MockBoolCmd) SetErr(err error) {
	m.err = err
}

// Val returns the result value
func (m *MockBoolCmd) Val() bool {
	return m.val
}

// Result returns the result and error
func (m *MockBoolCmd) Result() (bool, error) {
	return m.val, m.err
}

// String returns string representation
func (m *MockBoolCmd) String() string {
	return ""
}

// Args returns the command arguments
func (m *MockBoolCmd) Args() []interface{} {
	return nil
}

// Err returns the error
func (m *MockBoolCmd) Err() error {
	return m.err
}

// Name returns the command name
func (m *MockBoolCmd) Name() string {
	return "SETNX"
}

// FullName returns the full command name
func (m *MockBoolCmd) FullName() string {
	return "SETNX"
}

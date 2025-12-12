package eventhandlers

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/command-center-1c/batch-service/internal/models"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"
)

// MockExtensionInstaller is a mock implementation of ExtensionInstaller
type MockExtensionInstaller struct {
	mock.Mock
}

func (m *MockExtensionInstaller) InstallExtension(ctx context.Context, req *models.InstallExtensionRequest) (*models.InstallExtensionResponse, error) {
	args := m.Called(ctx, req)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*models.InstallExtensionResponse), args.Error(1)
}

// MockEventPublisher is a mock implementation of EventPublisher
type MockEventPublisher struct {
	mock.Mock
}

func (m *MockEventPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	args := m.Called(ctx, channel, eventType, payload, correlationID)
	return args.Error(0)
}

// MockRedisClient is a mock implementation of RedisClient
type MockRedisClient struct {
	mock.Mock
}

func (m *MockRedisClient) SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
	args := m.Called(ctx, key, value, expiration)
	return args.Get(0).(*redis.BoolCmd)
}

func TestNewInstallHandler(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	assert.NotNil(t, handler)
	assert.Equal(t, installer, handler.installer)
	assert.Equal(t, publisher, handler.publisher)
	assert.Equal(t, logger, handler.logger)
}

func TestHandleInstallCommand_Success(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	// Prepare payload
	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		Server:        "localhost:1545",
		InfobaseName:  "test_base",
		Username:      "admin",
		Password:      "password",
		ExtensionPath: "/path/to/extension.cfe",
		ExtensionName: "TestExtension",
	}

	payloadBytes, err := json.Marshal(payload)
	assert.NoError(t, err)

	envelope := &events.Envelope{
		Version:       "1.0",
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "batch.extension.install",
		ServiceName:   "batch-service",
		Payload:       payloadBytes,
	}

	// Mock started event publication
	publisher.On("Publish",
		mock.Anything,
		InstallStartedChannel,
		ExtensionInstallStartedEvent,
		mock.MatchedBy(func(p InstallStartedPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.ExtensionName == "TestExtension"
		}),
		"corr-123",
	).Return(nil)

	// Mock installation success (for async goroutine)
	installer.On("InstallExtension",
		mock.Anything,
		mock.MatchedBy(func(req *models.InstallExtensionRequest) bool {
			return req.Server == "localhost:1545" &&
				req.InfobaseName == "test_base" &&
				req.ExtensionName == "TestExtension"
		}),
	).Return(&models.InstallExtensionResponse{
		Success:         true,
		Message:         "Extension installed successfully",
		DurationSeconds: 2.5,
	}, nil)

	// Mock success event publication (for async goroutine)
	publisher.On("Publish",
		mock.Anything,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		mock.MatchedBy(func(p InstallSuccessPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.ExtensionName == "TestExtension"
		}),
		"corr-123",
	).Return(nil)

	// Call handler
	err = handler.HandleInstallCommand(context.Background(), envelope)

	assert.NoError(t, err)

	// Wait for async execution to complete
	time.Sleep(200 * time.Millisecond)

	publisher.AssertExpectations(t)
	installer.AssertExpectations(t)
}

func TestHandleInstallCommand_InvalidPayload(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	// Invalid JSON payload
	envelope := &events.Envelope{
		Version:       "1.0",
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "batch.extension.install",
		ServiceName:   "batch-service",
		Payload:       []byte("{invalid json}"),
	}

	// Mock error event publication
	publisher.On("Publish",
		mock.Anything,
		InstallFailedChannel,
		ExtensionInstallFailedEvent,
		mock.MatchedBy(func(p ErrorPayload) bool {
			return p.Error != ""
		}),
		"corr-123",
	).Return(nil)

	// Call handler
	err := handler.HandleInstallCommand(context.Background(), envelope)

	assert.Error(t, err)
	publisher.AssertExpectations(t)
}

func TestHandleInstallCommand_MissingRequiredFields(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	testCases := []struct {
		name    string
		payload InstallCommandPayload
	}{
		{
			name: "missing database_id",
			payload: InstallCommandPayload{
				Server:        "localhost:1545",
				InfobaseName:  "test_base",
				ExtensionPath: "/path/to/extension.cfe",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "missing server",
			payload: InstallCommandPayload{
				DatabaseID:    "db-123",
				InfobaseName:  "test_base",
				ExtensionPath: "/path/to/extension.cfe",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "missing infobase_name",
			payload: InstallCommandPayload{
				DatabaseID:    "db-123",
				Server:        "localhost:1545",
				ExtensionPath: "/path/to/extension.cfe",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "missing extension_path",
			payload: InstallCommandPayload{
				DatabaseID:    "db-123",
				Server:        "localhost:1545",
				InfobaseName:  "test_base",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "missing extension_name",
			payload: InstallCommandPayload{
				DatabaseID:    "db-123",
				Server:        "localhost:1545",
				InfobaseName:  "test_base",
				ExtensionPath: "/path/to/extension.cfe",
			},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			payloadBytes, err := json.Marshal(tc.payload)
			assert.NoError(t, err)

			envelope := &events.Envelope{
				Version:       "1.0",
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "batch.extension.install",
				ServiceName:   "batch-service",
				Payload:       payloadBytes,
			}

			// Mock error event publication
			publisher.On("Publish",
				mock.Anything,
				InstallFailedChannel,
				ExtensionInstallFailedEvent,
				mock.MatchedBy(func(p ErrorPayload) bool {
					return p.Error != ""
				}),
				"corr-123",
			).Return(nil).Once()

			// Call handler
			err = handler.HandleInstallCommand(context.Background(), envelope)

			assert.Error(t, err)
			publisher.AssertExpectations(t)
		})
	}
}

func TestExecuteInstallation_Success(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		Server:        "localhost:1545",
		InfobaseName:  "test_base",
		Username:      "admin",
		Password:      "password",
		ExtensionPath: "/path/to/extension.cfe",
		ExtensionName: "TestExtension",
	}

	// Mock installation success
	installer.On("InstallExtension",
		mock.Anything,
		mock.MatchedBy(func(req *models.InstallExtensionRequest) bool {
			return req.Server == "localhost:1545" &&
				req.InfobaseName == "test_base" &&
				req.ExtensionName == "TestExtension"
		}),
	).Return(&models.InstallExtensionResponse{
		Success:         true,
		Message:         "Extension installed successfully",
		DurationSeconds: 2.5,
	}, nil)

	// Mock success event publication
	publisher.On("Publish",
		mock.Anything,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		mock.MatchedBy(func(p InstallSuccessPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.ExtensionName == "TestExtension" &&
				p.DurationSeconds > 0
		}),
		"corr-123",
	).Return(nil)

	// Execute installation
	handler.executeInstallation(context.Background(), "corr-123", payload)

	// Wait for async execution
	time.Sleep(100 * time.Millisecond)

	installer.AssertExpectations(t)
	publisher.AssertExpectations(t)
}

func TestExecuteInstallation_Failure(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		Server:        "localhost:1545",
		InfobaseName:  "test_base",
		Username:      "admin",
		Password:      "password",
		ExtensionPath: "/path/to/extension.cfe",
		ExtensionName: "TestExtension",
	}

	// Mock installation failure
	installer.On("InstallExtension",
		mock.Anything,
		mock.MatchedBy(func(req *models.InstallExtensionRequest) bool {
			return req.Server == "localhost:1545"
		}),
	).Return(nil, errors.New("installation failed"))

	// Mock error event publication
	publisher.On("Publish",
		mock.Anything,
		InstallFailedChannel,
		ExtensionInstallFailedEvent,
		mock.MatchedBy(func(p ErrorPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.Error == "installation failed"
		}),
		"corr-123",
	).Return(nil)

	// Execute installation
	handler.executeInstallation(context.Background(), "corr-123", payload)

	// Wait for async execution
	time.Sleep(100 * time.Millisecond)

	installer.AssertExpectations(t)
	publisher.AssertExpectations(t)
}

func TestPublishStarted(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		InfobaseName:  "test_base",
		ExtensionName: "TestExtension",
	}

	// Mock started event publication
	publisher.On("Publish",
		mock.Anything,
		InstallStartedChannel,
		ExtensionInstallStartedEvent,
		mock.MatchedBy(func(p InstallStartedPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.ExtensionName == "TestExtension" &&
				p.Message != ""
		}),
		"corr-123",
	).Return(nil)

	err := handler.publishStarted(context.Background(), "corr-123", payload)

	assert.NoError(t, err)
	publisher.AssertExpectations(t)
}

func TestPublishSuccess(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		InfobaseName:  "test_base",
		ExtensionName: "TestExtension",
	}

	// Mock success event publication
	publisher.On("Publish",
		mock.Anything,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		mock.MatchedBy(func(p InstallSuccessPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.ExtensionName == "TestExtension" &&
				p.DurationSeconds == 2.5 &&
				p.Message != ""
		}),
		"corr-123",
	).Return(nil)

	err := handler.publishSuccess(context.Background(), "corr-123", payload, 2.5)

	assert.NoError(t, err)
	publisher.AssertExpectations(t)
}

func TestPublishError(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:   "db-123",
		InfobaseName: "test_base",
	}

	testErr := errors.New("installation failed")

	// Mock error event publication
	publisher.On("Publish",
		mock.Anything,
		InstallFailedChannel,
		ExtensionInstallFailedEvent,
		mock.MatchedBy(func(p ErrorPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.InfobaseName == "test_base" &&
				p.Error == "installation failed" &&
				p.Message != ""
		}),
		"corr-123",
	).Return(nil)

	err := handler.publishError(context.Background(), "corr-123", payload, testErr)

	assert.Error(t, err)
	assert.Equal(t, testErr, err)
	publisher.AssertExpectations(t)
}

func TestPublishError_PublishFails(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:   "db-123",
		InfobaseName: "test_base",
	}

	testErr := errors.New("installation failed")
	publishErr := errors.New("publish failed")

	// Mock error event publication failure
	publisher.On("Publish",
		mock.Anything,
		InstallFailedChannel,
		ExtensionInstallFailedEvent,
		mock.Anything,
		"corr-123",
	).Return(publishErr)

	err := handler.publishError(context.Background(), "corr-123", payload, testErr)

	// Should return original error, not publish error
	assert.Error(t, err)
	assert.Equal(t, testErr, err)
	publisher.AssertExpectations(t)
}

func TestValidateExtensionPath(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	testCases := []struct {
		name          string
		extensionPath string
		shouldFail    bool
		errorContains string
	}{
		{
			name:          "valid absolute path with .cfe extension",
			extensionPath: "/path/to/extension.cfe",
			shouldFail:    false,
		},
		{
			name:          "valid Windows absolute path with .cfe extension",
			extensionPath: "C:\\path\\to\\extension.cfe",
			shouldFail:    false,
		},
		{
			name:          "valid path with uppercase .CFE extension",
			extensionPath: "/path/to/extension.CFE",
			shouldFail:    false,
		},
		{
			name:          "relative path should fail",
			extensionPath: "relative/path/extension.cfe",
			shouldFail:    true,
			errorContains: "must be an absolute path",
		},
		{
			name:          "path without .cfe extension should fail",
			extensionPath: "/path/to/extension.txt",
			shouldFail:    true,
			errorContains: "must have .cfe extension",
		},
		{
			name:          "path with .cf extension (not .cfe) should fail",
			extensionPath: "/path/to/extension.cf",
			shouldFail:    true,
			errorContains: "must have .cfe extension",
		},
		{
			name:          "path traversal attempt with ../ should fail",
			extensionPath: "/path/to/../../etc/passwd.cfe",
			shouldFail:    true,
			errorContains: "invalid characters or path traversal",
		},
		{
			name:          "path traversal with parent directory should fail",
			extensionPath: "/path/../etc/passwd.cfe",
			shouldFail:    true,
			errorContains: "invalid characters or path traversal",
		},
		{
			name:          "empty path should fail",
			extensionPath: "",
			shouldFail:    true,
			errorContains: "must have .cfe extension",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := handler.validateExtensionPath(tc.extensionPath)

			if tc.shouldFail {
				assert.Error(t, err)
				if tc.errorContains != "" {
					assert.Contains(t, err.Error(), tc.errorContains)
				}
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestHandleInstallCommand_InvalidExtensionPath(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, nil, nil, logger)

	testCases := []struct {
		name          string
		extensionPath string
	}{
		{
			name:          "relative path",
			extensionPath: "relative/path/extension.cfe",
		},
		{
			name:          "path traversal attempt",
			extensionPath: "/path/to/../../etc/passwd.cfe",
		},
		{
			name:          "invalid extension",
			extensionPath: "/path/to/extension.txt",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			payload := InstallCommandPayload{
				DatabaseID:    "db-123",
				Server:        "localhost:1545",
				InfobaseName:  "test_base",
				Username:      "admin",
				Password:      "password",
				ExtensionPath: tc.extensionPath,
				ExtensionName: "TestExtension",
			}

			payloadBytes, err := json.Marshal(payload)
			assert.NoError(t, err)

			envelope := &events.Envelope{
				Version:       "1.0",
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "batch.extension.install",
				ServiceName:   "batch-service",
				Payload:       payloadBytes,
			}

			// Mock error event publication
			publisher.On("Publish",
				mock.Anything,
				InstallFailedChannel,
				ExtensionInstallFailedEvent,
				mock.MatchedBy(func(p ErrorPayload) bool {
					return p.DatabaseID == "db-123" &&
						p.InfobaseName == "test_base" &&
						p.Error != ""
				}),
				"corr-123",
			).Return(nil).Once()

			// Call handler
			err = handler.HandleInstallCommand(context.Background(), envelope)

			// Should return error due to invalid extension path
			assert.Error(t, err)
			publisher.AssertExpectations(t)
		})
	}
}

// ============================================================
// IDEMPOTENCY TESTS
// ============================================================

// TestInstallHandler_Idempotent tests duplicate install command is skipped
func TestInstallHandler_Idempotent(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	mockRedis := &MockRedisClient{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, mockRedis, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		Server:        "localhost:1545",
		InfobaseName:  "test_base",
		Username:      "admin",
		Password:      "password",
		ExtensionPath: "/path/to/extension.cfe",
		ExtensionName: "TestExtension",
	}

	payloadBytes, err := json.Marshal(payload)
	assert.NoError(t, err)

	envelope := &events.Envelope{
		Version:       "1.0",
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "batch.extension.install",
		ServiceName:   "batch-service",
		Payload:       payloadBytes,
	}

	// First call: SetNX returns true (key didn't exist)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:corr-123:install",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(true, nil)).Once()

	// Mock started event publication (first call)
	publisher.On("Publish",
		mock.Anything,
		InstallStartedChannel,
		ExtensionInstallStartedEvent,
		mock.MatchedBy(func(p InstallStartedPayload) bool {
			return p.DatabaseID == "db-123" && p.ExtensionName == "TestExtension"
		}),
		"corr-123",
	).Return(nil).Once()

	// Mock installation success (for async goroutine)
	installer.On("InstallExtension",
		mock.Anything,
		mock.MatchedBy(func(req *models.InstallExtensionRequest) bool {
			return req.Server == "localhost:1545" && req.ExtensionName == "TestExtension"
		}),
	).Return(&models.InstallExtensionResponse{
		Success:         true,
		Message:         "Extension installed successfully",
		DurationSeconds: 2.5,
	}, nil).Once()

	// Mock success event publication (for async goroutine)
	publisher.On("Publish",
		mock.Anything,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		mock.MatchedBy(func(p InstallSuccessPayload) bool {
			return p.DatabaseID == "db-123" && p.ExtensionName == "TestExtension"
		}),
		"corr-123",
	).Return(nil).Once()

	// First call should execute
	err = handler.HandleInstallCommand(context.Background(), envelope)
	assert.NoError(t, err)

	// Wait for async execution
	time.Sleep(200 * time.Millisecond)

	installer.AssertExpectations(t)

	// Second call: SetNX returns false (key exists)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:corr-123:install",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, nil)).Once()

	// Publisher should still be called with success event (idempotent response)
	publisher.On("Publish",
		mock.Anything,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		mock.MatchedBy(func(p InstallSuccessPayload) bool {
			return p.DatabaseID == "db-123" &&
				p.ExtensionName == "TestExtension" &&
				p.DurationSeconds == 0 // 0 duration means operation was already completed
		}),
		"corr-123",
	).Return(nil).Once()

	// Second call should skip operation but publish success
	err = handler.HandleInstallCommand(context.Background(), envelope)
	assert.NoError(t, err)

	// Service should NOT be called second time
	installer.AssertExpectations(t)
	publisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// TestInstallHandler_RedisError_FailOpen tests fail-open behavior when Redis is unavailable
func TestInstallHandler_RedisError_FailOpen(t *testing.T) {
	installer := &MockExtensionInstaller{}
	publisher := &MockEventPublisher{}
	mockRedis := &MockRedisClient{}
	logger := zap.NewNop()

	handler := NewInstallHandler(installer, publisher, mockRedis, nil, logger)

	payload := InstallCommandPayload{
		DatabaseID:    "db-123",
		Server:        "localhost:1545",
		InfobaseName:  "test_base",
		Username:      "admin",
		Password:      "password",
		ExtensionPath: "/path/to/extension.cfe",
		ExtensionName: "TestExtension",
	}

	payloadBytes, err := json.Marshal(payload)
	assert.NoError(t, err)

	envelope := &events.Envelope{
		Version:       "1.0",
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "batch.extension.install",
		ServiceName:   "batch-service",
		Payload:       payloadBytes,
	}

	// SetNX returns error (Redis unavailable)
	redisErr := errors.New("Redis connection failed")
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:corr-123:install",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, redisErr)).Once()

	// Operation should continue despite Redis error (fail-open)

	// Mock started event publication
	publisher.On("Publish",
		mock.Anything,
		InstallStartedChannel,
		ExtensionInstallStartedEvent,
		mock.MatchedBy(func(p InstallStartedPayload) bool {
			return p.DatabaseID == "db-123" && p.ExtensionName == "TestExtension"
		}),
		"corr-123",
	).Return(nil).Once()

	// Mock installation success (for async goroutine)
	installer.On("InstallExtension",
		mock.Anything,
		mock.MatchedBy(func(req *models.InstallExtensionRequest) bool {
			return req.Server == "localhost:1545" && req.ExtensionName == "TestExtension"
		}),
	).Return(&models.InstallExtensionResponse{
		Success:         true,
		Message:         "Extension installed successfully",
		DurationSeconds: 2.5,
	}, nil).Once()

	// Mock success event publication (for async goroutine)
	publisher.On("Publish",
		mock.Anything,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		mock.MatchedBy(func(p InstallSuccessPayload) bool {
			return p.DatabaseID == "db-123" && p.ExtensionName == "TestExtension"
		}),
		"corr-123",
	).Return(nil).Once()

	// Call should execute operation despite Redis error
	err = handler.HandleInstallCommand(context.Background(), envelope)
	assert.NoError(t, err)

	// Wait for async execution
	time.Sleep(200 * time.Millisecond)

	installer.AssertExpectations(t)
	publisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

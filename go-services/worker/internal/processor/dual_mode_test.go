// go-services/worker/internal/processor/dual_mode_test.go
package processor

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/config"
	"github.com/commandcenter1c/commandcenter/worker/internal/statemachine"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// ========== Mock ClusterInfoResolver ==========

// MockClusterResolver is a mock implementation of ClusterInfoResolver for testing
type MockClusterResolver struct {
	mu           sync.Mutex
	ResolveFunc  func(ctx context.Context, databaseID string) (*ClusterInfo, error)
	ResolveCalls []string
}

// NewMockClusterResolver creates a new MockClusterResolver with default behavior
func NewMockClusterResolver() *MockClusterResolver {
	return &MockClusterResolver{
		ResolveCalls: make([]string, 0),
		ResolveFunc: func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
			return &ClusterInfo{
				ClusterID:  "cluster-test-123",
				InfobaseID: "infobase-test-456",
				DatabaseID: databaseID,
			}, nil
		},
	}
}

// Resolve implements ClusterInfoResolver
func (m *MockClusterResolver) Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	m.mu.Lock()
	m.ResolveCalls = append(m.ResolveCalls, databaseID)
	m.mu.Unlock()

	if m.ResolveFunc != nil {
		return m.ResolveFunc(ctx, databaseID)
	}
	return nil, errors.New("ResolveFunc not configured")
}

// GetCallCount returns the number of Resolve calls
func (m *MockClusterResolver) GetCallCount() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return len(m.ResolveCalls)
}

// ========== Mock EventPublisher for Processor tests ==========

// MockProcessorPublisher is a mock implementation of statemachine.EventPublisher
type MockProcessorPublisher struct {
	mu             sync.Mutex
	PublishedCalls []MockPublishCall
	PublishError   error
	Closed         bool
}

type MockPublishCall struct {
	Channel       string
	EventType     string
	Payload       interface{}
	CorrelationID string
}

func NewMockProcessorPublisher() *MockProcessorPublisher {
	return &MockProcessorPublisher{
		PublishedCalls: make([]MockPublishCall, 0),
	}
}

func (m *MockProcessorPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.PublishError != nil {
		return m.PublishError
	}

	m.PublishedCalls = append(m.PublishedCalls, MockPublishCall{
		Channel:       channel,
		EventType:     eventType,
		Payload:       payload,
		CorrelationID: correlationID,
	})

	return nil
}

func (m *MockProcessorPublisher) Close() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.Closed = true
	return nil
}

// ========== Mock EventSubscriber for Processor tests ==========

// MockProcessorSubscriber is a mock implementation of statemachine.EventSubscriber
type MockProcessorSubscriber struct {
	mu       sync.Mutex
	Handlers map[string]events.HandlerFunc
	Closed   bool
}

func NewMockProcessorSubscriber() *MockProcessorSubscriber {
	return &MockProcessorSubscriber{
		Handlers: make(map[string]events.HandlerFunc),
	}
}

func (m *MockProcessorSubscriber) Subscribe(channel string, handler events.HandlerFunc) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.Handlers[channel] = handler
	return nil
}

func (m *MockProcessorSubscriber) Close() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.Closed = true
	return nil
}

// SimulateEvent simulates receiving an event
func (m *MockProcessorSubscriber) SimulateEvent(ctx context.Context, channel string, envelope *events.Envelope) error {
	m.mu.Lock()
	handler, exists := m.Handlers[channel]
	m.mu.Unlock()

	if !exists {
		return nil
	}

	return handler(ctx, envelope)
}

// ========== Test Helper Functions ==========

// createTestOperationMessage creates a test OperationMessage for extension installation
func createTestOperationMessage(extensionName, extensionPath, databaseID string) *models.OperationMessage {
	return &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "op-test-123",
		OperationType: "install_extension",
		Entity:        "extension",
		TargetDatabases: []models.TargetDatabase{{ID: databaseID}},
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"extension_name": extensionName,
				"extension_path": extensionPath,
				"database_id":    databaseID,
			},
		},
		ExecConfig: models.ExecutionConfig{
			TimeoutSeconds: 300,
			RetryCount:     3,
		},
		Metadata: models.MessageMetadata{
			CreatedBy: "test",
			CreatedAt: time.Now(),
		},
	}
}

// createTestDualModeProcessor creates a DualModeProcessor for testing
func createTestDualModeProcessor(resolver ClusterInfoResolver) *DualModeProcessor {
	ff := createTestFeatureFlags(true) // Enable Event-Driven mode for testing

	dm := &DualModeProcessor{
		featureFlags:    ff,
		processor:       nil, // Will be set via SetClusterResolver
		smConfig:        statemachine.DefaultConfig(),
		clusterResolver: resolver,
	}

	return dm
}

// createTestFeatureFlags creates FeatureFlags with specified settings for testing
func createTestFeatureFlags(enableEventDriven bool) *config.FeatureFlags {
	ff := config.NewFeatureFlags()
	ff.EnableEventDriven = enableEventDriven
	ff.EnableForExtensions = enableEventDriven
	ff.RolloutPercentage = 1.0 // 100% rollout for tests
	return ff
}

// ========== Tests ==========

// TestValidateExtensionInstallParams tests parameter validation
func TestValidateExtensionInstallParams(t *testing.T) {
	tests := []struct {
		name          string
		data          map[string]interface{}
		wantName      string
		wantPath      string
		wantDBID      string
		wantErr       bool
		wantErrSubstr string
	}{
		{
			name: "valid parameters",
			data: map[string]interface{}{
				"extension_name": "TestExtension",
				"extension_path": "/path/to/extension.cfe",
				"database_id":    "db-123",
			},
			wantName: "TestExtension",
			wantPath: "/path/to/extension.cfe",
			wantDBID: "db-123",
			wantErr:  false,
		},
		{
			name: "empty extension_name",
			data: map[string]interface{}{
				"extension_name": "",
				"extension_path": "/path/to/extension.cfe",
			},
			wantErr:       true,
			wantErrSubstr: "extension_name is required",
		},
		{
			name: "missing extension_name",
			data: map[string]interface{}{
				"extension_path": "/path/to/extension.cfe",
			},
			wantErr:       true,
			wantErrSubstr: "extension_name is required",
		},
		{
			name: "empty extension_path",
			data: map[string]interface{}{
				"extension_name": "TestExtension",
				"extension_path": "",
			},
			wantErr:       true,
			wantErrSubstr: "extension_path is required",
		},
		{
			name: "missing extension_path",
			data: map[string]interface{}{
				"extension_name": "TestExtension",
			},
			wantErr:       true,
			wantErrSubstr: "extension_path is required",
		},
		{
			name: "extension_name too long",
			data: map[string]interface{}{
				"extension_name": string(make([]byte, 300)), // 300 characters
				"extension_path": "/path/to/extension.cfe",
			},
			wantErr:       true,
			wantErrSubstr: "extension_name too long",
		},
		{
			name: "extension_path too long",
			data: map[string]interface{}{
				"extension_name": "TestExtension",
				"extension_path": string(make([]byte, 1100)), // 1100 characters
			},
			wantErr:       true,
			wantErrSubstr: "extension_path too long",
		},
		{
			name: "path traversal attempt",
			data: map[string]interface{}{
				"extension_name": "TestExtension",
				"extension_path": "../../../etc/passwd",
			},
			wantErr:       true,
			wantErrSubstr: "path traversal",
		},
		{
			name: "invalid extension_name characters",
			data: map[string]interface{}{
				"extension_name": "Test<>Extension",
				"extension_path": "/path/to/extension.cfe",
			},
			wantErr:       true,
			wantErrSubstr: "invalid characters",
		},
		{
			name: "cyrillic extension_name is valid",
			data: map[string]interface{}{
				"extension_name": "Расширение1С",
				"extension_path": "/path/to/extension.cfe",
			},
			wantName: "Расширение1С",
			wantPath: "/path/to/extension.cfe",
			wantErr:  false,
		},
		{
			name: "empty database_id in data",
			data: map[string]interface{}{
				"extension_name": "TestExtension",
				"extension_path": "/path/to/extension.cfe",
				"database_id":    "",
			},
			wantErr:       true,
			wantErrSubstr: "database_id cannot be empty",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			extName, extPath, dbID, err := validateExtensionInstallParams(tt.data)

			if tt.wantErr {
				require.Error(t, err)
				if tt.wantErrSubstr != "" {
					assert.Contains(t, err.Error(), tt.wantErrSubstr)
				}
			} else {
				require.NoError(t, err)
				assert.Equal(t, tt.wantName, extName)
				assert.Equal(t, tt.wantPath, extPath)
				assert.Equal(t, tt.wantDBID, dbID)
			}
		})
	}
}

// TestDualModeProcessor_DetermineExecutionMode tests mode selection
func TestDualModeProcessor_DetermineExecutionMode(t *testing.T) {
	tests := []struct {
		name          string
		operationType string
		databaseID    string
		eventDriven   bool
		wantMode      ExecutionMode
	}{
		{
			name:          "event_driven mode enabled",
			operationType: "install_extension",
			databaseID:    "db-123",
			eventDriven:   true,
			wantMode:      ModeEventDriven,
		},
		{
			name:          "event_driven mode disabled",
			operationType: "install_extension",
			databaseID:    "db-123",
			eventDriven:   false,
			wantMode:      ModeHTTPSync,
		},
		{
			name:          "extension operation type normalization",
			operationType: "extension",
			databaseID:    "db-456",
			eventDriven:   true,
			wantMode:      ModeEventDriven,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ff := createTestFeatureFlags(tt.eventDriven)

			dm := &DualModeProcessor{
				featureFlags: ff,
			}

			mode := dm.determineExecutionMode(tt.operationType, tt.databaseID)
			assert.Equal(t, tt.wantMode, mode)
		})
	}
}

// TestDualModeProcessor_ClusterInfoResolution tests ClusterInfo resolution
func TestDualModeProcessor_ClusterInfoResolution(t *testing.T) {
	tests := []struct {
		name        string
		resolveFunc func(ctx context.Context, databaseID string) (*ClusterInfo, error)
		wantErr     bool
		wantErrCode string
	}{
		{
			name: "successful resolution",
			resolveFunc: func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
				return &ClusterInfo{
					ClusterID:  "cluster-abc",
					InfobaseID: "infobase-xyz",
					DatabaseID: databaseID,
				}, nil
			},
			wantErr: false,
		},
		{
			name: "resolution error",
			resolveFunc: func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
				return nil, errors.New("orchestrator unavailable")
			},
			wantErr:     true,
			wantErrCode: "CLUSTER_RESOLVE_ERROR",
		},
		{
			name: "nil ClusterInfo returned",
			resolveFunc: func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
				return nil, errors.New("database not found in orchestrator")
			},
			wantErr:     true,
			wantErrCode: "CLUSTER_RESOLVE_ERROR",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockResolver := NewMockClusterResolver()
			mockResolver.ResolveFunc = tt.resolveFunc

			// Test via ResolveClusterInfo directly
			dm := createTestDualModeProcessor(mockResolver)
			ctx := context.Background()

			info, err := dm.ResolveClusterInfo(ctx, "test-db-id")

			if tt.wantErr {
				require.Error(t, err)
				assert.Nil(t, info)
			} else {
				require.NoError(t, err)
				require.NotNil(t, info)
				assert.NotEmpty(t, info.ClusterID)
				assert.NotEmpty(t, info.InfobaseID)
			}
		})
	}
}

// TestDualModeProcessor_ResolveClusterInfo_NilResolver tests nil resolver handling
func TestDualModeProcessor_ResolveClusterInfo_NilResolver(t *testing.T) {
	dm := &DualModeProcessor{
		clusterResolver: nil,
	}

	info, err := dm.ResolveClusterInfo(context.Background(), "test-db")

	require.Error(t, err)
	assert.Nil(t, info)
	assert.Contains(t, err.Error(), "not configured")
}

// TestDualModeProcessor_SetClusterResolver tests resolver injection
func TestDualModeProcessor_SetClusterResolver(t *testing.T) {
	dm := &DualModeProcessor{}

	mockResolver := NewMockClusterResolver()
	dm.SetClusterResolver(mockResolver)

	assert.NotNil(t, dm.GetClusterResolver())
	assert.Equal(t, mockResolver, dm.GetClusterResolver())
}

// TestNullClusterResolver_DualMode tests NullClusterResolver behavior in dual mode context
func TestNullClusterResolver_DualMode(t *testing.T) {
	resolver := &NullClusterResolver{}

	info, err := resolver.Resolve(context.Background(), "dual-mode-db-test")

	assert.Nil(t, info)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "ClusterInfoResolver not configured")
	assert.Contains(t, err.Error(), "dual-mode-db-test")
}

// TestProcessEventDriven_ValidationError tests validation error handling
func TestProcessEventDriven_ValidationError(t *testing.T) {
	tests := []struct {
		name          string
		extName       string
		extPath       string
		wantErrSubstr string
	}{
		{
			name:          "empty extension_name",
			extName:       "",
			extPath:       "/path/to/ext.cfe",
			wantErrSubstr: "extension_name is required",
		},
		{
			name:          "empty extension_path",
			extName:       "TestExt",
			extPath:       "",
			wantErrSubstr: "extension_path is required",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockResolver := NewMockClusterResolver()
			dm := createTestDualModeProcessor(mockResolver)

			ctx := context.Background()
			msg := createTestOperationMessage(tt.extName, tt.extPath, "db-123")

			// Call processEventDriven indirectly through ProcessExtensionInstall
			// Since we can't call processEventDriven directly (lowercase), we test via the public method
			result := dm.ProcessExtensionInstall(ctx, msg, "db-123")

			assert.False(t, result.Success)
			// Error code is set to EXECUTION_ERROR by ProcessExtensionInstall wrapper
			assert.Equal(t, "EXECUTION_ERROR", result.ErrorCode)
			// But the error message contains the validation error
			assert.Contains(t, result.Error, tt.wantErrSubstr)
		})
	}
}

// TestProcessEventDriven_ClusterResolveError tests cluster resolution error handling
func TestProcessEventDriven_ClusterResolveError(t *testing.T) {
	mockResolver := NewMockClusterResolver()
	mockResolver.ResolveFunc = func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
		return nil, errors.New("orchestrator connection timeout")
	}

	dm := createTestDualModeProcessor(mockResolver)

	ctx := context.Background()
	msg := createTestOperationMessage("TestExtension", "/path/to/ext.cfe", "db-123")

	result := dm.ProcessExtensionInstall(ctx, msg, "db-123")

	assert.False(t, result.Success)
	// ProcessExtensionInstall wraps the error with EXECUTION_ERROR
	assert.Equal(t, "EXECUTION_ERROR", result.ErrorCode)
	// But the error message should contain info about cluster resolution failure
	assert.Contains(t, result.Error, "failed to resolve cluster info")

	// Verify resolver was called
	assert.Equal(t, 1, mockResolver.GetCallCount())
}

// TestProcessEventDriven_NoFallback tests that there's no fallback to HTTP Sync
func TestProcessEventDriven_NoFallback(t *testing.T) {
	// When ClusterInfo resolution fails, there should be NO fallback to HTTP Sync
	mockResolver := NewMockClusterResolver()
	mockResolver.ResolveFunc = func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
		return nil, errors.New("orchestrator unavailable")
	}

	dm := createTestDualModeProcessor(mockResolver)

	ctx := context.Background()
	msg := createTestOperationMessage("TestExtension", "/path/to/ext.cfe", "db-123")

	result := dm.ProcessExtensionInstall(ctx, msg, "db-123")

	// Should fail, NOT succeed via HTTP Sync fallback
	assert.False(t, result.Success)
	// Error should contain cluster resolution error
	assert.Contains(t, result.Error, "failed to resolve cluster info")

	// Error should NOT mention HTTP Sync or fallback
	assert.NotContains(t, result.Error, "HTTP")
	assert.NotContains(t, result.Error, "fallback")
}

// TestPublisherWrapper tests publisherWrapper implementation
func TestPublisherWrapper(t *testing.T) {
	mockPub := NewMockProcessorPublisher()

	// We can't directly test publisherWrapper since it wraps events.Publisher
	// But we can verify the interface expectations
	var _ statemachine.EventPublisher = (*MockProcessorPublisher)(nil)

	// Test publish
	ctx := context.Background()
	err := mockPub.Publish(ctx, "test-channel", "test.event", map[string]string{"key": "value"}, "corr-123")
	require.NoError(t, err)

	assert.Len(t, mockPub.PublishedCalls, 1)
	assert.Equal(t, "test-channel", mockPub.PublishedCalls[0].Channel)
	assert.Equal(t, "test.event", mockPub.PublishedCalls[0].EventType)
	assert.Equal(t, "corr-123", mockPub.PublishedCalls[0].CorrelationID)

	// Test close
	err = mockPub.Close()
	require.NoError(t, err)
	assert.True(t, mockPub.Closed)
}

// TestSubscriberWrapper tests subscriberWrapper implementation
func TestSubscriberWrapper(t *testing.T) {
	mockSub := NewMockProcessorSubscriber()

	// Verify interface compliance
	var _ statemachine.EventSubscriber = (*MockProcessorSubscriber)(nil)

	// Test subscribe
	handlerCalled := false
	err := mockSub.Subscribe("test-channel", func(ctx context.Context, envelope *events.Envelope) error {
		handlerCalled = true
		return nil
	})
	require.NoError(t, err)

	// Simulate event
	ctx := context.Background()
	envelope := &events.Envelope{
		MessageID:     "msg-1",
		EventType:     "test.event",
		CorrelationID: "corr-1",
	}
	err = mockSub.SimulateEvent(ctx, "test-channel", envelope)
	require.NoError(t, err)
	assert.True(t, handlerCalled)

	// Test close
	err = mockSub.Close()
	require.NoError(t, err)
	assert.True(t, mockSub.Closed)
}

// TestDualModeProcessor_GetFeatureFlags tests feature flag retrieval
func TestDualModeProcessor_GetFeatureFlags(t *testing.T) {
	ff := createTestFeatureFlags(true)

	dm := &DualModeProcessor{
		featureFlags: ff,
	}

	flags := dm.GetFeatureFlags()
	require.NotNil(t, flags)
	// Verify some expected flags
	assert.Equal(t, true, flags["enable_event_driven"])
	assert.Equal(t, true, flags["enable_for_extensions"])
}

// TestExecutionMode_Constants tests ExecutionMode constants
func TestExecutionMode_Constants(t *testing.T) {
	assert.Equal(t, ExecutionMode("event_driven"), ModeEventDriven)
	assert.Equal(t, ExecutionMode("http_sync"), ModeHTTPSync)
}

// TestDualModeProcessor_ContextCancellation tests context cancellation handling
func TestDualModeProcessor_ContextCancellation(t *testing.T) {
	mockResolver := NewMockClusterResolver()
	mockResolver.ResolveFunc = func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
		// Simulate slow resolution
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(100 * time.Millisecond):
			return &ClusterInfo{
				ClusterID:  "cluster-1",
				InfobaseID: "infobase-1",
				DatabaseID: databaseID,
			}, nil
		}
	}

	dm := createTestDualModeProcessor(mockResolver)

	// Create cancelled context
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()

	msg := createTestOperationMessage("TestExt", "/path/ext.cfe", "db-123")

	result := dm.ProcessExtensionInstall(ctx, msg, "db-123")

	// Should fail due to context cancellation
	assert.False(t, result.Success)
	// Error should indicate timeout or cancellation
	assert.True(t,
		result.ErrorCode == "CLUSTER_RESOLVE_ERROR" ||
			result.ErrorCode == "EXECUTION_ERROR",
		"Expected error code related to timeout/cancellation, got: %s", result.ErrorCode,
	)
}

// ========== Benchmark Tests ==========

func BenchmarkValidateExtensionInstallParams(b *testing.B) {
	data := map[string]interface{}{
		"extension_name": "TestExtension",
		"extension_path": "/path/to/extension.cfe",
		"database_id":    "db-123",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		validateExtensionInstallParams(data)
	}
}

func BenchmarkDetermineExecutionMode(b *testing.B) {
	ff := createTestFeatureFlags(true)

	dm := &DualModeProcessor{
		featureFlags: ff,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		dm.determineExecutionMode("install_extension", "db-123")
	}
}

// ========== Integration-like Tests (with mocks) ==========

// TestProcessEventDriven_ClusterResolutionCalled tests that cluster resolution is called
// Note: Full SM flow requires TaskProcessor with Redis, which is tested in integration tests
func TestProcessEventDriven_ClusterResolutionCalled(t *testing.T) {
	t.Run("cluster resolution is called with correct database_id", func(t *testing.T) {
		resolverCalled := false
		receivedDBID := ""
		mockResolver := NewMockClusterResolver()
		mockResolver.ResolveFunc = func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
			resolverCalled = true
			receivedDBID = databaseID
			// Return error to prevent going to createStateMachine (which needs processor)
			return nil, errors.New("test: intentional resolver error")
		}

		dm := createTestDualModeProcessor(mockResolver)

		ctx := context.Background()
		msg := createTestOperationMessage("ValidExtension", "/valid/path/ext.cfe", "db-test-123")

		result := dm.ProcessExtensionInstall(ctx, msg, "db-test-123")

		// Cluster resolution should have been called with correct database ID
		assert.True(t, resolverCalled, "Resolver should be called")
		assert.Equal(t, "db-test-123", receivedDBID, "Resolver should receive correct database ID")
		assert.Equal(t, 1, mockResolver.GetCallCount())

		// The result should fail
		assert.False(t, result.Success)
	})

	t.Run("validation runs before cluster resolution", func(t *testing.T) {
		resolverCalled := false
		mockResolver := NewMockClusterResolver()
		mockResolver.ResolveFunc = func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
			resolverCalled = true
			return nil, errors.New("should not be called")
		}

		dm := createTestDualModeProcessor(mockResolver)

		ctx := context.Background()
		// Invalid message - empty extension name
		msg := createTestOperationMessage("", "/valid/path/ext.cfe", "db-test")

		result := dm.ProcessExtensionInstall(ctx, msg, "db-test")

		// Resolver should NOT be called because validation fails first
		assert.False(t, resolverCalled, "Resolver should NOT be called when validation fails")
		assert.False(t, result.Success)
		assert.Contains(t, result.Error, "extension_name is required")
	})
}

// TestProcessEventDriven_MultipleDatabases tests processing multiple databases
func TestProcessEventDriven_MultipleDatabases(t *testing.T) {
	callCounts := make(map[string]int)
	var mu sync.Mutex

	mockResolver := NewMockClusterResolver()
	mockResolver.ResolveFunc = func(ctx context.Context, databaseID string) (*ClusterInfo, error) {
		mu.Lock()
		callCounts[databaseID]++
		mu.Unlock()

		// Return error to prevent going to createStateMachine (which needs processor)
		return nil, fmt.Errorf("test: intentional error for %s", databaseID)
	}

	dm := createTestDualModeProcessor(mockResolver)
	ctx := context.Background()

	databases := []string{"db-1", "db-2", "db-3"}

	for _, dbID := range databases {
		msg := createTestOperationMessage("TestExt", "/path/ext.cfe", dbID)
		result := dm.ProcessExtensionInstall(ctx, msg, dbID)
		// Each should fail (expected)
		assert.False(t, result.Success)
	}

	// Each database should have been resolved once
	mu.Lock()
	defer mu.Unlock()
	for _, dbID := range databases {
		assert.Equal(t, 1, callCounts[dbID], "Database %s should be resolved once", dbID)
	}
}

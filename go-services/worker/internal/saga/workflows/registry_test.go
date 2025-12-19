package workflows

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap/zaptest"

	"github.com/commandcenter1c/commandcenter/worker/internal/saga"
)

// mockOrchestrator is a test double for saga.SagaOrchestrator.
type mockOrchestrator struct {
	registered map[string]*saga.SagaDefinition
}

func newMockOrchestrator() *mockOrchestrator {
	return &mockOrchestrator{
		registered: make(map[string]*saga.SagaDefinition),
	}
}

func (m *mockOrchestrator) RegisterSaga(def *saga.SagaDefinition) error {
	if err := def.Validate(); err != nil {
		return err
	}
	m.registered[def.ID] = def
	return nil
}

func (m *mockOrchestrator) GetSaga(sagaID string) (*saga.SagaDefinition, error) {
	if def, ok := m.registered[sagaID]; ok {
		return def, nil
	}
	return nil, saga.ErrSagaNotFound
}

func (m *mockOrchestrator) Execute(ctx context.Context, sagaID string, input map[string]interface{}) (*saga.SagaResult, error) {
	return &saga.SagaResult{}, nil
}

func (m *mockOrchestrator) ExecuteWithCorrelation(ctx context.Context, sagaID string, input map[string]interface{}, correlationID string) (*saga.SagaResult, error) {
	return &saga.SagaResult{}, nil
}

func (m *mockOrchestrator) Resume(ctx context.Context, executionID string) (*saga.SagaResult, error) {
	return &saga.SagaResult{}, nil
}

func (m *mockOrchestrator) GetStatus(ctx context.Context, executionID string) (*saga.SagaState, error) {
	return nil, nil
}

func (m *mockOrchestrator) Cancel(ctx context.Context, executionID string) error {
	return nil
}

func (m *mockOrchestrator) Close() error {
	return nil
}

// TestListRegisteredWorkflows verifies that all expected workflows are listed.
func TestListRegisteredWorkflows(t *testing.T) {
	workflows := ListRegisteredWorkflows()

	assert.Len(t, workflows, 10, "Should list all 10 workflows")
	assert.Contains(t, workflows, WorkflowExtensionInstall)
	assert.Contains(t, workflows, WorkflowExtensionRemove)
	assert.Contains(t, workflows, WorkflowLockScheduledJobs)
	assert.Contains(t, workflows, WorkflowUnlockScheduledJobs)
	assert.Contains(t, workflows, WorkflowTerminateSessions)
	assert.Contains(t, workflows, WorkflowBlockConnections)
	assert.Contains(t, workflows, WorkflowUnblockConnections)
	assert.Contains(t, workflows, WorkflowODataBatch)
	assert.Contains(t, workflows, WorkflowConfigUpdate)
	assert.Contains(t, workflows, WorkflowConfigLoad)
}

// TestGetWorkflowDescriptions verifies workflow metadata.
func TestGetWorkflowDescriptions(t *testing.T) {
	descriptions := GetWorkflowDescriptions()

	assert.Len(t, descriptions, 10, "Should return 10 workflow descriptions")

	// Check extension_install
	var extensionInstall *WorkflowDescription
	for i := range descriptions {
		if descriptions[i].ID == WorkflowExtensionInstall {
			extensionInstall = &descriptions[i]
			break
		}
	}

	require.NotNil(t, extensionInstall, "Should have extension_install workflow")
	assert.Equal(t, "Install Extension", extensionInstall.Name)
	assert.Equal(t, "extensions", extensionInstall.Category)
	assert.NotEmpty(t, extensionInstall.Description)
	assert.Greater(t, len(extensionInstall.Steps), 0, "Should have steps")
}

// TestWorkflowRegistryRegisterAll tests registering all workflows.
func TestWorkflowRegistryRegisterAll(t *testing.T) {
	// Setup
	orchestrator := newMockOrchestrator()
	rm := newMockResourceManager()
	logger := zaptest.NewLogger(t)

	registry, err := NewWorkflowRegistry(
		orchestrator,
		rm,
		&mockRASClient{},
		&mockODataClient{},
		&mockDesignerClient{},
		DefaultWorkflowConfig(),
		logger,
	)
	require.NoError(t, err)

	// Execute
	err = registry.RegisterAll()

	// Verify
	require.NoError(t, err)
	assert.Len(t, orchestrator.registered, 10, "Should register all 10 workflows")

	// Check specific workflows
	assert.Contains(t, orchestrator.registered, WorkflowExtensionInstall)
	assert.Contains(t, orchestrator.registered, WorkflowODataBatch)
	assert.Contains(t, orchestrator.registered, WorkflowConfigUpdate)
}

// TestWorkflowRegistryRegisterSubset tests selective workflow registration.
func TestWorkflowRegistryRegisterSubset(t *testing.T) {
	tests := []struct {
		name        string
		workflowIDs []string
		wantCount   int
		wantErr     bool
	}{
		{
			name:        "single workflow",
			workflowIDs: []string{WorkflowODataBatch},
			wantCount:   1,
			wantErr:     false,
		},
		{
			name:        "multiple workflows",
			workflowIDs: []string{WorkflowExtensionInstall, WorkflowExtensionRemove, WorkflowODataBatch},
			wantCount:   3,
			wantErr:     false,
		},
		{
			name:        "unknown workflow ID",
			workflowIDs: []string{"unknown_workflow"},
			wantCount:   0,
			wantErr:     true,
		},
		{
			name:        "empty list",
			workflowIDs: []string{},
			wantCount:   0,
			wantErr:     false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			orchestrator := newMockOrchestrator()
			rm := newMockResourceManager()
			logger := zaptest.NewLogger(t)

			registry, err := NewWorkflowRegistry(
				orchestrator,
				rm,
				&mockRASClient{},
				&mockODataClient{},
				&mockDesignerClient{},
				DefaultWorkflowConfig(),
				logger,
			)
			require.NoError(t, err)

			err = registry.RegisterSubset(tt.workflowIDs...)

			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}

			assert.Len(t, orchestrator.registered, tt.wantCount)
		})
	}
}

// TestWorkflowRegistryNilDefaults tests default parameter handling.
func TestWorkflowRegistryNilDefaults(t *testing.T) {
	orchestrator := newMockOrchestrator()
	rm := newMockResourceManager()

	// Create registry with nil config and logger
	registry, err := NewWorkflowRegistry(
		orchestrator,
		rm,
		&mockRASClient{},
		&mockODataClient{},
		&mockDesignerClient{},
		nil, // config = nil
		nil, // logger = nil
	)
	require.NoError(t, err)

	require.NotNil(t, registry)
	require.NotNil(t, registry.deps)
	require.NotNil(t, registry.deps.Config)
	require.NotNil(t, registry.deps.ODataClient)
	require.NotNil(t, registry.logger)

	// Should work without panics
	err = registry.RegisterSubset(WorkflowODataBatch)
	assert.NoError(t, err)
}

package poolops

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
)

type mockRuntimeStepAPI struct {
	lastCtx context.Context
	lastReq *orchestrator.PoolRuntimeStepExecutionRequest
	resp    *orchestrator.PoolRuntimeStepExecutionResponse
	err     error
}

func (m *mockRuntimeStepAPI) ExecutePoolRuntimeStep(
	ctx context.Context,
	req *orchestrator.PoolRuntimeStepExecutionRequest,
) (*orchestrator.PoolRuntimeStepExecutionResponse, error) {
	m.lastCtx = ctx
	m.lastReq = req
	if m.err != nil {
		return nil, m.err
	}
	return m.resp, nil
}

func TestBuildStepIdempotencyKey(t *testing.T) {
	key := buildStepIdempotencyKey("exec-1", "node-1", 2)
	assert.Equal(t, "exec-1:node-1:2", key)
}

func TestOrchestratorBridgeClient_ExecutePoolRuntimeStep_BuildsPayload(t *testing.T) {
	api := &mockRuntimeStepAPI{
		resp: &orchestrator.PoolRuntimeStepExecutionResponse{
			Result: map[string]interface{}{"ok": true},
		},
	}
	client := NewOrchestratorBridgeClientWithAPI(api, zap.NewNop())

	res, err := client.ExecutePoolRuntimeStep(context.Background(), &BridgeRequest{
		OperationType: "pool.publication_odata",
		ExecutionID:   "exec-1",
		NodeID:        "node-1",
		TenantID:      "tenant-1",
		PoolRunID:     "pool-run-1",
		StepAttempt:   3,
		PublicationAuth: &BridgePublicationAuth{
			Strategy:      "actor",
			ActorUsername: "alice",
			Source:        "confirm_publication",
		},
		Payload: map[string]interface{}{"k": "v"},
		OperationRef: &BridgeOperationRef{
			Alias:                    "pool.publication_odata",
			BindingMode:              "pinned_exposure",
			TemplateExposureID:       "e-1",
			TemplateExposureRevision: 7,
		},
		TimeoutSeconds: 1,
	})

	require.NoError(t, err)
	require.NotNil(t, api.lastReq)
	assert.Equal(t, "pool.publication_odata", api.lastReq.OperationType)
	assert.Equal(t, "tenant-1", api.lastReq.TenantID)
	assert.Equal(t, "pool-run-1", api.lastReq.PoolRunID)
	assert.Equal(t, "exec-1", api.lastReq.WorkflowExecutionID)
	assert.Equal(t, "node-1", api.lastReq.NodeID)
	assert.Equal(t, 3, api.lastReq.StepAttempt)
	assert.Equal(t, "exec-1:node-1:3", api.lastReq.IdempotencyKey)
	assert.Equal(t, "pool.publication_odata", api.lastReq.OperationRef.Alias)
	require.NotNil(t, api.lastReq.PublicationAuth)
	assert.Equal(t, "actor", api.lastReq.PublicationAuth.Strategy)
	assert.Equal(t, "alice", api.lastReq.PublicationAuth.ActorUsername)
	assert.Equal(t, "confirm_publication", api.lastReq.PublicationAuth.Source)
	assert.Equal(t, true, res.Result["ok"])

	deadline, ok := api.lastCtx.Deadline()
	assert.True(t, ok)
	assert.WithinDuration(t, time.Now().Add(time.Second), deadline, 2*time.Second)
}

func TestOrchestratorBridgeClient_ExecutePoolRuntimeStep_UsesProvidedIdempotencyKey(t *testing.T) {
	api := &mockRuntimeStepAPI{
		resp: &orchestrator.PoolRuntimeStepExecutionResponse{
			Result: map[string]interface{}{},
		},
	}
	client := NewOrchestratorBridgeClientWithAPI(api, zap.NewNop())

	_, err := client.ExecutePoolRuntimeStep(context.Background(), &BridgeRequest{
		OperationType:  "pool.prepare_input",
		ExecutionID:    "exec-1",
		NodeID:         "node-1",
		IdempotencyKey: "fixed-key",
	})

	require.NoError(t, err)
	require.NotNil(t, api.lastReq)
	assert.Equal(t, "fixed-key", api.lastReq.IdempotencyKey)
	assert.Equal(t, 1, api.lastReq.StepAttempt)
}

func TestOrchestratorBridgeClient_ExecutePoolRuntimeStep_PropagatesAPIError(t *testing.T) {
	api := &mockRuntimeStepAPI{err: errors.New("bridge call failed")}
	client := NewOrchestratorBridgeClientWithAPI(api, zap.NewNop())

	_, err := client.ExecutePoolRuntimeStep(context.Background(), &BridgeRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-1",
		NodeID:        "node-1",
	})

	assert.EqualError(t, err, "bridge call failed")
}

func TestOrchestratorBridgeClient_ExecutePoolRuntimeStep_MapsDeadlineExceededToRetryBudgetCode(t *testing.T) {
	api := &mockRuntimeStepAPI{err: context.DeadlineExceeded}
	client := NewOrchestratorBridgeClientWithAPI(api, zap.NewNop())

	_, err := client.ExecutePoolRuntimeStep(context.Background(), &BridgeRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-1",
		NodeID:        "node-1",
	})

	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimeBridgeRetryBudgetExhausted, opErr.Code)
	assert.Contains(t, opErr.Message, "retry budget exhausted")
}

package poolops

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

type mockBridgeClient struct {
	callCount int
	lastReq   *BridgeRequest
	res       *BridgeResponse
	err       error
}

func (m *mockBridgeClient) ExecutePoolRuntimeStep(ctx context.Context, req *BridgeRequest) (*BridgeResponse, error) {
	m.callCount++
	m.lastReq = req
	return m.res, m.err
}

type mockPublicationTransport struct {
	callCount int
	lastReq   *handlers.OperationRequest
	res       map[string]interface{}
	err       error
}

func (m *mockPublicationTransport) ExecutePublicationOData(
	ctx context.Context,
	req *handlers.OperationRequest,
) (map[string]interface{}, error) {
	m.callCount++
	m.lastReq = req
	return m.res, m.err
}

type mockFactualTransport struct {
	callCount int
	lastReq   *handlers.OperationRequest
	res       map[string]interface{}
	err       error
}

func (m *mockFactualTransport) ExecuteFactualSyncSourceSlice(
	ctx context.Context,
	req *handlers.OperationRequest,
) (map[string]interface{}, error) {
	m.callCount++
	m.lastReq = req
	return m.res, m.err
}

func TestIsPoolOperation(t *testing.T) {
	assert.True(t, IsPoolOperation("pool.publication_odata"))
	assert.True(t, IsPoolOperation("pool.prepare_input"))
	assert.False(t, IsPoolOperation("odata.create"))
	assert.False(t, IsPoolOperation(""))
}

func TestAdapter_ExecuteNilRequest(t *testing.T) {
	adapter := NewAdapter(nil, zap.NewNop())
	_, err := adapter.Execute(context.Background(), nil)
	assert.ErrorIs(t, err, ErrNilOperationRequest)
}

func TestAdapter_ExecuteNonPoolOperationIsSkipped(t *testing.T) {
	bridge := &mockBridgeClient{}
	adapter := NewAdapter(bridge, zap.NewNop())

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "odata.create",
	})

	assert.NoError(t, err)
	assert.Equal(t, 0, bridge.callCount)
	assert.Equal(t, true, out["execution_skipped"])
	assert.Equal(t, "odata.create", out["operation_type"])
}

func TestAdapter_ExecutePublicationOperationWithoutTransportFailsClosed(t *testing.T) {
	adapter := NewAdapter(nil, zap.NewNop())

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.publication_odata",
		TemplateID:    "tpl-1",
	})

	var opErr *handlers.OperationExecutionError
	assert.Error(t, err)
	assert.Nil(t, out)
	assert.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimePublicationPathDisabled, opErr.Code)
}

func TestAdapter_ExecutePoolOperationRouteDisabledFailsClosed(t *testing.T) {
	bridge := &mockBridgeClient{}
	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{PoolRouteEnabled: false})

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.publication_odata",
	})

	var opErr *handlers.OperationExecutionError
	assert.Error(t, err)
	assert.Nil(t, out)
	assert.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimeRouteDisabled, opErr.Code)
	assert.Equal(t, 0, bridge.callCount)
}

func TestAdapter_ExecutePoolOperationCallsBridge(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "ok"},
		},
	}
	adapter := NewAdapter(bridge, zap.NewNop())

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.prepare_input",
		TemplateID:      "tpl-1",
		TargetEntity:    "Document",
		Payload:         map[string]interface{}{"k": "v"},
		TargetDatabases: []string{"db-1"},
		TimeoutSeconds:  30,
		PublicationAuth: &handlers.PublicationAuth{
			Strategy:      "actor",
			ActorUsername: "alice",
			Source:        "confirm_publication",
		},
	})

	assert.NoError(t, err)
	assert.Equal(t, 1, bridge.callCount)
	assert.NotNil(t, bridge.lastReq)
	assert.Equal(t, "pool.prepare_input", bridge.lastReq.OperationType)
	require.NotNil(t, bridge.lastReq.PublicationAuth)
	assert.Equal(t, "actor", bridge.lastReq.PublicationAuth.Strategy)
	assert.Equal(t, "alice", bridge.lastReq.PublicationAuth.ActorUsername)
	assert.Equal(t, "confirm_publication", bridge.lastReq.PublicationAuth.Source)
	assert.Equal(t, "ok", out["status"])
}

func TestAdapter_ExecutePoolOperationPropagatesOperationRef(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "ok"},
		},
	}
	adapter := NewAdapter(bridge, zap.NewNop())

	_, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
		OperationRef: &models.OperationRef{
			Alias:                    "pool.prepare_input",
			BindingMode:              "pinned_exposure",
			TemplateExposureID:       "exposure-1",
			TemplateExposureRevision: 5,
		},
	})

	require.NoError(t, err)
	require.NotNil(t, bridge.lastReq)
	require.NotNil(t, bridge.lastReq.OperationRef)
	assert.Equal(t, "pool.prepare_input", bridge.lastReq.OperationRef.Alias)
	assert.Equal(t, "pinned_exposure", bridge.lastReq.OperationRef.BindingMode)
	assert.Equal(t, "exposure-1", bridge.lastReq.OperationRef.TemplateExposureID)
	assert.Equal(t, 5, bridge.lastReq.OperationRef.TemplateExposureRevision)
}

func TestAdapter_ExecutePoolOperationUsesTemplateIDAsFallbackOperationType(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "ok"},
		},
	}
	adapter := NewAdapter(bridge, zap.NewNop())

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		TemplateID: "pool.prepare_input",
	})

	assert.NoError(t, err)
	assert.Equal(t, 1, bridge.callCount)
	assert.Equal(t, "pool.prepare_input", bridge.lastReq.OperationType)
	assert.Equal(t, "ok", out["status"])
}

func TestAdapter_ExecutePoolOperationBridgeError(t *testing.T) {
	bridge := &mockBridgeClient{
		err: errors.New("bridge failed"),
	}
	adapter := NewAdapter(bridge, zap.NewNop())

	_, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
	})

	assert.Error(t, err)
	assert.EqualError(t, err, "bridge failed")
}

func TestAdapter_ExecutePublicationOperationUsesLocalTransportWhenEnabled(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "bridge"},
		},
	}
	publicationTransport := &mockPublicationTransport{
		res: map[string]interface{}{"status": "local"},
	}

	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabled:     true,
		PublicationTransport: publicationTransport,
		PublicationRouteEnabledProvider: func() bool {
			return true
		},
	})

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.publication_odata",
		ExecutionID:   "exec-1",
	})
	require.NoError(t, err)
	assert.Equal(t, "local", out["status"])
	assert.Equal(t, 1, publicationTransport.callCount)
	assert.Equal(t, 0, bridge.callCount)
}

func TestAdapter_ExecutePublicationOperationDoesNotFallbackToBridgeWhenTransportMissing(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "bridge"},
		},
	}
	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabled: true,
		PublicationRouteEnabledProvider: func() bool {
			return true
		},
	})

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.publication_odata",
		ExecutionID:   "exec-1",
	})

	var opErr *handlers.OperationExecutionError
	require.Error(t, err)
	assert.Nil(t, out)
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimePublicationPathDisabled, opErr.Code)
	assert.Equal(t, 0, bridge.callCount)
}

func TestAdapter_ExecutePublicationOperationRouteDisabledFailsClosed(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "bridge"},
		},
	}
	publicationTransport := &mockPublicationTransport{
		res: map[string]interface{}{"status": "local"},
	}
	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabled:     true,
		PublicationTransport: publicationTransport,
		PublicationRouteEnabledProvider: func() bool {
			return false
		},
	})

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.publication_odata",
		ExecutionID:   "exec-1",
	})

	var opErr *handlers.OperationExecutionError
	require.Error(t, err)
	assert.Nil(t, out)
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimePublicationPathDisabled, opErr.Code)
	assert.Equal(t, 0, publicationTransport.callCount)
	assert.Equal(t, 0, bridge.callCount)
}

func TestAdapter_ExecuteFactualOperationUsesLocalTransport(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "bridge"},
		},
	}
	factualTransport := &mockFactualTransport{
		res: map[string]interface{}{"status": "local"},
	}

	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabled: true,
		FactualTransport: factualTransport,
	})

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.factual.sync_source_slice",
		ExecutionID:   "exec-1",
	})
	require.NoError(t, err)
	assert.Equal(t, "local", out["status"])
	assert.Equal(t, 1, factualTransport.callCount)
	assert.Equal(t, 0, bridge.callCount)
}

func TestAdapter_ExecuteFactualOperationDoesNotFallbackToBridgeWhenTransportMissing(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "bridge"},
		},
	}
	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabled: true,
	})

	out, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.factual.sync_source_slice",
		ExecutionID:   "exec-1",
	})

	var opErr *handlers.OperationExecutionError
	require.Error(t, err)
	assert.Nil(t, out)
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimeFactualPathDisabled, opErr.Code)
	assert.Equal(t, 0, bridge.callCount)
}

func TestAdapter_ExecutePoolOperationRouteDecisionLatchedPerExecution(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "ok"},
		},
	}
	var routeEnabled atomic.Bool
	routeEnabled.Store(true)

	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabledProvider: routeEnabled.Load,
	})

	// First step for execution "exec-1" latches route=true.
	_, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-1",
		NodeID:        "node-1",
	})
	require.NoError(t, err)
	assert.Equal(t, 1, bridge.callCount)

	// Kill-switch toggles off route for new executions.
	routeEnabled.Store(false)

	// In-flight execution "exec-1" must keep latched route=true.
	_, err = adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-1",
		NodeID:        "node-2",
	})
	require.NoError(t, err)
	assert.Equal(t, 2, bridge.callCount)

	// New execution must observe updated route=false and fail-closed.
	_, err = adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-2",
		NodeID:        "node-1",
	})
	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimeRouteDisabled, opErr.Code)
	assert.Equal(t, 2, bridge.callCount)
}

func TestAdapter_LatchRouteDecision_BindsRouteBeforeFirstPoolNode(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "ok"},
		},
	}
	var routeEnabled atomic.Bool
	routeEnabled.Store(true)

	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabledProvider: routeEnabled.Load,
	})

	latched := adapter.LatchRouteDecision("exec-1")
	assert.True(t, latched)

	routeEnabled.Store(false)
	_, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-1",
		NodeID:        "node-1",
	})
	require.NoError(t, err)
	assert.Equal(t, 1, bridge.callCount)
}

func TestAdapter_ExecutePoolOperationWithoutExecutionIDUsesCurrentRouteDecision(t *testing.T) {
	bridge := &mockBridgeClient{
		res: &BridgeResponse{
			Result: map[string]interface{}{"status": "ok"},
		},
	}
	var routeEnabled atomic.Bool
	routeEnabled.Store(true)

	adapter := NewAdapterWithConfig(bridge, zap.NewNop(), AdapterConfig{
		PoolRouteEnabledProvider: routeEnabled.Load,
	})

	_, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
	})
	require.NoError(t, err)
	assert.Equal(t, 1, bridge.callCount)

	routeEnabled.Store(false)
	_, err = adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
	})
	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, handlers.ErrorCodePoolRuntimeRouteDisabled, opErr.Code)
	assert.Equal(t, 1, bridge.callCount)
}

package poolops

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
)

const defaultBridgeTimeout = 30 * time.Second

type runtimeStepAPI interface {
	ExecutePoolRuntimeStep(
		ctx context.Context,
		req *orchestrator.PoolRuntimeStepExecutionRequest,
	) (*orchestrator.PoolRuntimeStepExecutionResponse, error)
}

// OrchestratorBridgeClient invokes canonical pool runtime bridge endpoint.
type OrchestratorBridgeClient struct {
	api    runtimeStepAPI
	logger *zap.Logger
}

// NewOrchestratorBridgeClient creates a bridge client from orchestrator client.
func NewOrchestratorBridgeClient(client *orchestrator.Client, logger *zap.Logger) *OrchestratorBridgeClient {
	return NewOrchestratorBridgeClientWithAPI(client, logger)
}

// NewOrchestratorBridgeClientWithAPI creates a bridge client with pluggable API.
func NewOrchestratorBridgeClientWithAPI(api runtimeStepAPI, logger *zap.Logger) *OrchestratorBridgeClient {
	if logger == nil {
		logger = zap.NewNop()
	}
	return &OrchestratorBridgeClient{
		api:    api,
		logger: logger.Named("poolops_bridge_client"),
	}
}

// ExecutePoolRuntimeStep executes pool runtime step via Orchestrator internal API.
func (c *OrchestratorBridgeClient) ExecutePoolRuntimeStep(
	ctx context.Context,
	req *BridgeRequest,
) (*BridgeResponse, error) {
	if req == nil {
		return nil, ErrNilOperationRequest
	}
	if c.api == nil {
		return nil, fmt.Errorf("poolops bridge client is not configured")
	}

	timeout := defaultBridgeTimeout
	if req.TimeoutSeconds > 0 {
		timeout = time.Duration(req.TimeoutSeconds) * time.Second
	}
	callCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	idempotencyKey := strings.TrimSpace(req.IdempotencyKey)
	if idempotencyKey == "" {
		idempotencyKey = buildStepIdempotencyKey(req.ExecutionID, req.NodeID, req.StepAttempt)
	}

	request := &orchestrator.PoolRuntimeStepExecutionRequest{
		TenantID:            req.TenantID,
		PoolRunID:           req.PoolRunID,
		WorkflowExecutionID: req.ExecutionID,
		NodeID:              req.NodeID,
		OperationType:       req.OperationType,
		OperationRef:        toOrchestratorOperationRef(req.OperationRef),
		PublicationAuth:     toOrchestratorPublicationAuth(req.PublicationAuth),
		StepAttempt:         normalizeStepAttempt(req.StepAttempt),
		TransportAttempt:    1,
		IdempotencyKey:      idempotencyKey,
		Payload:             req.Payload,
	}

	resp, err := c.api.ExecutePoolRuntimeStep(callCtx, request)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(callCtx.Err(), context.DeadlineExceeded) {
			return nil, handlers.NewOperationExecutionError(
				handlers.ErrorCodePoolRuntimeBridgeRetryBudgetExhausted,
				fmt.Sprintf("pool runtime bridge retry budget exhausted: %v", err),
			)
		}
		return nil, err
	}
	if resp == nil || resp.Result == nil {
		return &BridgeResponse{Result: map[string]interface{}{}}, nil
	}
	return &BridgeResponse{Result: resp.Result}, nil
}

func buildStepIdempotencyKey(executionID, nodeID string, stepAttempt int) string {
	execution := strings.TrimSpace(executionID)
	if execution == "" {
		execution = "unknown_execution"
	}
	node := strings.TrimSpace(nodeID)
	if node == "" {
		node = "unknown_node"
	}
	return fmt.Sprintf("%s:%s:%d", execution, node, normalizeStepAttempt(stepAttempt))
}

func toOrchestratorOperationRef(ref *BridgeOperationRef) *orchestrator.PoolRuntimeOperationRef {
	if ref == nil {
		return nil
	}
	return &orchestrator.PoolRuntimeOperationRef{
		Alias:                    ref.Alias,
		BindingMode:              ref.BindingMode,
		TemplateExposureID:       ref.TemplateExposureID,
		TemplateExposureRevision: ref.TemplateExposureRevision,
	}
}

func toOrchestratorPublicationAuth(ref *BridgePublicationAuth) *orchestrator.PoolRuntimePublicationAuth {
	if ref == nil {
		return nil
	}
	return &orchestrator.PoolRuntimePublicationAuth{
		Strategy:      strings.TrimSpace(ref.Strategy),
		ActorUsername: strings.TrimSpace(ref.ActorUsername),
		Source:        strings.TrimSpace(ref.Source),
	}
}

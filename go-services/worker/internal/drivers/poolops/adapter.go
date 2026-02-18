package poolops

import (
	"context"
	"errors"
	"strings"
	"sync"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

var ErrNilOperationRequest = errors.New("poolops: operation request is nil")

// BridgeClient executes pool runtime steps against the domain backend.
type BridgeClient interface {
	ExecutePoolRuntimeStep(ctx context.Context, req *BridgeRequest) (*BridgeResponse, error)
}

// BridgeRequest is an internal payload for pool runtime step execution.
type BridgeRequest struct {
	OperationType   string
	TemplateID      string
	TargetEntity    string
	OperationRef    *BridgeOperationRef
	Payload         map[string]interface{}
	TargetDatabases []string
	TimeoutSeconds  int
	TenantID        string
	PoolRunID       string
	ExecutionID     string
	NodeID          string
	StepAttempt     int
	IdempotencyKey  string
}

// BridgeResponse is a normalized bridge response.
type BridgeResponse struct {
	Result map[string]interface{}
}

// BridgeOperationRef carries operation binding provenance to bridge payload.
type BridgeOperationRef struct {
	Alias                    string
	BindingMode              string
	TemplateExposureID       string
	TemplateExposureRevision int
}

// Adapter bridges workflow operation nodes to pool runtime backend.
type Adapter struct {
	bridge                   BridgeClient
	logger                   *zap.Logger
	poolRouteEnabledProvider func() bool
	routeDecisionByExecution sync.Map // map[execution_id]bool
}

// AdapterConfig controls runtime behavior of poolops adapter.
type AdapterConfig struct {
	PoolRouteEnabled         bool
	PoolRouteEnabledProvider func() bool
}

// NewAdapter creates a poolops adapter for workflow operation execution.
func NewAdapter(bridge BridgeClient, logger *zap.Logger) *Adapter {
	return NewAdapterWithConfig(bridge, logger, AdapterConfig{PoolRouteEnabled: true})
}

// NewAdapterWithConfig creates a configured poolops adapter.
func NewAdapterWithConfig(bridge BridgeClient, logger *zap.Logger, cfg AdapterConfig) *Adapter {
	if logger == nil {
		logger = zap.NewNop()
	}
	routeProvider := cfg.PoolRouteEnabledProvider
	if routeProvider == nil {
		poolRouteEnabled := cfg.PoolRouteEnabled
		routeProvider = func() bool {
			return poolRouteEnabled
		}
	}
	return &Adapter{
		bridge:                   bridge,
		logger:                   logger.Named("poolops_adapter"),
		poolRouteEnabledProvider: routeProvider,
	}
}

// Execute dispatches pool operations to bridge client.
func (a *Adapter) Execute(ctx context.Context, req *handlers.OperationRequest) (map[string]interface{}, error) {
	if req == nil {
		return nil, ErrNilOperationRequest
	}

	operationType := operationTypeForRequest(req)

	if !IsPoolOperation(operationType) {
		return map[string]interface{}{
			"execution_skipped": true,
			"reason":            "poolops adapter bypassed non-pool operation",
			"operation_type":    operationType,
		}, nil
	}

	if !a.poolRouteEnabledForExecution(req.ExecutionID) {
		return nil, handlers.NewOperationExecutionError(
			handlers.ErrorCodePoolRuntimeRouteDisabled,
			"poolops route is disabled by runtime guard",
		)
	}

	if a.bridge == nil {
		a.logger.Warn("pool operation received but poolops bridge is not configured",
			zap.String("operation_type", operationType),
			zap.String("template_id", req.TemplateID),
		)
		return nil, handlers.NewOperationExecutionError(
			handlers.ErrorCodeWorkflowOperationExecutorNotConfigured,
			"poolops bridge client is not configured",
		)
	}

	res, err := a.bridge.ExecutePoolRuntimeStep(ctx, &BridgeRequest{
		OperationType:   operationType,
		TemplateID:      req.TemplateID,
		TargetEntity:    req.TargetEntity,
		OperationRef:    toBridgeOperationRef(req.OperationRef),
		Payload:         req.Payload,
		TargetDatabases: req.TargetDatabases,
		TimeoutSeconds:  req.TimeoutSeconds,
		TenantID:        req.TenantID,
		PoolRunID:       req.PoolRunID,
		ExecutionID:     req.ExecutionID,
		NodeID:          req.NodeID,
		StepAttempt:     normalizeStepAttempt(req.StepAttempt),
		IdempotencyKey:  strings.TrimSpace(req.IdempotencyKey),
	})
	if err != nil {
		return nil, err
	}
	if res == nil || res.Result == nil {
		return map[string]interface{}{}, nil
	}
	return res.Result, nil
}

// IsPoolOperation reports whether operation_type belongs to pool runtime domain.
func IsPoolOperation(operationType string) bool {
	return strings.HasPrefix(operationType, "pool.")
}

func operationTypeForRequest(req *handlers.OperationRequest) string {
	if req == nil {
		return ""
	}
	if v := strings.TrimSpace(req.OperationType); v != "" {
		return v
	}
	return strings.TrimSpace(req.TemplateID)
}

func normalizeStepAttempt(stepAttempt int) int {
	if stepAttempt > 0 {
		return stepAttempt
	}
	return 1
}

func (a *Adapter) poolRouteEnabledForExecution(executionID string) bool {
	current := a.poolRouteEnabled()
	normalizedExecutionID := strings.TrimSpace(executionID)
	if normalizedExecutionID == "" {
		return current
	}

	if latched, ok := a.routeDecisionByExecution.Load(normalizedExecutionID); ok {
		if decision, typeOK := latched.(bool); typeOK {
			return decision
		}
	}

	a.routeDecisionByExecution.Store(normalizedExecutionID, current)
	return current
}

func (a *Adapter) poolRouteEnabled() bool {
	if a.poolRouteEnabledProvider == nil {
		return false
	}
	return a.poolRouteEnabledProvider()
}

func toBridgeOperationRef(src *models.OperationRef) *BridgeOperationRef {
	if src == nil {
		return nil
	}
	return &BridgeOperationRef{
		Alias:                    src.Alias,
		BindingMode:              src.BindingMode,
		TemplateExposureID:       src.TemplateExposureID,
		TemplateExposureRevision: src.TemplateExposureRevision,
	}
}

package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

const (
	poolPublicationOperationType     = "pool.publication_odata"
	poolFactualSyncOperationType     = "pool.factual.sync_source_slice"
	poolPublicationPayloadContextKey = "pool_runtime_publication_payload"
	poolMasterDataGateNodeID         = "master_data_gate"
	poolDistributionNodeID           = "distribution_calculation"
	poolReconciliationNodeID         = "reconciliation_report"
)

// OperationHandler executes operation nodes.
// Operation nodes render templates and execute operations against 1C databases
// via OData or RAS backends.
//
// Flow:
//  1. Parse operation config from node
//  2. Render payload with template engine
//  3. Execute operation via executor
//  4. Return result with output data
type OperationHandler struct {
	templateEngine TemplateRenderer
	executor       OperationExecutor
	logger         *zap.Logger
}

// NewOperationHandler creates a new operation handler.
func NewOperationHandler(deps *HandlerDependencies) *OperationHandler {
	logger := deps.Logger
	if logger == nil {
		logger = zap.NewNop()
	}
	return &OperationHandler{
		templateEngine: deps.TemplateEngine,
		executor:       deps.OperationExecutor,
		logger:         logger.Named("operation_handler"),
	}
}

// SupportedTypes returns the node types this handler can process.
func (h *OperationHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeOperation}
}

// HandleNode executes an operation node.
func (h *OperationHandler) HandleNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*executor.NodeResult, error) {
	startTime := time.Now()

	h.logger.Debug("Executing operation node",
		zap.String("node_id", node.ID),
		zap.String("node_name", node.Name),
		zap.String("template_id", node.TemplateID),
		zap.String("execution_id", execCtx.ExecutionID()))

	// Parse operation config
	config, err := parseOperationConfig(node)
	if err != nil {
		h.logger.Error("Failed to parse operation config",
			zap.String("node_id", node.ID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("invalid operation config: %w", err),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Render payload with template engine
	var renderedPayload map[string]interface{}
	if h.templateEngine != nil && config.Payload != nil {
		renderCtx := execCtx.ToMap()
		renderedPayload, err = h.templateEngine.RenderJSON(ctx, config.Payload, renderCtx)
		if err != nil {
			h.logger.Error("Template rendering failed",
				zap.String("node_id", node.ID),
				zap.Error(err))
			return &executor.NodeResult{
				NodeID:      node.ID,
				Status:      executor.NodeStatusFailed,
				Error:       fmt.Errorf("template rendering failed: %w", err),
				StartedAt:   startTime,
				CompletedAt: time.Now(),
				Duration:    time.Since(startTime),
			}, nil
		}
	} else {
		renderedPayload = config.Payload
	}

	// Check for operation executor
	if h.executor == nil {
		if isPoolOperationType(config.OperationType) {
			err := NewOperationExecutionError(
				ErrorCodeWorkflowOperationExecutorNotConfigured,
				"pool operation executor is not configured",
			)
			h.logger.Error("Pool operation executor is not configured",
				zap.String("node_id", node.ID),
				zap.String("operation_type", config.OperationType),
				zap.Error(err),
			)
			return &executor.NodeResult{
				NodeID:      node.ID,
				Status:      executor.NodeStatusFailed,
				Error:       err,
				StartedAt:   startTime,
				CompletedAt: time.Now(),
				Duration:    time.Since(startTime),
			}, nil
		}

		h.logger.Warn("No operation executor configured, returning rendered data only",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID: node.ID,
			Status: executor.NodeStatusCompleted,
			Output: map[string]interface{}{
				"rendered_payload":  renderedPayload,
				"execution_skipped": true,
				"reason":            "No operation executor configured",
				"operation_type":    config.OperationType,
				"target_entity":     config.TargetEntity,
			},
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Extract target databases from context
	targetDatabases := extractTargetDatabases(execCtx, node)
	tenantID, _ := execCtx.GetString("tenant_id")
	poolRunID, _ := execCtx.GetString("pool_run_id")
	operationID, _ := execCtx.GetString("operation_id")
	stepAttempt := getStepAttempt(execCtx, node.ID)
	operationPayload := renderedPayload
	if operationPayload == nil {
		operationPayload = resolveOperationPayloadFromContext(config.OperationType, execCtx)
	}
	if config.OperationType == poolPublicationOperationType {
		operationPayload = enrichPoolPublicationPayloadWithResolvedLinkRefs(operationPayload, execCtx)
	}

	// Build operation request
	req := &OperationRequest{
		OperationID:     operationID,
		OperationType:   config.OperationType,
		TargetEntity:    config.TargetEntity,
		Payload:         operationPayload,
		TemplateID:      config.TemplateID,
		OperationRef:    node.OperationRef,
		TargetDatabases: targetDatabases,
		TimeoutSeconds:  getNodeTimeout(node),
		ExecutionID:     execCtx.ExecutionID(),
		NodeID:          node.ID,
		TenantID:        tenantID,
		PoolRunID:       poolRunID,
		StepAttempt:     stepAttempt,
		PublicationAuth: extractPublicationAuth(execCtx),
	}

	h.logger.Debug("Executing operation",
		zap.String("node_id", node.ID),
		zap.String("operation_type", config.OperationType),
		zap.String("target_entity", config.TargetEntity),
		zap.Int("target_db_count", len(targetDatabases)))

	// Execute operation
	result, err := h.executor.Execute(ctx, req)
	if err != nil {
		h.logger.Error("Operation execution failed",
			zap.String("node_id", node.ID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       err,
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	h.logger.Debug("Operation completed successfully",
		zap.String("node_id", node.ID),
		zap.Duration("duration", time.Since(startTime)))

	return &executor.NodeResult{
		NodeID:      node.ID,
		Status:      executor.NodeStatusCompleted,
		Output:      result,
		StartedAt:   startTime,
		CompletedAt: time.Now(),
		Duration:    time.Since(startTime),
	}, nil
}

// parseOperationConfig extracts operation configuration from node.
func parseOperationConfig(node *models.Node) (*models.OperationNodeConfig, error) {
	config := &models.OperationNodeConfig{
		TemplateID:    node.TemplateID,
		OperationType: node.TemplateID,
	}

	if node.OperationRef != nil && node.OperationRef.Alias != "" {
		config.OperationType = node.OperationRef.Alias
	}

	// For operation nodes, TemplateID is typically required
	if config.TemplateID == "" && config.OperationType == "" {
		return nil, fmt.Errorf("operation node requires template_id or operation_type")
	}

	return config, nil
}

// extractTargetDatabases gets target database IDs from context and node config.
// Handles both new format ([]models.TargetDatabase) and JSON-deserialized format ([]interface{}).
func extractTargetDatabases(execCtx *wfcontext.ExecutionContext, node *models.Node) []string {
	// Check context for target_databases
	if val, ok := execCtx.Get("target_databases"); ok {
		// Handle []interface{} from JSON deserialization
		if dbs, ok := val.([]interface{}); ok {
			result := make([]string, 0, len(dbs))
			for _, db := range dbs {
				// Try to extract ID from map (JSON object format)
				if m, ok := db.(map[string]interface{}); ok {
					if id, ok := m["id"].(string); ok && id != "" {
						result = append(result, id)
						continue
					}
				}
				// Fallback: try direct string (old format)
				if s, ok := db.(string); ok {
					result = append(result, s)
				}
			}
			if len(result) > 0 {
				return result
			}
		}
		// Handle []string (backward compatibility)
		if dbs, ok := val.([]string); ok {
			return dbs
		}
	}

	// Check for target_database_ids (helper field from workflow_handler)
	if val, ok := execCtx.Get("target_database_ids"); ok {
		if ids, ok := val.([]string); ok {
			return ids
		}
		if ids, ok := val.([]interface{}); ok {
			result := make([]string, 0, len(ids))
			for _, id := range ids {
				if s, ok := id.(string); ok {
					result = append(result, s)
				}
			}
			if len(result) > 0 {
				return result
			}
		}
	}

	// Check for single database_id
	if val, ok := execCtx.GetString("database_id"); ok {
		return []string{val}
	}

	return nil
}

// getNodeTimeout gets timeout from node config or returns default.
func getNodeTimeout(node *models.Node) int {
	if node.Config != nil && node.Config.TimeoutSeconds > 0 {
		return node.Config.TimeoutSeconds
	}
	return 300 // 5 minutes default
}

func isPoolOperationType(operationType string) bool {
	return strings.HasPrefix(operationType, "pool.")
}

func resolveOperationPayloadFromContext(
	operationType string,
	execCtx *wfcontext.ExecutionContext,
) map[string]interface{} {
	if execCtx == nil {
		return nil
	}
	if operationType == poolFactualSyncOperationType {
		return resolvePoolFactualPayloadFromContext(execCtx)
	}
	if operationType != poolPublicationOperationType {
		return nil
	}
	if payload := resolvePoolPublicationPayloadFromNodeResult(execCtx, poolMasterDataGateNodeID); payload != nil {
		return payload
	}
	if payload := resolvePoolPublicationPayloadFromNodeResult(execCtx, poolReconciliationNodeID); payload != nil {
		return payload
	}
	if payload := resolvePoolPublicationPayloadFromNodeResult(execCtx, poolDistributionNodeID); payload != nil {
		return payload
	}
	rawPayload, ok := execCtx.Get(poolPublicationPayloadContextKey)
	if !ok {
		return nil
	}
	payload, ok := rawPayload.(map[string]interface{})
	if !ok || len(payload) == 0 {
		return nil
	}
	return payload
}

func resolvePoolFactualPayloadFromContext(execCtx *wfcontext.ExecutionContext) map[string]interface{} {
	if execCtx == nil {
		return nil
	}
	fields := []string{
		"contract_version",
		"tenant_id",
		"pool_id",
		"database_id",
		"checkpoint_id",
		"lane",
		"quarter_start",
		"quarter_end",
		"organization_ids",
		"account_codes",
		"movement_kinds",
		"activity",
		"freeze_quarter",
		"correlation_id",
		"origin_system",
		"origin_event_id",
		"document_entities",
		"accounting_register_entity",
		"accounting_register_function",
		"information_register_entity",
		"source_profile",
		"freshness_target_seconds",
		"scope_fingerprint",
		"factual_scope_contract",
		"subsystem",
		"read_boundary_kind",
		"direct_db_access",
		"read_boundary_entity_allowlist",
		"read_boundary_function_allowlist",
		"read_boundary_service_name",
		"read_boundary_endpoint_path",
		"read_boundary_operation_name",
		"factual_use_case",
		"priority",
		"role",
		"deadline_at",
		"per_database_cap",
		"per_cluster_cap",
		"global_cap",
		"polling_tier",
		"poll_interval_seconds",
		"quarter_scope",
		"schedule_window",
		"server_affinity",
		"server_affinity_source",
	}
	payload := make(map[string]interface{}, len(fields))
	for _, field := range fields {
		if value, ok := execCtx.Get(field); ok {
			payload[field] = value
		}
	}
	if len(payload) == 0 {
		return nil
	}
	return payload
}

func resolvePoolPublicationPayloadFromNodeResult(
	execCtx *wfcontext.ExecutionContext,
	nodeID string,
) map[string]interface{} {
	if execCtx == nil || strings.TrimSpace(nodeID) == "" {
		return nil
	}
	rawPayload, ok := execCtx.Get(fmt.Sprintf("%s.output.publication_payload", nodeID))
	if !ok {
		return nil
	}
	payload, ok := rawPayload.(map[string]interface{})
	if !ok || len(payload) == 0 {
		return nil
	}
	return payload
}

func enrichPoolPublicationPayloadWithResolvedLinkRefs(
	payload map[string]interface{},
	execCtx *wfcontext.ExecutionContext,
) map[string]interface{} {
	if payload == nil || execCtx == nil {
		return payload
	}
	successfulRefsByKey := collectSuccessfulPublicationDocumentRefs(execCtx)
	if len(successfulRefsByKey) == 0 {
		return payload
	}

	enriched := cloneJSONMap(payload)
	poolRuntime := enriched
	if nested, ok := enriched["pool_runtime"].(map[string]interface{}); ok {
		poolRuntime = nested
	}
	chainsByDatabase, ok := poolRuntime["document_chains_by_database"].(map[string]interface{})
	if !ok {
		return payload
	}

	var changed bool
	for _, rawChains := range chainsByDatabase {
		chains, ok := rawChains.([]interface{})
		if !ok {
			continue
		}
		for _, rawChain := range chains {
			chain, ok := rawChain.(map[string]interface{})
			if !ok {
				continue
			}
			rawDocuments, ok := chain["documents"].([]interface{})
			if !ok {
				continue
			}
			idempotencyKeyByDocumentID := make(map[string]string, len(rawDocuments))
			for _, rawDocument := range rawDocuments {
				document, ok := rawDocument.(map[string]interface{})
				if !ok {
					continue
				}
				documentID := strings.TrimSpace(readContextString(document["document_id"]))
				idempotencyKey := strings.TrimSpace(readContextString(document["idempotency_key"]))
				if documentID != "" && idempotencyKey != "" {
					idempotencyKeyByDocumentID[documentID] = idempotencyKey
				}
			}
			for _, rawDocument := range rawDocuments {
				document, ok := rawDocument.(map[string]interface{})
				if !ok {
					continue
				}
				for dependencyDocumentID := range collectPublicationDocumentDependencies(document) {
					dependencyKey := idempotencyKeyByDocumentID[dependencyDocumentID]
					if dependencyKey == "" {
						continue
					}
					dependencyRef := strings.TrimSpace(successfulRefsByKey[dependencyKey])
					if dependencyRef == "" {
						continue
					}
					resolvedLinkRefs := readMutableInterfaceStringMap(document["resolved_link_refs"])
					if strings.TrimSpace(readContextString(resolvedLinkRefs[dependencyDocumentID])) == dependencyRef {
						continue
					}
					resolvedLinkRefs[dependencyDocumentID] = dependencyRef
					document["resolved_link_refs"] = resolvedLinkRefs
					changed = true
				}
			}
		}
	}

	if !changed {
		return payload
	}
	return enriched
}

func collectSuccessfulPublicationDocumentRefs(
	execCtx *wfcontext.ExecutionContext,
) map[string]string {
	snapshot := execCtx.ToMap()
	nodeResults, ok := snapshot["node_results"].(map[string]interface{})
	if !ok {
		return map[string]string{}
	}
	refs := make(map[string]string)
	for _, rawResult := range nodeResults {
		result, ok := rawResult.(map[string]interface{})
		if !ok {
			continue
		}
		collectSuccessfulPublicationDocumentRefsFromResult(result, refs)
	}
	return refs
}

func collectSuccessfulPublicationDocumentRefsFromResult(
	result map[string]interface{},
	refs map[string]string,
) {
	rawAttempts, ok := result["attempts"]
	if !ok {
		return
	}
	for _, rawAttempt := range readInterfaceSlice(rawAttempts) {
		attempt, ok := rawAttempt.(map[string]interface{})
		if !ok {
			continue
		}
		responseSummary, ok := attempt["response_summary"].(map[string]interface{})
		if !ok {
			continue
		}
		successfulRefs, ok := responseSummary["successful_document_refs"].(map[string]interface{})
		if !ok {
			continue
		}
		for rawKey, rawRef := range successfulRefs {
			documentKey := strings.TrimSpace(rawKey)
			documentRef := strings.TrimSpace(readContextString(rawRef))
			if documentKey == "" || documentRef == "" {
				continue
			}
			refs[documentKey] = documentRef
		}
	}
}

func collectPublicationDocumentDependencies(document map[string]interface{}) map[string]struct{} {
	dependencies := make(map[string]struct{})
	if linkTo := strings.TrimSpace(readContextString(document["link_to"])); linkTo != "" {
		dependencies[linkTo] = struct{}{}
	}
	if linkRules, ok := document["link_rules"].(map[string]interface{}); ok {
		if dependsOn := strings.TrimSpace(readContextString(linkRules["depends_on"])); dependsOn != "" {
			dependencies[dependsOn] = struct{}{}
		}
	}
	collectRefTokenDependencies(document["field_mapping"], dependencies)
	collectRefTokenDependencies(document["table_parts_mapping"], dependencies)
	return dependencies
}

func collectRefTokenDependencies(value interface{}, dependencies map[string]struct{}) {
	switch typed := value.(type) {
	case string:
		token := strings.TrimSpace(typed)
		if !strings.HasSuffix(token, ".ref") || strings.HasPrefix(token, "master_data.") {
			return
		}
		documentID := strings.TrimSpace(strings.TrimSuffix(token, ".ref"))
		if documentID != "" {
			dependencies[documentID] = struct{}{}
		}
	case map[string]interface{}:
		for _, nested := range typed {
			collectRefTokenDependencies(nested, dependencies)
		}
	case []interface{}:
		for _, nested := range typed {
			collectRefTokenDependencies(nested, dependencies)
		}
	}
}

func readMutableInterfaceStringMap(value interface{}) map[string]interface{} {
	result := make(map[string]interface{})
	switch raw := value.(type) {
	case map[string]interface{}:
		for rawKey, rawValue := range raw {
			key := strings.TrimSpace(rawKey)
			ref := strings.TrimSpace(readContextString(rawValue))
			if key != "" && ref != "" {
				result[key] = ref
			}
		}
	case map[string]string:
		for rawKey, rawValue := range raw {
			key := strings.TrimSpace(rawKey)
			ref := strings.TrimSpace(rawValue)
			if key != "" && ref != "" {
				result[key] = ref
			}
		}
	}
	return result
}

func readInterfaceSlice(value interface{}) []interface{} {
	if typed, ok := value.([]interface{}); ok {
		return typed
	}
	if typed, ok := value.([]map[string]interface{}); ok {
		result := make([]interface{}, 0, len(typed))
		for _, item := range typed {
			result = append(result, item)
		}
		return result
	}
	return nil
}

func cloneJSONMap(src map[string]interface{}) map[string]interface{} {
	if src == nil {
		return nil
	}
	raw, err := json.Marshal(src)
	if err != nil {
		dst := make(map[string]interface{}, len(src))
		for key, value := range src {
			dst[key] = value
		}
		return dst
	}
	var dst map[string]interface{}
	if err := json.Unmarshal(raw, &dst); err != nil {
		dst = make(map[string]interface{}, len(src))
		for key, value := range src {
			dst[key] = value
		}
	}
	return dst
}

func getStepAttempt(execCtx *wfcontext.ExecutionContext, nodeID string) int {
	if execCtx == nil {
		return 1
	}
	if nodeID != "" {
		if v, ok := execCtx.GetInt(fmt.Sprintf("step_attempts.%s", nodeID)); ok && v > 0 {
			return v
		}
	}
	if v, ok := execCtx.GetInt("step_attempt"); ok && v > 0 {
		return v
	}
	return 1
}

func extractPublicationAuth(execCtx *wfcontext.ExecutionContext) *PublicationAuth {
	if execCtx == nil {
		return nil
	}
	raw, ok := execCtx.Get("publication_auth")
	if !ok {
		return nil
	}
	payload, ok := raw.(map[string]interface{})
	if !ok {
		return nil
	}
	strategy := strings.ToLower(strings.TrimSpace(readContextString(payload["strategy"])))
	actorUsername := strings.TrimSpace(readContextString(payload["actor_username"]))
	source := strings.TrimSpace(readContextString(payload["source"]))
	if strategy == "" && actorUsername == "" && source == "" {
		return nil
	}
	return &PublicationAuth{
		Strategy:      strategy,
		ActorUsername: actorUsername,
		Source:        source,
	}
}

func readContextString(value interface{}) string {
	if value == nil {
		return ""
	}
	return fmt.Sprintf("%v", value)
}

// OperationNodeConfigFromJSON parses operation config from JSON.
func OperationNodeConfigFromJSON(data []byte) (*models.OperationNodeConfig, error) {
	var config models.OperationNodeConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse operation config: %w", err)
	}
	return &config, nil
}

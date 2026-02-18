package poolops

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	workerodata "github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
)

const (
	defaultPublicationEntityName       = "Document_РеализацияТоваровУслуг"
	defaultPublicationExternalKeyField = "ExternalRunKey"
	defaultPublicationMaxAttempts      = 5
	defaultPublicationRetryIntervalSec = 0
	defaultPublicationRetryIntervalCap = 120
)

const (
	ErrorCodePoolRuntimePublicationPayloadInvalid       = "POOL_RUNTIME_PUBLICATION_PAYLOAD_INVALID"
	ErrorCodePoolRuntimePublicationCredentialsError     = "POOL_RUNTIME_PUBLICATION_CREDENTIALS_ERROR"
	ErrorCodePoolRuntimePublicationTransportFailed      = "POOL_RUNTIME_PUBLICATION_ODATA_FAILED"
	ErrorCodePoolRuntimePublicationCompatibilityBlocked = "POOL_RUNTIME_PUBLICATION_COMPATIBILITY_BLOCKED"
	ErrorCodeODataMappingNotConfigured                  = "ODATA_MAPPING_NOT_CONFIGURED"
	ErrorCodeODataMappingAmbiguous                      = "ODATA_MAPPING_AMBIGUOUS"
	ErrorCodeODataPublicationAuthContextInvalid         = "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID"
)

const (
	publicationAuthStrategyActor        = "actor"
	publicationAuthStrategyService      = "service"
	publicationCredentialsPurpose       = "pool_publication_odata"
	resolutionOutcomeActorSuccess       = "actor_success"
	resolutionOutcomeServiceSuccess     = "service_success"
	resolutionOutcomeMissingMapping     = "missing_mapping"
	resolutionOutcomeAmbiguousMapping   = "ambiguous_mapping"
	resolutionOutcomeInvalidAuthContext = "invalid_auth_context"
)

type publicationODataService interface {
	Create(
		ctx context.Context,
		creds sharedodata.ODataCredentials,
		entity string,
		data map[string]interface{},
	) (map[string]interface{}, error)
	Update(
		ctx context.Context,
		creds sharedodata.ODataCredentials,
		entity, entityID string,
		data map[string]interface{},
	) error
}

// PublicationTransportConfig controls publication transport defaults.
type PublicationTransportConfig struct {
	DefaultEntityName                  string
	DefaultMaxAttempts                 int
	DefaultRetryIntervalSec            int
	MaxRetryIntervalSec                int
	Timeline                           tracing.TimelineRecorder
	CompatibilityProfilePath           string
	CompatibilityConfigurationID       string
	CompatibilityMode                  string
	CompatibilityWriteContentType      string
	CompatibilityReleaseProfileVersion string
}

// ODataPublicationTransport executes pool.publication_odata locally through shared odata service.
type ODataPublicationTransport struct {
	credsClient credentials.Fetcher
	service     publicationODataService
	logger      *zap.Logger
	timeline    tracing.TimelineRecorder
	cfg         PublicationTransportConfig
}

type publicationTransportFailure struct {
	err        error
	normalized workerodata.NormalizedError
}

type publicationTargetAttempt struct {
	AttemptNumber   int
	Status          string
	DocumentsCount  int
	Posted          bool
	ErrorCode       string
	ErrorMessage    string
	HTTPStatus      *int
	RequestSummary  map[string]interface{}
	ResponseSummary map[string]interface{}
}

type publicationTargetResult struct {
	Attempts []publicationTargetAttempt
}

type publicationAuthContext struct {
	Strategy      string
	ActorUsername string
	Source        string
}

func (r publicationTargetResult) attemptsCount() int {
	return len(r.Attempts)
}

func (e *publicationTransportFailure) Error() string {
	if e == nil || e.err == nil {
		return ""
	}
	return e.err.Error()
}

func (e *publicationTransportFailure) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.err
}

func NewODataPublicationTransport(
	credsClient credentials.Fetcher,
	service publicationODataService,
	logger *zap.Logger,
	cfg PublicationTransportConfig,
) *ODataPublicationTransport {
	if logger == nil {
		logger = zap.NewNop()
	}
	if cfg.Timeline == nil {
		cfg.Timeline = tracing.NewNoopTimeline()
	}
	if strings.TrimSpace(cfg.DefaultEntityName) == "" {
		cfg.DefaultEntityName = defaultPublicationEntityName
	}
	if cfg.DefaultMaxAttempts <= 0 {
		cfg.DefaultMaxAttempts = defaultPublicationMaxAttempts
	}
	if cfg.DefaultRetryIntervalSec < 0 {
		cfg.DefaultRetryIntervalSec = defaultPublicationRetryIntervalSec
	}
	if cfg.MaxRetryIntervalSec <= 0 {
		cfg.MaxRetryIntervalSec = defaultPublicationRetryIntervalCap
	}
	if strings.TrimSpace(cfg.CompatibilityConfigurationID) == "" {
		cfg.CompatibilityConfigurationID = defaultPublicationCompatibilityConfigurationID
	}
	if strings.TrimSpace(cfg.CompatibilityWriteContentType) == "" {
		cfg.CompatibilityWriteContentType = defaultPublicationWriteContentType
	}
	return &ODataPublicationTransport{
		credsClient: credsClient,
		service:     service,
		logger:      logger.Named("poolops_publication_transport"),
		timeline:    cfg.Timeline,
		cfg:         cfg,
	}
}

func (t *ODataPublicationTransport) ExecutePublicationOData(
	ctx context.Context,
	req *handlers.OperationRequest,
) (map[string]interface{}, error) {
	if req == nil {
		return nil, ErrNilOperationRequest
	}
	if t.credsClient == nil || t.service == nil {
		return nil, handlers.NewOperationExecutionError(
			handlers.ErrorCodeWorkflowOperationExecutorNotConfigured,
			"publication odata transport dependencies are not configured",
		)
	}
	publicationAuth, err := parsePublicationAuthContext(req)
	if err != nil {
		t.logger.Warn("publication auth context validation failed",
			zap.String("resolution_outcome", resolutionOutcomeInvalidAuthContext),
			zap.Error(err),
		)
		return nil, err
	}

	publicationPayload := resolvePublicationPayload(req.Payload)
	documentsByDatabase, err := normalizeDocumentsByDatabase(publicationPayload["documents_by_database"])
	if err != nil {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolRuntimePublicationPayloadInvalid,
			err.Error(),
		)
	}

	entityName := readOptionalString(publicationPayload["entity_name"])
	if entityName == "" {
		entityName = t.cfg.DefaultEntityName
	}
	externalKeyField := readOptionalString(publicationPayload["external_key_field"])
	if externalKeyField == "" {
		externalKeyField = defaultPublicationExternalKeyField
	}

	compatibilityInput := resolvePublicationCompatibilityInput(publicationPayload, t.cfg)
	compatibilityReport, err := runPublicationCompatibilityGate(compatibilityInput)
	if err != nil {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolRuntimePublicationCompatibilityBlocked,
			err.Error(),
		)
	}
	t.logger.Info("publication compatibility profile validated",
		zap.String("configuration_id", compatibilityReport.ConfigurationID),
		zap.String("profile_version", compatibilityReport.ProfileVersion),
		zap.String("release_profile_version", compatibilityReport.ReleaseProfileVersion),
		zap.String("write_content_type", compatibilityReport.WriteContentType),
	)

	maxAttempts, err := t.readMaxAttempts(publicationPayload["max_attempts"])
	if err != nil {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolRuntimePublicationPayloadInvalid,
			err.Error(),
		)
	}
	retryIntervalSec, err := t.readRetryInterval(publicationPayload["retry_interval_seconds"])
	if err != nil {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolRuntimePublicationPayloadInvalid,
			err.Error(),
		)
	}

	if len(documentsByDatabase) == 0 {
		return map[string]interface{}{
			"step":                        "publication_odata",
			"pool_run_id":                 req.PoolRunID,
			"status":                      "skipped_no_targets",
			"entity_name":                 entityName,
			"documents_targets":           0,
			"max_attempts":                maxAttempts,
			"target_databases":            []string{},
			"documents_count_by_database": map[string]int{},
			"attempts":                    []map[string]interface{}{},
		}, nil
	}

	targetDatabases := make([]string, 0, len(documentsByDatabase))
	documentsCountByDatabase := make(map[string]int, len(documentsByDatabase))
	for databaseID, documents := range documentsByDatabase {
		targetDatabases = append(targetDatabases, databaseID)
		documentsCountByDatabase[databaseID] = len(documents)
	}
	sort.Strings(targetDatabases)

	succeededTargets := 0
	failedTargets := 0
	failedDatabases := map[string]string{}
	failedDatabasesDiagnostics := map[string]map[string]interface{}{}
	attempts := make([]map[string]interface{}, 0)

	for _, databaseID := range targetDatabases {
		documents := documentsByDatabase[databaseID]
		targetResult, publishErr := t.publishTargetWithRetries(
			ctx,
			req,
			publicationAuth,
			databaseID,
			entityName,
			externalKeyField,
			documents,
			maxAttempts,
			retryIntervalSec,
		)
		for _, attempt := range targetResult.Attempts {
			attempts = append(attempts, publicationAttemptToMap(databaseID, entityName, attempt))
		}
		if publishErr != nil {
			failedTargets++
			failedDatabases[databaseID] = publishErr.Error()
			normalized := normalizePublicationFailure(publishErr)
			failedDatabasesDiagnostics[databaseID] = map[string]interface{}{
				"error":        publishErr.Error(),
				"error_code":   normalized.Code,
				"error_class":  normalized.Class,
				"status_class": normalized.StatusClass(),
				"retryable":    normalized.Retryable,
				"attempts":     targetResult.attemptsCount(),
			}
			t.logger.Warn("publication target failed",
				zap.String("database_id", databaseID),
				zap.String("error_code", normalized.Code),
				zap.String("error_class", normalized.Class),
				zap.String("status_class", normalized.StatusClass()),
				zap.Bool("retryable", normalized.Retryable),
				zap.Error(publishErr),
			)
			continue
		}
		succeededTargets++
	}

	status := "published"
	if failedTargets > 0 {
		if succeededTargets > 0 {
			status = "partial_success"
		} else {
			status = "failed"
		}
	}

	result := map[string]interface{}{
		"step":                        "publication_odata",
		"pool_run_id":                 req.PoolRunID,
		"status":                      status,
		"entity_name":                 entityName,
		"documents_targets":           len(documentsByDatabase),
		"succeeded_targets":           succeededTargets,
		"failed_targets":              failedTargets,
		"max_attempts":                maxAttempts,
		"target_databases":            targetDatabases,
		"documents_count_by_database": documentsCountByDatabase,
		"attempts":                    attempts,
	}
	if len(failedDatabases) > 0 {
		result["failed_databases"] = failedDatabases
		result["failed_databases_diagnostics"] = failedDatabasesDiagnostics
	}
	return result, nil
}

func (t *ODataPublicationTransport) publishTargetWithRetries(
	ctx context.Context,
	req *handlers.OperationRequest,
	publicationAuth publicationAuthContext,
	databaseID string,
	entityName string,
	externalKeyField string,
	documents []map[string]interface{},
	maxAttempts int,
	retryIntervalSec int,
) (publicationTargetResult, error) {
	result := publicationTargetResult{
		Attempts: make([]publicationTargetAttempt, 0, maxAttempts),
	}
	credsCtx := t.withPublicationCredentialsContext(ctx, publicationAuth)
	creds, err := t.credsClient.Fetch(credsCtx, databaseID)
	if err != nil {
		errorCode := mapPublicationCredentialsErrorCode(err)
		t.logger.Warn("publication credentials lookup failed",
			zap.String("database_id", databaseID),
			zap.String("error_code", errorCode),
			zap.String("auth_strategy", publicationAuth.Strategy),
			zap.String("auth_source", publicationAuth.Source),
			zap.String("resolution_outcome", mapPublicationResolutionOutcome(errorCode, publicationAuth)),
			zap.Error(err),
		)
		operationErr := handlers.NewOperationExecutionError(
			errorCode,
			fmt.Sprintf("failed to fetch credentials for %s: %v", databaseID, err),
		)
		return result, newPublicationTransportFailure(operationErr, workerodata.NormalizeErrorCode(operationErr.Code))
	}
	if creds == nil || strings.TrimSpace(creds.ODataURL) == "" || strings.TrimSpace(creds.Username) == "" || strings.TrimSpace(creds.Password) == "" {
		t.logger.Warn("publication credentials lookup returned incomplete mapping",
			zap.String("database_id", databaseID),
			zap.String("auth_strategy", publicationAuth.Strategy),
			zap.String("auth_source", publicationAuth.Source),
			zap.String("resolution_outcome", resolutionOutcomeMissingMapping),
		)
		operationErr := handlers.NewOperationExecutionError(
			ErrorCodeODataMappingNotConfigured,
			fmt.Sprintf("odata mapping credentials are not configured for %s", databaseID),
		)
		return result, newPublicationTransportFailure(operationErr, workerodata.NormalizeErrorCode(operationErr.Code))
	}
	t.logger.Info("publication credentials lookup resolved",
		zap.String("database_id", databaseID),
		zap.String("auth_strategy", publicationAuth.Strategy),
		zap.String("auth_source", publicationAuth.Source),
		zap.String("resolution_outcome", mapPublicationResolutionOutcome("", publicationAuth)),
	)

	odataCreds := sharedodata.ODataCredentials{
		BaseURL:  creds.ODataURL,
		Username: creds.Username,
		Password: creds.Password,
	}
	ctx = t.withTransportTelemetry(ctx, req, databaseID, entityName)

	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		lastErr = t.publishDocumentsOnce(
			ctx,
			req,
			databaseID,
			entityName,
			externalKeyField,
			documents,
			odataCreds,
		)
		if lastErr == nil {
			result.Attempts = append(result.Attempts, publicationTargetAttempt{
				AttemptNumber:  attempt,
				Status:         "success",
				DocumentsCount: len(documents),
				Posted:         true,
				RequestSummary: map[string]interface{}{
					"documents_count": len(documents),
				},
				ResponseSummary: map[string]interface{}{
					"posted": true,
				},
			})
			return result, nil
		}
		normalized := workerodata.NormalizeError(lastErr)
		failedAttempt := publicationTargetAttempt{
			AttemptNumber:  attempt,
			Status:         "failed",
			DocumentsCount: len(documents),
			Posted:         false,
			ErrorCode:      normalized.Code,
			ErrorMessage:   lastErr.Error(),
			RequestSummary: map[string]interface{}{
				"documents_count": len(documents),
			},
			ResponseSummary: map[string]interface{}{},
		}
		if normalized.StatusCode > 0 {
			statusCode := normalized.StatusCode
			failedAttempt.HTTPStatus = &statusCode
		}
		result.Attempts = append(result.Attempts, failedAttempt)
		if !isRetryablePublicationErr(lastErr) || attempt == maxAttempts {
			operationErr := handlers.NewOperationExecutionError(
				ErrorCodePoolRuntimePublicationTransportFailed,
				lastErr.Error(),
			)
			return result, newPublicationTransportFailure(operationErr, normalized)
		}
		baseDelay := time.Duration(retryIntervalSec) * time.Second
		waitDelay := workerodata.ComputeExponentialBackoffWithJitter(baseDelay, attempt)
		t.logger.Info("publication transport retry scheduled",
			zap.String("database_id", databaseID),
			zap.Int("attempt", attempt),
			zap.Int("max_attempts", maxAttempts),
			zap.String("error_code", normalized.Code),
			zap.String("error_class", normalized.Class),
			zap.String("status_class", normalized.StatusClass()),
			zap.Bool("retryable", normalized.Retryable),
			zap.Duration("backoff", waitDelay),
		)
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		case <-time.After(waitDelay):
		}
	}
	if lastErr == nil {
		return result, nil
	}
	return result, handlers.NewOperationExecutionError(
		ErrorCodePoolRuntimePublicationTransportFailed,
		lastErr.Error(),
	)
}

func (t *ODataPublicationTransport) publishDocumentsOnce(
	ctx context.Context,
	req *handlers.OperationRequest,
	databaseID string,
	entityName string,
	externalKeyField string,
	documents []map[string]interface{},
	creds sharedodata.ODataCredentials,
) error {
	for idx, doc := range documents {
		documentPayload := cloneMap(doc)
		if externalKeyField != "" {
			if _, exists := documentPayload[externalKeyField]; !exists {
				documentPayload[externalKeyField] = buildExternalRunKey(
					req.PoolRunID,
					databaseID,
					entityName,
					req.StepAttempt,
					idx,
				)
			}
		}

		created, err := t.service.Create(ctx, creds, entityName, documentPayload)
		if err != nil {
			return err
		}

		documentRef := extractDocumentRef(created)
		if documentRef == "" {
			continue
		}

		err = t.service.Update(ctx, creds, entityName, guidLiteral(documentRef), map[string]interface{}{"Posted": true})
		if err != nil {
			return err
		}
	}
	return nil
}

func (t *ODataPublicationTransport) readMaxAttempts(value interface{}) (int, error) {
	if value == nil {
		return t.cfg.DefaultMaxAttempts, nil
	}
	parsed, ok := readInt(value)
	if !ok || parsed <= 0 || parsed > defaultPublicationMaxAttempts {
		return 0, fmt.Errorf("max_attempts must be in range 1..%d", defaultPublicationMaxAttempts)
	}
	return parsed, nil
}

func (t *ODataPublicationTransport) readRetryInterval(value interface{}) (int, error) {
	if value == nil {
		return t.cfg.DefaultRetryIntervalSec, nil
	}
	parsed, ok := readInt(value)
	if !ok || parsed < 0 {
		return 0, fmt.Errorf("retry_interval_seconds must be >= 0")
	}
	if parsed > t.cfg.MaxRetryIntervalSec {
		return 0, fmt.Errorf("retry_interval_seconds must be <= %d", t.cfg.MaxRetryIntervalSec)
	}
	return parsed, nil
}

func parsePublicationAuthContext(req *handlers.OperationRequest) (publicationAuthContext, error) {
	if req == nil || req.PublicationAuth == nil {
		return publicationAuthContext{}, handlers.NewOperationExecutionError(
			ErrorCodeODataPublicationAuthContextInvalid,
			"publication_auth context is required for pool.publication_odata",
		)
	}
	strategy := strings.ToLower(strings.TrimSpace(req.PublicationAuth.Strategy))
	actorUsername := strings.TrimSpace(req.PublicationAuth.ActorUsername)
	source := strings.TrimSpace(req.PublicationAuth.Source)
	if source == "" {
		return publicationAuthContext{}, handlers.NewOperationExecutionError(
			ErrorCodeODataPublicationAuthContextInvalid,
			"publication_auth.source is required",
		)
	}
	switch strategy {
	case publicationAuthStrategyActor:
		if actorUsername == "" {
			return publicationAuthContext{}, handlers.NewOperationExecutionError(
				ErrorCodeODataPublicationAuthContextInvalid,
				"publication_auth.actor_username is required for actor strategy",
			)
		}
	case publicationAuthStrategyService:
		actorUsername = ""
	default:
		return publicationAuthContext{}, handlers.NewOperationExecutionError(
			ErrorCodeODataPublicationAuthContextInvalid,
			"publication_auth.strategy must be actor|service",
		)
	}
	return publicationAuthContext{
		Strategy:      strategy,
		ActorUsername: actorUsername,
		Source:        source,
	}, nil
}

func (t *ODataPublicationTransport) withPublicationCredentialsContext(
	ctx context.Context,
	publicationAuth publicationAuthContext,
) context.Context {
	credsCtx := credentials.WithCredentialsPurpose(ctx, publicationCredentialsPurpose)
	credsCtx = credentials.WithIbAuthStrategy(credsCtx, publicationAuth.Strategy)
	if publicationAuth.Strategy == publicationAuthStrategyActor {
		credsCtx = credentials.WithRequestedBy(credsCtx, publicationAuth.ActorUsername)
	}
	return credsCtx
}

func mapPublicationCredentialsErrorCode(err error) string {
	if err == nil {
		return ErrorCodePoolRuntimePublicationCredentialsError
	}
	message := strings.ToUpper(strings.TrimSpace(err.Error()))
	switch {
	case strings.Contains(message, ErrorCodeODataMappingAmbiguous):
		return ErrorCodeODataMappingAmbiguous
	case strings.Contains(message, ErrorCodeODataMappingNotConfigured):
		return ErrorCodeODataMappingNotConfigured
	case strings.Contains(message, ErrorCodeODataPublicationAuthContextInvalid):
		return ErrorCodeODataPublicationAuthContextInvalid
	default:
		return ErrorCodePoolRuntimePublicationCredentialsError
	}
}

func mapPublicationResolutionOutcome(
	errorCode string,
	publicationAuth publicationAuthContext,
) string {
	switch strings.TrimSpace(errorCode) {
	case ErrorCodeODataMappingAmbiguous:
		return resolutionOutcomeAmbiguousMapping
	case ErrorCodeODataPublicationAuthContextInvalid:
		return resolutionOutcomeInvalidAuthContext
	case ErrorCodeODataMappingNotConfigured:
		return resolutionOutcomeMissingMapping
	}
	if publicationAuth.Strategy == publicationAuthStrategyActor {
		return resolutionOutcomeActorSuccess
	}
	return resolutionOutcomeServiceSuccess
}

func resolvePublicationPayload(payload map[string]interface{}) map[string]interface{} {
	if payload == nil {
		return map[string]interface{}{}
	}
	poolRuntime, ok := payload["pool_runtime"].(map[string]interface{})
	if ok {
		return poolRuntime
	}
	return payload
}

func normalizeDocumentsByDatabase(value interface{}) (map[string][]map[string]interface{}, error) {
	if value == nil {
		return map[string][]map[string]interface{}{}, nil
	}

	if typed, ok := value.(map[string][]map[string]interface{}); ok {
		return typed, nil
	}

	src, ok := value.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("documents_by_database must be an object")
	}

	result := make(map[string][]map[string]interface{}, len(src))
	for rawDatabaseID, rawDocs := range src {
		databaseID := strings.TrimSpace(rawDatabaseID)
		if databaseID == "" {
			return nil, fmt.Errorf("documents_by_database contains empty database id")
		}

		docsSlice, ok := rawDocs.([]interface{})
		if !ok {
			return nil, fmt.Errorf("documents_by_database[%s] must be a list", databaseID)
		}

		docs := make([]map[string]interface{}, 0, len(docsSlice))
		for _, rawDoc := range docsSlice {
			doc, ok := rawDoc.(map[string]interface{})
			if !ok {
				return nil, fmt.Errorf("documents_by_database[%s] contains non-object item", databaseID)
			}
			docs = append(docs, cloneMap(doc))
		}

		result[databaseID] = docs
	}
	return result, nil
}

func readOptionalString(value interface{}) string {
	str, ok := value.(string)
	if !ok {
		return ""
	}
	return strings.TrimSpace(str)
}

func readInt(value interface{}) (int, bool) {
	switch v := value.(type) {
	case int:
		return v, true
	case int8:
		return int(v), true
	case int16:
		return int(v), true
	case int32:
		return int(v), true
	case int64:
		return int(v), true
	case float32:
		return int(v), float32(int(v)) == v
	case float64:
		return int(v), float64(int(v)) == v
	default:
		return 0, false
	}
}

func cloneMap(src map[string]interface{}) map[string]interface{} {
	if src == nil {
		return map[string]interface{}{}
	}
	out := make(map[string]interface{}, len(src))
	for k, v := range src {
		out[k] = v
	}
	return out
}

func publicationAttemptToMap(databaseID, entityName string, attempt publicationTargetAttempt) map[string]interface{} {
	out := map[string]interface{}{
		"target_database":  databaseID,
		"attempt_number":   attempt.AttemptNumber,
		"status":           attempt.Status,
		"entity_name":      entityName,
		"documents_count":  attempt.DocumentsCount,
		"posted":           attempt.Posted,
		"request_summary":  cloneMap(attempt.RequestSummary),
		"response_summary": cloneMap(attempt.ResponseSummary),
	}
	if attempt.ErrorCode != "" {
		out["error_code"] = attempt.ErrorCode
	}
	if attempt.ErrorMessage != "" {
		out["error_message"] = attempt.ErrorMessage
	}
	if attempt.HTTPStatus != nil {
		out["http_status"] = *attempt.HTTPStatus
	}
	return out
}

func extractDocumentRef(created map[string]interface{}) string {
	if created == nil {
		return ""
	}
	if value, ok := created["Ref_Key"].(string); ok {
		return strings.TrimSpace(value)
	}
	if value, ok := created["_IDRRef"].(string); ok {
		return strings.TrimSpace(value)
	}
	return ""
}

func guidLiteral(raw string) string {
	normalized := strings.TrimSpace(raw)
	if normalized == "" {
		return ""
	}
	if strings.HasPrefix(normalized, "guid'") && strings.HasSuffix(normalized, "'") {
		return normalized
	}
	return fmt.Sprintf("guid'%s'", normalized)
}

func buildExternalRunKey(runID, databaseID, entityName string, stepAttempt int, idx int) string {
	source := strings.Join([]string{
		strings.TrimSpace(runID),
		strings.TrimSpace(databaseID),
		strings.TrimSpace(entityName),
		fmt.Sprintf("%d", stepAttempt),
		fmt.Sprintf("%d", idx),
	}, ":")
	sum := sha256.Sum256([]byte(source))
	return "runkey-" + hex.EncodeToString(sum[:16])
}

func isRetryablePublicationErr(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.Canceled) {
		return false
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	return workerodata.IsTransient(err)
}

func newPublicationTransportFailure(err error, normalized workerodata.NormalizedError) error {
	if err == nil {
		return nil
	}
	if strings.TrimSpace(normalized.Code) == "" {
		normalized = workerodata.NormalizeError(err)
	}
	if strings.TrimSpace(normalized.Message) == "" {
		normalized.Message = err.Error()
	}
	return &publicationTransportFailure{
		err:        err,
		normalized: normalized,
	}
}

func normalizePublicationFailure(err error) workerodata.NormalizedError {
	var transportErr *publicationTransportFailure
	if errors.As(err, &transportErr) {
		return transportErr.normalized
	}
	var operationErr *handlers.OperationExecutionError
	if errors.As(err, &operationErr) {
		normalized := workerodata.NormalizeErrorCode(operationErr.Code)
		if strings.TrimSpace(normalized.Message) == "" {
			normalized.Message = operationErr.Message
		}
		return normalized
	}
	return workerodata.NormalizeError(err)
}

func (t *ODataPublicationTransport) withTransportTelemetry(
	ctx context.Context,
	req *handlers.OperationRequest,
	databaseID string,
	entityName string,
) context.Context {
	if req == nil {
		return workerodata.WithTransportTelemetry(ctx, workerodata.TransportTelemetry{
			Operation:  "pool.publication_odata",
			DatabaseID: strings.TrimSpace(databaseID),
			Entity:     strings.TrimSpace(entityName),
		})
	}

	var traceFn workerodata.TransportTraceFunc
	traceOperationID := strings.TrimSpace(req.OperationID)
	if traceOperationID == "" {
		traceOperationID = strings.TrimSpace(req.ExecutionID)
	}
	if t.timeline != nil && traceOperationID != "" {
		stepAttempt := req.StepAttempt
		idempotencyKey := strings.TrimSpace(req.IdempotencyKey)
		traceFn = func(traceCtx context.Context, event string, metadata map[string]interface{}) {
			payload := make(map[string]interface{}, len(metadata)+2)
			for key, value := range metadata {
				payload[key] = value
			}
			if stepAttempt > 0 {
				payload["step_attempt"] = stepAttempt
			}
			if idempotencyKey != "" {
				payload["idempotency_key"] = idempotencyKey
			}
			t.timeline.Record(traceCtx, traceOperationID, event, payload)
		}
	}

	return workerodata.WithTransportTelemetry(ctx, workerodata.TransportTelemetry{
		Operation:   "pool.publication_odata",
		ExecutionID: strings.TrimSpace(req.ExecutionID),
		NodeID:      strings.TrimSpace(req.NodeID),
		DatabaseID:  strings.TrimSpace(databaseID),
		Entity:      strings.TrimSpace(entityName),
		Trace:       traceFn,
	})
}

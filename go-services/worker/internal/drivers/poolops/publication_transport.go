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
	invoiceModeOptional                = "optional"
	invoiceModeRequired                = "required"
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

type publicationDocument struct {
	ChainID           string
	DocumentID        string
	DocumentRole      string
	InvoiceMode       string
	LinkTo            string
	EntityName        string
	IdempotencyKey    string
	Payload           map[string]interface{}
	Allocation        map[string]interface{}
	FieldMapping      map[string]interface{}
	TablePartsMapping map[string]interface{}
	LinkRules         map[string]interface{}
	ResolvedLinkRefs  map[string]string
}

type publicationDocumentsExecutionResult struct {
	SuccessfulDocumentKeys []string
	SuccessfulDocumentRefs map[string]string
	FailedDocumentKey      string
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
	chainedDocumentsByDatabase, err := normalizeDocumentChainsByDatabase(
		publicationPayload["document_chains_by_database"],
	)
	if err != nil {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolRuntimePublicationPayloadInvalid,
			err.Error(),
		)
	}
	legacyDocumentsByDatabase, err := normalizeDocumentsByDatabase(publicationPayload["documents_by_database"])
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
	documentsByDatabase := chainedDocumentsByDatabase
	if len(documentsByDatabase) == 0 {
		documentsByDatabase = toPublicationDocumentsByDatabase(entityName, legacyDocumentsByDatabase)
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
	documents []publicationDocument,
	maxAttempts int,
	retryIntervalSec int,
) (publicationTargetResult, error) {
	result := publicationTargetResult{
		Attempts: make([]publicationTargetAttempt, 0, maxAttempts),
	}
	requestDocumentKeys := collectDocumentIdempotencyKeys(entityName, documents)
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
		publishResult, publishErr := t.publishDocumentsOnce(
			ctx,
			req,
			databaseID,
			entityName,
			externalKeyField,
			documents,
			odataCreds,
		)
		lastErr = publishErr
		requestSummary := map[string]interface{}{
			"documents_count": len(documents),
		}
		if len(requestDocumentKeys) > 0 {
			requestSummary["document_idempotency_keys"] = append([]string(nil), requestDocumentKeys...)
		}
		if lastErr == nil {
			responseSummary := map[string]interface{}{
				"posted": true,
			}
			if len(publishResult.SuccessfulDocumentKeys) > 0 {
				responseSummary["successful_document_idempotency_keys"] = append(
					[]string(nil),
					publishResult.SuccessfulDocumentKeys...,
				)
			}
			if len(publishResult.SuccessfulDocumentRefs) > 0 {
				successfulDocumentRefs := make(map[string]interface{}, len(publishResult.SuccessfulDocumentRefs))
				for key, value := range publishResult.SuccessfulDocumentRefs {
					documentKey := strings.TrimSpace(key)
					documentRef := strings.TrimSpace(value)
					if documentKey == "" || documentRef == "" {
						continue
					}
					successfulDocumentRefs[documentKey] = documentRef
				}
				if len(successfulDocumentRefs) > 0 {
					responseSummary["successful_document_refs"] = successfulDocumentRefs
				}
			}
			result.Attempts = append(result.Attempts, publicationTargetAttempt{
				AttemptNumber:   attempt,
				Status:          "success",
				DocumentsCount:  len(documents),
				Posted:          true,
				RequestSummary:  requestSummary,
				ResponseSummary: responseSummary,
			})
			return result, nil
		}
		normalized := workerodata.NormalizeError(lastErr)
		responseSummary := map[string]interface{}{}
		if len(publishResult.SuccessfulDocumentKeys) > 0 {
			responseSummary["successful_document_idempotency_keys"] = append(
				[]string(nil),
				publishResult.SuccessfulDocumentKeys...,
			)
		}
		if len(publishResult.SuccessfulDocumentRefs) > 0 {
			successfulDocumentRefs := make(map[string]interface{}, len(publishResult.SuccessfulDocumentRefs))
			for key, value := range publishResult.SuccessfulDocumentRefs {
				documentKey := strings.TrimSpace(key)
				documentRef := strings.TrimSpace(value)
				if documentKey == "" || documentRef == "" {
					continue
				}
				successfulDocumentRefs[documentKey] = documentRef
			}
			if len(successfulDocumentRefs) > 0 {
				responseSummary["successful_document_refs"] = successfulDocumentRefs
			}
		}
		if strings.TrimSpace(publishResult.FailedDocumentKey) != "" {
			responseSummary["failed_document_idempotency_key"] = strings.TrimSpace(
				publishResult.FailedDocumentKey,
			)
		}
		failedAttempt := publicationTargetAttempt{
			AttemptNumber:   attempt,
			Status:          "failed",
			DocumentsCount:  len(documents),
			Posted:          false,
			ErrorCode:       normalized.Code,
			ErrorMessage:    lastErr.Error(),
			RequestSummary:  requestSummary,
			ResponseSummary: responseSummary,
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
	documents []publicationDocument,
	creds sharedodata.ODataCredentials,
) (publicationDocumentsExecutionResult, error) {
	result := publicationDocumentsExecutionResult{
		SuccessfulDocumentKeys: make([]string, 0, len(documents)),
		SuccessfulDocumentRefs: make(map[string]string, len(documents)),
	}
	createdDocumentRefsByChain := map[string]map[string]string{}
	for idx, doc := range documents {
		documentPayload := cloneMap(doc.Payload)
		documentEntityName := strings.TrimSpace(doc.EntityName)
		if documentEntityName == "" {
			documentEntityName = entityName
		}
		chainScope := strings.TrimSpace(doc.ChainID)
		if chainScope == "" {
			chainScope = "__default__"
		}
		chainDocumentRefs, ok := createdDocumentRefsByChain[chainScope]
		if !ok {
			chainDocumentRefs = map[string]string{}
			createdDocumentRefsByChain[chainScope] = chainDocumentRefs
		}
		documentKey := resolvePublicationDocumentKey(entityName, doc, idx)
		resolvedPayload, resolveErr := resolveDocumentPayloadForPublication(
			documentPayload,
			doc,
			chainDocumentRefs,
		)
		if resolveErr != nil {
			result.FailedDocumentKey = documentKey
			return result, resolveErr
		}
		documentPayload = resolvedPayload
		if externalKeyField != "" {
			if _, exists := documentPayload[externalKeyField]; !exists {
				documentPayload[externalKeyField] = buildExternalRunKey(
					req.PoolRunID,
					databaseID,
					documentEntityName,
					req.StepAttempt,
					idx,
				)
			}
		}

		created, err := t.service.Create(ctx, creds, documentEntityName, documentPayload)
		if err != nil {
			result.FailedDocumentKey = documentKey
			return result, err
		}

		documentRef := extractDocumentRef(created)
		if documentRef == "" {
			continue
		}
		documentID := strings.TrimSpace(doc.DocumentID)
		if documentID != "" {
			chainDocumentRefs[documentID] = documentRef
		}

		err = t.service.Update(
			ctx,
			creds,
			documentEntityName,
			guidLiteral(documentRef),
			map[string]interface{}{"Posted": true},
		)
		if err != nil {
			result.FailedDocumentKey = documentKey
			return result, err
		}
		result.SuccessfulDocumentKeys = append(result.SuccessfulDocumentKeys, documentKey)
		result.SuccessfulDocumentRefs[documentKey] = documentRef
	}
	return result, nil
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

func toPublicationDocumentsByDatabase(
	entityName string,
	legacy map[string][]map[string]interface{},
) map[string][]publicationDocument {
	result := make(map[string][]publicationDocument, len(legacy))
	for databaseID, documents := range legacy {
		items := make([]publicationDocument, 0, len(documents))
		for _, document := range documents {
			items = append(items, publicationDocument{
				EntityName:     strings.TrimSpace(entityName),
				IdempotencyKey: "",
				Payload:        cloneMap(document),
			})
		}
		if len(items) > 0 {
			result[databaseID] = items
		}
	}
	return result
}

func normalizeDocumentChainsByDatabase(value interface{}) (map[string][]publicationDocument, error) {
	if value == nil {
		return map[string][]publicationDocument{}, nil
	}

	if typed, ok := value.(map[string][]publicationDocument); ok {
		return typed, nil
	}

	src, ok := value.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("document_chains_by_database must be an object")
	}

	result := make(map[string][]publicationDocument, len(src))
	for rawDatabaseID, rawChains := range src {
		databaseID := strings.TrimSpace(rawDatabaseID)
		if databaseID == "" {
			return nil, fmt.Errorf("document_chains_by_database contains empty database id")
		}

		chainsSlice, ok := rawChains.([]interface{})
		if !ok {
			return nil, fmt.Errorf("document_chains_by_database[%s] must be a list", databaseID)
		}

		docs := make([]publicationDocument, 0)
		for chainIdx, rawChain := range chainsSlice {
			chain, ok := rawChain.(map[string]interface{})
			if !ok {
				return nil, fmt.Errorf("document_chains_by_database[%s] contains non-object chain", databaseID)
			}
			chainID := readOptionalString(chain["chain_id"])
			if chainID == "" {
				chainID = fmt.Sprintf("__chain_%d", chainIdx)
			}
			allocation := readOptionalObject(chain["allocation"])
			rawDocuments, ok := chain["documents"].([]interface{})
			if !ok {
				return nil, fmt.Errorf("document_chains_by_database[%s].documents must be a list", databaseID)
			}
			chainDocumentIDs := map[string]struct{}{}
			chainDocuments := make([]publicationDocument, 0, len(rawDocuments))
			hasInvoiceDocument := false
			requiresInvoice := false
			for _, rawDocument := range rawDocuments {
				document, ok := rawDocument.(map[string]interface{})
				if !ok {
					return nil, fmt.Errorf("document_chains_by_database[%s] contains non-object document", databaseID)
				}
				documentID := readOptionalString(document["document_id"])
				if documentID != "" {
					chainDocumentIDs[documentID] = struct{}{}
				}
				documentRole := readOptionalString(document["document_role"])
				if strings.EqualFold(documentRole, "invoice") {
					hasInvoiceDocument = true
				}
				invoiceMode, invoiceModeErr := normalizeInvoiceMode(readOptionalString(document["invoice_mode"]))
				if invoiceModeErr != nil {
					return nil, fmt.Errorf(
						"document_chains_by_database[%s] has invalid invoice_mode: %v",
						databaseID,
						invoiceModeErr,
					)
				}
				if invoiceMode == invoiceModeRequired {
					requiresInvoice = true
					hasInvoiceDocument = true
				}
				entityName := readOptionalString(document["entity_name"])
				if entityName == "" {
					return nil, fmt.Errorf(
						"document_chains_by_database[%s] document entity_name must be a non-empty string",
						databaseID,
					)
				}
				payload, ok := document["payload"].(map[string]interface{})
				if !ok {
					return nil, fmt.Errorf(
						"document_chains_by_database[%s] document payload must be an object",
						databaseID,
					)
				}
				chainDocuments = append(chainDocuments, publicationDocument{
					ChainID:           chainID,
					DocumentID:        documentID,
					DocumentRole:      documentRole,
					InvoiceMode:       invoiceMode,
					LinkTo:            readOptionalString(document["link_to"]),
					EntityName:        entityName,
					IdempotencyKey:    readOptionalString(document["idempotency_key"]),
					Payload:           cloneMap(payload),
					Allocation:        allocation,
					FieldMapping:      readOptionalObject(document["field_mapping"]),
					TablePartsMapping: readOptionalObject(document["table_parts_mapping"]),
					LinkRules:         readOptionalObject(document["link_rules"]),
					ResolvedLinkRefs:  readOptionalStringMap(document["resolved_link_refs"]),
				})
			}
			if requiresInvoice && !hasInvoiceDocument {
				return nil, fmt.Errorf(
					"document_chains_by_database[%s] chain %s requires invoice document",
					databaseID,
					chainID,
				)
			}
			for _, document := range chainDocuments {
				linkTo := strings.TrimSpace(document.LinkTo)
				if linkTo == "" {
					continue
				}
				_, linkedInChain := chainDocumentIDs[linkTo]
				linkedRef := strings.TrimSpace(document.ResolvedLinkRefs[linkTo])
				if !linkedInChain && linkedRef == "" && strings.TrimSpace(document.InvoiceMode) == invoiceModeRequired {
					return nil, fmt.Errorf(
						"document_chains_by_database[%s] chain %s required invoice link_to %s is unresolved",
						databaseID,
						chainID,
						linkTo,
					)
				}
			}
			docs = append(docs, chainDocuments...)
		}
		if len(docs) > 0 {
			result[databaseID] = docs
		}
	}
	return result, nil
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

func collectDocumentIdempotencyKeys(
	defaultEntityName string,
	documents []publicationDocument,
) []string {
	keys := make([]string, 0, len(documents))
	for idx, document := range documents {
		keys = append(
			keys,
			resolvePublicationDocumentKey(defaultEntityName, document, idx),
		)
	}
	return keys
}

func resolvePublicationDocumentKey(
	defaultEntityName string,
	document publicationDocument,
	idx int,
) string {
	documentKey := strings.TrimSpace(document.IdempotencyKey)
	if documentKey != "" {
		return documentKey
	}
	entityName := strings.TrimSpace(document.EntityName)
	if entityName == "" {
		entityName = strings.TrimSpace(defaultEntityName)
	}
	if entityName == "" {
		entityName = defaultPublicationEntityName
	}
	return fmt.Sprintf("fallback:%s:%d", entityName, idx)
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

func readOptionalObject(value interface{}) map[string]interface{} {
	obj, ok := value.(map[string]interface{})
	if !ok {
		return map[string]interface{}{}
	}
	return cloneMap(obj)
}

func readOptionalStringMap(value interface{}) map[string]string {
	obj, ok := value.(map[string]interface{})
	if !ok {
		return map[string]string{}
	}
	out := make(map[string]string, len(obj))
	for rawKey, rawValue := range obj {
		key := strings.TrimSpace(rawKey)
		if key == "" {
			continue
		}
		ref := strings.TrimSpace(fmt.Sprintf("%v", rawValue))
		if ref == "" {
			continue
		}
		out[key] = ref
	}
	return out
}

func normalizeInvoiceMode(raw string) (string, error) {
	mode := strings.ToLower(strings.TrimSpace(raw))
	if mode == "" {
		return invoiceModeOptional, nil
	}
	if mode != invoiceModeOptional && mode != invoiceModeRequired {
		return "", fmt.Errorf("invoice_mode must be optional|required")
	}
	return mode, nil
}

func resolveDocumentPayloadForPublication(
	payload map[string]interface{},
	document publicationDocument,
	createdDocumentRefs map[string]string,
) (map[string]interface{}, error) {
	resolvedPayload := cloneMap(payload)
	applyFieldMappings(
		resolvedPayload,
		document.FieldMapping,
		document.Allocation,
		createdDocumentRefs,
		document.ResolvedLinkRefs,
	)
	applyTablePartsMappings(
		resolvedPayload,
		document.TablePartsMapping,
		document.Allocation,
		createdDocumentRefs,
		document.ResolvedLinkRefs,
	)
	if err := validateDocumentLinkage(
		document,
		resolvedPayload,
		createdDocumentRefs,
	); err != nil {
		return nil, err
	}
	return resolvedPayload, nil
}

func applyFieldMappings(
	payload map[string]interface{},
	fieldMapping map[string]interface{},
	allocation map[string]interface{},
	createdDocumentRefs map[string]string,
	resolvedLinkRefs map[string]string,
) {
	for rawFieldName, mappingValue := range fieldMapping {
		fieldName := strings.TrimSpace(rawFieldName)
		if fieldName == "" {
			continue
		}
		resolvedValue, ok := resolveMappingValue(
			mappingValue,
			allocation,
			createdDocumentRefs,
			resolvedLinkRefs,
		)
		if !ok {
			continue
		}
		payload[fieldName] = resolvedValue
	}
}

func applyTablePartsMappings(
	payload map[string]interface{},
	tablePartsMapping map[string]interface{},
	allocation map[string]interface{},
	createdDocumentRefs map[string]string,
	resolvedLinkRefs map[string]string,
) {
	for rawTableName, rawRows := range tablePartsMapping {
		tableName := strings.TrimSpace(rawTableName)
		if tableName == "" {
			continue
		}
		rows, ok := rawRows.([]interface{})
		if !ok {
			continue
		}
		compiledRows := make([]interface{}, 0, len(rows))
		for _, rawRow := range rows {
			row, ok := rawRow.(map[string]interface{})
			if !ok {
				continue
			}
			compiledRow := map[string]interface{}{}
			for rawColumnName, mappingValue := range row {
				columnName := strings.TrimSpace(rawColumnName)
				if columnName == "" {
					continue
				}
				resolvedValue, resolved := resolveMappingValue(
					mappingValue,
					allocation,
					createdDocumentRefs,
					resolvedLinkRefs,
				)
				if resolved {
					compiledRow[columnName] = resolvedValue
				}
			}
			if len(compiledRow) > 0 {
				compiledRows = append(compiledRows, compiledRow)
			}
		}
		if len(compiledRows) > 0 {
			payload[tableName] = compiledRows
		}
	}
}

func resolveMappingValue(
	mappingValue interface{},
	allocation map[string]interface{},
	createdDocumentRefs map[string]string,
	resolvedLinkRefs map[string]string,
) (interface{}, bool) {
	switch value := mappingValue.(type) {
	case string:
		token := strings.TrimSpace(value)
		if token == "" {
			return nil, false
		}
		if strings.HasPrefix(token, "allocation.") {
			path := strings.TrimSpace(strings.TrimPrefix(token, "allocation."))
			if path == "" {
				return nil, false
			}
			return resolveDottedPath(allocation, path)
		}
		if strings.HasSuffix(token, ".ref") {
			documentID := strings.TrimSpace(strings.TrimSuffix(token, ".ref"))
			if documentID == "" {
				return nil, false
			}
			if ref := strings.TrimSpace(createdDocumentRefs[documentID]); ref != "" {
				return ref, true
			}
			if ref := strings.TrimSpace(resolvedLinkRefs[documentID]); ref != "" {
				return ref, true
			}
			return nil, false
		}
		return token, true
	case map[string]interface{}:
		resolvedMap := map[string]interface{}{}
		for rawKey, nested := range value {
			key := strings.TrimSpace(rawKey)
			if key == "" {
				continue
			}
			resolvedValue, ok := resolveMappingValue(
				nested,
				allocation,
				createdDocumentRefs,
				resolvedLinkRefs,
			)
			if ok {
				resolvedMap[key] = resolvedValue
			}
		}
		return resolvedMap, len(resolvedMap) > 0
	case []interface{}:
		items := make([]interface{}, 0, len(value))
		for _, nested := range value {
			resolvedValue, ok := resolveMappingValue(
				nested,
				allocation,
				createdDocumentRefs,
				resolvedLinkRefs,
			)
			if ok {
				items = append(items, resolvedValue)
			}
		}
		return items, len(items) > 0
	case nil:
		return nil, false
	default:
		return value, true
	}
}

func resolveDottedPath(source map[string]interface{}, path string) (interface{}, bool) {
	current := interface{}(source)
	for _, rawPart := range strings.Split(path, ".") {
		part := strings.TrimSpace(rawPart)
		if part == "" {
			return nil, false
		}
		node, ok := current.(map[string]interface{})
		if !ok {
			return nil, false
		}
		next, exists := node[part]
		if !exists {
			return nil, false
		}
		current = next
	}
	return current, true
}

func validateDocumentLinkage(
	document publicationDocument,
	payload map[string]interface{},
	createdDocumentRefs map[string]string,
) error {
	invoiceMode := strings.TrimSpace(document.InvoiceMode)
	linkTo := strings.TrimSpace(document.LinkTo)

	if invoiceMode == invoiceModeRequired && linkTo == "" {
		return fmt.Errorf(
			"required invoice document %s must declare link_to",
			strings.TrimSpace(document.DocumentID),
		)
	}
	if linkTo != "" {
		linkedDocumentRef := strings.TrimSpace(createdDocumentRefs[linkTo])
		if linkedDocumentRef == "" {
			linkedDocumentRef = strings.TrimSpace(document.ResolvedLinkRefs[linkTo])
		}
		if linkedDocumentRef == "" && invoiceMode == invoiceModeRequired {
			return fmt.Errorf(
				"required invoice document %s has unresolved link_to reference %s",
				strings.TrimSpace(document.DocumentID),
				linkTo,
			)
		}
		if linkedDocumentRef != "" && invoiceMode == invoiceModeRequired && !payloadContainsValue(payload, linkedDocumentRef) {
			return fmt.Errorf(
				"required invoice document %s must include mapped link reference for %s",
				strings.TrimSpace(document.DocumentID),
				linkTo,
			)
		}
	}

	dependsOn := strings.TrimSpace(readOptionalString(document.LinkRules["depends_on"]))
	if dependsOn == "" {
		return nil
	}
	dependencyRef := strings.TrimSpace(createdDocumentRefs[dependsOn])
	if dependencyRef == "" {
		dependencyRef = strings.TrimSpace(document.ResolvedLinkRefs[dependsOn])
	}
	if dependencyRef == "" {
		return fmt.Errorf(
			"document %s depends_on unresolved document %s",
			strings.TrimSpace(document.DocumentID),
			dependsOn,
		)
	}
	return nil
}

func payloadContainsValue(value interface{}, expected string) bool {
	expectedValue := strings.TrimSpace(expected)
	if expectedValue == "" {
		return false
	}
	switch typed := value.(type) {
	case map[string]interface{}:
		for _, nested := range typed {
			if payloadContainsValue(nested, expectedValue) {
				return true
			}
		}
	case []interface{}:
		for _, nested := range typed {
			if payloadContainsValue(nested, expectedValue) {
				return true
			}
		}
	case string:
		return strings.TrimSpace(typed) == expectedValue
	}
	return false
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

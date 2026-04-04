package poolops

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	workerodata "github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
	"go.uber.org/zap"
)

const (
	factualSyncCredentialsPurpose            = "pool_factual_odata"
	defaultFactualQueryPageSize              = 500
	ErrorCodePoolFactualSyncPayloadInvalid   = "POOL_FACTUAL_SYNC_PAYLOAD_INVALID"
	ErrorCodePoolFactualSyncCredentialsError = "POOL_FACTUAL_SYNC_CREDENTIALS_ERROR"
	ErrorCodePoolFactualSyncODATAFailed      = "POOL_FACTUAL_SYNC_ODATA_FAILED"
)

type factualODataService interface {
	Query(
		ctx context.Context,
		creds sharedodata.ODataCredentials,
		entity string,
		query *sharedodata.QueryParams,
	) ([]map[string]interface{}, error)
}

type ODataFactualTransport struct {
	credsClient credentials.Fetcher
	service     factualODataService
	logger      *zap.Logger
}

type factualSyncInput struct {
	PoolID                   string
	DatabaseID               string
	Lane                     string
	QuarterStart             time.Time
	QuarterEnd               time.Time
	OrganizationIDs          []string
	AccountCodes             []string
	MovementKinds            []string
	DocumentEntities         []string
	AccountingRegisterEntity string
	AccountingFunction       string
	InformationRegister      string
	ScopeFingerprint         string
	ResolvedAccountRefs      []string
}

type factualScopeContract struct {
	ContractVersion string
	ScopeFingerprint string
	ResolvedBindings []factualResolvedBinding
}

type factualResolvedBinding struct {
	Code         string
	TargetRefKey string
}

func NewODataFactualTransport(
	credsClient credentials.Fetcher,
	service factualODataService,
	logger *zap.Logger,
) *ODataFactualTransport {
	if logger == nil {
		logger = zap.NewNop()
	}
	return &ODataFactualTransport{
		credsClient: credsClient,
		service:     service,
		logger:      logger.Named("poolops_factual_transport"),
	}
}

func (t *ODataFactualTransport) ExecuteFactualSyncSourceSlice(
	ctx context.Context,
	req *handlers.OperationRequest,
) (map[string]interface{}, error) {
	if req == nil {
		return nil, ErrNilOperationRequest
	}
	if t.credsClient == nil || t.service == nil {
		return nil, handlers.NewOperationExecutionError(
			handlers.ErrorCodeWorkflowOperationExecutorNotConfigured,
			"factual odata transport dependencies are not configured",
		)
	}

	input, err := parseFactualSyncInput(req.Payload)
	if err != nil {
		return nil, err
	}
	credsCtx := credentials.WithCredentialsPurpose(ctx, factualSyncCredentialsPurpose)
	creds, err := t.credsClient.Fetch(credsCtx, input.DatabaseID)
	if err != nil {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncCredentialsError,
			err.Error(),
		)
	}
	odataCreds := sharedodata.ODataCredentials{
		BaseURL:  strings.TrimSpace(creds.ODataURL),
		Username: strings.TrimSpace(creds.Username),
		Password: strings.TrimSpace(creds.Password),
	}
	if odataCreds.BaseURL == "" || odataCreds.Username == "" {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncCredentialsError,
			"factual sync requires OData URL and credentials",
		)
	}

	boundaryReads := map[string]int{}
	accountRefs := input.ResolvedAccountRefs
	if len(accountRefs) == 0 {
		accountRefs, err = resolveAccountCodeRefs(
			ctx,
			t.service,
			odataCreds,
			input.AccountingRegisterEntity,
			input.AccountCodes,
		)
		if err != nil {
			return nil, mapFactualODataError("chart_of_accounts", err)
		}
	}
	accountingRows, err := queryAllFactualRows(
		ctx,
		t.service,
		odataCreds,
		buildAccountingRegisterEntity(input, accountRefs),
		nil,
	)
	if err != nil {
		return nil, mapFactualODataError("accounting_register", err)
	}
	boundaryReads["accounting_register"] = len(accountingRows)

	informationRows, err := queryFactualProbeRows(
		ctx,
		t.service,
		odataCreds,
		input.InformationRegister,
	)
	if err != nil {
		return nil, mapFactualODataError("information_register", err)
	}
	boundaryReads["information_register"] = len(informationRows)

	documentRefsByEntity := collectRegisterDocumentRefsByEntity(accountingRows, input.DocumentEntities)
	factualDocuments := make([]map[string]interface{}, 0)
	for _, entity := range input.DocumentEntities {
		documentRefs := documentRefsByEntity[entity]
		if len(documentRefs) == 0 {
			boundaryReads[entity] = 0
			continue
		}
		rows, queryErr := queryFactualEntityRefs(
			ctx,
			t.service,
			odataCreds,
			documentRefs,
		)
		if queryErr != nil {
			return nil, mapFactualODataError(entity, queryErr)
		}
		boundaryReads[entity] = len(rows)
		factualDocuments = append(
			factualDocuments,
			normalizeFactualDocumentRows(entity, rows, input.OrganizationIDs)...,
		)
	}
	factualDocuments = applyAuthoritativeRegisterAmounts(
		factualDocuments,
		accountingRows,
		informationRows,
		input.MovementKinds,
	)

	sort.Slice(factualDocuments, func(i, j int) bool {
		left := strings.TrimSpace(fmt.Sprintf("%v", factualDocuments[i]["source_document_ref"]))
		right := strings.TrimSpace(fmt.Sprintf("%v", factualDocuments[j]["source_document_ref"]))
		return left < right
	})
	return map[string]interface{}{
		"step":                    "factual_sync_source_slice",
		"status":                  "completed",
		"pool_id":                 input.PoolID,
		"database_id":             input.DatabaseID,
		"lane":                    input.Lane,
		"quarter_start":           input.QuarterStart.Format("2006-01-02"),
		"quarter_end":             input.QuarterEnd.Format("2006-01-02"),
		"boundary_reads":          boundaryReads,
		"source_checkpoint_token": buildFactualSourceCheckpointToken(boundaryReads, factualDocuments),
		"factual_documents":       factualDocuments,
	}, nil
}

func parseFactualSyncInput(payload map[string]interface{}) (factualSyncInput, error) {
	if payload == nil {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"payload is required for pool.factual.sync_source_slice",
		)
	}
	quarterStart, err := time.Parse("2006-01-02", readRequiredString(payload, "quarter_start"))
	if err != nil {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"quarter_start must be an ISO date",
		)
	}
	quarterEnd, err := time.Parse("2006-01-02", readRequiredString(payload, "quarter_end"))
	if err != nil {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"quarter_end must be an ISO date",
		)
	}
	documentEntities := splitCSV(readRequiredString(payload, "document_entities"))
	if len(documentEntities) == 0 {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"document_entities must not be empty",
		)
	}
	organizationIDs := normalizeScopeTokens(splitCSV(readRequiredString(payload, "organization_ids")))
	if len(organizationIDs) == 0 {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"organization_ids must not be empty",
		)
	}
	accountCodes := normalizeScopeTokens(splitCSV(readRequiredString(payload, "account_codes")))
	if len(accountCodes) == 0 {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"account_codes must not be empty",
		)
	}
	scopeContract, err := parseFactualScopeContract(payload["factual_scope_contract"])
	if err != nil {
		return factualSyncInput{}, err
	}
	resolvedAccountRefs := make([]string, 0)
	if scopeContract != nil {
		bindingsByCode := make(map[string]string, len(scopeContract.ResolvedBindings))
		codes := make([]string, 0, len(scopeContract.ResolvedBindings))
		for _, binding := range scopeContract.ResolvedBindings {
			if _, exists := bindingsByCode[binding.Code]; exists {
				return factualSyncInput{}, handlers.NewOperationExecutionError(
					ErrorCodePoolFactualSyncPayloadInvalid,
					fmt.Sprintf("factual_scope_contract has duplicate binding for code '%s'", binding.Code),
				)
			}
			bindingsByCode[binding.Code] = binding.TargetRefKey
			codes = append(codes, binding.Code)
		}
		contractCodes := normalizeScopeTokens(codes)
		if strings.Join(accountCodes, ",") != strings.Join(contractCodes, ",") {
			return factualSyncInput{}, handlers.NewOperationExecutionError(
				ErrorCodePoolFactualSyncPayloadInvalid,
				"account_codes must match factual_scope_contract.resolved_bindings codes",
			)
		}
		for _, code := range contractCodes {
			targetRefKey := strings.TrimSpace(bindingsByCode[code])
			if targetRefKey == "" {
				return factualSyncInput{}, handlers.NewOperationExecutionError(
					ErrorCodePoolFactualSyncPayloadInvalid,
					fmt.Sprintf("factual_scope_contract binding for code '%s' must include target_ref_key", code),
				)
			}
			resolvedAccountRefs = append(resolvedAccountRefs, targetRefKey)
		}
	}
	movementKinds, err := normalizeMovementKinds(splitCSV(readRequiredString(payload, "movement_kinds")))
	if err != nil {
		return factualSyncInput{}, err
	}
	if len(movementKinds) == 0 {
		return factualSyncInput{}, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"movement_kinds must contain credit and/or debit",
		)
	}
	return factualSyncInput{
		PoolID:                   readRequiredString(payload, "pool_id"),
		DatabaseID:               readRequiredString(payload, "database_id"),
		Lane:                     strings.TrimSpace(fmt.Sprintf("%v", payload["lane"])),
		QuarterStart:             quarterStart.UTC(),
		QuarterEnd:               quarterEnd.UTC(),
		OrganizationIDs:          organizationIDs,
		AccountCodes:             accountCodes,
		MovementKinds:            movementKinds,
		DocumentEntities:         documentEntities,
		AccountingRegisterEntity: readRequiredString(payload, "accounting_register_entity"),
		AccountingFunction:       readRequiredString(payload, "accounting_register_function"),
		InformationRegister:      readRequiredString(payload, "information_register_entity"),
		ScopeFingerprint:         strings.TrimSpace(fmt.Sprintf("%v", payload["scope_fingerprint"])),
		ResolvedAccountRefs:      resolvedAccountRefs,
	}, nil
}

func parseFactualScopeContract(raw interface{}) (*factualScopeContract, error) {
	if raw == nil {
		return nil, nil
	}
	payload, ok := raw.(map[string]interface{})
	if !ok {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"factual_scope_contract must be an object",
		)
	}
	contractVersion := readRequiredString(payload, "contract_version")
	if contractVersion != "factual_scope_contract.v2" {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			fmt.Sprintf("unsupported factual_scope_contract version '%s'", contractVersion),
		)
	}
	rawBindings, ok := payload["resolved_bindings"].([]interface{})
	if !ok || len(rawBindings) == 0 {
		return nil, handlers.NewOperationExecutionError(
			ErrorCodePoolFactualSyncPayloadInvalid,
			"factual_scope_contract.resolved_bindings must be a non-empty array",
		)
	}
	bindings := make([]factualResolvedBinding, 0, len(rawBindings))
	for _, item := range rawBindings {
		binding, ok := item.(map[string]interface{})
		if !ok {
			return nil, handlers.NewOperationExecutionError(
				ErrorCodePoolFactualSyncPayloadInvalid,
				"factual_scope_contract.resolved_bindings must contain objects",
			)
		}
		bindings = append(bindings, factualResolvedBinding{
			Code:         strings.TrimSpace(readRequiredString(binding, "code")),
			TargetRefKey: strings.TrimSpace(readRequiredString(binding, "target_ref_key")),
		})
	}
	return &factualScopeContract{
		ContractVersion: contractVersion,
		ScopeFingerprint: strings.TrimSpace(readRequiredString(payload, "scope_fingerprint")),
		ResolvedBindings: bindings,
	}, nil
}

func buildAccountingRegisterEntity(input factualSyncInput, accountRefs []string) string {
	start := input.QuarterStart.Format("2006-01-02T15:04:05")
	end := input.QuarterEnd.Add(23*time.Hour + 59*time.Minute + 59*time.Second).Format("2006-01-02T15:04:05")
	condition := buildAccountingRegisterCondition(input)
	accountCondition := buildAccountingAccountCondition(accountRefs)
	periodArguments := buildAccountingFunctionPeriodArguments(input.AccountingFunction, start, end)
	return fmt.Sprintf(
		"%s/%s(%s,Condition='%s',AccountCondition='%s')",
		input.AccountingRegisterEntity,
		input.AccountingFunction,
		periodArguments,
		escapeODataFunctionString(condition),
		escapeODataFunctionString(accountCondition),
	)
}

func buildAccountingFunctionPeriodArguments(functionName, start, end string) string {
	if strings.TrimSpace(functionName) == "Balance" {
		return fmt.Sprintf("Period=datetime'%s'", end)
	}
	return fmt.Sprintf("StartPeriod=datetime'%s',EndPeriod=datetime'%s'", start, end)
}

func buildAccountingRegisterCondition(input factualSyncInput) string {
	parts := make([]string, 0, 1)
	if orgFilter := buildGuidOrFilter("Организация_Key", input.OrganizationIDs); orgFilter != "" {
		parts = append(parts, fmt.Sprintf("(%s)", orgFilter))
	}
	return strings.Join(parts, " and ")
}

func buildAccountingAccountCondition(accountRefs []string) string {
	return buildGuidOrFilter("Account_Key", accountRefs)
}

func buildGuidOrFilter(field string, values []string) string {
	if len(values) == 0 {
		return ""
	}
	clauses := make([]string, 0, len(values))
	for _, value := range values {
		clauses = append(clauses, fmt.Sprintf("%s eq guid'%s'", field, value))
	}
	return strings.Join(clauses, " or ")
}

func escapeODataFunctionString(value string) string {
	return strings.ReplaceAll(value, "'", "''")
}

func queryAllFactualRows(
	ctx context.Context,
	service factualODataService,
	creds sharedodata.ODataCredentials,
	entity string,
	query *sharedodata.QueryParams,
) ([]map[string]interface{}, error) {
	rows := make([]map[string]interface{}, 0)
	for skip := 0; ; {
		pageQuery := cloneQueryParams(query)
		pageQuery.Top = defaultFactualQueryPageSize
		pageQuery.Skip = skip
		pageRows, err := service.Query(ctx, creds, entity, pageQuery)
		if err != nil {
			return nil, err
		}
		rows = append(rows, pageRows...)
		if len(pageRows) == 0 || len(pageRows) < defaultFactualQueryPageSize {
			break
		}
		skip += len(pageRows)
	}
	return rows, nil
}

func queryFactualProbeRows(
	ctx context.Context,
	service factualODataService,
	creds sharedodata.ODataCredentials,
	entity string,
) ([]map[string]interface{}, error) {
	return service.Query(
		ctx,
		creds,
		entity,
		&sharedodata.QueryParams{Top: 1},
	)
}

func queryFactualEntityRefs(
	ctx context.Context,
	service factualODataService,
	creds sharedodata.ODataCredentials,
	entityRefs []string,
) ([]map[string]interface{}, error) {
	rows := make([]map[string]interface{}, 0, len(entityRefs))
	for _, entityRef := range entityRefs {
		entityRows, err := service.Query(ctx, creds, entityRef, nil)
		if err != nil {
			return nil, err
		}
		rows = append(rows, entityRows...)
	}
	return rows, nil
}

func resolveAccountCodeRefs(
	ctx context.Context,
	service factualODataService,
	creds sharedodata.ODataCredentials,
	accountingRegisterEntity string,
	accountCodes []string,
) ([]string, error) {
	chartEntity := deriveChartOfAccountsEntity(accountingRegisterEntity)
	query := &sharedodata.QueryParams{
		Select: []string{"Ref_Key", "Code"},
	}
	rows, err := queryAllFactualRows(ctx, service, creds, chartEntity, query)
	if err != nil {
		return nil, err
	}

	codeToRef := make(map[string]string, len(accountCodes))
	for _, row := range rows {
		code := strings.TrimSpace(fmt.Sprintf("%v", firstNonEmpty(row["Code"], row["code"])))
		refKey := strings.TrimSpace(fmt.Sprintf("%v", firstNonEmpty(row["Ref_Key"], row["ref_key"])))
		if code == "" || refKey == "" {
			continue
		}
		codeToRef[code] = refKey
		if len(codeToRef) == len(accountCodes) {
			break
		}
	}

	missingCodes := make([]string, 0)
	accountRefs := make([]string, 0, len(accountCodes))
	for _, code := range accountCodes {
		refKey, ok := codeToRef[code]
		if !ok {
			missingCodes = append(missingCodes, code)
			continue
		}
		accountRefs = append(accountRefs, refKey)
	}
	if len(missingCodes) > 0 {
		sort.Strings(missingCodes)
		return nil, fmt.Errorf("chart of accounts is missing factual account codes: %s", strings.Join(missingCodes, ", "))
	}
	return accountRefs, nil
}

func deriveChartOfAccountsEntity(accountingRegisterEntity string) string {
	entity := strings.TrimSpace(accountingRegisterEntity)
	if entity == "" {
		return "ChartOfAccounts_Хозрасчетный"
	}
	if strings.HasPrefix(entity, "AccountingRegister_") {
		return strings.Replace(entity, "AccountingRegister_", "ChartOfAccounts_", 1)
	}
	return "ChartOfAccounts_Хозрасчетный"
}

func collectRegisterDocumentRefsByEntity(
	accountingRows []map[string]interface{},
	allowedEntities []string,
) map[string][]string {
	allowed := make(map[string]struct{}, len(allowedEntities))
	for _, entity := range allowedEntities {
		allowed[strings.TrimSpace(entity)] = struct{}{}
	}
	result := make(map[string][]string, len(allowedEntities))
	seen := make(map[string]map[string]struct{}, len(allowedEntities))
	for _, row := range accountingRows {
		documentRef := strings.TrimSpace(
			fmt.Sprintf(
				"%v",
				firstNonEmpty(
					extractSourceDocumentRefFromRegisterDimensions(row),
					row["Документ"],
					row["Document"],
					row["source_document_ref"],
					row["document_ref"],
				),
			),
		)
		entity := extractSourceDocumentEntity(documentRef)
		if entity == "" {
			continue
		}
		if _, ok := allowed[entity]; !ok {
			continue
		}
		if seen[entity] == nil {
			seen[entity] = make(map[string]struct{})
		}
		if _, ok := seen[entity][documentRef]; ok {
			continue
		}
		seen[entity][documentRef] = struct{}{}
		result[entity] = append(result[entity], documentRef)
	}
	return result
}

func extractSourceDocumentEntity(sourceDocumentRef string) string {
	ref := strings.TrimSpace(sourceDocumentRef)
	if ref == "" {
		return ""
	}
	openParen := strings.Index(ref, "(")
	if openParen <= 0 {
		return ""
	}
	entity := strings.TrimSpace(ref[:openParen])
	if !strings.HasPrefix(entity, "Document_") {
		return ""
	}
	return entity
}

func cloneQueryParams(query *sharedodata.QueryParams) *sharedodata.QueryParams {
	if query == nil {
		return &sharedodata.QueryParams{}
	}
	copy := *query
	return &copy
}

func normalizeFactualDocumentRows(
	entity string,
	rows []map[string]interface{},
	organizationIDs []string,
) []map[string]interface{} {
	defaultKind := resolveDocumentKind(entity)
	result := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		document := cloneMap(row)
		organizationID := firstNonEmpty(
			document["organization_id"],
			document["OrganizationId"],
			document["Organization_Key"],
			document["organization_key"],
			document["Организация_Key"],
		)
		if organizationID == "" && len(organizationIDs) == 1 {
			organizationID = organizationIDs[0]
		}
		if len(organizationIDs) > 0 && !containsString(organizationIDs, organizationID) {
			continue
		}
		vatAmount := parseDecimalString(firstNonEmpty(document["vat_amount"], document["VATAmount"], document["СуммаНДС"]))
		amountWithVAT := parseDecimalString(firstNonEmpty(document["amount_with_vat"], document["Amount"], document["СуммаДокумента"], document["Сумма"]))
		amountWithoutVAT := parseDecimalString(firstNonEmpty(document["amount_without_vat"], document["AmountWithoutVAT"], document["СуммаБезНДС"]))
		if amountWithoutVAT == "0.00" && amountWithVAT != "0.00" {
			amountWithoutVAT = parseDecimalString(mustParseFloat(amountWithVAT) - mustParseFloat(vatAmount))
		}
		result = append(result, map[string]interface{}{
			"source_document_ref": buildSourceDocumentRef(entity, document),
			"organization_id":     organizationID,
			"batch_id":            firstNonEmpty(document["batch_id"], document["BatchID"]),
			"edge_id":             firstNonEmpty(document["edge_id"], document["EdgeID"]),
			"amount_with_vat":     amountWithVAT,
			"amount_without_vat":  amountWithoutVAT,
			"vat_amount":          vatAmount,
			"comment":             firstNonEmpty(document["comment"], document["Comment"], document["Комментарий"]),
			"kind":                firstNonEmpty(document["kind"], defaultKind),
			"modified_at":         firstNonEmpty(document["modified_at"], document["ModifiedAt"], document["Date"], document["Дата"]),
		})
	}
	return result
}

func normalizeScopeTokens(values []string) []string {
	seen := make(map[string]struct{}, len(values))
	normalized := make([]string, 0, len(values))
	for _, value := range values {
		token := strings.TrimSpace(value)
		if token == "" {
			continue
		}
		if _, ok := seen[token]; ok {
			continue
		}
		seen[token] = struct{}{}
		normalized = append(normalized, token)
	}
	sort.Strings(normalized)
	return normalized
}

func normalizeMovementKinds(values []string) ([]string, error) {
	if len(values) == 0 {
		return nil, nil
	}
	seen := make(map[string]struct{}, len(values))
	normalized := make([]string, 0, len(values))
	for _, value := range values {
		token := strings.ToLower(strings.TrimSpace(value))
		switch token {
		case "credit", "debit":
			if _, ok := seen[token]; ok {
				continue
			}
			seen[token] = struct{}{}
			normalized = append(normalized, token)
		default:
			return nil, handlers.NewOperationExecutionError(
				ErrorCodePoolFactualSyncPayloadInvalid,
				fmt.Sprintf("movement_kinds contains unsupported value '%s'", value),
			)
		}
	}
	sort.Strings(normalized)
	return normalized, nil
}

func containsString(values []string, needle string) bool {
	for _, value := range values {
		if strings.TrimSpace(value) == strings.TrimSpace(needle) {
			return true
		}
	}
	return false
}

func buildSourceDocumentRef(entity string, row map[string]interface{}) string {
	if ref := firstNonEmpty(row["source_document_ref"]); ref != "" {
		return ref
	}
	refKey := firstNonEmpty(row["Ref_Key"], row["ref_key"], row["ID"], row["id"])
	if refKey == "" {
		return entity
	}
	return fmt.Sprintf("%s(guid'%s')", entity, refKey)
}

func resolveDocumentKind(entity string) string {
	switch strings.TrimSpace(entity) {
	case "Document_РеализацияТоваровУслуг":
		return "sale"
	case "Document_ВозвратТоваровОтПокупателя":
		return "receipt"
	case "Document_КорректировкаРеализации":
		return "manual"
	default:
		return "manual"
	}
}

func mapFactualODataError(scope string, err error) error {
	normalized := workerodata.NormalizeError(err)
	return handlers.NewOperationExecutionError(
		ErrorCodePoolFactualSyncODATAFailed,
		fmt.Sprintf("%s: %s", scope, strings.TrimSpace(normalized.Message)),
	)
}

func buildFactualSourceCheckpointToken(boundaryReads map[string]int, documents []map[string]interface{}) string {
	hasher := sha256.New()
	keys := make([]string, 0, len(boundaryReads))
	for key := range boundaryReads {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		_, _ = hasher.Write([]byte(fmt.Sprintf("%s:%d|", key, boundaryReads[key])))
	}
	for _, document := range documents {
		_, _ = hasher.Write([]byte(fmt.Sprintf(
			"%v|%v|%v|%v|%v|",
			document["source_document_ref"],
			document["modified_at"],
			document["amount_with_vat"],
			document["amount_without_vat"],
			document["vat_amount"],
		)))
	}
	return hex.EncodeToString(hasher.Sum(nil))
}

func firstNonEmpty(values ...interface{}) string {
	for _, value := range values {
		text := strings.TrimSpace(fmt.Sprintf("%v", value))
		if text != "" && text != "<nil>" {
			return text
		}
	}
	return ""
}

func splitCSV(raw string) []string {
	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		token := strings.TrimSpace(part)
		if token != "" {
			values = append(values, token)
		}
	}
	return values
}

func readRequiredString(payload map[string]interface{}, field string) string {
	value := firstNonEmpty(payload[field])
	if value == "" {
		return ""
	}
	return value
}

func parseDecimalString(value interface{}) string {
	text := firstNonEmpty(value)
	if text == "" {
		return "0.00"
	}
	parsed, err := strconv.ParseFloat(strings.ReplaceAll(text, ",", "."), 64)
	if err != nil {
		return "0.00"
	}
	return strconv.FormatFloat(parsed, 'f', 2, 64)
}

func mustParseFloat(raw string) float64 {
	parsed, err := strconv.ParseFloat(strings.ReplaceAll(raw, ",", "."), 64)
	if err != nil {
		return 0
	}
	return parsed
}

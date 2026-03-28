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
	accountingRows, err := queryAllFactualRows(
		ctx,
		t.service,
		odataCreds,
		buildAccountingRegisterEntity(input),
		nil,
	)
	if err != nil {
		return nil, mapFactualODataError("accounting_register", err)
	}
	boundaryReads["accounting_register"] = len(accountingRows)

	informationRows, err := queryAllFactualRows(
		ctx,
		t.service,
		odataCreds,
		input.InformationRegister,
		buildFactualInformationRegisterQuery(input),
	)
	if err != nil {
		return nil, mapFactualODataError("information_register", err)
	}
	boundaryReads["information_register"] = len(informationRows)

	factualDocuments := make([]map[string]interface{}, 0)
	for _, entity := range input.DocumentEntities {
		rows, queryErr := queryAllFactualRows(
			ctx,
			t.service,
			odataCreds,
			entity,
			buildDocumentQuery(input, entity),
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
	}, nil
}

func buildAccountingRegisterEntity(input factualSyncInput) string {
	start := input.QuarterStart.Format("2006-01-02T15:04:05")
	end := input.QuarterEnd.Add(23*time.Hour + 59*time.Minute + 59*time.Second).Format("2006-01-02T15:04:05")
	condition := buildAccountingRegisterCondition(input)
	accountCondition := buildAccountingAccountCondition(input)
	return fmt.Sprintf(
		"%s/%s(PeriodStart=datetime'%s',PeriodEnd=datetime'%s',Condition='%s',AccountCondition='%s')",
		input.AccountingRegisterEntity,
		input.AccountingFunction,
		start,
		end,
		escapeODataFunctionString(condition),
		escapeODataFunctionString(accountCondition),
	)
}

func buildDocumentQuery(input factualSyncInput, entity string) *sharedodata.QueryParams {
	temporalField := "Date"
	if strings.HasPrefix(strings.TrimSpace(entity), "InformationRegister_") {
		temporalField = "Period"
	}
	return &sharedodata.QueryParams{
		Filter:  buildTemporalEntityFilter(temporalField, input.OrganizationIDs, input.QuarterStart, input.QuarterEnd),
		OrderBy: fmt.Sprintf("%s desc", temporalField),
		Top:     defaultFactualQueryPageSize,
	}
}

func buildFactualInformationRegisterQuery(input factualSyncInput) *sharedodata.QueryParams {
	return &sharedodata.QueryParams{
		Filter:  buildTemporalEntityFilter("Period", input.OrganizationIDs, input.QuarterStart, input.QuarterEnd),
		OrderBy: "Period desc",
		Top:     defaultFactualQueryPageSize,
	}
}

func buildTemporalEntityFilter(field string, organizationIDs []string, quarterStart, quarterEnd time.Time) string {
	start := quarterStart.Format("2006-01-02T15:04:05")
	end := quarterEnd.Add(23*time.Hour + 59*time.Minute + 59*time.Second).Format("2006-01-02T15:04:05")
	parts := []string{
		fmt.Sprintf(
			"%s ge datetime'%s' and %s le datetime'%s'",
			field,
			start,
			field,
			end,
		),
	}
	if orgFilter := buildOrganizationFilter(organizationIDs); orgFilter != "" {
		parts = append(parts, fmt.Sprintf("(%s)", orgFilter))
	}
	return strings.Join(parts, " and ")
}

func buildAccountingRegisterCondition(input factualSyncInput) string {
	parts := make([]string, 0, 2)
	if orgFilter := buildOrganizationFilter(input.OrganizationIDs); orgFilter != "" {
		parts = append(parts, fmt.Sprintf("(%s)", orgFilter))
	}
	if movementFilter := buildRecordTypeFilter(input.MovementKinds); movementFilter != "" {
		parts = append(parts, movementFilter)
	}
	return strings.Join(parts, " and ")
}

func buildAccountingAccountCondition(input factualSyncInput) string {
	return buildCodeFilter("Code", input.AccountCodes)
}

func buildOrganizationFilter(organizationIDs []string) string {
	return buildGuidOrFilter("Organization_Key", organizationIDs)
}

func buildRecordTypeFilter(movementKinds []string) string {
	if len(movementKinds) == 0 {
		return ""
	}
	clauses := make([]string, 0, len(movementKinds))
	for _, kind := range movementKinds {
		switch strings.ToLower(strings.TrimSpace(kind)) {
		case "credit":
			clauses = append(clauses, "RecordType eq 'Credit'")
		case "debit":
			clauses = append(clauses, "RecordType eq 'Debit'")
		}
	}
	if len(clauses) == 1 {
		return clauses[0]
	}
	return fmt.Sprintf("(%s)", strings.Join(clauses, " or "))
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

func buildCodeFilter(field string, values []string) string {
	if len(values) == 0 {
		return ""
	}
	clauses := make([]string, 0, len(values))
	for _, value := range values {
		clauses = append(clauses, fmt.Sprintf("%s eq '%s'", field, escapeODataLiteral(value)))
	}
	return strings.Join(clauses, " or ")
}

func escapeODataLiteral(value string) string {
	return strings.ReplaceAll(value, "'", "''")
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

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
	defaultFactualQueryTop                   = 500
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
	accountingRows, err := t.service.Query(
		ctx,
		odataCreds,
		buildAccountingRegisterEntity(input),
		&sharedodata.QueryParams{Top: defaultFactualQueryTop},
	)
	if err != nil {
		return nil, mapFactualODataError("accounting_register", err)
	}
	boundaryReads["accounting_register"] = len(accountingRows)

	informationRows, err := t.service.Query(
		ctx,
		odataCreds,
		input.InformationRegister,
		&sharedodata.QueryParams{Top: defaultFactualQueryTop},
	)
	if err != nil {
		return nil, mapFactualODataError("information_register", err)
	}
	boundaryReads["information_register"] = len(informationRows)

	factualDocuments := make([]map[string]interface{}, 0)
	for _, entity := range input.DocumentEntities {
		rows, queryErr := t.service.Query(
			ctx,
			odataCreds,
			entity,
			&sharedodata.QueryParams{
				Filter:  buildDocumentDateFilter(input),
				OrderBy: "Date desc",
				Top:     defaultFactualQueryTop,
			},
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
	return factualSyncInput{
		PoolID:                   readRequiredString(payload, "pool_id"),
		DatabaseID:               readRequiredString(payload, "database_id"),
		Lane:                     strings.TrimSpace(fmt.Sprintf("%v", payload["lane"])),
		QuarterStart:             quarterStart.UTC(),
		QuarterEnd:               quarterEnd.UTC(),
		OrganizationIDs:          splitCSV(readRequiredString(payload, "organization_ids")),
		DocumentEntities:         documentEntities,
		AccountingRegisterEntity: readRequiredString(payload, "accounting_register_entity"),
		AccountingFunction:       readRequiredString(payload, "accounting_register_function"),
		InformationRegister:      readRequiredString(payload, "information_register_entity"),
	}, nil
}

func buildAccountingRegisterEntity(input factualSyncInput) string {
	start := input.QuarterStart.Format("2006-01-02T15:04:05")
	end := input.QuarterEnd.Add(23*time.Hour + 59*time.Minute + 59*time.Second).Format("2006-01-02T15:04:05")
	return fmt.Sprintf(
		"%s/%s(PeriodStart=datetime'%s',PeriodEnd=datetime'%s',Condition='')",
		input.AccountingRegisterEntity,
		input.AccountingFunction,
		start,
		end,
	)
}

func buildDocumentDateFilter(input factualSyncInput) string {
	return fmt.Sprintf(
		"Date ge datetime'%s' and Date le datetime'%s'",
		input.QuarterStart.Format("2006-01-02T00:00:00"),
		input.QuarterEnd.Format("2006-01-02T23:59:59"),
	)
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
		_, _ = hasher.Write([]byte(fmt.Sprintf("%v|%v|", document["source_document_ref"], document["modified_at"])))
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

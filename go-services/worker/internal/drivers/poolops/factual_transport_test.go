package poolops

import (
	"context"
	"errors"
	"fmt"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
)

type mockFactualCredentialsFetcher struct {
	cred                   *credentials.DatabaseCredentials
	err                    error
	lastCredentialsPurpose string
	lastDatabaseID         string
}

func (m *mockFactualCredentialsFetcher) Fetch(ctx context.Context, databaseID string) (*credentials.DatabaseCredentials, error) {
	m.lastCredentialsPurpose = credentials.CredentialsPurposeFromContext(ctx)
	m.lastDatabaseID = databaseID
	if m.err != nil {
		return nil, m.err
	}
	return m.cred, nil
}

type mockFactualODataService struct {
	queryCalls          []mockFactualODataQueryCall
	rowsByEntity        map[string][]map[string]interface{}
	rowsByEntityAndSkip map[string]map[int][]map[string]interface{}
	errByEntity         map[string]error
}

type mockFactualODataQueryCall struct {
	entity string
	query  sharedodata.QueryParams
}

func (m *mockFactualODataService) Query(
	ctx context.Context,
	creds sharedodata.ODataCredentials,
	entity string,
	query *sharedodata.QueryParams,
) ([]map[string]interface{}, error) {
	call := mockFactualODataQueryCall{entity: entity}
	if query != nil {
		call.query = *query
	}
	m.queryCalls = append(m.queryCalls, call)
	if m.errByEntity != nil {
		if err, ok := m.errByEntity[entity]; ok && err != nil {
			return nil, err
		}
	}
	if m.rowsByEntityAndSkip != nil {
		if bySkip, ok := m.rowsByEntityAndSkip[entity]; ok {
			skip := 0
			if query != nil {
				skip = query.Skip
			}
			if rows, ok := bySkip[skip]; ok {
				return rows, nil
			}
		}
	}
	if m.rowsByEntity == nil {
		return nil, nil
	}
	return m.rowsByEntity[entity], nil
}

func TestODataFactualTransport_ExecuteFactualSyncSourceSlice_BoundsScopeAndNormalizesDocuments(t *testing.T) {
	fetcher := &mockFactualCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockFactualODataService{
		rowsByEntity: map[string][]map[string]interface{}{
			"AccountingRegister_Хозрасчетный/Turnovers(PeriodStart=datetime'2026-01-01T00:00:00',PeriodEnd=datetime'2026-03-31T23:59:59',Condition='(Organization_Key eq guid''org-1'') and (RecordType eq ''Credit'' or RecordType eq ''Debit'')',AccountCondition='Code eq ''62.01'' or Code eq ''90.01''')": {
				{"Amount": "100.00"},
			},
			"InformationRegister_ДанныеПервичныхДокументов": {
				{"Ref_Key": "info-1"},
			},
			"Document_РеализацияТоваровУслуг": {
				{
					"Ref_Key":         "sale-1",
					"Организация_Key": "org-1",
					"СуммаДокумента":  "120.00",
					"СуммаНДС":        "20.00",
					"Комментарий":     "CCPOOL:v=1;pool=pool-1;run=-;batch=batch-1;org=org-1;q=2026Q1;kind=sale||manual tail",
					"Date":            "2026-03-27T10:00:00Z",
				},
				{
					"Ref_Key":         "sale-out-of-scope",
					"Организация_Key": "org-2",
					"СуммаДокумента":  "999.00",
					"СуммаНДС":        "0.00",
					"Комментарий":     "CCPOOL:v=1;pool=pool-1;run=-;batch=batch-1;org=org-2;q=2026Q1;kind=sale",
					"Date":            "2026-03-27T10:05:00Z",
				},
			},
			"Document_КорректировкаРеализации": {
				{
					"Ref_Key":        "corr-1",
					"OrganizationId": "org-1",
					"Amount":         "15.00",
					"VATAmount":      "2.50",
					"Comment":        "manual correction",
					"ModifiedAt":     "2026-03-28T11:00:00Z",
				},
			},
		},
	}
	transport := NewODataFactualTransport(fetcher, service, zap.NewNop())

	out, err := transport.ExecuteFactualSyncSourceSlice(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.factual.sync_source_slice",
		Payload: map[string]interface{}{
			"pool_id":                      "pool-1",
			"database_id":                  "db-1",
			"lane":                         "read",
			"quarter_start":                "2026-01-01",
			"quarter_end":                  "2026-03-31",
			"organization_ids":             "org-1",
			"account_codes":                "90.01,62.01",
			"movement_kinds":               "debit,credit",
			"document_entities":            "Document_РеализацияТоваровУслуг,Document_КорректировкаРеализации",
			"accounting_register_entity":   "AccountingRegister_Хозрасчетный",
			"accounting_register_function": "Turnovers",
			"information_register_entity":  "InformationRegister_ДанныеПервичныхДокументов",
		},
	})

	require.NoError(t, err)
	assert.Equal(t, factualSyncCredentialsPurpose, fetcher.lastCredentialsPurpose)
	assert.Equal(t, "db-1", fetcher.lastDatabaseID)
	assert.Equal(t, "factual_sync_source_slice", out["step"])
	assert.Equal(t, "completed", out["status"])
	assert.Equal(t, "db-1", out["database_id"])
	require.Len(t, service.queryCalls, 4)

	assert.Equal(t, "AccountingRegister_Хозрасчетный/Turnovers(PeriodStart=datetime'2026-01-01T00:00:00',PeriodEnd=datetime'2026-03-31T23:59:59',Condition='(Organization_Key eq guid''org-1'') and (RecordType eq ''Credit'' or RecordType eq ''Debit'')',AccountCondition='Code eq ''62.01'' or Code eq ''90.01''')", service.queryCalls[0].entity)
	assert.Equal(t, 500, service.queryCalls[0].query.Top)
	assert.Equal(t, 0, service.queryCalls[0].query.Skip)

	assert.Equal(t, "InformationRegister_ДанныеПервичныхДокументов", service.queryCalls[1].entity)
	assert.Equal(t, "Period ge datetime'2026-01-01T00:00:00' and Period le datetime'2026-03-31T23:59:59' and (Organization_Key eq guid'org-1')", service.queryCalls[1].query.Filter)
	assert.Equal(t, "Period desc", service.queryCalls[1].query.OrderBy)
	assert.Equal(t, 500, service.queryCalls[1].query.Top)
	assert.Equal(t, 0, service.queryCalls[1].query.Skip)

	assert.Equal(t, "Document_РеализацияТоваровУслуг", service.queryCalls[2].entity)
	assert.Equal(t, "Date ge datetime'2026-01-01T00:00:00' and Date le datetime'2026-03-31T23:59:59' and (Organization_Key eq guid'org-1')", service.queryCalls[2].query.Filter)
	assert.Equal(t, "Date desc", service.queryCalls[2].query.OrderBy)
	assert.Equal(t, 500, service.queryCalls[2].query.Top)
	assert.Equal(t, 0, service.queryCalls[2].query.Skip)

	assert.Equal(t, "Document_КорректировкаРеализации", service.queryCalls[3].entity)
	assert.Equal(t, "Date ge datetime'2026-01-01T00:00:00' and Date le datetime'2026-03-31T23:59:59' and (Organization_Key eq guid'org-1')", service.queryCalls[3].query.Filter)

	boundaryReads, ok := out["boundary_reads"].(map[string]int)
	require.True(t, ok)
	assert.Equal(t, 1, boundaryReads["accounting_register"])
	assert.Equal(t, 1, boundaryReads["information_register"])
	assert.Equal(t, 2, boundaryReads["Document_РеализацияТоваровУслуг"])

	factualDocuments, ok := out["factual_documents"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, factualDocuments, 2)
	assert.Equal(t, "Document_КорректировкаРеализации(guid'corr-1')", factualDocuments[0]["source_document_ref"])
	assert.Equal(t, "manual", factualDocuments[0]["kind"])
	assert.Equal(t, "12.50", factualDocuments[0]["amount_without_vat"])
	assert.Equal(t, "sale", factualDocuments[1]["kind"])
	assert.NotEmpty(t, out["source_checkpoint_token"])
}

func TestODataFactualTransport_ExecuteFactualSyncSourceSlice_UsesRegisterBackedAmountsForMatchedDocument(t *testing.T) {
	fetcher := &mockFactualCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockFactualODataService{
		rowsByEntity: map[string][]map[string]interface{}{
			"AccountingRegister_Хозрасчетный/Turnovers(PeriodStart=datetime'2026-01-01T00:00:00',PeriodEnd=datetime'2026-03-31T23:59:59',Condition='(Organization_Key eq guid''org-1'') and (RecordType eq ''Credit'' or RecordType eq ''Debit'')',AccountCondition='Code eq ''62.01'' or Code eq ''90.01''')": {
				{
					"Recorder": "SALE-0001",
					"Amount":   "90.00",
				},
			},
			"InformationRegister_ДанныеПервичныхДокументов": {
				{
					"Документ": "Document_РеализацияТоваровУслуг(guid'sale-1')",
					"Номер":    "SALE-0001",
				},
			},
			"Document_РеализацияТоваровУслуг": {
				{
					"Ref_Key":         "sale-1",
					"Организация_Key": "org-1",
					"СуммаДокумента":  "120.00",
					"СуммаНДС":        "20.00",
					"Комментарий":     "CCPOOL:v=1;pool=pool-1;run=-;batch=batch-1;org=org-1;q=2026Q1;kind=sale",
					"Date":            "2026-03-27T10:00:00Z",
				},
				{
					"Ref_Key":         "sale-unmatched",
					"Организация_Key": "org-1",
					"СуммаДокумента":  "15.00",
					"СуммаНДС":        "2.50",
					"Комментарий":     "CCPOOL:v=1;pool=pool-1;run=-;batch=batch-2;org=org-1;q=2026Q1;kind=sale",
					"Date":            "2026-03-27T11:00:00Z",
				},
			},
		},
	}
	transport := NewODataFactualTransport(fetcher, service, zap.NewNop())

	out, err := transport.ExecuteFactualSyncSourceSlice(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.factual.sync_source_slice",
		Payload: map[string]interface{}{
			"pool_id":                      "pool-1",
			"database_id":                  "db-1",
			"lane":                         "read",
			"quarter_start":                "2026-01-01",
			"quarter_end":                  "2026-03-31",
			"organization_ids":             "org-1",
			"account_codes":                "90.01,62.01",
			"movement_kinds":               "debit,credit",
			"document_entities":            "Document_РеализацияТоваровУслуг",
			"accounting_register_entity":   "AccountingRegister_Хозрасчетный",
			"accounting_register_function": "Turnovers",
			"information_register_entity":  "InformationRegister_ДанныеПервичныхДокументов",
		},
	})

	require.NoError(t, err)
	factualDocuments, ok := out["factual_documents"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, factualDocuments, 1)
	assert.Equal(t, "Document_РеализацияТоваровУслуг(guid'sale-1')", factualDocuments[0]["source_document_ref"])
	assert.Equal(t, "90.00", factualDocuments[0]["amount_with_vat"])
	assert.Equal(t, "75.00", factualDocuments[0]["amount_without_vat"])
	assert.Equal(t, "15.00", factualDocuments[0]["vat_amount"])
}

func TestQueryAllFactualRows_PaginatesThroughAllRows(t *testing.T) {
	service := &mockFactualODataService{
		rowsByEntityAndSkip: map[string]map[int][]map[string]interface{}{
			"Document_РеализацияТоваровУслуг": {
				0:   makeRowsForPaginationTest("sale", 500, 0),
				500: makeRowsForPaginationTest("sale", 7, 500),
			},
		},
	}

	rows, err := queryAllFactualRows(
		context.Background(),
		service,
		sharedodata.ODataCredentials{BaseURL: "http://localhost/odata/standard.odata", Username: "admin"},
		"Document_РеализацияТоваровУслуг",
		&sharedodata.QueryParams{Filter: "Date ge datetime'2026-01-01T00:00:00' and Date le datetime'2026-03-31T23:59:59'"},
	)

	require.NoError(t, err)
	require.Len(t, rows, 507)
	require.Len(t, service.queryCalls, 2)
	assert.Equal(t, 500, service.queryCalls[0].query.Top)
	assert.Equal(t, 0, service.queryCalls[0].query.Skip)
	assert.Equal(t, 500, service.queryCalls[1].query.Top)
	assert.Equal(t, 500, service.queryCalls[1].query.Skip)
}

func makeRowsForPaginationTest(kind string, count int, startIndex int) []map[string]interface{} {
	rows := make([]map[string]interface{}, 0, count)
	for i := 0; i < count; i++ {
		index := startIndex + i
		rows = append(rows, map[string]interface{}{
			"Ref_Key":         fmt.Sprintf("%s-%d", kind, index),
			"Организация_Key": "org-1",
			"СуммаДокумента":  "1.00",
			"СуммаНДС":        "0.00",
			"Комментарий":     "CCPOOL:v=1;pool=pool-1;run=-;batch=batch-1;org=org-1;q=2026Q1;kind=sale",
			"Date":            "2026-03-27T10:00:00Z",
		})
	}
	return rows
}

func TestODataFactualTransport_ExecuteFactualSyncSourceSlice_MapsODataFailure(t *testing.T) {
	fetcher := &mockFactualCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockFactualODataService{
		errByEntity: map[string]error{
			"InformationRegister_ДанныеПервичныхДокументов": errors.New("odata 503"),
		},
	}
	transport := NewODataFactualTransport(fetcher, service, zap.NewNop())

	_, err := transport.ExecuteFactualSyncSourceSlice(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.factual.sync_source_slice",
		Payload: map[string]interface{}{
			"pool_id":                      "pool-1",
			"database_id":                  "db-1",
			"lane":                         "read",
			"quarter_start":                "2026-01-01",
			"quarter_end":                  "2026-03-31",
			"organization_ids":             "org-1",
			"account_codes":                "62.01",
			"movement_kinds":               "credit",
			"document_entities":            "Document_РеализацияТоваровУслуг",
			"accounting_register_entity":   "AccountingRegister_Хозрасчетный",
			"accounting_register_function": "Turnovers",
			"information_register_entity":  "InformationRegister_ДанныеПервичныхДокументов",
		},
	})

	var opErr *handlers.OperationExecutionError
	require.Error(t, err)
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodePoolFactualSyncODATAFailed, opErr.Code)
	assert.Contains(t, opErr.Message, "information_register")
}

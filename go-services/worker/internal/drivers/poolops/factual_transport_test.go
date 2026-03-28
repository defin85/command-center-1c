package poolops

import (
	"context"
	"errors"
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
	lastEntities []string
	rowsByEntity map[string][]map[string]interface{}
	errByEntity  map[string]error
}

func (m *mockFactualODataService) Query(
	ctx context.Context,
	creds sharedodata.ODataCredentials,
	entity string,
	query *sharedodata.QueryParams,
) ([]map[string]interface{}, error) {
	m.lastEntities = append(m.lastEntities, entity)
	if m.errByEntity != nil {
		if err, ok := m.errByEntity[entity]; ok && err != nil {
			return nil, err
		}
	}
	if m.rowsByEntity == nil {
		return nil, nil
	}
	return m.rowsByEntity[entity], nil
}

func TestODataFactualTransport_ExecuteFactualSyncSourceSlice_Success(t *testing.T) {
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
			"AccountingRegister_Хозрасчетный/Turnovers(PeriodStart=datetime'2026-01-01T00:00:00',PeriodEnd=datetime'2026-03-31T23:59:59',Condition='')": {
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
					"Комментарий":     "CCPOOL:v1 pool=pool-1 batch=batch-1 organization=org-1",
					"Date":            "2026-03-27T10:00:00Z",
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

	boundaryReads, ok := out["boundary_reads"].(map[string]int)
	require.True(t, ok)
	assert.Equal(t, 1, boundaryReads["accounting_register"])
	assert.Equal(t, 1, boundaryReads["information_register"])
	assert.Equal(t, 1, boundaryReads["Document_РеализацияТоваровУслуг"])

	factualDocuments, ok := out["factual_documents"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, factualDocuments, 2)
	assert.Equal(t, "Document_КорректировкаРеализации(guid'corr-1')", factualDocuments[0]["source_document_ref"])
	assert.Equal(t, "manual", factualDocuments[0]["kind"])
	assert.Equal(t, "12.50", factualDocuments[0]["amount_without_vat"])
	assert.Equal(t, "sale", factualDocuments[1]["kind"])
	assert.NotEmpty(t, out["source_checkpoint_token"])
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

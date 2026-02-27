package poolops

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
)

type publicationTimelineRecord struct {
	operationID string
	event       string
	metadata    map[string]interface{}
}

type publicationTimelineSpy struct {
	records []publicationTimelineRecord
}

func (s *publicationTimelineSpy) Record(
	ctx context.Context,
	operationID string,
	event string,
	metadata map[string]interface{},
) {
	copied := make(map[string]interface{}, len(metadata))
	for key, value := range metadata {
		copied[key] = value
	}
	s.records = append(s.records, publicationTimelineRecord{
		operationID: operationID,
		event:       event,
		metadata:    copied,
	})
}

func (s *publicationTimelineSpy) GetTimeline(
	ctx context.Context,
	operationID string,
) ([]tracing.TimelineEntry, error) {
	return nil, nil
}

type mockPublicationCredentialsFetcher struct {
	cred                   *credentials.DatabaseCredentials
	err                    error
	credsByDatabase        map[string]*credentials.DatabaseCredentials
	errByDatabase          map[string]error
	lastRequestedBy        string
	lastIbAuthStrategy     string
	lastCredentialsPurpose string
}

func (m *mockPublicationCredentialsFetcher) Fetch(ctx context.Context, databaseID string) (*credentials.DatabaseCredentials, error) {
	m.lastRequestedBy = credentials.RequestedByFromContext(ctx)
	m.lastIbAuthStrategy = credentials.IbAuthStrategyFromContext(ctx)
	m.lastCredentialsPurpose = credentials.CredentialsPurposeFromContext(ctx)
	if m.errByDatabase != nil {
		if err, ok := m.errByDatabase[databaseID]; ok && err != nil {
			return nil, err
		}
	}
	if m.credsByDatabase != nil {
		if cred, ok := m.credsByDatabase[databaseID]; ok {
			return cred, nil
		}
	}
	return m.cred, m.err
}

func publicationAuthActorForTests() *handlers.PublicationAuth {
	return &handlers.PublicationAuth{
		Strategy:      "actor",
		ActorUsername: "alice",
		Source:        "confirm_publication",
	}
}

func publicationAuthServiceForTests() *handlers.PublicationAuth {
	return &handlers.PublicationAuth{
		Strategy: "service",
		Source:   "run_create",
	}
}

type mockPublicationODataService struct {
	createCalls int
	updateCalls int

	lastCreateEntity string
	lastCreateData   map[string]interface{}
	lastUpdateEntity string
	lastUpdateID     string
	lastUpdateData   map[string]interface{}
	createEntities   []string
	createPayloads   []map[string]interface{}

	createResponse         map[string]interface{}
	createResponseSequence []map[string]interface{}
	createErr              error
	createErrSequence      []error
	createErrByBaseURL     map[string]error
	updateErr              error
}

func (m *mockPublicationODataService) Create(
	ctx context.Context,
	creds sharedodata.ODataCredentials,
	entity string,
	data map[string]interface{},
) (map[string]interface{}, error) {
	m.createCalls++
	m.lastCreateEntity = entity
	m.lastCreateData = cloneMap(data)
	m.createEntities = append(m.createEntities, entity)
	m.createPayloads = append(m.createPayloads, cloneMap(data))
	if m.createErrByBaseURL != nil {
		if err, ok := m.createErrByBaseURL[creds.BaseURL]; ok && err != nil {
			return nil, err
		}
	}
	if len(m.createErrSequence) > 0 {
		err := m.createErrSequence[0]
		m.createErrSequence = m.createErrSequence[1:]
		if err != nil {
			return nil, err
		}
	}
	if len(m.createResponseSequence) > 0 {
		response := cloneMap(m.createResponseSequence[0])
		m.createResponseSequence = m.createResponseSequence[1:]
		if len(response) > 0 {
			return response, nil
		}
	}
	if m.createErr != nil {
		return nil, m.createErr
	}
	if m.createResponse == nil {
		return map[string]interface{}{"Ref_Key": "550e8400-e29b-41d4-a716-446655440000"}, nil
	}
	return m.createResponse, nil
}

func (m *mockPublicationODataService) Update(
	ctx context.Context,
	creds sharedodata.ODataCredentials,
	entity, entityID string,
	data map[string]interface{},
) error {
	m.updateCalls++
	m.lastUpdateEntity = entity
	m.lastUpdateID = entityID
	m.lastUpdateData = cloneMap(data)
	return m.updateErr
}

func TestODataPublicationTransport_ExecutePublicationOData_Success(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PoolRunID:       "run-1",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"entity_name": "Document_IntercompanyPoolDistribution",
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{"Amount": "100.00"},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "publication_odata", out["step"])
	assert.Equal(t, "published", out["status"])
	assert.Equal(t, 1, out["documents_targets"])
	assert.Equal(t, 1, out["succeeded_targets"])
	assert.Equal(t, 0, out["failed_targets"])
	assert.Equal(t, []string{"db-1"}, out["target_databases"])
	documentsCountByDatabase, ok := out["documents_count_by_database"].(map[string]int)
	require.True(t, ok)
	assert.Equal(t, 1, documentsCountByDatabase["db-1"])
	attempts, ok := out["attempts"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, attempts, 1)
	assert.Equal(t, "db-1", attempts[0]["target_database"])
	assert.Equal(t, "success", attempts[0]["status"])
	assert.Equal(t, 1, attempts[0]["attempt_number"])
	assert.Equal(t, 1, service.createCalls)
	assert.Equal(t, 1, service.updateCalls)
	assert.Equal(t, "Document_IntercompanyPoolDistribution", service.lastCreateEntity)
	assert.Equal(t, "Document_IntercompanyPoolDistribution", service.lastUpdateEntity)
	assert.Equal(t, "guid'550e8400-e29b-41d4-a716-446655440000'", service.lastUpdateID)
	assert.Equal(t, true, service.lastUpdateData["Posted"])
	_, hasExternalRunKey := service.lastCreateData[defaultPublicationExternalKeyField]
	assert.True(t, hasExternalRunKey)
	assert.Equal(t, "alice", fetcher.lastRequestedBy)
	assert.Equal(t, "actor", fetcher.lastIbAuthStrategy)
	assert.Equal(t, publicationCredentialsPurpose, fetcher.lastCredentialsPurpose)
}

func TestODataPublicationTransport_ExecutePublicationOData_UsesDocumentChainsPayloadWithMultipleEntities(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PoolRunID:       "run-1",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"entity_name": "Document_Raw_Bypass",
				"documents_by_database": map[string]interface{}{
					"db-raw": []interface{}{
						map[string]interface{}{"Amount": "999.00"},
					},
				},
				"document_chains_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{
							"chain_id": "sale_chain",
							"documents": []interface{}{
								map[string]interface{}{
									"entity_name": "Document_Sales",
									"payload": map[string]interface{}{
										"Amount": "100.00",
									},
								},
								map[string]interface{}{
									"entity_name": "Document_Invoice",
									"payload": map[string]interface{}{
										"Amount": "100.00",
									},
								},
							},
						},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "published", out["status"])
	assert.Equal(t, 1, out["documents_targets"])
	assert.Equal(t, []string{"db-1"}, out["target_databases"])
	documentsCountByDatabase, ok := out["documents_count_by_database"].(map[string]int)
	require.True(t, ok)
	assert.Equal(t, 2, documentsCountByDatabase["db-1"])
	_, hasRawTarget := documentsCountByDatabase["db-raw"]
	assert.False(t, hasRawTarget)

	require.Len(t, service.createEntities, 2)
	assert.Equal(t, []string{"Document_Sales", "Document_Invoice"}, service.createEntities)
	require.Len(t, service.createPayloads, 2)
	assert.Equal(t, "100.00", service.createPayloads[0]["Amount"])
	assert.Equal(t, "100.00", service.createPayloads[1]["Amount"])
}

func TestODataPublicationTransport_ExecutePublicationOData_AppliesChainMappingAndRequiredInvoiceLinkage(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{
		createResponseSequence: []map[string]interface{}{
			{"Ref_Key": "sale-ref-1"},
			{"Ref_Key": "invoice-ref-1"},
		},
	}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PoolRunID:       "run-chain-mapping",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"document_chains_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{
							"chain_id": "sale_chain",
							"allocation": map[string]interface{}{
								"amount": "100.00",
							},
							"documents": []interface{}{
								map[string]interface{}{
									"document_id": "sale",
									"entity_name": "Document_Sales",
									"field_mapping": map[string]interface{}{
										"Amount": "allocation.amount",
									},
									"payload": map[string]interface{}{},
								},
								map[string]interface{}{
									"document_id":  "invoice",
									"entity_name":  "Document_Invoice",
									"invoice_mode": "required",
									"link_to":      "sale",
									"field_mapping": map[string]interface{}{
										"Amount":       "allocation.amount",
										"BaseDocument": "sale.ref",
									},
									"payload": map[string]interface{}{},
								},
							},
						},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "published", out["status"])
	require.Len(t, service.createPayloads, 2)
	assert.Equal(t, "100.00", service.createPayloads[0]["Amount"])
	assert.Equal(t, "100.00", service.createPayloads[1]["Amount"])
	assert.Equal(t, "sale-ref-1", service.createPayloads[1]["BaseDocument"])

	attempts, ok := out["attempts"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, attempts, 1)
	responseSummary, ok := attempts[0]["response_summary"].(map[string]interface{})
	require.True(t, ok)
	successfulRefsRaw, ok := responseSummary["successful_document_refs"].(map[string]interface{})
	require.True(t, ok)
	assert.NotEmpty(t, successfulRefsRaw)
}

func TestODataPublicationTransport_ExecutePublicationOData_RejectsRequiredInvoiceWithUnresolvedLink(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PoolRunID:       "run-chain-invalid",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"document_chains_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{
							"chain_id": "sale_chain",
							"documents": []interface{}{
								map[string]interface{}{
									"document_id":  "invoice",
									"entity_name":  "Document_Invoice",
									"invoice_mode": "required",
									"link_to":      "sale",
									"payload":      map[string]interface{}{"Amount": "100.00"},
								},
							},
						},
					},
				},
			},
		},
	})

	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodePoolRuntimePublicationPayloadInvalid, opErr.Code)
	assert.Contains(t, opErr.Message, "required invoice link_to")
	assert.Equal(t, 0, service.createCalls)
}

func TestODataPublicationTransport_ExecutePublicationOData_UsesResolvedLinkRefsForRetriedInvoice(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PoolRunID:       "run-chain-retry-ref",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"document_chains_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{
							"chain_id": "sale_chain",
							"allocation": map[string]interface{}{
								"amount": "100.00",
							},
							"documents": []interface{}{
								map[string]interface{}{
									"document_id":  "invoice",
									"entity_name":  "Document_Invoice",
									"invoice_mode": "required",
									"link_to":      "sale",
									"field_mapping": map[string]interface{}{
										"BaseDocument": "sale.ref",
									},
									"resolved_link_refs": map[string]interface{}{
										"sale": "sale-ref-1",
									},
									"payload": map[string]interface{}{},
								},
							},
						},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "published", out["status"])
	require.Len(t, service.createPayloads, 1)
	assert.Equal(t, "sale-ref-1", service.createPayloads[0]["BaseDocument"])
}

func TestODataPublicationTransport_ExecutePublicationOData_ChainFailureIncludesDocumentRetryDiagnostics(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{
		createErrSequence: []error{
			nil,
			&odata.ODataError{
				Code:        odata.ErrorCategoryValidation,
				Message:     "invoice validation failed",
				StatusCode:  400,
				IsTransient: false,
			},
		},
	}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PoolRunID:       "run-chain-retry",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"max_attempts": float64(1),
				"document_chains_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{
							"chain_id": "sale_invoice_chain",
							"documents": []interface{}{
								map[string]interface{}{
									"entity_name":     "Document_Sales",
									"idempotency_key": "doc-sale-key",
									"payload": map[string]interface{}{
										"Amount": "100.00",
									},
								},
								map[string]interface{}{
									"entity_name":     "Document_Invoice",
									"idempotency_key": "doc-invoice-key",
									"payload": map[string]interface{}{
										"Amount": "100.00",
									},
								},
							},
						},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "failed", out["status"])
	attempts, ok := out["attempts"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, attempts, 1)

	requestSummary, ok := attempts[0]["request_summary"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(
		t,
		[]string{"doc-sale-key", "doc-invoice-key"},
		requestSummary["document_idempotency_keys"],
	)

	responseSummary, ok := attempts[0]["response_summary"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(
		t,
		[]string{"doc-sale-key"},
		responseSummary["successful_document_idempotency_keys"],
	)
	assert.Equal(t, "doc-invoice-key", responseSummary["failed_document_idempotency_key"])
}

func TestODataPublicationTransport_ExecutePublicationOData_ServiceStrategySetsCredentialsContext(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{"Amount": "100.00"},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "", fetcher.lastRequestedBy)
	assert.Equal(t, "service", fetcher.lastIbAuthStrategy)
	assert.Equal(t, publicationCredentialsPurpose, fetcher.lastCredentialsPurpose)
}

func TestODataPublicationTransport_ExecutePublicationOData_ActorStrategySupportsUnicodeCredentials(t *testing.T) {
	username := "ГлавБух"
	password := "пароль"
	expectedAuthorization := "Basic " + base64.StdEncoding.EncodeToString([]byte(username+":"+password))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, expectedAuthorization, r.Header.Get("Authorization"))
		switch r.Method {
		case http.MethodPost:
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"Ref_Key": "550e8400-e29b-41d4-a716-446655440000",
			})
		case http.MethodPatch:
			w.WriteHeader(http.StatusNoContent)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
	defer server.Close()

	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   server.URL,
			Username:   username,
			Password:   password,
		},
	}
	service := odata.NewService(odata.NewClientPool())
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationID:     "op-unicode-actor",
		OperationType:   "pool.publication_odata",
		ExecutionID:     "exec-unicode-actor",
		NodeID:          "publication_odata",
		PoolRunID:       "run-unicode-actor",
		StepAttempt:     1,
		PublicationAuth: publicationAuthActorForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{"Amount": "100.00"},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "published", out["status"])
}

func TestODataPublicationTransport_ExecutePublicationOData_ServiceStrategySupportsUnicodeCredentials(t *testing.T) {
	username := "СервисПользователь"
	password := "секретПароль"
	expectedAuthorization := "Basic " + base64.StdEncoding.EncodeToString([]byte(username+":"+password))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, expectedAuthorization, r.Header.Get("Authorization"))
		switch r.Method {
		case http.MethodPost:
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"Ref_Key": "550e8400-e29b-41d4-a716-446655440001",
			})
		case http.MethodPatch:
			w.WriteHeader(http.StatusNoContent)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
	defer server.Close()

	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   server.URL,
			Username:   username,
			Password:   password,
		},
	}
	service := odata.NewService(odata.NewClientPool())
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationID:     "op-unicode-service",
		OperationType:   "pool.publication_odata",
		ExecutionID:     "exec-unicode-service",
		NodeID:          "publication_odata",
		PoolRunID:       "run-unicode-service",
		StepAttempt:     1,
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{"Amount": "100.00"},
					},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "published", out["status"])
}

func TestODataPublicationTransport_ExecutePublicationOData_InvalidPayload(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": []interface{}{"invalid"},
			},
		},
	})

	var opErr *handlers.OperationExecutionError
	require.Error(t, err)
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodePoolRuntimePublicationPayloadInvalid, opErr.Code)
}

func TestODataPublicationTransport_ExecutePublicationOData_FailsClosedWithoutPublicationAuth(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.publication_odata",
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodeODataPublicationAuthContextInvalid, opErr.Code)
	assert.Equal(t, 0, service.createCalls)
}

func TestODataPublicationTransport_ExecutePublicationOData_FailsClosedForInvalidPublicationAuthVariants(t *testing.T) {
	testCases := []struct {
		name            string
		publicationAuth *handlers.PublicationAuth
	}{
		{
			name: "missing source",
			publicationAuth: &handlers.PublicationAuth{
				Strategy: "service",
			},
		},
		{
			name: "actor strategy without actor username",
			publicationAuth: &handlers.PublicationAuth{
				Strategy: "actor",
				Source:   "confirm_publication",
			},
		},
		{
			name: "unknown strategy",
			publicationAuth: &handlers.PublicationAuth{
				Strategy: "invalid",
				Source:   "run_create",
			},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			fetcher := &mockPublicationCredentialsFetcher{}
			service := &mockPublicationODataService{}
			transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

			_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
				OperationType:   "pool.publication_odata",
				PublicationAuth: tc.publicationAuth,
				Payload: map[string]interface{}{
					"pool_runtime": map[string]interface{}{
						"documents_by_database": map[string]interface{}{
							"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
						},
					},
				},
			})

			require.Error(t, err)
			var opErr *handlers.OperationExecutionError
			require.True(t, errors.As(err, &opErr))
			assert.Equal(t, ErrorCodeODataPublicationAuthContextInvalid, opErr.Code)
			assert.Equal(t, 0, service.createCalls)
		})
	}
}

func TestODataPublicationTransport_ExecutePublicationOData_TransientErrorRetriesToBudget(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{
		createErr: &odata.ODataError{Code: odata.ErrorCategoryServer, Message: "temporary", StatusCode: 503, IsTransient: true},
	}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"max_attempts": float64(3),
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "failed", out["status"])
	assert.Equal(t, 1, out["failed_targets"])
	assert.Equal(t, 0, out["succeeded_targets"])
	assert.Equal(t, 3, service.createCalls)
}

func TestODataPublicationTransport_ExecutePublicationOData_PartialSuccess(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		credsByDatabase: map[string]*credentials.DatabaseCredentials{
			"db-success": {
				DatabaseID: "db-success",
				ODataURL:   "http://success/odata/standard.odata",
				Username:   "admin",
				Password:   "secret",
			},
			"db-failed": {
				DatabaseID: "db-failed",
				ODataURL:   "http://failed/odata/standard.odata",
				Username:   "admin",
				Password:   "secret",
			},
		},
	}
	service := &mockPublicationODataService{
		createErrByBaseURL: map[string]error{
			"http://failed/odata/standard.odata": &odata.ODataError{
				Code:        odata.ErrorCategoryValidation,
				Message:     "invalid payload",
				StatusCode:  400,
				IsTransient: false,
			},
		},
	}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{
		CompatibilityProfilePath:           testCompatibilityProfilePath(t),
		CompatibilityConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityWriteContentType:      "application/json;odata=nometadata",
		CompatibilityReleaseProfileVersion: "0.4.2-draft",
	})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-success": []interface{}{map[string]interface{}{"Amount": "70.00"}},
					"db-failed":  []interface{}{map[string]interface{}{"Amount": "30.00"}},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "partial_success", out["status"])
	assert.Equal(t, 2, out["documents_targets"])
	assert.Equal(t, 1, out["succeeded_targets"])
	assert.Equal(t, 1, out["failed_targets"])
}

func TestODataPublicationTransport_ExecutePublicationOData_RejectsMaxAttemptsOutOfContract(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{
		CompatibilityProfilePath:           testCompatibilityProfilePath(t),
		CompatibilityConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityWriteContentType:      "application/json;odata=nometadata",
		CompatibilityReleaseProfileVersion: "0.4.2-draft",
	})

	_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"max_attempts": float64(6),
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodePoolRuntimePublicationPayloadInvalid, opErr.Code)
	assert.Contains(t, opErr.Message, "max_attempts")
}

func TestODataPublicationTransport_ExecutePublicationOData_RejectsRetryIntervalOutOfContract(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{
		CompatibilityProfilePath:           testCompatibilityProfilePath(t),
		CompatibilityConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityWriteContentType:      "application/json;odata=nometadata",
		CompatibilityReleaseProfileVersion: "0.4.2-draft",
	})

	_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"retry_interval_seconds": float64(121),
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodePoolRuntimePublicationPayloadInvalid, opErr.Code)
	assert.Contains(t, opErr.Message, "retry_interval_seconds")
}

func TestODataPublicationTransport_ExecutePublicationOData_NormalizesFailedDatabaseDiagnostics(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{
		createErr: &odata.ODataError{
			Code:        "CONFLICT_WRITE",
			Message:     "already exists",
			StatusCode:  409,
			IsTransient: false,
		},
	}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)

	diagnosticsRaw, ok := out["failed_databases_diagnostics"].(map[string]map[string]interface{})
	require.True(t, ok)
	diagnostics, ok := diagnosticsRaw["db-1"]
	require.True(t, ok)
	assert.Equal(t, "CONFLICT_WRITE", diagnostics["error_code"])
	assert.Equal(t, "conflict", diagnostics["error_class"])
	assert.Equal(t, "4xx", diagnostics["status_class"])
	assert.Equal(t, false, diagnostics["retryable"])
	assert.Equal(t, 1, diagnostics["attempts"])
}

func TestODataPublicationTransport_ExecutePublicationOData_ClassifiesAuthRejectionAsMappingNotConfigured(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{
		createErr: &odata.ODataError{
			Code:        odata.ErrorCategoryAuth,
			Message:     "Unauthorized",
			StatusCode:  401,
			IsTransient: false,
		},
	}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)
	assert.Equal(t, "failed", out["status"])

	diagnosticsRaw, ok := out["failed_databases_diagnostics"].(map[string]map[string]interface{})
	require.True(t, ok)
	diagnostics, ok := diagnosticsRaw["db-1"]
	require.True(t, ok)
	assert.Equal(t, ErrorCodeODataMappingNotConfigured, diagnostics["error_code"])
	assert.Equal(t, "validation", diagnostics["error_class"])
	assert.Equal(t, "4xx", diagnostics["status_class"])
	assert.Equal(t, false, diagnostics["retryable"])
	assert.Equal(t, 1, diagnostics["attempts"])

	attempts, ok := out["attempts"].([]map[string]interface{})
	require.True(t, ok)
	require.Len(t, attempts, 1)
	assert.Equal(t, ErrorCodeODataMappingNotConfigured, attempts[0]["error_code"])
}

func TestODataPublicationTransport_ExecutePublicationOData_FailsClosedOnCompatibilityMismatch(t *testing.T) {
	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   "http://localhost/odata/standard.odata",
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := &mockPublicationODataService{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{
		CompatibilityProfilePath:           testCompatibilityProfilePath(t),
		CompatibilityConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityWriteContentType:      "application/json;odata=verbose",
		CompatibilityReleaseProfileVersion: "0.4.2-draft",
	})

	_, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationType:   "pool.publication_odata",
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.Error(t, err)
	var opErr *handlers.OperationExecutionError
	require.True(t, errors.As(err, &opErr))
	assert.Equal(t, ErrorCodePoolRuntimePublicationCompatibilityBlocked, opErr.Code)
	assert.Contains(t, opErr.Message, "write_content_type")
	assert.Equal(t, 0, service.createCalls)
}

func TestODataPublicationTransport_ExecutePublicationOData_EmitsTransportRetryTrace(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodPost:
			attempts++
			if attempts == 1 {
				w.WriteHeader(http.StatusServiceUnavailable)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"Ref_Key": "550e8400-e29b-41d4-a716-446655440000",
			})
		case http.MethodPatch:
			w.WriteHeader(http.StatusNoContent)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
	defer server.Close()

	fetcher := &mockPublicationCredentialsFetcher{
		cred: &credentials.DatabaseCredentials{
			DatabaseID: "db-1",
			ODataURL:   server.URL,
			Username:   "admin",
			Password:   "secret",
		},
	}
	service := odata.NewService(odata.NewClientPool())
	timeline := &publicationTimelineSpy{}
	transport := NewODataPublicationTransport(fetcher, service, zap.NewNop(), PublicationTransportConfig{
		Timeline: timeline,
	})

	out, err := transport.ExecutePublicationOData(context.Background(), &handlers.OperationRequest{
		OperationID:     "op-transport-1",
		OperationType:   "pool.publication_odata",
		ExecutionID:     "exec-1",
		NodeID:          "publication_odata",
		PoolRunID:       "run-1",
		StepAttempt:     1,
		PublicationAuth: publicationAuthServiceForTests(),
		Payload: map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"max_attempts": float64(2),
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{map[string]interface{}{"Amount": "100.00"}},
				},
			},
		},
	})

	require.NoError(t, err)
	require.NotNil(t, out)

	var sawRetry bool
	var sawResendCompleted bool
	for _, record := range timeline.records {
		if record.event == "external.odata.transport.retry.scheduled" {
			sawRetry = true
			assert.Equal(t, "op-transport-1", record.operationID)
			assert.Equal(t, "pool.publication_odata", record.metadata["transport_operation"])
			assert.Equal(t, "db-1", record.metadata["database_id"])
			assert.Equal(t, 1, record.metadata["attempt"])
			assert.Equal(t, 2, record.metadata["next_attempt"])
		}
		if record.event == "external.odata.transport.request.completed" && record.metadata["attempt"] == 2 {
			sawResendCompleted = true
			assert.Equal(t, true, record.metadata["resend_attempt"])
		}
	}
	assert.True(t, sawRetry)
	assert.True(t, sawResendCompleted)
}

func TestBuildExternalRunKey_IsDeterministicForSameAttempt(t *testing.T) {
	first := buildExternalRunKey("run-1", "db-1", "Document_IntercompanyPoolDistribution", 2, 0)
	second := buildExternalRunKey("run-1", "db-1", "Document_IntercompanyPoolDistribution", 2, 0)

	assert.Equal(t, first, second)
	assert.Contains(t, first, "runkey-")
}

func TestBuildExternalRunKey_ChangesAcrossAttempts(t *testing.T) {
	first := buildExternalRunKey("run-1", "db-1", "Document_IntercompanyPoolDistribution", 1, 0)
	second := buildExternalRunKey("run-1", "db-1", "Document_IntercompanyPoolDistribution", 2, 0)

	assert.NotEqual(t, first, second)
}

func TestMapPublicationResolutionOutcome(t *testing.T) {
	assert.Equal(
		t,
		"ambiguous_mapping",
		mapPublicationResolutionOutcome(
			ErrorCodeODataMappingAmbiguous,
			publicationAuthContext{Strategy: publicationAuthStrategyActor},
		),
	)
	assert.Equal(
		t,
		"missing_mapping",
		mapPublicationResolutionOutcome(
			ErrorCodeODataMappingNotConfigured,
			publicationAuthContext{Strategy: publicationAuthStrategyActor},
		),
	)
	assert.Equal(
		t,
		"invalid_auth_context",
		mapPublicationResolutionOutcome(
			ErrorCodeODataPublicationAuthContextInvalid,
			publicationAuthContext{Strategy: publicationAuthStrategyActor},
		),
	)
	assert.Equal(
		t,
		"actor_success",
		mapPublicationResolutionOutcome(
			"",
			publicationAuthContext{Strategy: publicationAuthStrategyActor},
		),
	)
	assert.Equal(
		t,
		"service_success",
		mapPublicationResolutionOutcome(
			"",
			publicationAuthContext{Strategy: publicationAuthStrategyService},
		),
	)
}

func TestIsRetryablePublicationErr_Classifier(t *testing.T) {
	assert.True(t, isRetryablePublicationErr(context.DeadlineExceeded))
	assert.False(t, isRetryablePublicationErr(context.Canceled))
	assert.True(t, isRetryablePublicationErr(&odata.ODataError{
		Code:        odata.ErrorCategoryServer,
		Message:     "temporary",
		StatusCode:  503,
		IsTransient: true,
	}))
	assert.False(t, isRetryablePublicationErr(&odata.ODataError{
		Code:        odata.ErrorCategoryValidation,
		Message:     "invalid request",
		StatusCode:  400,
		IsTransient: false,
	}))
}

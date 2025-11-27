package v2

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
)

// ============================================================================
// Mock Services
// ============================================================================

type mockClusterService struct {
	clusters     []*models.Cluster
	getError     error
	getByIDError error
}

func (m *mockClusterService) GetClusters(ctx context.Context, serverAddr string) ([]*models.Cluster, error) {
	if m.getError != nil {
		return nil, m.getError
	}
	return m.clusters, nil
}

func (m *mockClusterService) GetClusterByID(ctx context.Context, serverAddr, clusterID string) (*models.Cluster, error) {
	if m.getByIDError != nil {
		return nil, m.getByIDError
	}
	for _, c := range m.clusters {
		if c.UUID == clusterID {
			return c, nil
		}
	}
	return nil, fmt.Errorf("cluster not found")
}

type mockInfobaseService struct {
	infobases         []*models.Infobase
	getError          error
	getByIDError      error
	createError       error
	dropError         error
	lockError         error
	unlockError       error
	blockError        error
	unblockError      error
	createdInfobaseID string
}

func (m *mockInfobaseService) GetInfobases(ctx context.Context, clusterID string) ([]*models.Infobase, error) {
	if m.getError != nil {
		return nil, m.getError
	}
	return m.infobases, nil
}

func (m *mockInfobaseService) GetInfobaseByID(ctx context.Context, clusterID, infobaseID string) (*models.Infobase, error) {
	if m.getByIDError != nil {
		return nil, m.getByIDError
	}
	for _, i := range m.infobases {
		if i.UUID == infobaseID {
			return i, nil
		}
	}
	return nil, fmt.Errorf("infobase not found")
}

func (m *mockInfobaseService) CreateInfobase(ctx context.Context, clusterID string, infobase *models.Infobase) (string, error) {
	if m.createError != nil {
		return "", m.createError
	}
	if m.createdInfobaseID == "" {
		m.createdInfobaseID = uuid.New().String()
	}
	return m.createdInfobaseID, nil
}

func (m *mockInfobaseService) DropInfobase(ctx context.Context, clusterID, infobaseID string, dropDB bool) error {
	if m.dropError != nil {
		return m.dropError
	}
	return nil
}

func (m *mockInfobaseService) LockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error {
	if m.lockError != nil {
		return m.lockError
	}
	return nil
}

func (m *mockInfobaseService) UnlockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error {
	if m.unlockError != nil {
		return m.unlockError
	}
	return nil
}

func (m *mockInfobaseService) BlockSessions(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string, deniedFrom, deniedTo time.Time, deniedMsg, permCode, param string) error {
	if m.blockError != nil {
		return m.blockError
	}
	return nil
}

func (m *mockInfobaseService) UnblockSessions(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error {
	if m.unblockError != nil {
		return m.unblockError
	}
	return nil
}

type mockSessionService struct {
	sessions             []*models.Session
	getError             error
	terminateError       error
	terminateSingleError error
	terminatedCount      int
}

func (m *mockSessionService) GetSessions(ctx context.Context, clusterID, infobaseID string) ([]*models.Session, error) {
	if m.getError != nil {
		return nil, m.getError
	}
	return m.sessions, nil
}

func (m *mockSessionService) TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error) {
	if m.terminateError != nil {
		return 0, m.terminateError
	}
	return m.terminatedCount, nil
}

func (m *mockSessionService) TerminateSession(ctx context.Context, clusterID, sessionID string) error {
	if m.terminateSingleError != nil {
		return m.terminateSingleError
	}
	return nil
}

// ============================================================================
// Test Helpers
// ============================================================================

func setupTestRouter(
	clusterSvc *mockClusterService,
	infobaseSvc *mockInfobaseService,
	sessionSvc *mockSessionService,
) *gin.Engine {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	v2Group := router.Group("/api/v2")

	// Use the REAL SetupRoutes function from routes.go
	// This ensures tests validate actual handler behavior, not duplicated logic
	SetupRoutes(v2Group, clusterSvc, infobaseSvc, sessionSvc)

	return router
}

func makeRequest(
	t *testing.T,
	router *gin.Engine,
	method string,
	path string,
	body interface{},
	contentType string,
) *httptest.ResponseRecorder {
	var bodyReader *bytes.Buffer
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		assert.NoError(t, err)
		bodyReader = bytes.NewBuffer(bodyBytes)
	} else {
		bodyReader = bytes.NewBuffer([]byte{})
	}

	req := httptest.NewRequest(method, path, bodyReader)
	if body != nil && contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}

	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	return w
}

func validUUID() string {
	return uuid.New().String()
}

func newTestCluster() *models.Cluster {
	return &models.Cluster{
		UUID: validUUID(),
		Name: "Test Cluster",
		Host: "localhost",
		Port: 1545,
	}
}

func newTestInfobase() *models.Infobase {
	return &models.Infobase{
		UUID:     validUUID(),
		Name:     "TestDB",
		DBMS:     "PostgreSQL",
		DBServer: "localhost",
		DBName:   "test_db",
	}
}

func newTestSession() *models.Session {
	return &models.Session{
		UUID:        validUUID(),
		SessionID:   validUUID(),
		UserName:    "TestUser",
		Application: "1cv8",
		StartedAt:   time.Now().Format(time.RFC3339),
	}
}

// ============================================================================
// ListClusters Tests
// ============================================================================

func TestListClusters_Success(t *testing.T) {
	mockClusterSvc := &mockClusterService{
		clusters: []*models.Cluster{newTestCluster()},
	}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-clusters?server=localhost:1545", nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp ClustersResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 1, resp.Count)
	assert.Len(t, resp.Clusters, 1)
}

func TestListClusters_MissingServer(t *testing.T) {
	mockClusterSvc := &mockClusterService{}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-clusters", nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "server parameter is required")
	assert.Equal(t, "MISSING_PARAMETER", resp.Code)
}

func TestListClusters_ServiceError(t *testing.T) {
	mockClusterSvc := &mockClusterService{
		getError: fmt.Errorf("RAS connection failed"),
	}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-clusters?server=localhost:1545", nil, "")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to retrieve clusters")
}

func TestListClusters_EmptyList(t *testing.T) {
	mockClusterSvc := &mockClusterService{
		clusters: []*models.Cluster{},
	}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-clusters?server=localhost:1545", nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp ClustersResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 0, resp.Count)
	assert.Len(t, resp.Clusters, 0)
}

func TestListClusters_MultipleResults(t *testing.T) {
	mockClusterSvc := &mockClusterService{
		clusters: []*models.Cluster{
			newTestCluster(),
			newTestCluster(),
			newTestCluster(),
		},
	}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-clusters?server=localhost:1545", nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp ClustersResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 3, resp.Count)
	assert.Len(t, resp.Clusters, 3)
}

// ============================================================================
// GetCluster Tests
// ============================================================================

func TestGetCluster_Success(t *testing.T) {
	cluster := newTestCluster()
	mockClusterSvc := &mockClusterService{
		clusters: []*models.Cluster{cluster},
	}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-cluster?cluster_id=%s&server=localhost:1545", cluster.UUID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp ClusterResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.NotNil(t, resp.Cluster)
	assert.Equal(t, cluster.UUID, resp.Cluster.UUID)
}

func TestGetCluster_MissingClusterID(t *testing.T) {
	mockClusterSvc := &mockClusterService{}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/get-cluster?server=localhost:1545", nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "cluster_id")
}

func TestGetCluster_MissingServer(t *testing.T) {
	clusterID := validUUID()
	mockClusterSvc := &mockClusterService{}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-cluster?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "server")
}

func TestGetCluster_InvalidUUID(t *testing.T) {
	mockClusterSvc := &mockClusterService{}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/get-cluster?cluster_id=invalid-uuid&server=localhost:1545", nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "must be a valid UUID")
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestGetCluster_NotFound(t *testing.T) {
	mockClusterSvc := &mockClusterService{
		getByIDError: fmt.Errorf("cluster not found"),
	}
	router := setupTestRouter(mockClusterSvc, &mockInfobaseService{}, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-cluster?cluster_id=%s&server=localhost:1545", validUUID())
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusNotFound, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Cluster not found")
}

// ============================================================================
// ListInfobases Tests
// ============================================================================

func TestListInfobases_Success(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		infobases: []*models.Infobase{newTestInfobase()},
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/list-infobases?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp InfobasesResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 1, resp.Count)
	assert.Len(t, resp.Infobases, 1)
}

func TestListInfobases_MissingClusterID(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-infobases", nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "cluster_id")
}

func TestListInfobases_InvalidClusterUUID(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	w := makeRequest(t, router, "GET", "/api/v2/list-infobases?cluster_id=not-a-uuid", nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestListInfobases_ServiceError(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{
		getError: fmt.Errorf("RAS error"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/list-infobases?cluster_id=%s", validUUID())
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to retrieve infobases")
}

func TestListInfobases_EmptyList(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{
		infobases: []*models.Infobase{},
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/list-infobases?cluster_id=%s", validUUID())
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp InfobasesResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 0, resp.Count)
}

// ============================================================================
// GetInfobase Tests
// ============================================================================

func TestGetInfobase_Success(t *testing.T) {
	clusterID := validUUID()
	infobase := newTestInfobase()
	mockInfobaseSvc := &mockInfobaseService{
		infobases: []*models.Infobase{infobase},
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobase.UUID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp InfobaseResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.NotNil(t, resp.Infobase)
	assert.Equal(t, infobase.UUID, resp.Infobase.UUID)
}

func TestGetInfobase_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-infobase?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "cluster_id")
}

func TestGetInfobase_MissingInfobaseID(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-infobase?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "infobase_id")
}

func TestGetInfobase_InvalidClusterUUID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-infobase?cluster_id=invalid&infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestGetInfobase_InvalidInfobaseUUID(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-infobase?cluster_id=%s&infobase_id=invalid", clusterID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestGetInfobase_NotFound(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		getByIDError: fmt.Errorf("infobase not found"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/get-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusNotFound, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Infobase not found")
}

// ============================================================================
// CreateInfobase Tests
// ============================================================================

func TestCreateInfobase_Success(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		createdInfobaseID: validUUID(),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := CreateInfobaseRequest{
		Name:   "NewDB",
		DBMS:   "PostgreSQL",
		DBName: "new_db",
	}

	path := fmt.Sprintf("/api/v2/create-infobase?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusCreated, w.Code)

	var resp CreateInfobaseResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
	assert.NotEmpty(t, resp.InfobaseID)
	assert.Equal(t, "Infobase created successfully", resp.Message)
}

func TestCreateInfobase_MissingClusterID(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := CreateInfobaseRequest{
		Name:   "NewDB",
		DBMS:   "PostgreSQL",
		DBName: "new_db",
	}

	w := makeRequest(t, router, "POST", "/api/v2/create-infobase", body, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "cluster_id")
}

func TestCreateInfobase_InvalidClusterUUID(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := CreateInfobaseRequest{
		Name:   "NewDB",
		DBMS:   "PostgreSQL",
		DBName: "new_db",
	}

	w := makeRequest(t, router, "POST", "/api/v2/create-infobase?cluster_id=invalid", body, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestCreateInfobase_InvalidBody(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/create-infobase?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "POST", path, "invalid json", "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Invalid request body")
}

func TestCreateInfobase_ServiceError(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		createError: fmt.Errorf("database error"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := CreateInfobaseRequest{
		Name:   "NewDB",
		DBMS:   "PostgreSQL",
		DBName: "new_db",
	}

	path := fmt.Sprintf("/api/v2/create-infobase?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to create infobase")
}

// ============================================================================
// DropInfobase Tests
// ============================================================================

func TestDropInfobase_Success(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := DropInfobaseRequest{DropDatabase: true}
	path := fmt.Sprintf("/api/v2/drop-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SuccessResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
	assert.Contains(t, resp.Message, "dropped")
}

func TestDropInfobase_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/drop-infobase?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestDropInfobase_InvalidClusterUUID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/drop-infobase?cluster_id=invalid&infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestDropInfobase_InvalidInfobaseUUID(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/drop-infobase?cluster_id=%s&infobase_id=invalid", clusterID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestDropInfobase_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		dropError: fmt.Errorf("drop failed"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := DropInfobaseRequest{DropDatabase: true}
	path := fmt.Sprintf("/api/v2/drop-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to drop infobase")
}

// ============================================================================
// LockInfobase Tests
// ============================================================================

func TestLockInfobase_Success(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/lock-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SuccessResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
	assert.Contains(t, resp.Message, "locked")
}

func TestLockInfobase_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/lock-infobase?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestLockInfobase_MissingInfobaseID(t *testing.T) {
	clusterID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/lock-infobase?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestLockInfobase_InvalidUUIDs(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	w := makeRequest(t, router, "POST", "/api/v2/lock-infobase?cluster_id=bad&infobase_id=bad", map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestLockInfobase_WithCredentials(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := LockInfobaseRequest{
		DBUser:     "admin",
		DBPassword: "password123",
	}

	path := fmt.Sprintf("/api/v2/lock-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestLockInfobase_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		lockError: fmt.Errorf("lock failed"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/lock-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

// ============================================================================
// UnlockInfobase Tests
// ============================================================================

func TestUnlockInfobase_Success(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/unlock-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SuccessResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
	assert.Contains(t, resp.Message, "unlocked")
}

func TestUnlockInfobase_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/unlock-infobase?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestUnlockInfobase_InvalidUUIDs(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	w := makeRequest(t, router, "POST", "/api/v2/unlock-infobase?cluster_id=bad&infobase_id=bad", map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestUnlockInfobase_WithCredentials(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := UnlockInfobaseRequest{
		DBUser:     "admin",
		DBPassword: "password123",
	}

	path := fmt.Sprintf("/api/v2/unlock-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestUnlockInfobase_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		unlockError: fmt.Errorf("unlock failed"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/unlock-infobase?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

// ============================================================================
// BlockSessions Tests
// ============================================================================

func TestBlockSessions_Success(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := BlockSessionsRequest{
		DeniedMessage:  "Scheduled maintenance",
		PermissionCode: "ADMIN",
	}

	path := fmt.Sprintf("/api/v2/block-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SuccessResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
}

func TestBlockSessions_WithTimeRange(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	now := time.Now()
	deniedFrom := now.Add(time.Hour)
	deniedTo := now.Add(2 * time.Hour)

	body := BlockSessionsRequest{
		DeniedFrom:     &deniedFrom,
		DeniedTo:       &deniedTo,
		DeniedMessage:  "Scheduled maintenance",
		PermissionCode: "ADMIN",
	}

	path := fmt.Sprintf("/api/v2/block-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestBlockSessions_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/block-sessions?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestBlockSessions_InvalidUUIDs(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	w := makeRequest(t, router, "POST", "/api/v2/block-sessions?cluster_id=bad&infobase_id=bad", map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestBlockSessions_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		blockError: fmt.Errorf("block failed"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := BlockSessionsRequest{
		DeniedMessage: "Maintenance",
	}

	path := fmt.Sprintf("/api/v2/block-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestBlockSessions_MinimalBody(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/block-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)
}

// ============================================================================
// UnblockSessions Tests
// ============================================================================

func TestUnblockSessions_Success(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/unblock-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SuccessResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
}

func TestUnblockSessions_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/unblock-sessions?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestUnblockSessions_InvalidUUIDs(t *testing.T) {
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	w := makeRequest(t, router, "POST", "/api/v2/unblock-sessions?cluster_id=bad&infobase_id=bad", map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestUnblockSessions_WithCredentials(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	body := UnblockSessionsRequest{
		DBUser:     "admin",
		DBPassword: "password123",
	}

	path := fmt.Sprintf("/api/v2/unblock-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestUnblockSessions_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockInfobaseSvc := &mockInfobaseService{
		unblockError: fmt.Errorf("unblock failed"),
	}
	router := setupTestRouter(&mockClusterService{}, mockInfobaseSvc, &mockSessionService{})

	path := fmt.Sprintf("/api/v2/unblock-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

// ============================================================================
// ListSessions Tests
// ============================================================================

func TestListSessions_Success(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{
		sessions: []*models.Session{newTestSession()},
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/list-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SessionsResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 1, resp.Count)
	assert.Len(t, resp.Sessions, 1)
}

func TestListSessions_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/list-sessions?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestListSessions_InvalidClusterUUID(t *testing.T) {
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/list-sessions?cluster_id=bad&infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestListSessions_InvalidInfobaseUUID(t *testing.T) {
	clusterID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/list-sessions?cluster_id=%s&infobase_id=bad", clusterID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestListSessions_EmptyList(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{
		sessions: []*models.Session{},
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/list-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp SessionsResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 0, resp.Count)
}

func TestListSessions_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{
		getError: fmt.Errorf("RAS error"),
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/list-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "GET", path, nil, "")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to retrieve sessions")
}

// ============================================================================
// TerminateSession Tests
// ============================================================================

func TestTerminateSession_Success(t *testing.T) {
	clusterID := validUUID()
	sessionID := validUUID()

	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-session?cluster_id=%s&session_id=%s", clusterID, sessionID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp TerminateSessionResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
	assert.Equal(t, sessionID, resp.SessionID)
	assert.Contains(t, resp.Message, "terminated")
}

func TestTerminateSession_MissingClusterID(t *testing.T) {
	sessionID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-session?session_id=%s", sessionID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestTerminateSession_MissingSessionID(t *testing.T) {
	clusterID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-session?cluster_id=%s", clusterID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestTerminateSession_InvalidUUIDs(t *testing.T) {
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	w := makeRequest(t, router, "POST", "/api/v2/terminate-session?cluster_id=bad&session_id=bad", map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestTerminateSession_SessionNotFound_IsIdempotent(t *testing.T) {
	// Idempotent behavior: if session not found, return success (session already terminated)
	clusterID := validUUID()
	sessionID := validUUID()
	mockSessionSvc := &mockSessionService{
		// No error - idempotent behavior means success even if session doesn't exist
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-session?cluster_id=%s&session_id=%s", clusterID, sessionID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	// Idempotent: session not found = success
	assert.Equal(t, http.StatusOK, w.Code)

	var resp TerminateSessionResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.True(t, resp.Success)
}

func TestTerminateSession_ServiceError(t *testing.T) {
	clusterID := validUUID()
	sessionID := validUUID()
	mockSessionSvc := &mockSessionService{
		terminateSingleError: fmt.Errorf("RAS error"),
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-session?cluster_id=%s&session_id=%s", clusterID, sessionID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to terminate session")
}

// ============================================================================
// TerminateSessions Tests
// ============================================================================

func TestTerminateSessions_AllSessions(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{
		terminatedCount: 5,
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp TerminateSessionsResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 5, resp.TerminatedCount)
	assert.Equal(t, 0, resp.FailedCount)
}

func TestTerminateSessions_MissingClusterID(t *testing.T) {
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-sessions?infobase_id=%s", infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestTerminateSessions_InvalidUUIDs(t *testing.T) {
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	w := makeRequest(t, router, "POST", "/api/v2/terminate-sessions?cluster_id=bad&infobase_id=bad", map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestTerminateSessions_WithSessionIDs(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	body := TerminateSessionsRequest{
		SessionIDs: []string{validUUID(), validUUID()},
	}

	path := fmt.Sprintf("/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	// Currently returns NOT_IMPLEMENTED
	assert.Equal(t, http.StatusNotImplemented, w.Code)
}

func TestTerminateSessions_InvalidSessionID(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	body := TerminateSessionsRequest{
		SessionIDs: []string{"invalid-uuid"},
	}

	path := fmt.Sprintf("/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, body, "application/json")

	assert.Equal(t, http.StatusBadRequest, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "INVALID_UUID", resp.Code)
}

func TestTerminateSessions_ServiceError(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{
		terminateError: fmt.Errorf("RAS error"),
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusInternalServerError, w.Code)

	var resp ErrorResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Contains(t, resp.Error, "Failed to terminate sessions")
}

func TestTerminateSessions_NoSessions(t *testing.T) {
	clusterID := validUUID()
	infobaseID := validUUID()
	mockSessionSvc := &mockSessionService{
		terminatedCount: 0,
	}
	router := setupTestRouter(&mockClusterService{}, &mockInfobaseService{}, mockSessionSvc)

	path := fmt.Sprintf("/api/v2/terminate-sessions?cluster_id=%s&infobase_id=%s", clusterID, infobaseID)
	w := makeRequest(t, router, "POST", path, map[string]interface{}{}, "application/json")

	assert.Equal(t, http.StatusOK, w.Code)

	var resp TerminateSessionsResponse
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, 0, resp.TerminatedCount)
}

// ============================================================================
// UUID Validation Helper Tests
// ============================================================================

func TestIsValidUUID(t *testing.T) {
	tests := []struct {
		name  string
		uuid  string
		valid bool
	}{
		{
			name:  "Valid UUID v4",
			uuid:  "550e8400-e29b-41d4-a716-446655440000",
			valid: true,
		},
		{
			name:  "Invalid UUID",
			uuid:  "not-a-uuid",
			valid: false,
		},
		{
			name:  "Empty string",
			uuid:  "",
			valid: false,
		},
		{
			name:  "UUID without hyphens (still valid in Go)",
			uuid:  "550e8400e29b41d4a716446655440000",
			valid: true, // Go's uuid.Parse accepts UUIDs without hyphens
		},
		{
			name:  "Invalid hex characters",
			uuid:  "550e8400-e29b-41d4-a716-44665544000g",
			valid: false,
		},
		{
			name:  "Valid generated UUID",
			uuid:  validUUID(),
			valid: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isValidUUID(tt.uuid)
			assert.Equal(t, tt.valid, result)
		})
	}
}

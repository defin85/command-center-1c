package workflows

import (
	"context"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
)

// Mock implementations for testing

// mockResourceManager is a test double for resourcemanager.ResourceManager.
type mockResourceManager struct {
	locks map[string]string // database_id -> owner_id
}

func newMockResourceManager() *mockResourceManager {
	return &mockResourceManager{
		locks: make(map[string]string),
	}
}

func (m *mockResourceManager) AcquireLock(ctx context.Context, req *resourcemanager.LockRequest) (*resourcemanager.LockResult, error) {
	if owner, exists := m.locks[req.DatabaseID]; exists {
		if owner == req.OwnerID {
			return &resourcemanager.LockResult{Acquired: true}, nil
		}
		return &resourcemanager.LockResult{Acquired: false, QueuePosition: 1}, nil
	}
	m.locks[req.DatabaseID] = req.OwnerID
	return &resourcemanager.LockResult{Acquired: true}, nil
}

func (m *mockResourceManager) ReleaseLock(ctx context.Context, databaseID, ownerID string) error {
	if m.locks[databaseID] == ownerID {
		delete(m.locks, databaseID)
	}
	return nil
}

func (m *mockResourceManager) ExtendLock(ctx context.Context, databaseID, ownerID string, ttl time.Duration) error {
	return nil
}

func (m *mockResourceManager) GetLockInfo(ctx context.Context, databaseID string) (*resourcemanager.LockInfo, error) {
	if owner, exists := m.locks[databaseID]; exists {
		return &resourcemanager.LockInfo{
			DatabaseID: databaseID,
			OwnerID:    owner,
		}, nil
	}
	return nil, fmt.Errorf("lock not found")
}

func (m *mockResourceManager) GetQueuePosition(ctx context.Context, databaseID, ownerID string) (int, error) {
	return 0, nil
}

func (m *mockResourceManager) CancelWait(ctx context.Context, databaseID, ownerID string) error {
	return nil
}

func (m *mockResourceManager) GetQueue(ctx context.Context, databaseID string) ([]*resourcemanager.QueueEntry, error) {
	return nil, nil
}

func (m *mockResourceManager) GetAllLocks(ctx context.Context) ([]*resourcemanager.LockInfo, error) {
	var locks []*resourcemanager.LockInfo
	for dbID, owner := range m.locks {
		locks = append(locks, &resourcemanager.LockInfo{
			DatabaseID: dbID,
			OwnerID:    owner,
		})
	}
	return locks, nil
}

func (m *mockResourceManager) ReleaseAllByOwner(ctx context.Context, ownerID string) (int, error) {
	count := 0
	for dbID, owner := range m.locks {
		if owner == ownerID {
			delete(m.locks, dbID)
			count++
		}
	}
	return count, nil
}

func (m *mockResourceManager) StartCleanupWorker(ctx context.Context, interval time.Duration) {
}

func (m *mockResourceManager) Close() error {
	return nil
}

// mockRASClient is a test double for RASClient.
type mockRASClient struct {
	lockScheduledJobsCalled   bool
	unlockScheduledJobsCalled bool
	terminateSessionsCalled   bool
	blockConnectionsCalled    bool
	unblockConnectionsCalled  bool
}

func (m *mockRASClient) LockScheduledJobs(ctx context.Context, clusterID, databaseID string) error {
	m.lockScheduledJobsCalled = true
	return nil
}

func (m *mockRASClient) UnlockScheduledJobs(ctx context.Context, clusterID, databaseID string) error {
	m.unlockScheduledJobsCalled = true
	return nil
}

func (m *mockRASClient) TerminateSessions(ctx context.Context, clusterID, databaseID string) error {
	m.terminateSessionsCalled = true
	return nil
}

func (m *mockRASClient) BlockConnections(ctx context.Context, clusterID, databaseID string) error {
	m.blockConnectionsCalled = true
	return nil
}

func (m *mockRASClient) UnblockConnections(ctx context.Context, clusterID, databaseID string) error {
	m.unblockConnectionsCalled = true
	return nil
}

func (m *mockRASClient) GetSessionCount(ctx context.Context, clusterID, databaseID string) (int, error) {
	return 0, nil
}

// mockODataClient is a test double for ODataClient.
type mockODataClient struct {
	executeBatchCalled bool
}

func (m *mockODataClient) Query(ctx context.Context, creds odata.ODataCredentials, entity string, query *odata.QueryParams) ([]map[string]interface{}, error) {
	return nil, nil
}

func (m *mockODataClient) Create(ctx context.Context, creds odata.ODataCredentials, entity string, data map[string]interface{}) (map[string]interface{}, error) {
	return data, nil
}

func (m *mockODataClient) Update(ctx context.Context, creds odata.ODataCredentials, entity, entityID string, data map[string]interface{}) error {
	return nil
}

func (m *mockODataClient) Delete(ctx context.Context, creds odata.ODataCredentials, entity, entityID string) error {
	return nil
}

func (m *mockODataClient) ExecuteBatch(ctx context.Context, creds odata.ODataCredentials, items []odata.BatchItem) (*odata.BatchResult, error) {
	m.executeBatchCalled = true
	return &odata.BatchResult{
		TotalCount:   len(items),
		SuccessCount: len(items),
		FailureCount: 0,
		Items:        make([]odata.BatchItemResult, len(items)),
	}, nil
}

// mockDesignerClient is a test double for DesignerClient.
type mockDesignerClient struct {
	installExtensionCalled bool
	removeExtensionCalled  bool
	loadConfigCalled       bool
	updateDBCfgCalled      bool
	dumpConfigCalled       bool
}

func (m *mockDesignerClient) InstallExtension(ctx context.Context, ssh SSHCredentials, dbPath, extFile, extName string) error {
	m.installExtensionCalled = true
	return nil
}

func (m *mockDesignerClient) RemoveExtension(ctx context.Context, ssh SSHCredentials, dbPath, extName string) error {
	m.removeExtensionCalled = true
	return nil
}

func (m *mockDesignerClient) UpdateDBCfg(ctx context.Context, ssh SSHCredentials, dbPath string) error {
	m.updateDBCfgCalled = true
	return nil
}

func (m *mockDesignerClient) LoadConfig(ctx context.Context, ssh SSHCredentials, dbPath, cfFile string) error {
	m.loadConfigCalled = true
	return nil
}

func (m *mockDesignerClient) DumpConfig(ctx context.Context, ssh SSHCredentials, dbPath, targetPath string) error {
	m.dumpConfigCalled = true
	return nil
}

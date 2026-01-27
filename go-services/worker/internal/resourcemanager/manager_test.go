package resourcemanager

import (
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupTestRedis creates a miniredis instance and client for testing.
func setupTestRedis(t *testing.T) (*miniredis.Miniredis, *redis.Client) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	t.Cleanup(func() {
		mr.Close()
	})

	client := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})
	t.Cleanup(func() {
		client.Close()
	})

	return mr, client
}

// TestLockRequest_Validate tests LockRequest validation.
func TestLockRequest_Validate(t *testing.T) {
	tests := []struct {
		name    string
		req     *LockRequest
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid request",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				Operation:  "extension_install",
			},
			wantErr: false,
		},
		{
			name: "missing database_id",
			req: &LockRequest{
				OwnerID:   "workflow-456",
				Operation: "extension_install",
			},
			wantErr: true,
			errMsg:  "database_id is required",
		},
		{
			name: "missing owner_id",
			req: &LockRequest{
				DatabaseID: "db-123",
				Operation:  "extension_install",
			},
			wantErr: true,
			errMsg:  "owner_id is required",
		},
		{
			name: "ttl below minimum",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				TTL:        10 * time.Second,
			},
			wantErr: true,
			errMsg:  "ttl is below minimum",
		},
		{
			name: "ttl exceeds maximum",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				TTL:        2 * time.Hour,
			},
			wantErr: true,
			errMsg:  "ttl exceeds maximum",
		},
		{
			name: "negative ttl",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				TTL:        -1 * time.Second,
			},
			wantErr: true,
			errMsg:  "ttl cannot be negative",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.req.Validate()
			if tt.wantErr {
				assert.Error(t, err)
				assert.Contains(t, err.Error(), tt.errMsg)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

// TestLockRequest_GetTTL tests TTL default behavior.
func TestLockRequest_GetTTL(t *testing.T) {
	t.Run("returns default when zero", func(t *testing.T) {
		req := &LockRequest{TTL: 0}
		assert.Equal(t, DefaultLockTTL, req.GetTTL())
	})

	t.Run("returns specified when set", func(t *testing.T) {
		req := &LockRequest{TTL: 5 * time.Minute}
		assert.Equal(t, 5*time.Minute, req.GetTTL())
	})
}

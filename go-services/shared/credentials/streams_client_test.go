package credentials

import (
	"context"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

func createTestRedisClientForCredentials(t *testing.T) *redis.Client {
	t.Helper()

	client := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   15,
	})

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		t.Skipf("Redis not available: %v", err)
	}

	require.NoError(t, client.FlushDB(context.Background()).Err())
	return client
}

func TestStreamsClient_Fetch_Success(t *testing.T) {
	redisClient := createTestRedisClientForCredentials(t)
	defer redisClient.Close()

	transportKey := make([]byte, 32)
	for i := range transportKey {
		transportKey[i] = byte(i)
	}

	client, err := NewStreamsClient(StreamsClientConfig{
		RedisClient:    redisClient,
		TransportKey:   transportKey,
		RequestTimeout: 2 * time.Second,
	})
	require.NoError(t, err)
	defer client.Close()

	resultCh := make(chan *DatabaseCredentials, 1)
	errCh := make(chan error, 1)

	go func() {
		creds, err := client.Fetch(context.Background(), "db-123")
		if err != nil {
			errCh <- err
			return
		}
		resultCh <- creds
	}()

	// Read the request from command stream
	reqMsg, err := redisClient.XRead(context.Background(), &redis.XReadArgs{
		Streams: []string{events.StreamCommandsGetDatabaseCredentials, "0"},
		Count:   1,
		Block:   2 * time.Second,
	}).Result()
	require.NoError(t, err)
	require.Len(t, reqMsg, 1)
	require.Len(t, reqMsg[0].Messages, 1)

	msg := reqMsg[0].Messages[0]
	corrID, _ := msg.Values["correlation_id"].(string)
	dbID, _ := msg.Values["database_id"].(string)
	require.NotEmpty(t, corrID)
	require.Equal(t, "db-123", dbID)

	enc, err := EncryptCredentials(&DatabaseCredentials{
		DatabaseID: "db-123",
		ODataURL:   "http://localhost/odata",
		Username:   "admin",
		Password:   "secret",
	}, transportKey)
	require.NoError(t, err)

	// Publish the response as if orchestrator responded
	err = redisClient.XAdd(context.Background(), &redis.XAddArgs{
		Stream: events.StreamEventsDatabaseCredentialsResponse,
		Values: map[string]interface{}{
			"correlation_id":     corrID,
			"database_id":        "db-123",
			"success":            "true",
			"error":              "",
			"encrypted_data":     enc.EncryptedData,
			"nonce":              enc.Nonce,
			"expires_at":         enc.ExpiresAt,
			"encryption_version": enc.EncryptionVersion,
		},
	}).Err()
	require.NoError(t, err)

	select {
	case got := <-resultCh:
		require.Equal(t, "db-123", got.DatabaseID)
		require.Equal(t, "secret", got.Password)
	case err := <-errCh:
		t.Fatalf("unexpected error: %v", err)
	case <-time.After(3 * time.Second):
		t.Fatal("timeout waiting for credentials")
	}
}

func TestStreamsClient_Fetch_NotFound(t *testing.T) {
	redisClient := createTestRedisClientForCredentials(t)
	defer redisClient.Close()

	transportKey := make([]byte, 32)
	client, err := NewStreamsClient(StreamsClientConfig{
		RedisClient:    redisClient,
		TransportKey:   transportKey,
		RequestTimeout: 2 * time.Second,
	})
	require.NoError(t, err)
	defer client.Close()

	errCh := make(chan error, 1)
	go func() {
		_, err := client.Fetch(context.Background(), "db-missing")
		errCh <- err
	}()

	reqMsg, err := redisClient.XRead(context.Background(), &redis.XReadArgs{
		Streams: []string{events.StreamCommandsGetDatabaseCredentials, "0"},
		Count:   1,
		Block:   2 * time.Second,
	}).Result()
	require.NoError(t, err)
	msg := reqMsg[0].Messages[0]
	corrID, _ := msg.Values["correlation_id"].(string)
	require.NotEmpty(t, corrID)

	require.NoError(t, redisClient.XAdd(context.Background(), &redis.XAddArgs{
		Stream: events.StreamEventsDatabaseCredentialsResponse,
		Values: map[string]interface{}{
			"correlation_id": corrID,
			"database_id":    "db-missing",
			"success":        "false",
			"error":          "Database db-missing not found",
		},
	}).Err())

	select {
	case err := <-errCh:
		require.Error(t, err)
	case <-time.After(3 * time.Second):
		t.Fatal("timeout waiting for error")
	}
}

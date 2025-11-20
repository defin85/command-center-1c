// +build integration

package integration

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// TestRedisConnectionHealthIntegration tests basic Redis health
func TestRedisConnectionHealthIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("redis_ping", func(t *testing.T) {
		result, err := redisClient.Ping(ctx).Result()
		require.NoError(t, err)
		assert.Equal(t, "PONG", result)
		t.Log("Redis Ping: PONG")
	})
}

// TestRedisKeyValueIntegration tests basic Redis key/value operations
func TestRedisKeyValueIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("redis_set_get", func(t *testing.T) {
		key := "test:integration:key"
		value := "test-value"

		// Set value
		err := redisClient.Set(ctx, key, value, 10*time.Second).Err()
		require.NoError(t, err)

		// Get value
		result, err := redisClient.Get(ctx, key).Result()
		require.NoError(t, err)
		assert.Equal(t, value, result)

		// Delete
		redisClient.Del(ctx, key)
		t.Log("Redis Set/Get: OK")
	})
}

// TestRedisEventEnvelopeIntegration tests event envelope serialization
func TestRedisEventEnvelopeIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("event_envelope_serialization", func(t *testing.T) {
		key := "test:envelope"

		// Create event envelope
		envelope := events.Envelope{
			CorrelationID: "test-op-001",
			Timestamp:     time.Now(),
			Payload: map[string]interface{}{
				"cluster_id":  "cluster-uuid",
				"infobase_id": "infobase-uuid",
			},
		}

		// Serialize
		data, err := json.Marshal(envelope)
		require.NoError(t, err)

		// Store in Redis
		err = redisClient.Set(ctx, key, data, 10*time.Second).Err()
		require.NoError(t, err)

		// Retrieve and deserialize
		stored, err := redisClient.Get(ctx, key).Result()
		require.NoError(t, err)

		var retrieved events.Envelope
		err = json.Unmarshal([]byte(stored), &retrieved)
		require.NoError(t, err)

		assert.Equal(t, envelope.CorrelationID, retrieved.CorrelationID)

		// Cleanup
		redisClient.Del(ctx, key)
		t.Log("Event envelope serialization: OK")
	})
}

// TestRedisPubSubIntegration tests Redis Pub/Sub functionality
func TestRedisPubSubIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("redis_pubsub", func(t *testing.T) {
		channel := "test:channel"
		message := "test-message"

		// Subscribe
		pubsub := redisClient.Subscribe(ctx, channel)
		defer pubsub.Close()

		// Wait for subscription
		_, err := pubsub.Receive(ctx)
		require.NoError(t, err)

		// Publish message
		go func() {
			time.Sleep(100 * time.Millisecond)
			err := redisClient.Publish(ctx, channel, message).Err()
			assert.NoError(t, err)
		}()

		// Receive message
		msgChan := pubsub.Channel()
		select {
		case msg := <-msgChan:
			assert.Equal(t, message, msg.Payload)
			t.Logf("Redis Pub/Sub: received %s", msg.Payload)
		case <-time.After(2 * time.Second):
			t.Fatal("Timeout waiting for message")
		}
	})
}

// TestRedisPubSubWithEnvelope tests Pub/Sub with event envelopes
func TestRedisPubSubWithEnvelope(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("pubsub_with_envelope", func(t *testing.T) {
		channel := "test:envelope:channel"

		// Subscribe to channel
		pubsub := redisClient.Subscribe(ctx, channel)
		defer pubsub.Close()

		// Wait for subscription
		_, err := pubsub.Receive(ctx)
		require.NoError(t, err)

		// Create and publish event
		go func() {
			time.Sleep(100 * time.Millisecond)

			envelope := events.Envelope{
				CorrelationID: "test-op-001",
				Timestamp:     time.Now(),
				Payload: map[string]interface{}{
					"action": "lock",
					"status": "success",
				},
			}

			data, err := json.Marshal(envelope)
			assert.NoError(t, err)

			err = redisClient.Publish(ctx, channel, data).Err()
			assert.NoError(t, err)
		}()

		// Receive and deserialize event
		msgChan := pubsub.Channel()
		select {
		case msg := <-msgChan:
			var received events.Envelope
			err := json.Unmarshal([]byte(msg.Payload), &received)
			assert.NoError(t, err)
			assert.Equal(t, "test-op-001", received.CorrelationID)
			t.Logf("Received envelope: %s", received.CorrelationID)

		case <-time.After(2 * time.Second):
			t.Fatal("Timeout waiting for envelope")
		}
	})
}

// TestRedisMultiplePubSubChannels tests multiple Pub/Sub channels
func TestRedisMultiplePubSubChannels(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("multiple_pubsub_channels", func(t *testing.T) {
		channel1 := "test:channel:1"
		channel2 := "test:channel:2"

		// Subscribe to both channels
		pubsub := redisClient.Subscribe(ctx, channel1, channel2)
		defer pubsub.Close()

		// Wait for subscriptions
		for i := 0; i < 2; i++ {
			_, err := pubsub.Receive(ctx)
			require.NoError(t, err)
		}

		// Publish to both channels
		go func() {
			time.Sleep(100 * time.Millisecond)
			redisClient.Publish(ctx, channel1, "message1")
			redisClient.Publish(ctx, channel2, "message2")
		}()

		// Receive messages
		msgChan := pubsub.Channel()
		receivedCount := 0
		received := make(map[string]bool)

		for receivedCount < 2 {
			select {
			case msg := <-msgChan:
				received[msg.Channel] = true
				receivedCount++

			case <-time.After(3 * time.Second):
				t.Fatal("Timeout waiting for messages")
			}
		}

		assert.True(t, received[channel1])
		assert.True(t, received[channel2])
		t.Log("Multiple channels: OK")
	})
}

// TestRedisPatternSubscription tests pattern-based subscription
func TestRedisPatternSubscription(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("pattern_subscription", func(t *testing.T) {
		pattern := "test:event:*"

		// Subscribe to pattern
		pubsub := redisClient.PSubscribe(ctx, pattern)
		defer pubsub.Close()

		// Wait for subscription
		_, err := pubsub.Receive(ctx)
		require.NoError(t, err)

		// Publish to matching channels
		go func() {
			time.Sleep(100 * time.Millisecond)
			redisClient.Publish(ctx, "test:event:lock", "data1")
			redisClient.Publish(ctx, "test:event:unlock", "data2")
		}()

		// Receive messages
		msgChan := pubsub.Channel()
		receivedCount := 0

		for receivedCount < 2 {
			select {
			case msg := <-msgChan:
				assert.Contains(t, msg.Channel, "test:event:")
				receivedCount++

			case <-time.After(3 * time.Second):
				t.Fatal("Timeout waiting for messages")
			}
		}

		t.Log("Pattern subscription: OK")
	})
}

// TestRedisConcurrentPublishers tests concurrent publishers
func TestRedisConcurrentPublishers(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("concurrent_publishers", func(t *testing.T) {
		channel := "test:concurrent"
		const numPublishers = 5

		// Subscribe
		pubsub := redisClient.Subscribe(ctx, channel)
		defer pubsub.Close()

		_, err := pubsub.Receive(ctx)
		require.NoError(t, err)

		// Launch concurrent publishers
		go func() {
			time.Sleep(100 * time.Millisecond)
			for i := 0; i < numPublishers; i++ {
				redisClient.Publish(ctx, channel, "msg")
			}
		}()

		// Receive messages
		msgChan := pubsub.Channel()
		receivedCount := 0

		for receivedCount < numPublishers {
			select {
			case <-msgChan:
				receivedCount++
			case <-time.After(3 * time.Second):
				t.Fatal("Timeout waiting for messages")
			}
		}

		assert.Equal(t, numPublishers, receivedCount)
		t.Logf("Concurrent publishers: %d messages received", receivedCount)
	})
}

// TestRedisConnectionReuse tests connection reuse
func TestRedisConnectionReuse(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("redis_connection_reuse", func(t *testing.T) {
		const iterations = 10

		for i := 0; i < iterations; i++ {
			// Multiple operations on same connection
			err := redisClient.Set(ctx, "key", "value", time.Second).Err()
			require.NoError(t, err)

			_, err = redisClient.Get(ctx, "key").Result()
			require.NoError(t, err)

			err = redisClient.Del(ctx, "key").Err()
			require.NoError(t, err)
		}

		t.Logf("Redis connection reuse: %d iterations completed", iterations)
	})
}

// TestRedisEventChannelIntegration tests full event channel workflow
func TestRedisEventChannelIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("event_channel_workflow", func(t *testing.T) {
		commandChannel := "commands:cluster-service:infobase:lock"
		eventChannel := "events:cluster-service:infobase:locked"
		operationID := "test-op-" + time.Now().Format("20060102150405")

		// Subscribe to event channel
		pubsub := redisClient.Subscribe(ctx, eventChannel)
		defer pubsub.Close()

		_, err := pubsub.Receive(ctx)
		require.NoError(t, err)

		// Publish command
		go func() {
			time.Sleep(100 * time.Millisecond)

			payload := map[string]interface{}{
				"cluster_id":  "cluster-1",
				"infobase_id": "infobase-1",
			}

			envelope := events.Envelope{
				CorrelationID: operationID,
				Timestamp:     time.Now(),
				Payload:       payload,
			}

			data, err := json.Marshal(envelope)
			assert.NoError(t, err)

			err = redisClient.Publish(ctx, commandChannel, data).Err()
			assert.NoError(t, err)

			// Simulate event handler publishing success event
			time.Sleep(200 * time.Millisecond)

			eventData, _ := json.Marshal(events.Envelope{
				CorrelationID: operationID,
				Timestamp:     time.Now(),
				Payload: map[string]interface{}{
					"status": "success",
				},
			})

			redisClient.Publish(ctx, eventChannel, eventData)
		}()

		// Wait for event
		msgChan := pubsub.Channel()
		select {
		case msg := <-msgChan:
			var received events.Envelope
			err := json.Unmarshal([]byte(msg.Payload), &received)
			require.NoError(t, err)

			assert.Equal(t, operationID, received.CorrelationID)
			t.Logf("Event channel workflow: received event for %s", operationID)

		case <-time.After(5 * time.Second):
			t.Fatal("Timeout waiting for event channel")
		}
	})
}

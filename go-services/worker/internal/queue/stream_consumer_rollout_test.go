package queue

import (
	"context"
	"strconv"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

func factualSyncRolloutMessage(
	operationID string,
	perDatabaseCap int,
	perClusterCap int,
	globalCap int,
	targetDatabases ...models.TargetDatabase,
) *models.OperationMessage {
	return &models.OperationMessage{
		Version:         "2.0",
		OperationID:     operationID,
		OperationType:   "pool.factual.sync_source_slice",
		Entity:          "pool_factual_sync",
		TargetDatabases: targetDatabases,
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"per_database_cap": strconv.Itoa(perDatabaseCap),
				"per_cluster_cap":  strconv.Itoa(perClusterCap),
				"global_cap":       strconv.Itoa(globalCap),
			},
		},
		ExecConfig: models.ExecutionConfig{
			Priority: "p1",
		},
		Metadata: models.MessageMetadata{
			Role:           "read",
			ServerAffinity: "srv-factual-a",
		},
	}
}

func TestTryAcquireFactualRolloutAdmission_EnforcesEnvelopeCaps(t *testing.T) {
	t.Run("per database cap", func(t *testing.T) {
		consumer := &Consumer{}
		first := factualSyncRolloutMessage(
			"op-db-1",
			2,
			3,
			4,
			models.TargetDatabase{ID: "db-a", ClusterID: "cluster-a"},
		)
		second := factualSyncRolloutMessage(
			"op-db-2",
			2,
			3,
			4,
			models.TargetDatabase{ID: "db-a", ClusterID: "cluster-b"},
		)
		third := factualSyncRolloutMessage(
			"op-db-3",
			2,
			3,
			4,
			models.TargetDatabase{ID: "db-a", ClusterID: "cluster-c"},
		)

		release1, ok1 := consumer.tryAcquireFactualRolloutAdmission(first)
		require.True(t, ok1)
		require.NotNil(t, release1)

		release2, ok2 := consumer.tryAcquireFactualRolloutAdmission(second)
		require.True(t, ok2)
		require.NotNil(t, release2)

		release3, ok3 := consumer.tryAcquireFactualRolloutAdmission(third)
		assert.False(t, ok3, "same database must be capped even across different clusters")
		assert.Nil(t, release3)

		release1()
		release2()
	})

	t.Run("per cluster cap", func(t *testing.T) {
		consumer := &Consumer{}
		first := factualSyncRolloutMessage(
			"op-cluster-1",
			3,
			2,
			4,
			models.TargetDatabase{ID: "db-a", ClusterID: "cluster-a"},
		)
		second := factualSyncRolloutMessage(
			"op-cluster-2",
			3,
			2,
			4,
			models.TargetDatabase{ID: "db-b", ClusterID: "cluster-a"},
		)
		third := factualSyncRolloutMessage(
			"op-cluster-3",
			3,
			2,
			4,
			models.TargetDatabase{ID: "db-c", ClusterID: "cluster-a"},
		)

		release1, ok1 := consumer.tryAcquireFactualRolloutAdmission(first)
		require.True(t, ok1)
		require.NotNil(t, release1)

		release2, ok2 := consumer.tryAcquireFactualRolloutAdmission(second)
		require.True(t, ok2)
		require.NotNil(t, release2)

		release3, ok3 := consumer.tryAcquireFactualRolloutAdmission(third)
		assert.False(t, ok3, "same cluster must be capped even across different databases")
		assert.Nil(t, release3)

		release1()
		release2()
	})

	t.Run("global cap", func(t *testing.T) {
		consumer := &Consumer{}
		first := factualSyncRolloutMessage(
			"op-global-1",
			3,
			3,
			1,
			models.TargetDatabase{ID: "db-a", ClusterID: "cluster-a"},
		)
		second := factualSyncRolloutMessage(
			"op-global-2",
			3,
			3,
			1,
			models.TargetDatabase{ID: "db-b", ClusterID: "cluster-b"},
		)

		release1, ok1 := consumer.tryAcquireFactualRolloutAdmission(first)
		require.True(t, ok1)
		require.NotNil(t, release1)

		release2, ok2 := consumer.tryAcquireFactualRolloutAdmission(second)
		assert.False(t, ok2, "global factual cap must limit total active syncs")
		assert.Nil(t, release2)

		release1()
	})
}

func TestAcquireFactualRolloutAdmission_WaitsUntilCapacityFreed(t *testing.T) {
	consumer := &Consumer{}
	msg := factualSyncRolloutMessage(
		"op-wait-1",
		1,
		1,
		1,
		models.TargetDatabase{ID: "db-a", ClusterID: "cluster-a"},
	)

	release1, ok := consumer.tryAcquireFactualRolloutAdmission(msg)
	require.True(t, ok)
	require.NotNil(t, release1)

	releaseCh := make(chan struct{})
	go func() {
		time.Sleep(20 * time.Millisecond)
		release1()
		close(releaseCh)
	}()

	ctx, cancel := context.WithTimeout(context.Background(), 150*time.Millisecond)
	defer cancel()

	release2, ok := consumer.acquireFactualRolloutAdmission(ctx, msg)
	require.True(t, ok)
	require.NotNil(t, release2)
	release2()

	<-releaseCh
}

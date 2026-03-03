package queue

import (
	"testing"

	"github.com/stretchr/testify/assert"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

func TestResolveSchedulingPoolKey_UsesMetadata(t *testing.T) {
	msg := &models.OperationMessage{
		Metadata: models.MessageMetadata{
			Role:           "Inbound",
			ServerAffinity: "SRV-1C-A",
			Priority:       "P1",
		},
	}

	poolKey := resolveSchedulingPoolKey(msg)
	assert.Equal(t, "srv-1c-a|inbound|p1", poolKey)
}

func TestResolveSchedulingPoolKey_FallsBackToPayloadData(t *testing.T) {
	msg := &models.OperationMessage{
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"role":            "manual_remediation",
				"server_affinity": "Srv-1C-B",
				"priority":        "p0",
			},
		},
	}

	poolKey := resolveSchedulingPoolKey(msg)
	assert.Equal(t, "srv-1c-b|manual_remediation|p0", poolKey)
}

func TestResolveSchedulingPoolKey_UsesExecConfigPriorityFallback(t *testing.T) {
	msg := &models.OperationMessage{
		Metadata: models.MessageMetadata{
			Role:           "reconcile",
			ServerAffinity: "srv-1c-c",
		},
		ExecConfig: models.ExecutionConfig{
			Priority: "p2",
		},
	}

	poolKey := resolveSchedulingPoolKey(msg)
	assert.Equal(t, "srv-1c-c|reconcile|p2", poolKey)
}

func TestResolveSchedulingPoolKey_UsesDefaultWhenSchedulingFieldsMissing(t *testing.T) {
	assert.Equal(t, defaultSchedulingPoolKey, resolveSchedulingPoolKey(nil))
	assert.Equal(t, defaultSchedulingPoolKey, resolveSchedulingPoolKey(&models.OperationMessage{}))
}

func TestEnsureSchedulingPool_RespectsPoolGroupLimit(t *testing.T) {
	defaultPool := make(chan struct{}, 1)
	consumer := &Consumer{
		schedulingPools: map[string]chan struct{}{
			defaultSchedulingPoolKey: defaultPool,
		},
		perSchedulingPoolSize:   1,
		maxSchedulingPoolGroups: 2,
	}

	poolA := consumer.ensureSchedulingPool("srv-a|inbound|p1")
	assert.NotEqual(t, defaultPool, poolA)

	poolB := consumer.ensureSchedulingPool("srv-b|outbound|p2")
	assert.Equal(t, defaultPool, poolB)
}

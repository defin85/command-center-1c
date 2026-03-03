package queue

import (
	"context"
	"fmt"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

func TestResolveTenantKey_UsesPayloadAndInputContextFallback(t *testing.T) {
	msg := &models.OperationMessage{
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"input_context": map[string]interface{}{
					"tenant_id": "tenant-nested",
				},
			},
		},
	}
	assert.Equal(t, "tenant-nested", resolveTenantKey(msg))

	msg.Payload.Data["tenant_id"] = "tenant-top-level"
	assert.Equal(t, "tenant-top-level", resolveTenantKey(msg))
}

func TestBuildFairnessProfile_PromotesOldMessages(t *testing.T) {
	consumer := &Consumer{
		oldestAgeThreshold: defaultOldestAgeThreshold,
	}
	messageID := fmt.Sprintf("%d-0", time.Now().Add(-3*time.Minute).UnixMilli())
	msg := &models.OperationMessage{
		Metadata: models.MessageMetadata{
			Role:           "reconcile",
			ServerAffinity: "srv-1c-a",
		},
	}

	profile := consumer.buildFairnessProfile(msg, messageID)
	assert.Equal(t, "reconcile", profile.role)
	assert.Equal(t, "srv-1c-a", profile.affinity)
	assert.True(t, profile.promoted)
	assert.GreaterOrEqual(t, profile.age, 3*time.Minute-time.Second)
}

func TestAcquireTenantBudget_EnforcesShareWithPromotionBypass(t *testing.T) {
	consumer := &Consumer{
		workerPoolSize:       4,
		tenantBudgetShare:    0.5,
		tenantActiveByServer: map[string]map[string]int{},
	}
	profile := fairnessProfile{tenant: "tenant-a", affinity: "srv-a"}

	release1, ok1 := consumer.acquireTenantBudget(profile)
	release2, ok2 := consumer.acquireTenantBudget(profile)
	_, ok3 := consumer.acquireTenantBudget(profile)

	assert.True(t, ok1)
	assert.True(t, ok2)
	assert.False(t, ok3, "third task for same tenant should be throttled at limit=2")

	promotedProfile := fairnessProfile{tenant: "tenant-a", affinity: "srv-a", promoted: true}
	releasePromoted, okPromoted := consumer.acquireTenantBudget(promotedProfile)
	assert.True(t, okPromoted, "promoted task should bypass tenant budget for anti-starvation")

	if releasePromoted != nil {
		releasePromoted()
	}
	if release2 != nil {
		release2()
	}
	if release1 != nil {
		release1()
	}
}

func TestAcquireRegularExecutionSlot_PromotedTaskCanUseManualReserve(t *testing.T) {
	consumer := &Consumer{
		generalWorkerSlots: make(chan struct{}, 1),
		manualReserveSlots: make(chan struct{}, 1),
	}

	consumer.generalWorkerSlots <- struct{}{}

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	release, ok := consumer.acquireRegularExecutionSlot(ctx, true)
	assert.True(t, ok)
	assert.NotNil(t, release)
	release()

	<-consumer.generalWorkerSlots
}

func TestAcquireManualExecutionSlot_TracksWaiters(t *testing.T) {
	consumer := &Consumer{
		generalWorkerSlots: make(chan struct{}, 1),
		manualReserveSlots: make(chan struct{}, 1),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	release, ok := consumer.acquireManualExecutionSlot(ctx, "srv-a")
	assert.True(t, ok)
	assert.NotNil(t, release)
	release()

	assert.Equal(t, int64(0), atomic.LoadInt64(&consumer.manualWaiters))
}

package queue

import (
	"context"
	"math"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

const (
	defaultOldestAgeThreshold  = 120 * time.Second
	defaultTenantBudgetShare   = 0.5
	defaultTenantBudgetBackoff = 25 * time.Millisecond
)

type fairnessProfile struct {
	role     string
	affinity string
	tenant   string
	age      time.Duration
	promoted bool
}

func (c *Consumer) buildFairnessProfile(msg *models.OperationMessage, messageID string) fairnessProfile {
	role := normalizeSchedulingToken(msg.Metadata.Role)
	if role == "" {
		role = normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "role"))
	}

	affinity := normalizeSchedulingToken(msg.Metadata.ServerAffinity)
	if affinity == "" {
		affinity = normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "server_affinity"))
	}
	if affinity == "" {
		affinity = "shared"
	}

	tenant := resolveTenantKey(msg)
	age := resolveMessageAge(msg, messageID)
	threshold := c.oldestAgeThreshold
	if threshold <= 0 {
		threshold = defaultOldestAgeThreshold
	}

	return fairnessProfile{
		role:     role,
		affinity: affinity,
		tenant:   tenant,
		age:      age,
		promoted: age >= threshold,
	}
}

func resolveTenantKey(msg *models.OperationMessage) string {
	if msg == nil {
		return "shared"
	}

	if tenant := normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "tenant_id")); tenant != "" {
		return tenant
	}
	if tenant := normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "tenant")); tenant != "" {
		return tenant
	}

	inputContext, ok := msg.Payload.Data["input_context"].(map[string]interface{})
	if ok {
		if tenant := normalizeSchedulingToken(readMessagePayloadToken(inputContext, "tenant_id")); tenant != "" {
			return tenant
		}
		if tenant := normalizeSchedulingToken(readMessagePayloadToken(inputContext, "tenant")); tenant != "" {
			return tenant
		}
	}

	return "shared"
}

func resolveMessageAge(msg *models.OperationMessage, messageID string) time.Duration {
	now := time.Now().UTC()
	if msg != nil && !msg.Metadata.CreatedAt.IsZero() {
		createdAt := msg.Metadata.CreatedAt.UTC()
		if createdAt.Before(now) {
			return now.Sub(createdAt)
		}
	}

	createdAt := parseRedisMessageTimestamp(messageID)
	if createdAt.IsZero() || createdAt.After(now) {
		return 0
	}
	return now.Sub(createdAt)
}

func parseRedisMessageTimestamp(messageID string) time.Time {
	token := strings.TrimSpace(messageID)
	if token == "" {
		return time.Time{}
	}
	msToken := token
	if idx := strings.Index(token, "-"); idx > 0 {
		msToken = token[:idx]
	}
	ms, err := strconv.ParseInt(msToken, 10, 64)
	if err != nil || ms <= 0 {
		return time.Time{}
	}
	return time.UnixMilli(ms).UTC()
}

func (c *Consumer) acquireFairnessGuards(
	ctx context.Context,
	profile fairnessProfile,
) (release func(), ok bool) {
	for {
		execRelease, acquired := c.acquireExecutionSlot(ctx, profile)
		if !acquired {
			return nil, false
		}

		budgetRelease, budgetAllowed := c.acquireTenantBudget(profile)
		if budgetAllowed {
			return func() {
				if budgetRelease != nil {
					budgetRelease()
				}
				if execRelease != nil {
					execRelease()
				}
			}, true
		}

		execRelease()

		select {
		case <-ctx.Done():
			return nil, false
		case <-time.After(c.tenantBudgetBackoffDuration()):
		}
	}
}

func (c *Consumer) acquireExecutionSlot(
	ctx context.Context,
	profile fairnessProfile,
) (release func(), ok bool) {
	role := normalizeSchedulingToken(profile.role)
	if role == "manual_remediation" {
		return c.acquireManualExecutionSlot(ctx, profile.affinity)
	}
	return c.acquireRegularExecutionSlot(ctx, profile.promoted)
}

func (c *Consumer) acquireManualExecutionSlot(ctx context.Context, affinity string) (func(), bool) {
	atomic.AddInt64(&c.manualWaiters, 1)
	defer atomic.AddInt64(&c.manualWaiters, -1)

	for {
		if c.manualReserveSlots != nil {
			select {
			case c.manualReserveSlots <- struct{}{}:
				setManualRemediationQuotaSaturationMetric(affinity, false)
				return func() { <-c.manualReserveSlots }, true
			default:
				setManualRemediationQuotaSaturationMetric(affinity, true)
			}
		}

		if c.generalWorkerSlots != nil {
			select {
			case c.generalWorkerSlots <- struct{}{}:
				if c.manualReserveSlots != nil {
					setManualRemediationQuotaSaturationMetric(affinity, true)
				}
				return func() { <-c.generalWorkerSlots }, true
			default:
			}
		}

		select {
		case <-ctx.Done():
			setManualRemediationQuotaSaturationMetric(affinity, false)
			return nil, false
		case <-time.After(10 * time.Millisecond):
		}
	}
}

func (c *Consumer) acquireRegularExecutionSlot(ctx context.Context, promoted bool) (func(), bool) {
	for {
		if c.generalWorkerSlots != nil {
			select {
			case c.generalWorkerSlots <- struct{}{}:
				return func() { <-c.generalWorkerSlots }, true
			default:
			}
		}

		if promoted && c.manualReserveSlots != nil && atomic.LoadInt64(&c.manualWaiters) == 0 {
			select {
			case c.manualReserveSlots <- struct{}{}:
				return func() { <-c.manualReserveSlots }, true
			default:
			}
		}

		select {
		case <-ctx.Done():
			return nil, false
		case <-time.After(10 * time.Millisecond):
		}
	}
}

func (c *Consumer) acquireTenantBudget(profile fairnessProfile) (release func(), ok bool) {
	tenantKey := strings.TrimSpace(profile.tenant)
	if tenantKey == "" {
		tenantKey = "shared"
	}

	affinityKey := strings.TrimSpace(profile.affinity)
	if affinityKey == "" {
		affinityKey = "shared"
	}

	c.tenantBudgetMu.Lock()
	defer c.tenantBudgetMu.Unlock()

	if c.tenantActiveByServer == nil {
		c.tenantActiveByServer = map[string]map[string]int{}
	}

	tenantCounters, exists := c.tenantActiveByServer[affinityKey]
	if !exists {
		tenantCounters = map[string]int{}
		c.tenantActiveByServer[affinityKey] = tenantCounters
	}

	limit := c.tenantBudgetLimit()
	current := tenantCounters[tenantKey]
	if !profile.promoted && current >= limit {
		recordTenantBudgetThrottleMetric(affinityKey)
		return nil, false
	}

	tenantCounters[tenantKey] = current + 1
	return func() {
		c.tenantBudgetMu.Lock()
		defer c.tenantBudgetMu.Unlock()
		counters := c.tenantActiveByServer[affinityKey]
		if counters == nil {
			return
		}
		next := counters[tenantKey] - 1
		if next <= 0 {
			delete(counters, tenantKey)
		} else {
			counters[tenantKey] = next
		}
		if len(counters) == 0 {
			delete(c.tenantActiveByServer, affinityKey)
		}
	}, true
}

func (c *Consumer) tenantBudgetLimit() int {
	share := c.tenantBudgetShare
	if share <= 0 || share > 1 {
		share = defaultTenantBudgetShare
	}
	size := c.workerPoolSize
	if size <= 0 {
		size = 1
	}
	limit := int(math.Floor(float64(size) * share))
	if limit < 1 {
		limit = 1
	}
	if limit > size {
		limit = size
	}
	return limit
}

func (c *Consumer) tenantBudgetBackoffDuration() time.Duration {
	delay := c.tenantBudgetBackoff
	if delay <= 0 {
		return defaultTenantBudgetBackoff
	}
	return delay
}

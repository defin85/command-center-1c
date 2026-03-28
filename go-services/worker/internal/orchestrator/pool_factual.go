package orchestrator

import "context"

const (
	pathPoolFactualActiveSyncWindow             = "/api/v2/internal/pools/factual/trigger-active-sync-window"
	pathPoolFactualClosedQuarterReconcileWindow = "/api/v2/internal/pools/factual/trigger-closed-quarter-reconcile-window"
)

// TriggerPoolFactualActiveSyncWindow triggers periodic active-quarter factual sync on orchestrator side.
func (c *Client) TriggerPoolFactualActiveSyncWindow(ctx context.Context) (*PoolFactualSyncWindowResponse, error) {
	var resp PoolFactualSyncWindowResponse
	if err := c.post(ctx, pathPoolFactualActiveSyncWindow, map[string]interface{}{}, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// TriggerPoolFactualClosedQuarterReconcileWindow triggers closed-quarter factual reconcile on orchestrator side.
func (c *Client) TriggerPoolFactualClosedQuarterReconcileWindow(ctx context.Context) (*PoolFactualSyncWindowResponse, error) {
	var resp PoolFactualSyncWindowResponse
	if err := c.post(ctx, pathPoolFactualClosedQuarterReconcileWindow, map[string]interface{}{}, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

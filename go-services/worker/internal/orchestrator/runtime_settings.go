package orchestrator

import "context"

// GetRuntimeSettings fetches runtime settings via internal API.
func (c *Client) GetRuntimeSettings(ctx context.Context) ([]RuntimeSetting, error) {
	var response RuntimeSettingsResponse
	if err := c.get(ctx, "/api/v2/internal/runtime-settings", &response); err != nil {
		return nil, err
	}
	return response.Settings, nil
}

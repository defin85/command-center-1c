package clusterclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}
}

// LockInfobase блокирует регламентные задания
func (c *Client) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	url := fmt.Sprintf("%s/api/v1/infobases/lock", c.baseURL)

	reqBody, _ := json.Marshal(map[string]string{
		"cluster_id":  clusterID,
		"infobase_id": infobaseID,
	})

	req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(reqBody))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to lock infobase: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("lock failed with status %d", resp.StatusCode)
	}

	return nil
}

// UnlockInfobase разблокирует регламентные задания
func (c *Client) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	url := fmt.Sprintf("%s/api/v1/infobases/unlock", c.baseURL)

	reqBody, _ := json.Marshal(map[string]string{
		"cluster_id":  clusterID,
		"infobase_id": infobaseID,
	})

	req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(reqBody))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to unlock infobase: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unlock failed with status %d", resp.StatusCode)
	}

	return nil
}

// TerminateSessions завершает все сессии
func (c *Client) TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error) {
	url := fmt.Sprintf("%s/api/v1/infobases/terminate-sessions", c.baseURL)

	reqBody, _ := json.Marshal(map[string]string{
		"cluster_id":  clusterID,
		"infobase_id": infobaseID,
	})

	req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(reqBody))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("failed to terminate sessions: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("terminate sessions failed with status %d", resp.StatusCode)
	}

	var result struct {
		TotalSessions int `json:"total_sessions"`
		Terminated    int `json:"terminated"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to parse response: %w", err)
	}

	return result.Terminated, nil
}

// GetSessionsCount получает количество активных сессий
func (c *Client) GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error) {
	url := fmt.Sprintf("%s/api/v1/infobases/sessions-count?cluster_id=%s&infobase_id=%s",
		c.baseURL, clusterID, infobaseID)

	req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("failed to get sessions count: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("get sessions count failed with status %d", resp.StatusCode)
	}

	var result struct {
		SessionsCount int `json:"sessions_count"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to parse response: %w", err)
	}

	return result.SessionsCount, nil
}

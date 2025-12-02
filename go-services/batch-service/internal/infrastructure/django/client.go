package django

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

// Client is an HTTP client for Django Orchestrator callbacks
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// NewClient creates a new Django client
func NewClient(baseURL string) *Client {
	if baseURL == "" {
		baseURL = "http://localhost:8200"
	}

	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// CallbackPayload represents the payload sent to Django callback endpoint
type CallbackPayload struct {
	DatabaseID      string  `json:"database_id"`
	ExtensionName   string  `json:"extension_name"`
	Status          string  `json:"status"` // "completed" | "failed"
	DurationSeconds float64 `json:"duration_seconds"`
	ErrorMessage    string  `json:"error_message,omitempty"`
}

// NotifyInstallationComplete sends a callback to Django after extension installation
func (c *Client) NotifyInstallationComplete(payload CallbackPayload) error {
	url := c.baseURL + "/api/v1/extensions/installation/callback/"

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	log.Printf("Sending callback to Django: %s (status: %s)", url, payload.Status)

	resp, err := c.httpClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("callback request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("callback error: status %d", resp.StatusCode)
	}

	log.Printf("Callback sent successfully to Django")
	return nil
}

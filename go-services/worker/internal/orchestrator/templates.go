package orchestrator

import (
	"context"
	"fmt"
)

// Template represents operation template from Orchestrator.
type Template struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	OperationType string                 `json:"operation_type"`
	TargetEntity  string                 `json:"target_entity"`
	TemplateData  map[string]interface{} `json:"template_data"`
	Version       int                    `json:"version"`
	IsActive      bool                   `json:"is_active"`
}

// TemplateRenderRequest is the request body for template rendering.
type TemplateRenderRequest struct {
	Context map[string]interface{} `json:"context"`
}

// TemplateRenderResponse is the response from template rendering.
type TemplateRenderResponse struct {
	Rendered map[string]interface{} `json:"rendered"`
	Success  bool                   `json:"success"`
	Error    string                 `json:"error,omitempty"`
}

// GetTemplate fetches template by ID from Orchestrator.
func (c *Client) GetTemplate(ctx context.Context, templateID string) (*Template, error) {
	path := fmt.Sprintf("/api/internal/templates/%s", templateID)

	var template Template
	if err := c.get(ctx, path, &template); err != nil {
		return nil, fmt.Errorf("failed to get template %s: %w", templateID, err)
	}

	return &template, nil
}

// RenderTemplate renders template via Python fallback API.
// This is called when Go pongo2 cannot handle the template syntax.
func (c *Client) RenderTemplate(ctx context.Context, templateID string, templateContext map[string]interface{}) (*TemplateRenderResponse, error) {
	path := fmt.Sprintf("/api/internal/templates/%s/render", templateID)

	reqBody := TemplateRenderRequest{Context: templateContext}

	var result TemplateRenderResponse
	if err := c.post(ctx, path, reqBody, &result); err != nil {
		return nil, fmt.Errorf("failed to render template %s: %w", templateID, err)
	}

	if !result.Success {
		return nil, fmt.Errorf("template render failed: %s", result.Error)
	}

	return &result, nil
}

// RenderTemplateRaw renders template and returns the raw response,
// including error information even on failed renders.
func (c *Client) RenderTemplateRaw(ctx context.Context, templateID string, templateContext map[string]interface{}) (*TemplateRenderResponse, error) {
	path := fmt.Sprintf("/api/internal/templates/%s/render", templateID)

	reqBody := TemplateRenderRequest{Context: templateContext}

	var result TemplateRenderResponse
	if err := c.post(ctx, path, reqBody, &result); err != nil {
		return nil, fmt.Errorf("failed to render template %s: %w", templateID, err)
	}

	return &result, nil
}

// FallbackRenderer implements template.FallbackClient interface
// for use with EngineWithFallback.
type FallbackRenderer struct {
	client *Client
}

// NewFallbackRenderer creates a new FallbackRenderer for template fallback.
func NewFallbackRenderer(client *Client) *FallbackRenderer {
	return &FallbackRenderer{client: client}
}

// RenderTemplate implements template.FallbackClient interface.
func (f *FallbackRenderer) RenderTemplate(ctx context.Context, templateID string, templateContext map[string]interface{}) (map[string]interface{}, error) {
	resp, err := f.client.RenderTemplate(ctx, templateID, templateContext)
	if err != nil {
		return nil, err
	}
	return resp.Rendered, nil
}

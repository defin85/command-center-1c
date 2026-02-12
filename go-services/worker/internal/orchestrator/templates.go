package orchestrator

import (
	"context"
	"fmt"
	"net/url"
	"strings"
)

const (
	// API paths for template endpoints
	pathTemplateGet    = "/api/v2/internal/get-template"
	pathTemplateRender = "/api/v2/internal/render-template"
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

func buildTemplateLookupPath(
	basePath,
	templateID,
	templateExposureID string,
	templateExposureRevision int,
) (string, error) {
	templateID = strings.TrimSpace(templateID)
	templateExposureID = strings.TrimSpace(templateExposureID)
	if templateID == "" && templateExposureID == "" {
		return "", fmt.Errorf("template reference is required")
	}

	params := url.Values{}
	if templateID != "" {
		params.Set("template_id", templateID)
	}
	if templateExposureID != "" {
		params.Set("template_exposure_id", templateExposureID)
	}
	if templateExposureRevision > 0 {
		params.Set("template_exposure_revision", fmt.Sprintf("%d", templateExposureRevision))
	}

	return fmt.Sprintf("%s?%s", basePath, params.Encode()), nil
}

// GetTemplate fetches template by alias or exposure ID from Orchestrator.
func (c *Client) GetTemplate(
	ctx context.Context,
	templateID,
	templateExposureID string,
	templateExposureRevision int,
) (*Template, error) {
	path, err := buildTemplateLookupPath(pathTemplateGet, templateID, templateExposureID, templateExposureRevision)
	if err != nil {
		return nil, err
	}

	var resp TemplateGetResponse
	if err := c.get(ctx, path, &resp); err != nil {
		templateRef := templateExposureID
		if templateRef == "" {
			templateRef = templateID
		}
		return nil, fmt.Errorf("failed to get template %s: %w", templateRef, err)
	}
	return &Template{
		ID:            resp.Template.ID,
		Name:          resp.Template.Name,
		OperationType: resp.Template.OperationType,
		TargetEntity:  resp.Template.TargetEntity,
		TemplateData:  resp.Template.TemplateData,
		Version:       resp.Template.Version,
		IsActive:      resp.Template.IsActive,
	}, nil
}

// RenderTemplate renders template via Python fallback API.
// This is called when Go pongo2 cannot handle the template syntax.
func (c *Client) RenderTemplate(
	ctx context.Context,
	templateID,
	templateExposureID string,
	templateExposureRevision int,
	templateContext map[string]interface{},
) (*TemplateRenderResponse, error) {
	result, err := c.RenderTemplateRaw(
		ctx,
		templateID,
		templateExposureID,
		templateExposureRevision,
		templateContext,
	)
	if err != nil {
		return nil, err
	}

	if !result.Success {
		return nil, fmt.Errorf("template render failed: %s", result.Error)
	}

	return result, nil
}

// RenderTemplateRaw renders template and returns the raw response,
// including error information even on failed renders.
func (c *Client) RenderTemplateRaw(
	ctx context.Context,
	templateID,
	templateExposureID string,
	templateExposureRevision int,
	templateContext map[string]interface{},
) (*TemplateRenderResponse, error) {
	path, err := buildTemplateLookupPath(
		pathTemplateRender,
		templateID,
		templateExposureID,
		templateExposureRevision,
	)
	if err != nil {
		return nil, err
	}

	reqBody := TemplateRenderRequest{Context: templateContext}

	var resp TemplateRenderResponse
	if err := c.post(ctx, path, reqBody, &resp); err != nil {
		templateRef := templateExposureID
		if templateRef == "" {
			templateRef = templateID
		}
		return nil, fmt.Errorf("failed to render template %s: %w", templateRef, err)
	}
	return &resp, nil
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
func (f *FallbackRenderer) RenderTemplate(
	ctx context.Context,
	templateID string,
	templateExposureID string,
	templateExposureRevision int,
	templateContext map[string]interface{},
) (map[string]interface{}, error) {
	resp, err := f.client.RenderTemplate(
		ctx,
		templateID,
		templateExposureID,
		templateExposureRevision,
		templateContext,
	)
	if err != nil {
		return nil, err
	}
	return resp.Rendered, nil
}

package templatesvc

import (
	"context"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

// OrchestratorTemplateClient adapts orchestrator.Client to TemplateClient interface.
type OrchestratorTemplateClient struct {
	client *orchestrator.Client
}

// NewOrchestratorTemplateClient creates a new adapter for orchestrator.Client.
func NewOrchestratorTemplateClient(client *orchestrator.Client) *OrchestratorTemplateClient {
	return &OrchestratorTemplateClient{client: client}
}

// GetTemplate fetches template from Orchestrator and converts to TemplateData.
func (a *OrchestratorTemplateClient) GetTemplate(ctx context.Context, templateID string) (*TemplateData, error) {
	tmpl, err := a.client.GetTemplate(ctx, templateID)
	if err != nil {
		return nil, err
	}

	return &TemplateData{
		ID:            tmpl.ID,
		Name:          tmpl.Name,
		OperationType: tmpl.OperationType,
		TargetEntity:  tmpl.TargetEntity,
		TemplateData:  tmpl.TemplateData,
		Version:       tmpl.Version,
		IsActive:      tmpl.IsActive,
	}, nil
}

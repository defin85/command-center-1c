package templatesvc

import "context"

// TemplateClient fetches operation templates from Orchestrator.
type TemplateClient interface {
	GetTemplate(
		ctx context.Context,
		templateID string,
		templateExposureID string,
		templateExposureRevision int,
	) (*TemplateData, error)
}

// TemplateData represents template data from Orchestrator.
type TemplateData struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	OperationType string                 `json:"operation_type"`
	TargetEntity  string                 `json:"target_entity"`
	TemplateData  map[string]interface{} `json:"template_data"`
	Version       int                    `json:"version"`
	IsActive      bool                   `json:"is_active"`
}

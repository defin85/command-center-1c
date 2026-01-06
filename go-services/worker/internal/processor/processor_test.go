package processor

import (
	"context"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers"
)

type fakeMetaDriver struct {
	name      string
	opTypes   []string
	result    *models.OperationResultV2
	execError error
}

func (d *fakeMetaDriver) Name() string { return d.name }

func (d *fakeMetaDriver) OperationTypes() []string { return d.opTypes }

func (d *fakeMetaDriver) Execute(_ context.Context, _ *models.OperationMessage) (*models.OperationResultV2, error) {
	return d.result, d.execError
}

func TestTaskProcessor_Process_GlobalScope_UnknownType(t *testing.T) {
	p := &TaskProcessor{
		workerID:       "test-worker",
		driverRegistry: drivers.NewRegistry(),
		timeline:       tracing.NewNoopTimeline(),
	}

	msg := &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "op-1",
		OperationType: "unknown",
		Payload: models.OperationPayload{
			Options: map[string]interface{}{"target_scope": "global"},
		},
		ExecConfig: models.ExecutionConfig{TimeoutSeconds: 1},
	}

	res := p.Process(context.Background(), msg)
	if res == nil {
		t.Fatalf("expected result, got nil")
	}
	if res.Status != "failed" {
		t.Fatalf("expected status=failed, got %q", res.Status)
	}
	if res.Summary.Total != 1 || res.Summary.Failed != 1 {
		t.Fatalf("unexpected summary: %+v", res.Summary)
	}
	if len(res.Results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(res.Results))
	}
	if res.Results[0].DatabaseID != "" {
		t.Fatalf("expected empty database_id for global result, got %q", res.Results[0].DatabaseID)
	}
}

func TestTaskProcessor_Process_GlobalScope_MetaDriverResultIsNormalized(t *testing.T) {
	reg := drivers.NewRegistry()
	_ = reg.RegisterMeta(&fakeMetaDriver{
		name:    "fake",
		opTypes: []string{"ibcmd_cli"},
		result: &models.OperationResultV2{
			Status:  "completed",
			Results: []models.DatabaseResultV2{},
		},
	})

	p := &TaskProcessor{
		workerID:       "test-worker",
		driverRegistry: reg,
		timeline:       tracing.NewNoopTimeline(),
	}

	msg := &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "op-2",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Options: map[string]interface{}{"target_scope": "global"},
		},
		ExecConfig: models.ExecutionConfig{TimeoutSeconds: 1},
	}

	res := p.Process(context.Background(), msg)
	if res == nil {
		t.Fatalf("expected result, got nil")
	}
	if res.Status != "completed" {
		t.Fatalf("expected status=completed, got %q", res.Status)
	}
	if res.Summary.Total != 1 || res.Summary.Succeeded != 1 || res.Summary.Failed != 0 {
		t.Fatalf("unexpected summary: %+v", res.Summary)
	}
	if len(res.Results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(res.Results))
	}
	if res.Results[0].DatabaseID != "" {
		t.Fatalf("expected empty database_id for global result, got %q", res.Results[0].DatabaseID)
	}
	if !res.Results[0].Success {
		t.Fatalf("expected success=true for normalized global result")
	}
}

func TestTaskProcessor_Process_MetaOperation_WithGlobalScope_IsNotNormalized(t *testing.T) {
	reg := drivers.NewRegistry()
	_ = reg.RegisterMeta(&fakeMetaDriver{
		name:    "fake-meta",
		opTypes: []string{"sync_cluster"},
		result: &models.OperationResultV2{
			Status:  "completed",
			Results: []models.DatabaseResultV2{},
			Summary: models.ResultSummary{Total: 0, Succeeded: 0, Failed: 0, AvgDuration: 0},
		},
	})

	p := &TaskProcessor{
		workerID:       "test-worker",
		driverRegistry: reg,
		timeline:       tracing.NewNoopTimeline(),
	}

	msg := &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "op-3",
		OperationType: "sync_cluster",
		Payload: models.OperationPayload{
			Options: map[string]interface{}{"target_scope": "global"},
		},
		ExecConfig: models.ExecutionConfig{TimeoutSeconds: 1},
	}

	res := p.Process(context.Background(), msg)
	if res == nil {
		t.Fatalf("expected result, got nil")
	}
	if res.Status != "completed" {
		t.Fatalf("expected status=completed, got %q", res.Status)
	}
	if len(res.Results) != 0 {
		t.Fatalf("expected 0 results for meta op, got %d", len(res.Results))
	}
	if res.Summary.Total != 0 {
		t.Fatalf("expected summary.total=0 for meta op, got %+v", res.Summary)
	}
}

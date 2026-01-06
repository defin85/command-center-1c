package ibcmdops

import (
	"context"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

func TestCLIMetaDriverRequiresAuthDatabaseID(t *testing.T) {
	driver := NewCLIMetaDriver(nil, nil)
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{},
		},
	}

	res, err := driver.Execute(context.Background(), msg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res == nil {
		t.Fatalf("expected result")
	}
	if res.Status != "failed" {
		t.Fatalf("expected status=failed, got %q", res.Status)
	}
	if len(res.Results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(res.Results))
	}
	if res.Results[0].ErrorCode != "VALIDATION_ERROR" {
		t.Fatalf("expected error_code=VALIDATION_ERROR, got %q", res.Results[0].ErrorCode)
	}
}

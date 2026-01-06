package ibcmdops

import (
	"context"
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
)

// CLIMetaDriver executes ibcmd_cli in global scope (single execution unit).
// It uses auth_database_id from payload.data to fetch infobase user mapping.
type CLIMetaDriver struct {
	dbDriver *Driver
}

func NewCLIMetaDriver(credsClient credentials.Fetcher, timeline tracing.TimelineRecorder) *CLIMetaDriver {
	return &CLIMetaDriver{
		dbDriver: NewDriver(credsClient, timeline),
	}
}

func (d *CLIMetaDriver) Name() string { return "ibcmd-cli" }

func (d *CLIMetaDriver) OperationTypes() []string { return []string{"ibcmd_cli"} }

func (d *CLIMetaDriver) Execute(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error) {
	authDatabaseID := strings.TrimSpace(extractString(msg.Payload.Data, "auth_database_id"))
	if authDatabaseID == "" {
		return &models.OperationResultV2{
			OperationID: msg.OperationID,
			Status:      "failed",
			Results: []models.DatabaseResultV2{{
				DatabaseID: "",
				Success:    false,
				Error:      "auth_database_id is required for global scope",
				ErrorCode:  "VALIDATION_ERROR",
				Duration:   0,
			}},
			Summary: models.ResultSummary{Total: 1, Succeeded: 0, Failed: 1, AvgDuration: 0},
		}, nil
	}

	dbRes, _ := d.dbDriver.Execute(ctx, msg, authDatabaseID)
	dbRes.DatabaseID = ""

	status := "failed"
	succeeded := 0
	failed := 1
	if dbRes.Success {
		status = "completed"
		succeeded = 1
		failed = 0
	}

	return &models.OperationResultV2{
		OperationID: msg.OperationID,
		Status:      status,
		Results:     []models.DatabaseResultV2{dbRes},
		Summary: models.ResultSummary{
			Total:       1,
			Succeeded:   succeeded,
			Failed:      failed,
			AvgDuration: dbRes.Duration,
		},
	}, nil
}


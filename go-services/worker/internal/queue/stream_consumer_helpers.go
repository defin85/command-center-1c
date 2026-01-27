package queue

import (
	"fmt"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

// getErrorSummary extracts error summary from OperationResultV2
func getErrorSummary(result *models.OperationResultV2) string {
	if result.Status == "completed" {
		return ""
	}

	// Collect errors from failed results
	var errorMsgs []string
	for _, dbResult := range result.Results {
		if !dbResult.Success && dbResult.Error != "" {
			errorMsgs = append(errorMsgs, fmt.Sprintf("%s: %s", dbResult.DatabaseID, dbResult.Error))
		}
	}

	if len(errorMsgs) == 0 {
		return fmt.Sprintf("operation %s failed", result.OperationID)
	}

	if len(errorMsgs) == 1 {
		return errorMsgs[0]
	}

	return fmt.Sprintf("%d errors: %s", len(errorMsgs), errorMsgs[0])
}

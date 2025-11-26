package v2

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// Validation helpers

// isValidUUID validates UUID format
func isValidUUID(u string) bool {
	_, err := uuid.Parse(u)
	return err == nil
}

// validateRequiredQueryParams validates that required query parameters are present.
// Returns true if all parameters are valid, false otherwise (response already sent).
func validateRequiredQueryParams(c *gin.Context, params ...string) bool {
	for _, param := range params {
		if c.Query(param) == "" {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: param + " is required",
				Code:  "MISSING_PARAMETER",
			})
			return false
		}
	}
	return true
}

// validateUUIDParams validates UUID format for specified query parameters.
// Returns true if all parameters are valid UUIDs, false otherwise (response already sent).
func validateUUIDParams(c *gin.Context, params ...string) bool {
	for _, param := range params {
		value := c.Query(param)
		if value != "" && !isValidUUID(value) {
			c.JSON(http.StatusBadRequest, ErrorResponse{
				Error: param + " must be a valid UUID",
				Code:  "INVALID_UUID",
			})
			return false
		}
	}
	return true
}

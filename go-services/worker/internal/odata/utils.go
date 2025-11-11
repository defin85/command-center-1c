// go-services/worker/internal/odata/utils.go
package odata

import (
	"fmt"
	"time"
)

// FormatGUID formats UUID for 1C OData
// Example: "12345678-1234-1234-1234-123456789012" → "guid'12345678-1234-1234-1234-123456789012'"
func FormatGUID(guid string) string {
	return fmt.Sprintf("guid'%s'", guid)
}

// FormatDatetime formats datetime for 1C OData
// Example: 2025-11-09T12:00:00 → "datetime'2025-11-09T12:00:00'"
func FormatDatetime(t time.Time) string {
	return fmt.Sprintf("datetime'%s'", t.Format("2006-01-02T15:04:05"))
}

// FormatDate formats date for 1C OData
// Example: 2025-11-09 → "datetime'2025-11-09T00:00:00'"
func FormatDate(t time.Time) string {
	return fmt.Sprintf("datetime'%s'", t.Format("2006-01-02T00:00:00"))
}

// BuildEntityURL constructs entity URL
// Examples:
//   - BuildEntityURL("http://server/odata", "Catalog_Пользователи", "")
//     → "http://server/odata/Catalog_Пользователи"
//   - BuildEntityURL("http://server/odata", "Catalog_Пользователи", "guid'...'")
//     → "http://server/odata/Catalog_Пользователи(guid'...')"
func BuildEntityURL(baseURL, entity, id string) string {
	if id != "" {
		return fmt.Sprintf("%s/%s(%s)", baseURL, entity, id)
	}
	return fmt.Sprintf("%s/%s", baseURL, entity)
}

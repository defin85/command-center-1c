package odata

import (
	"fmt"
	"net/url"
	"strings"
	"time"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

// BuildEntityURL constructs entity URL.
// Examples:
//   - BuildEntityURL("http://server/db/odata/standard.odata", "Catalog_Users", "")
//     -> "http://server/db/odata/standard.odata/Catalog_Users"
//   - BuildEntityURL("http://server/db/odata/standard.odata", "Catalog_Users", "guid'123'")
//     -> "http://server/db/odata/standard.odata/Catalog_Users(guid'123')"
func BuildEntityURL(baseURL, entity, entityID string) string {
	if entityID != "" {
		return fmt.Sprintf("%s/%s(%s)", baseURL, entity, entityID)
	}
	return fmt.Sprintf("%s/%s", baseURL, entity)
}

// BuildQueryString builds query string from QueryParams.
// Returns empty string if no params are set.
func BuildQueryString(q *sharedodata.QueryParams) string {
	if q == nil {
		return ""
	}

	params := url.Values{}

	if q.Filter != "" {
		params.Set("$filter", q.Filter)
	}

	if len(q.Select) > 0 {
		params.Set("$select", strings.Join(q.Select, ","))
	}

	if q.OrderBy != "" {
		params.Set("$orderby", q.OrderBy)
	}

	if q.Top > 0 {
		params.Set("$top", fmt.Sprintf("%d", q.Top))
	}

	if q.Skip > 0 {
		params.Set("$skip", fmt.Sprintf("%d", q.Skip))
	}

	if q.Expand != "" {
		params.Set("$expand", q.Expand)
	}

	if len(params) == 0 {
		return ""
	}

	return params.Encode()
}

// FormatGUID formats UUID for 1C OData.
// Example: "12345678-1234-1234-1234-123456789012" -> "guid'12345678-1234-1234-1234-123456789012'"
func FormatGUID(guid string) string {
	return fmt.Sprintf("guid'%s'", guid)
}

// FormatDatetime formats datetime for 1C OData.
// Example: 2025-11-09T12:00:00 -> "datetime'2025-11-09T12:00:00'"
func FormatDatetime(t time.Time) string {
	return fmt.Sprintf("datetime'%s'", t.Format("2006-01-02T15:04:05"))
}

// FormatDate formats date for 1C OData.
// Example: 2025-11-09 -> "datetime'2025-11-09T00:00:00'"
func FormatDate(t time.Time) string {
	return fmt.Sprintf("datetime'%s'", t.Format("2006-01-02T00:00:00"))
}

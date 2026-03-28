// go-services/worker/internal/odata/types.go
package odata

import (
	"encoding/json"
	"time"
)

// Auth contains authentication credentials
type Auth struct {
	Username string
	Password string
}

// ClientConfig contains client configuration
type ClientConfig struct {
	BaseURL       string
	Auth          Auth
	Timeout       time.Duration
	MaxRetries    int
	RetryWaitTime time.Duration
}

// CreateRequest represents entity creation request
type CreateRequest struct {
	Entity string                 `json:"-"` // Entity name (e.g., "Catalog_Пользователи")
	Data   map[string]interface{} `json:"-"` // Entity data
}

// UpdateRequest represents entity update request
type UpdateRequest struct {
	Entity string                 `json:"-"`
	ID     string                 `json:"-"` // Entity ID (e.g., "guid'...'")
	Data   map[string]interface{} `json:"-"`
}

// DeleteRequest represents entity deletion request
type DeleteRequest struct {
	Entity string `json:"-"`
	ID     string `json:"-"`
}

// QueryRequest represents entity query request
type QueryRequest struct {
	Entity  string   `json:"-"`
	Filter  string   `json:"-"` // OData $filter query
	Select  []string `json:"-"` // Fields to select
	OrderBy string   `json:"-"` // OData $orderby
	Top     int      `json:"-"` // Limit
	Skip    int      `json:"-"` // Offset
	Expand  string   `json:"-"` // OData $expand
}

// QueryResponse represents query result from OData
type QueryResponse struct {
	Value []map[string]interface{} `json:"value"`
}

func (r *QueryResponse) UnmarshalJSON(data []byte) error {
	type queryResponseAlias QueryResponse
	var alias queryResponseAlias
	if err := json.Unmarshal(data, &alias); err == nil && alias.Value != nil {
		r.Value = alias.Value
		return nil
	}

	var single map[string]interface{}
	if err := json.Unmarshal(data, &single); err != nil {
		return err
	}
	if len(single) == 0 {
		r.Value = nil
		return nil
	}
	r.Value = []map[string]interface{}{single}
	return nil
}

// ODataErrorResponse represents 1C OData error format
type ODataErrorResponse struct {
	Error ODataErrorDetail `json:"odata.error"`
}

type ODataErrorDetail struct {
	Code    string            `json:"code"`
	Message ODataErrorMessage `json:"message"`
}

type ODataErrorMessage struct {
	Lang  string `json:"lang"`
	Value string `json:"value"`
}

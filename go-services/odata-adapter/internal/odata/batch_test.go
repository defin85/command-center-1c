package odata

import (
	"bytes"
	"fmt"
	"strings"
	"testing"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

func TestBuildBatchBody_CreateItems(t *testing.T) {
	baseURL := "http://server/db/odata/standard.odata"
	items := []sharedodata.BatchItem{
		{
			Operation: sharedodata.BatchOperationCreate,
			Entity:    "Catalog_Users",
			Data:      map[string]interface{}{"Description": "Test User", "Code": "001"},
		},
	}

	body, contentType, err := buildBatchBody(baseURL, items)
	if err != nil {
		t.Fatalf("buildBatchBody() error = %v", err)
	}

	// Check content type contains multipart/mixed with batch boundary
	if !strings.HasPrefix(contentType, "multipart/mixed; boundary=batch_") {
		t.Errorf("contentType = %v, want to start with 'multipart/mixed; boundary=batch_'", contentType)
	}

	// Check body contains required parts
	bodyStr := string(body)
	if !strings.Contains(bodyStr, "batch_") {
		t.Error("body should contain batch boundary")
	}
	if !strings.Contains(bodyStr, "changeset_") {
		t.Error("body should contain changeset boundary")
	}
	if !strings.Contains(bodyStr, "POST") {
		t.Error("body should contain POST method for create")
	}
	if !strings.Contains(bodyStr, "/Catalog_Users") {
		t.Error("body should contain entity path")
	}
	if !strings.Contains(bodyStr, "Test User") {
		t.Error("body should contain entity data")
	}
}

func TestBuildBatchBody_UpdateItems(t *testing.T) {
	baseURL := "http://server/db/odata/standard.odata"
	items := []sharedodata.BatchItem{
		{
			Operation: sharedodata.BatchOperationUpdate,
			Entity:    "Catalog_Users",
			EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
			Data:      map[string]interface{}{"Description": "Updated User"},
		},
	}

	body, contentType, err := buildBatchBody(baseURL, items)
	if err != nil {
		t.Fatalf("buildBatchBody() error = %v", err)
	}

	if contentType == "" {
		t.Error("contentType should not be empty")
	}

	bodyStr := string(body)
	if !strings.Contains(bodyStr, "PATCH") {
		t.Error("body should contain PATCH method for update")
	}
	if !strings.Contains(bodyStr, "/Catalog_Users(guid'12345678-1234-1234-1234-123456789012')") {
		t.Error("body should contain entity path with ID")
	}
	if !strings.Contains(bodyStr, "Updated User") {
		t.Error("body should contain update data")
	}
}

func TestBuildBatchBody_DeleteItems(t *testing.T) {
	baseURL := "http://server/db/odata/standard.odata"
	items := []sharedodata.BatchItem{
		{
			Operation: sharedodata.BatchOperationDelete,
			Entity:    "Catalog_Users",
			EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
		},
	}

	body, contentType, err := buildBatchBody(baseURL, items)
	if err != nil {
		t.Fatalf("buildBatchBody() error = %v", err)
	}

	if contentType == "" {
		t.Error("contentType should not be empty")
	}

	bodyStr := string(body)
	if !strings.Contains(bodyStr, "DELETE") {
		t.Error("body should contain DELETE method")
	}
	if !strings.Contains(bodyStr, "/Catalog_Users(guid'12345678-1234-1234-1234-123456789012')") {
		t.Error("body should contain entity path with ID")
	}
	// DELETE should not have body
	if strings.Contains(bodyStr, `"Description"`) {
		t.Error("DELETE should not contain JSON data")
	}
}

func TestBuildBatchBody_MixedItems(t *testing.T) {
	baseURL := "http://server/db/odata/standard.odata"
	items := []sharedodata.BatchItem{
		{
			Operation: sharedodata.BatchOperationCreate,
			Entity:    "Catalog_Users",
			Data:      map[string]interface{}{"Description": "New User"},
		},
		{
			Operation: sharedodata.BatchOperationUpdate,
			Entity:    "Catalog_Users",
			EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
			Data:      map[string]interface{}{"Description": "Updated User"},
		},
		{
			Operation: sharedodata.BatchOperationDelete,
			Entity:    "Catalog_Users",
			EntityID:  "guid'87654321-4321-4321-4321-210987654321'",
		},
	}

	body, contentType, err := buildBatchBody(baseURL, items)
	if err != nil {
		t.Fatalf("buildBatchBody() error = %v", err)
	}

	if contentType == "" {
		t.Error("contentType should not be empty")
	}

	bodyStr := string(body)
	// Should contain all methods
	if !strings.Contains(bodyStr, "POST") {
		t.Error("body should contain POST for create")
	}
	if !strings.Contains(bodyStr, "PATCH") {
		t.Error("body should contain PATCH for update")
	}
	if !strings.Contains(bodyStr, "DELETE") {
		t.Error("body should contain DELETE")
	}

	// Check Content-ID headers (1-based)
	// Note: multipart.Writer uses "Content-Id" (lowercase 'd'), not "Content-ID"
	if !strings.Contains(bodyStr, "Content-Id: 1") && !strings.Contains(bodyStr, "Content-ID: 1") {
		t.Errorf("body should contain Content-Id: 1, body:\n%s", bodyStr)
	}
	if !strings.Contains(bodyStr, "Content-Id: 2") && !strings.Contains(bodyStr, "Content-ID: 2") {
		t.Errorf("body should contain Content-Id: 2, body:\n%s", bodyStr)
	}
	if !strings.Contains(bodyStr, "Content-Id: 3") && !strings.Contains(bodyStr, "Content-ID: 3") {
		t.Errorf("body should contain Content-Id: 3, body:\n%s", bodyStr)
	}
}

func TestParseBatchResponse_Success(t *testing.T) {
	items := []sharedodata.BatchItem{
		{
			Operation: sharedodata.BatchOperationCreate,
			Entity:    "Catalog_Users",
			Data:      map[string]interface{}{"Description": "Test"},
		},
	}

	// Mock successful batch response
	responseBody := buildMockBatchResponse([]mockResponseItem{
		{
			statusCode: 201,
			body:       `{"Ref_Key": "12345678-1234-1234-1234-123456789012", "Description": "Test"}`,
		},
	})

	contentType := "multipart/mixed; boundary=batchresponse_boundary"

	result, err := parseBatchResponse([]byte(responseBody), contentType, items)
	if err != nil {
		t.Fatalf("parseBatchResponse() error = %v", err)
	}

	if result.TotalCount != 1 {
		t.Errorf("TotalCount = %d, want 1", result.TotalCount)
	}
	if result.SuccessCount != 1 {
		t.Errorf("SuccessCount = %d, want 1", result.SuccessCount)
	}
	if result.FailureCount != 0 {
		t.Errorf("FailureCount = %d, want 0", result.FailureCount)
	}
	if !result.AllSucceeded() {
		t.Error("AllSucceeded() should be true")
	}
	if result.ChangesetFailed {
		t.Error("ChangesetFailed should be false")
	}

	if len(result.Items) != 1 {
		t.Fatalf("Items length = %d, want 1", len(result.Items))
	}

	item := result.Items[0]
	if !item.Success {
		t.Error("Item success should be true")
	}
	if item.HTTPStatus != 201 {
		t.Errorf("HTTPStatus = %d, want 201", item.HTTPStatus)
	}
	if item.EntityID != "guid'12345678-1234-1234-1234-123456789012'" {
		t.Errorf("EntityID = %s, want formatted GUID", item.EntityID)
	}
}

func TestParseBatchResponse_WithErrors(t *testing.T) {
	items := []sharedodata.BatchItem{
		{
			Operation: sharedodata.BatchOperationCreate,
			Entity:    "Catalog_Users",
			Data:      map[string]interface{}{"Description": "Test"},
		},
		{
			Operation: sharedodata.BatchOperationUpdate,
			Entity:    "Catalog_Users",
			EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
			Data:      map[string]interface{}{"Description": "Updated"},
		},
	}

	// Mock response with one success and one error
	responseBody := buildMockBatchResponse([]mockResponseItem{
		{
			statusCode: 201,
			body:       `{"Ref_Key": "12345678-1234-1234-1234-123456789012", "Description": "Test"}`,
		},
		{
			statusCode: 404,
			body:       `{"odata.error": {"message": {"value": "Entity not found"}}}`,
		},
	})

	contentType := "multipart/mixed; boundary=batchresponse_boundary"

	result, err := parseBatchResponse([]byte(responseBody), contentType, items)
	if err != nil {
		t.Fatalf("parseBatchResponse() error = %v", err)
	}

	if result.TotalCount != 2 {
		t.Errorf("TotalCount = %d, want 2", result.TotalCount)
	}
	if result.SuccessCount != 1 {
		t.Errorf("SuccessCount = %d, want 1", result.SuccessCount)
	}
	if result.FailureCount != 1 {
		t.Errorf("FailureCount = %d, want 1", result.FailureCount)
	}
	if result.AllSucceeded() {
		t.Error("AllSucceeded() should be false")
	}
	if !result.ChangesetFailed {
		t.Error("ChangesetFailed should be true when any item fails")
	}

	if len(result.Items) != 2 {
		t.Fatalf("Items length = %d, want 2", len(result.Items))
	}

	// Check first item (success)
	item0 := result.Items[0]
	if !item0.Success {
		t.Error("First item should be success")
	}

	// Check second item (failure)
	item1 := result.Items[1]
	if item1.Success {
		t.Error("Second item should be failure")
	}
	if item1.HTTPStatus != 404 {
		t.Errorf("HTTPStatus = %d, want 404", item1.HTTPStatus)
	}
	if !strings.Contains(item1.Error, "Entity not found") {
		t.Errorf("Error = %s, should contain 'Entity not found'", item1.Error)
	}
}

func TestParseStatusLine(t *testing.T) {
	tests := []struct {
		name       string
		statusLine string
		want       int
		wantErr    bool
	}{
		{
			name:       "HTTP 200 OK",
			statusLine: "HTTP/1.1 200 OK\r\n",
			want:       200,
			wantErr:    false,
		},
		{
			name:       "HTTP 201 Created",
			statusLine: "HTTP/1.1 201 Created\r\n",
			want:       201,
			wantErr:    false,
		},
		{
			name:       "HTTP 404 Not Found",
			statusLine: "HTTP/1.1 404 Not Found\r\n",
			want:       404,
			wantErr:    false,
		},
		{
			name:       "HTTP 500 Internal Server Error",
			statusLine: "HTTP/1.1 500 Internal Server Error\r\n",
			want:       500,
			wantErr:    false,
		},
		{
			name:       "invalid status line",
			statusLine: "Invalid\r\n",
			want:       0,
			wantErr:    true,
		},
		{
			name:       "non-numeric status",
			statusLine: "HTTP/1.1 ABC OK\r\n",
			want:       0,
			wantErr:    true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseStatusLine(tt.statusLine)
			if (err != nil) != tt.wantErr {
				t.Errorf("parseStatusLine() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if got != tt.want {
				t.Errorf("parseStatusLine() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestExtractErrorMessage(t *testing.T) {
	tests := []struct {
		name string
		body []byte
		want string
	}{
		{
			name: "OData error format",
			body: []byte(`{"odata.error": {"message": {"value": "Entity not found"}}}`),
			want: "Entity not found",
		},
		{
			name: "empty body",
			body: []byte{},
			want: "unknown error",
		},
		{
			name: "non-JSON body",
			body: []byte("Some error text"),
			want: "Some error text",
		},
		{
			name: "long body truncated",
			body: []byte(strings.Repeat("a", 250)),
			want: strings.Repeat("a", 200) + "...",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := extractErrorMessage(tt.body)
			if got != tt.want {
				t.Errorf("extractErrorMessage() = %v, want %v", got, tt.want)
			}
		})
	}
}

// Helper type for building mock batch responses
type mockResponseItem struct {
	statusCode int
	body       string
}

// buildMockBatchResponse creates a mock OData batch response body
func buildMockBatchResponse(items []mockResponseItem) string {
	var buf bytes.Buffer

	// Batch boundary
	buf.WriteString("--batchresponse_boundary\r\n")
	buf.WriteString("Content-Type: multipart/mixed; boundary=changesetresponse_boundary\r\n")
	buf.WriteString("\r\n")

	// Changeset items
	for i, item := range items {
		buf.WriteString("--changesetresponse_boundary\r\n")
		buf.WriteString("Content-Type: application/http\r\n")
		buf.WriteString("Content-Transfer-Encoding: binary\r\n")
		buf.WriteString("Content-ID: ")
		buf.WriteString(fmt.Sprintf("%d", i+1))
		buf.WriteString("\r\n\r\n")

		// HTTP response
		buf.WriteString(fmt.Sprintf("HTTP/1.1 %d ", item.statusCode))
		switch item.statusCode {
		case 200:
			buf.WriteString("OK")
		case 201:
			buf.WriteString("Created")
		case 204:
			buf.WriteString("No Content")
		case 404:
			buf.WriteString("Not Found")
		case 500:
			buf.WriteString("Internal Server Error")
		default:
			buf.WriteString("Status")
		}
		buf.WriteString("\r\n")
		buf.WriteString("Content-Type: application/json\r\n")
		buf.WriteString("\r\n")
		buf.WriteString(item.body)
		buf.WriteString("\r\n")
	}

	buf.WriteString("--changesetresponse_boundary--\r\n")
	buf.WriteString("--batchresponse_boundary--\r\n")

	return buf.String()
}

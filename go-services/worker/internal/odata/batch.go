// Package odata provides OData client implementation for 1C integration.
package odata

import (
	"bufio"
	"bytes"
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"strconv"
	"strings"
	"time"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

// maxBatchResponseSize limits the size of batch response to prevent memory exhaustion.
const maxBatchResponseSize = 50 * 1024 * 1024 // 50 MB

// generateBoundary creates a unique boundary string for multipart requests.
func generateBoundary(prefix string) string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		binary.LittleEndian.PutUint64(b, uint64(time.Now().UnixNano()))
	}
	return fmt.Sprintf("%s_%x", prefix, b)
}

// buildBatchBody constructs multipart/mixed body for OData batch request.
// Format:
//
//	--batch_boundary
//	Content-Type: multipart/mixed; boundary=changeset_boundary
//
//	--changeset_boundary
//	Content-Type: application/http
//	Content-Transfer-Encoding: binary
//
//	POST /Entity HTTP/1.1
//	Content-Type: application/json
//
//	{"field": "value"}
//	--changeset_boundary--
//	--batch_boundary--
func buildBatchBody(baseURL string, items []sharedodata.BatchItem) ([]byte, string, error) {
	batchBoundary := generateBoundary("batch")
	changesetBoundary := generateBoundary("changeset")

	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	if err := writer.SetBoundary(batchBoundary); err != nil {
		return nil, "", fmt.Errorf("set batch boundary: %w", err)
	}

	changesetHeader := textproto.MIMEHeader{}
	changesetHeader.Set("Content-Type", fmt.Sprintf("multipart/mixed; boundary=%s", changesetBoundary))

	changesetPart, err := writer.CreatePart(changesetHeader)
	if err != nil {
		return nil, "", fmt.Errorf("create changeset part: %w", err)
	}

	changesetWriter := multipart.NewWriter(changesetPart)
	if err := changesetWriter.SetBoundary(changesetBoundary); err != nil {
		return nil, "", fmt.Errorf("set changeset boundary: %w", err)
	}

	for i, item := range items {
		if err := writeChangesetItem(changesetWriter, baseURL, item, i); err != nil {
			return nil, "", fmt.Errorf("write item %d: %w", i, err)
		}
	}

	if err := changesetWriter.Close(); err != nil {
		return nil, "", fmt.Errorf("close changeset: %w", err)
	}

	if err := writer.Close(); err != nil {
		return nil, "", fmt.Errorf("close batch: %w", err)
	}

	contentType := fmt.Sprintf("multipart/mixed; boundary=%s", batchBoundary)
	return buf.Bytes(), contentType, nil
}

// writeChangesetItem writes a single operation to the changeset.
func writeChangesetItem(writer *multipart.Writer, baseURL string, item sharedodata.BatchItem, index int) error {
	header := textproto.MIMEHeader{}
	header.Set("Content-Type", "application/http")
	header.Set("Content-Transfer-Encoding", "binary")
	header.Set("Content-ID", strconv.Itoa(index+1)) // 1-based for OData

	part, err := writer.CreatePart(header)
	if err != nil {
		return err
	}

	method, path := buildItemRequest(baseURL, item)
	fmt.Fprintf(part, "%s %s HTTP/1.1\r\n", method, path)
	fmt.Fprintf(part, "Content-Type: application/json\r\n")

	if item.Operation == sharedodata.BatchOperationCreate || item.Operation == sharedodata.BatchOperationUpdate {
		body, err := json.Marshal(item.Data)
		if err != nil {
			return fmt.Errorf("marshal data: %w", err)
		}
		fmt.Fprintf(part, "Content-Length: %d\r\n", len(body))
		fmt.Fprintf(part, "\r\n")
		if _, err := part.Write(body); err != nil {
			return err
		}
	} else {
		fmt.Fprintf(part, "\r\n")
	}

	return nil
}

// buildItemRequest returns HTTP method and relative path for batch item.
func buildItemRequest(baseURL string, item sharedodata.BatchItem) (method, path string) {
	relativePath := fmt.Sprintf("/%s", item.Entity)

	switch item.Operation {
	case sharedodata.BatchOperationCreate:
		method = http.MethodPost
		path = relativePath
	case sharedodata.BatchOperationUpdate:
		method = http.MethodPatch
		path = fmt.Sprintf("%s(%s)", relativePath, item.EntityID)
	case sharedodata.BatchOperationDelete:
		method = http.MethodDelete
		path = fmt.Sprintf("%s(%s)", relativePath, item.EntityID)
	}
	return
}

// parseBatchResponse parses multipart/mixed response from OData batch.
func parseBatchResponse(body []byte, contentType string, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
	result := sharedodata.NewBatchResult(len(items))

	_, params, err := mime.ParseMediaType(contentType)
	if err != nil {
		return nil, fmt.Errorf("parse content type: %w", err)
	}

	boundary, ok := params["boundary"]
	if !ok {
		return nil, fmt.Errorf("no boundary in content type")
	}

	reader := multipart.NewReader(bytes.NewReader(body), boundary)

	for {
		part, err := reader.NextPart()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("read part: %w", err)
		}

		partContentType := part.Header.Get("Content-Type")
		if strings.HasPrefix(partContentType, "multipart/mixed") {
			if err := parseChangesetResponse(part, partContentType, items, result); err != nil {
				return nil, fmt.Errorf("parse changeset: %w", err)
			}
		}
	}

	return result, nil
}

// parseChangesetResponse parses changeset part of batch response.
func parseChangesetResponse(part *multipart.Part, contentType string, items []sharedodata.BatchItem, result *sharedodata.BatchResult) error {
	_, params, err := mime.ParseMediaType(contentType)
	if err != nil {
		return fmt.Errorf("parse changeset content type: %w", err)
	}

	boundary, ok := params["boundary"]
	if !ok {
		return fmt.Errorf("no boundary in changeset content type")
	}

	partBody, err := io.ReadAll(io.LimitReader(part, maxBatchResponseSize))
	if err != nil {
		return fmt.Errorf("read changeset body: %w", err)
	}

	reader := multipart.NewReader(bytes.NewReader(partBody), boundary)
	itemIndex := 0

	for {
		itemPart, err := reader.NextPart()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("read item part: %w", err)
		}

		status, respBody, parseErr := parseHTTPResponse(itemPart)

		if itemIndex >= len(items) {
			continue
		}

		item := items[itemIndex]

		if parseErr != nil {
			result.AddFailure(itemIndex, item.Operation, item.Entity, parseErr.Error(), 0)
		} else if status >= 200 && status < 300 {
			var data map[string]interface{}
			if len(respBody) > 0 {
				if jsonErr := json.Unmarshal(respBody, &data); jsonErr != nil {
					data = nil
				}
			}
			entityID := item.EntityID
			if item.Operation == sharedodata.BatchOperationCreate && data != nil {
				if refKey, ok := data["Ref_Key"].(string); ok {
					entityID = FormatGUID(refKey)
				}
			}
			result.AddSuccess(itemIndex, item.Operation, item.Entity, entityID, data, status)
		} else {
			errMsg := extractErrorMessage(respBody)
			result.AddFailure(itemIndex, item.Operation, item.Entity, errMsg, status)
		}

		itemIndex++
	}

	if result.FailureCount > 0 {
		result.ChangesetFailed = true
	}

	return nil
}

// parseHTTPResponse parses HTTP response from batch item part.
func parseHTTPResponse(part *multipart.Part) (int, []byte, error) {
	partBody, err := io.ReadAll(io.LimitReader(part, maxBatchResponseSize))
	if err != nil {
		return 0, nil, fmt.Errorf("read response body: %w", err)
	}

	reader := bufio.NewReader(bytes.NewReader(partBody))

	statusLine, err := reader.ReadString('\n')
	if err != nil {
		return 0, nil, fmt.Errorf("read status line: %w", err)
	}

	status, err := parseStatusLine(statusLine)
	if err != nil {
		return 0, nil, err
	}

	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			break
		}
		if strings.TrimSpace(line) == "" {
			break
		}
	}

	body, _ := io.ReadAll(reader)
	return status, body, nil
}

// parseStatusLine parses HTTP status line and returns status code.
func parseStatusLine(line string) (int, error) {
	parts := strings.SplitN(strings.TrimSpace(line), " ", 3)
	if len(parts) < 2 {
		return 0, fmt.Errorf("invalid status line: %s", line)
	}

	status, err := strconv.Atoi(parts[1])
	if err != nil {
		return 0, fmt.Errorf("parse status code: %w", err)
	}

	return status, nil
}

// extractErrorMessage extracts error message from OData error response.
func extractErrorMessage(body []byte) string {
	if len(body) == 0 {
		return "unknown error"
	}

	var errResp struct {
		Error struct {
			Message struct {
				Value string `json:"value"`
			} `json:"message"`
		} `json:"odata.error"`
	}

	if err := json.Unmarshal(body, &errResp); err == nil && errResp.Error.Message.Value != "" {
		return errResp.Error.Message.Value
	}

	msg := string(body)
	if len(msg) > 200 {
		msg = msg[:200] + "..."
	}
	return msg
}

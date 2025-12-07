// Package workflow provides DAG-based workflow engine for operation orchestration.
package workflow

import (
	"errors"
	"fmt"
	"strings"
)

// WorkflowError represents a workflow execution error with context.
type WorkflowError struct {
	Type    ErrorType
	Message string
	NodeID  string
	Cause   error
	Details map[string]interface{}
}

// ErrorType classifies workflow errors.
type ErrorType string

const (
	// ErrTypeValidation indicates DAG structure validation failed.
	ErrTypeValidation ErrorType = "validation_error"
	// ErrTypeExecution indicates runtime execution failed.
	ErrTypeExecution ErrorType = "execution_error"
	// ErrTypeTimeout indicates operation timed out.
	ErrTypeTimeout ErrorType = "timeout_error"
	// ErrTypeCancelled indicates workflow was cancelled.
	ErrTypeCancelled ErrorType = "cancelled_error"
	// ErrTypeCycle indicates cycle detected in DAG.
	ErrTypeCycle ErrorType = "cycle_error"
	// ErrTypeUnreachable indicates unreachable nodes in DAG.
	ErrTypeUnreachable ErrorType = "unreachable_error"
	// ErrTypeInvalidNode indicates invalid node configuration.
	ErrTypeInvalidNode ErrorType = "invalid_node_error"
	// ErrTypeInvalidEdge indicates invalid edge reference.
	ErrTypeInvalidEdge ErrorType = "invalid_edge_error"
)

// Error implements the error interface.
func (e *WorkflowError) Error() string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("[%s] %s", e.Type, e.Message))
	if e.NodeID != "" {
		sb.WriteString(fmt.Sprintf(" (node: %s)", e.NodeID))
	}
	if e.Cause != nil {
		sb.WriteString(fmt.Sprintf(": %v", e.Cause))
	}
	return sb.String()
}

// Unwrap returns the underlying cause for errors.Is/As support.
func (e *WorkflowError) Unwrap() error {
	return e.Cause
}

// Is checks if the error is of a specific type.
func (e *WorkflowError) Is(target error) bool {
	var we *WorkflowError
	if errors.As(target, &we) {
		return e.Type == we.Type
	}
	return false
}

// NewValidationError creates a validation error.
func NewValidationError(message string, nodeIDs ...string) *WorkflowError {
	nodeID := ""
	if len(nodeIDs) > 0 {
		nodeID = strings.Join(nodeIDs, ", ")
	}
	return &WorkflowError{
		Type:    ErrTypeValidation,
		Message: message,
		NodeID:  nodeID,
	}
}

// NewCycleError creates a cycle detection error.
func NewCycleError(nodeIDs []string) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeCycle,
		Message: fmt.Sprintf("cycle detected involving %d node(s)", len(nodeIDs)),
		NodeID:  strings.Join(nodeIDs, ", "),
		Details: map[string]interface{}{
			"cycle_nodes": nodeIDs,
		},
	}
}

// NewUnreachableError creates an unreachable nodes error.
func NewUnreachableError(nodeIDs []string) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeUnreachable,
		Message: fmt.Sprintf("%d node(s) are unreachable from start nodes", len(nodeIDs)),
		NodeID:  strings.Join(nodeIDs, ", "),
		Details: map[string]interface{}{
			"unreachable_nodes": nodeIDs,
		},
	}
}

// NewInvalidNodeError creates an invalid node error.
func NewInvalidNodeError(nodeID, reason string) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeInvalidNode,
		Message: reason,
		NodeID:  nodeID,
	}
}

// NewInvalidEdgeError creates an invalid edge error.
func NewInvalidEdgeError(from, to, reason string) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeInvalidEdge,
		Message: reason,
		Details: map[string]interface{}{
			"from": from,
			"to":   to,
		},
	}
}

// NewExecutionError creates an execution error.
func NewExecutionError(nodeID, message string, cause error) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeExecution,
		Message: message,
		NodeID:  nodeID,
		Cause:   cause,
	}
}

// NewTimeoutError creates a timeout error.
func NewTimeoutError(nodeID string, timeoutSeconds int) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeTimeout,
		Message: fmt.Sprintf("operation timed out after %d seconds", timeoutSeconds),
		NodeID:  nodeID,
		Details: map[string]interface{}{
			"timeout_seconds": timeoutSeconds,
		},
	}
}

// NewCancelledError creates a cancellation error.
func NewCancelledError(reason string) *WorkflowError {
	return &WorkflowError{
		Type:    ErrTypeCancelled,
		Message: reason,
	}
}

// Sentinel errors for quick type checking.
var (
	ErrEmptyDAG         = NewValidationError("DAG contains no nodes")
	ErrNoEntryNode      = NewValidationError("entry_node is required")
	ErrNoStartNodes     = NewValidationError("no start nodes found (all nodes have incoming edges)")
	ErrNoEndNodes       = NewValidationError("no end nodes found (all nodes have outgoing edges)")
	ErrDuplicateNodeIDs = NewValidationError("duplicate node IDs found")
	ErrSelfLoop         = NewValidationError("self-loop detected")
)

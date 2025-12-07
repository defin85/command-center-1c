// Package context provides immutable execution context for workflow engine.
package context

import (
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"
)

// ExecutionContext holds the immutable execution state for a workflow.
// It provides thread-safe access to variables, node results, and scoped data.
//
// Features:
// - Immutable operations (Set returns new context)
// - Dot notation access for nested values (e.g., "user.profile.name")
// - Node results storage with structured access
// - Scoped variables for loops (push/pop scope stack)
// - System variables (execution_id, timestamps, etc.)
//
// Usage:
//
//	ctx := NewExecutionContext("exec-123", "workflow-456")
//	ctx = ctx.Set("database_id", "db-789")
//	ctx = ctx.SetNodeResult("node_1", map[string]interface{}{"status": "ok"})
//	value, ok := ctx.Get("database_id")
type ExecutionContext struct {
	mu sync.RWMutex

	// Identifiers
	executionID string
	workflowID  string

	// Variables storage
	globalVars  map[string]interface{}
	nodeResults map[string]interface{} // nodeID -> result
	scopeStack  []map[string]interface{}

	// System data
	startTime   time.Time
	currentNode string

	// Metadata
	metadata map[string]interface{}
}

// NewExecutionContext creates a new execution context.
func NewExecutionContext(executionID, workflowID string) *ExecutionContext {
	return &ExecutionContext{
		executionID: executionID,
		workflowID:  workflowID,
		globalVars:  make(map[string]interface{}),
		nodeResults: make(map[string]interface{}),
		scopeStack:  make([]map[string]interface{}, 0),
		startTime:   time.Now(),
		metadata:    make(map[string]interface{}),
	}
}

// NewExecutionContextWithVars creates a new execution context with initial variables.
func NewExecutionContextWithVars(executionID, workflowID string, initialVars map[string]interface{}) *ExecutionContext {
	ctx := NewExecutionContext(executionID, workflowID)
	if initialVars != nil {
		ctx.globalVars = deepCopyMap(initialVars)
	}
	return ctx
}

// ExecutionID returns the execution identifier.
func (c *ExecutionContext) ExecutionID() string {
	return c.executionID
}

// WorkflowID returns the workflow identifier.
func (c *ExecutionContext) WorkflowID() string {
	return c.workflowID
}

// StartTime returns the execution start time.
func (c *ExecutionContext) StartTime() time.Time {
	return c.startTime
}

// CurrentNode returns the currently executing node ID.
func (c *ExecutionContext) CurrentNode() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.currentNode
}

// SetCurrentNode sets the currently executing node ID.
// This is a mutable operation for execution tracking.
func (c *ExecutionContext) SetCurrentNode(nodeID string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.currentNode = nodeID
}

// Get retrieves a value by key with dot notation support.
// First checks scope stack (last to first), then global vars.
//
// Supports nested access via dot notation:
//   - "database_id" -> direct key
//   - "user.profile.name" -> nested access
//   - "nodes.node_1.output" -> node result access
//
// Returns the value and true if found, nil and false otherwise.
func (c *ExecutionContext) Get(key string) (interface{}, bool) {
	if key == "" {
		return nil, false
	}

	c.mu.RLock()
	defer c.mu.RUnlock()

	// Check scope stack (last to first) for simple keys
	parts := strings.Split(key, ".")
	firstPart := parts[0]

	for i := len(c.scopeStack) - 1; i >= 0; i-- {
		if val, ok := c.scopeStack[i][firstPart]; ok {
			if len(parts) == 1 {
				return val, true
			}
			// Navigate nested path
			return getNestedValue(val, parts[1:])
		}
	}

	// Check global vars
	if val, ok := c.globalVars[firstPart]; ok {
		if len(parts) == 1 {
			return val, true
		}
		return getNestedValue(val, parts[1:])
	}

	// Check special keys
	if firstPart == "nodes" && len(parts) > 1 {
		nodeID := parts[1]
		if result, ok := c.nodeResults[nodeID]; ok {
			if len(parts) == 2 {
				return result, true
			}
			return getNestedValue(result, parts[2:])
		}
	}

	return nil, false
}

// GetString retrieves a string value by key.
// Returns the value and true if found and is a string, empty string and false otherwise.
func (c *ExecutionContext) GetString(key string) (string, bool) {
	val, ok := c.Get(key)
	if !ok {
		return "", false
	}
	if s, ok := val.(string); ok {
		return s, true
	}
	return "", false
}

// GetInt retrieves an integer value by key.
// Handles int, int64, float64 types.
func (c *ExecutionContext) GetInt(key string) (int, bool) {
	val, ok := c.Get(key)
	if !ok {
		return 0, false
	}
	switch v := val.(type) {
	case int:
		return v, true
	case int64:
		return int(v), true
	case float64:
		return int(v), true
	}
	return 0, false
}

// GetBool retrieves a boolean value by key.
func (c *ExecutionContext) GetBool(key string) (bool, bool) {
	val, ok := c.Get(key)
	if !ok {
		return false, false
	}
	if b, ok := val.(bool); ok {
		return b, true
	}
	return false, false
}

// Set creates a new ExecutionContext with the key set to value.
// Supports dot notation for nested setting.
//
// Returns a NEW ExecutionContext (immutable operation).
func (c *ExecutionContext) Set(key string, value interface{}) *ExecutionContext {
	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	parts := strings.Split(key, ".")

	if len(parts) == 1 {
		newCtx.globalVars[key] = deepCopy(value)
	} else {
		// Navigate and create intermediate maps
		current := newCtx.globalVars
		for i := 0; i < len(parts)-1; i++ {
			part := parts[i]
			if existing, ok := current[part]; ok {
				if m, ok := existing.(map[string]interface{}); ok {
					// Clone the map to maintain immutability
					newMap := make(map[string]interface{})
					for k, v := range m {
						newMap[k] = v
					}
					current[part] = newMap
					current = newMap
				} else {
					// Overwrite non-map value with new map
					newMap := make(map[string]interface{})
					current[part] = newMap
					current = newMap
				}
			} else {
				newMap := make(map[string]interface{})
				current[part] = newMap
				current = newMap
			}
		}
		current[parts[len(parts)-1]] = deepCopy(value)
	}

	return newCtx
}

// Merge creates a new ExecutionContext with values from other merged in.
// Returns a NEW ExecutionContext (immutable operation).
func (c *ExecutionContext) Merge(other map[string]interface{}) *ExecutionContext {
	if other == nil || len(other) == 0 {
		return c.Clone()
	}

	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	for k, v := range other {
		newCtx.globalVars[k] = deepCopy(v)
	}

	return newCtx
}

// SetNodeResult stores a node's execution result.
// The result is stored in the nodeResults map and also accessible via
// node_id.output pattern for template compatibility.
//
// Returns a NEW ExecutionContext (immutable operation).
func (c *ExecutionContext) SetNodeResult(nodeID string, result interface{}) *ExecutionContext {
	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	// Store in nodeResults
	newCtx.nodeResults[nodeID] = deepCopy(result)

	// Also store with output key for template compatibility: {{ node_id.output.field }}
	if newCtx.globalVars[nodeID] == nil {
		newCtx.globalVars[nodeID] = make(map[string]interface{})
	}
	if m, ok := newCtx.globalVars[nodeID].(map[string]interface{}); ok {
		m["output"] = deepCopy(result)
	} else {
		newCtx.globalVars[nodeID] = map[string]interface{}{
			"output": deepCopy(result),
		}
	}

	return newCtx
}

// GetNodeResult retrieves a node's execution result.
func (c *ExecutionContext) GetNodeResult(nodeID string) (interface{}, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	result, ok := c.nodeResults[nodeID]
	return result, ok
}

// HasNodeResult checks if a node result exists.
func (c *ExecutionContext) HasNodeResult(nodeID string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	_, ok := c.nodeResults[nodeID]
	return ok
}

// PushScope creates a new variable scope for loop iterations.
func (c *ExecutionContext) PushScope() *ExecutionContext {
	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	newCtx.scopeStack = append(newCtx.scopeStack, make(map[string]interface{}))
	return newCtx
}

// PopScope removes the current variable scope.
func (c *ExecutionContext) PopScope() *ExecutionContext {
	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	if len(newCtx.scopeStack) > 0 {
		newCtx.scopeStack = newCtx.scopeStack[:len(newCtx.scopeStack)-1]
	}
	return newCtx
}

// SetScoped sets a variable in the current scope.
// If no scope exists, sets in global scope.
//
// Returns a NEW ExecutionContext (immutable operation).
func (c *ExecutionContext) SetScoped(key string, value interface{}) *ExecutionContext {
	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	if len(newCtx.scopeStack) > 0 {
		// Set in current scope (last element)
		newCtx.scopeStack[len(newCtx.scopeStack)-1][key] = deepCopy(value)
	} else {
		newCtx.globalVars[key] = deepCopy(value)
	}

	return newCtx
}

// ScopeDepth returns the current scope stack depth.
func (c *ExecutionContext) ScopeDepth() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.scopeStack)
}

// SetMetadata sets a metadata value.
func (c *ExecutionContext) SetMetadata(key string, value interface{}) *ExecutionContext {
	c.mu.RLock()
	newCtx := c.cloneUnlocked()
	c.mu.RUnlock()

	newCtx.metadata[key] = deepCopy(value)
	return newCtx
}

// GetMetadata retrieves a metadata value.
func (c *ExecutionContext) GetMetadata(key string) (interface{}, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	val, ok := c.metadata[key]
	return val, ok
}

// ToMap converts the context to a map for template rendering.
// Includes all variables, node results, and system variables.
func (c *ExecutionContext) ToMap() map[string]interface{} {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make(map[string]interface{})

	// Copy global vars
	for k, v := range c.globalVars {
		result[k] = deepCopy(v)
	}

	// Apply scope vars (override global)
	for _, scope := range c.scopeStack {
		for k, v := range scope {
			result[k] = deepCopy(v)
		}
	}

	// Add node_results map
	nodeResults := make(map[string]interface{})
	for k, v := range c.nodeResults {
		nodeResults[k] = deepCopy(v)
	}
	result["node_results"] = nodeResults

	// Also add nodes.{node_id} for backward compatibility
	nodes := make(map[string]interface{})
	for k, v := range c.nodeResults {
		nodes[k] = deepCopy(v)
	}
	result["nodes"] = nodes

	// Add system vars
	result["execution_id"] = c.executionID
	result["workflow_id"] = c.workflowID
	result["start_time"] = c.startTime.Format(time.RFC3339)
	result["current_time"] = time.Now().Format(time.RFC3339)
	result["current_node"] = c.currentNode

	return result
}

// Clone creates an independent copy of the context.
func (c *ExecutionContext) Clone() *ExecutionContext {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.cloneUnlocked()
}

// cloneUnlocked creates a copy without locking (caller must hold lock).
func (c *ExecutionContext) cloneUnlocked() *ExecutionContext {
	newCtx := &ExecutionContext{
		executionID: c.executionID,
		workflowID:  c.workflowID,
		globalVars:  deepCopyMap(c.globalVars),
		nodeResults: deepCopyMap(c.nodeResults),
		scopeStack:  make([]map[string]interface{}, len(c.scopeStack)),
		startTime:   c.startTime,
		currentNode: c.currentNode,
		metadata:    deepCopyMap(c.metadata),
	}

	// Deep copy scope stack
	for i, scope := range c.scopeStack {
		newCtx.scopeStack[i] = deepCopyMap(scope)
	}

	return newCtx
}

// Keys returns the list of top-level variable keys.
func (c *ExecutionContext) Keys() []string {
	c.mu.RLock()
	defer c.mu.RUnlock()

	keys := make([]string, 0, len(c.globalVars))
	for k := range c.globalVars {
		keys = append(keys, k)
	}
	return keys
}

// Contains checks if a key exists in the context.
func (c *ExecutionContext) Contains(key string) bool {
	_, ok := c.Get(key)
	return ok
}

// String returns a debug string representation.
func (c *ExecutionContext) String() string {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return fmt.Sprintf("ExecutionContext{execution_id=%s, workflow_id=%s, vars=%d, node_results=%d, scope_depth=%d}",
		c.executionID, c.workflowID, len(c.globalVars), len(c.nodeResults), len(c.scopeStack))
}

// getNestedValue navigates through nested maps using the path parts.
func getNestedValue(val interface{}, parts []string) (interface{}, bool) {
	current := val

	for _, part := range parts {
		switch v := current.(type) {
		case map[string]interface{}:
			next, ok := v[part]
			if !ok {
				return nil, false
			}
			current = next
		case map[string]string:
			next, ok := v[part]
			if !ok {
				return nil, false
			}
			current = next
		default:
			return nil, false
		}
	}

	return current, true
}

// deepCopy creates a deep copy of a value.
func deepCopy(value interface{}) interface{} {
	if value == nil {
		return nil
	}

	switch v := value.(type) {
	case map[string]interface{}:
		return deepCopyMap(v)
	case []interface{}:
		return deepCopySlice(v)
	case string, int, int64, float64, bool:
		return v
	default:
		// For complex types, use JSON marshaling
		data, err := json.Marshal(v)
		if err != nil {
			return v
		}
		var result interface{}
		if err := json.Unmarshal(data, &result); err != nil {
			return v
		}
		return result
	}
}

// deepCopyMap creates a deep copy of a map.
func deepCopyMap(m map[string]interface{}) map[string]interface{} {
	if m == nil {
		return make(map[string]interface{})
	}

	result := make(map[string]interface{}, len(m))
	for k, v := range m {
		result[k] = deepCopy(v)
	}
	return result
}

// deepCopySlice creates a deep copy of a slice.
func deepCopySlice(s []interface{}) []interface{} {
	if s == nil {
		return nil
	}

	result := make([]interface{}, len(s))
	for i, v := range s {
		result[i] = deepCopy(v)
	}
	return result
}

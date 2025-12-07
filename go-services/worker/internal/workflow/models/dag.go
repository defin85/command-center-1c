// Package models provides DAG data structures for workflow engine.
package models

import (
	"encoding/json"
	"fmt"
	"time"
)

// NodeType represents the type of workflow node.
type NodeType string

const (
	// NodeTypeOperation executes a template-based operation.
	NodeTypeOperation NodeType = "operation"
	// NodeTypeCondition evaluates a boolean expression for branching.
	NodeTypeCondition NodeType = "condition"
	// NodeTypeParallel executes multiple nodes in parallel.
	NodeTypeParallel NodeType = "parallel"
	// NodeTypeLoop iterates over items or conditions.
	NodeTypeLoop NodeType = "loop"
	// NodeTypeSubworkflow executes a nested workflow.
	NodeTypeSubworkflow NodeType = "subworkflow"
)

// ValidNodeTypes contains all valid node types.
var ValidNodeTypes = map[NodeType]bool{
	NodeTypeOperation:   true,
	NodeTypeCondition:   true,
	NodeTypeParallel:    true,
	NodeTypeLoop:        true,
	NodeTypeSubworkflow: true,
}

// IsValid checks if the node type is valid.
func (nt NodeType) IsValid() bool {
	return ValidNodeTypes[nt]
}

// String returns the string representation of the node type.
func (nt NodeType) String() string {
	return string(nt)
}

// DAG represents a Directed Acyclic Graph for workflow.
type DAG struct {
	// ID is the unique identifier for the DAG.
	ID string `json:"id"`
	// Name is the human-readable name.
	Name string `json:"name"`
	// Description provides additional context.
	Description string `json:"description,omitempty"`
	// Version is the DAG version number.
	Version int `json:"version"`
	// Nodes is a map of node ID to Node.
	Nodes map[string]*Node `json:"nodes"`
	// Edges defines connections between nodes.
	Edges []*Edge `json:"edges"`
	// EntryNode is the ID of the starting node.
	EntryNode string `json:"entry_node"`
	// Config holds global workflow configuration.
	Config *WorkflowConfig `json:"config,omitempty"`
	// Metadata stores additional arbitrary data.
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// WorkflowConfig holds global workflow configuration.
type WorkflowConfig struct {
	// TimeoutSeconds is the total workflow timeout (default: 3600).
	TimeoutSeconds int `json:"timeout_seconds,omitempty"`
	// MaxRetries is the workflow-level retry attempts (default: 0).
	MaxRetries int `json:"max_retries,omitempty"`
}

// DefaultWorkflowConfig returns the default workflow configuration.
func DefaultWorkflowConfig() *WorkflowConfig {
	return &WorkflowConfig{
		TimeoutSeconds: 3600,
		MaxRetries:     0,
	}
}

// Node represents a single node in the workflow DAG.
type Node struct {
	// ID is the unique identifier within the DAG.
	ID string `json:"id"`
	// Type specifies the node behavior.
	Type NodeType `json:"type"`
	// Name is the human-readable name.
	Name string `json:"name"`
	// TemplateID references the operation template (for operation nodes).
	TemplateID string `json:"template_id,omitempty"`
	// Config holds node-specific configuration.
	Config *NodeConfig `json:"config,omitempty"`
	// NextNodes lists the IDs of successor nodes.
	NextNodes []string `json:"next_nodes,omitempty"`
	// OnError specifies the node to execute on error (optional).
	OnError string `json:"on_error,omitempty"`
	// RetryPolicy defines retry behavior.
	RetryPolicy *RetryPolicy `json:"retry_policy,omitempty"`

	// Type-specific configurations
	ParallelConfig    *ParallelNodeConfig    `json:"parallel_config,omitempty"`
	LoopConfig        *LoopNodeConfig        `json:"loop_config,omitempty"`
	SubworkflowConfig *SubworkflowNodeConfig `json:"subworkflow_config,omitempty"`
	ConditionConfig   *ConditionNodeConfig   `json:"condition_config,omitempty"`
}

// NodeConfig holds common node configuration.
type NodeConfig struct {
	// TimeoutSeconds is the node execution timeout (1-3600, default: 300).
	TimeoutSeconds int `json:"timeout_seconds,omitempty"`
	// MaxRetries is the maximum retry attempts (0-5, default: 0).
	MaxRetries int `json:"max_retries,omitempty"`
	// Expression is the Jinja2 boolean expression for condition nodes.
	Expression string `json:"expression,omitempty"`
}

// DefaultNodeConfig returns the default node configuration.
func DefaultNodeConfig() *NodeConfig {
	return &NodeConfig{
		TimeoutSeconds: 300,
		MaxRetries:     0,
	}
}

// GetTimeoutDuration returns the timeout as a time.Duration.
func (nc *NodeConfig) GetTimeoutDuration() time.Duration {
	if nc == nil || nc.TimeoutSeconds <= 0 {
		return 300 * time.Second
	}
	return time.Duration(nc.TimeoutSeconds) * time.Second
}

// Edge represents a directed edge between nodes in the DAG.
type Edge struct {
	// From is the source node ID.
	From string `json:"from"`
	// To is the destination node ID.
	To string `json:"to"`
	// Condition is an optional Jinja2 expression for conditional edges.
	Condition string `json:"condition,omitempty"`
	// Label provides a human-readable description (for visualization).
	Label string `json:"label,omitempty"`
}

// RetryPolicy defines the retry behavior for a node.
type RetryPolicy struct {
	// MaxRetries is the maximum number of retry attempts.
	MaxRetries int `json:"max_retries"`
	// DelayMs is the initial delay between retries in milliseconds.
	DelayMs int `json:"delay_ms"`
	// Backoff is the multiplier for exponential backoff (e.g., 2.0).
	Backoff float64 `json:"backoff"`
	// MaxDelayMs is the maximum delay between retries (optional).
	MaxDelayMs int `json:"max_delay_ms,omitempty"`
}

// DefaultRetryPolicy returns a default retry policy.
func DefaultRetryPolicy() *RetryPolicy {
	return &RetryPolicy{
		MaxRetries: 3,
		DelayMs:    1000,
		Backoff:    2.0,
		MaxDelayMs: 30000,
	}
}

// GetDelayForAttempt calculates the delay for a specific retry attempt.
func (rp *RetryPolicy) GetDelayForAttempt(attempt int) time.Duration {
	if rp == nil || attempt < 1 {
		return 0
	}

	// Calculate exponential backoff delay
	delayMs := float64(rp.DelayMs)
	for i := 1; i < attempt; i++ {
		delayMs *= rp.Backoff
	}

	// Apply max delay cap if set
	if rp.MaxDelayMs > 0 && int(delayMs) > rp.MaxDelayMs {
		delayMs = float64(rp.MaxDelayMs)
	}

	return time.Duration(delayMs) * time.Millisecond
}

// NewDAG creates a new DAG with the given ID and name.
func NewDAG(id, name string) *DAG {
	return &DAG{
		ID:       id,
		Name:     name,
		Version:  1,
		Nodes:    make(map[string]*Node),
		Edges:    make([]*Edge, 0),
		Config:   DefaultWorkflowConfig(),
		Metadata: make(map[string]interface{}),
	}
}

// AddNode adds a node to the DAG.
func (d *DAG) AddNode(node *Node) error {
	if node == nil {
		return fmt.Errorf("node cannot be nil")
	}
	if node.ID == "" {
		return fmt.Errorf("node ID is required")
	}
	if _, exists := d.Nodes[node.ID]; exists {
		return fmt.Errorf("node %q already exists", node.ID)
	}
	d.Nodes[node.ID] = node
	return nil
}

// AddEdge adds an edge between two nodes.
func (d *DAG) AddEdge(from, to string) error {
	return d.AddEdgeWithCondition(from, to, "")
}

// AddEdgeWithCondition adds a conditional edge between two nodes.
func (d *DAG) AddEdgeWithCondition(from, to, condition string) error {
	if from == "" || to == "" {
		return fmt.Errorf("edge requires both from and to node IDs")
	}
	edge := &Edge{
		From:      from,
		To:        to,
		Condition: condition,
	}
	d.Edges = append(d.Edges, edge)
	return nil
}

// GetNode returns a node by ID, or nil if not found.
func (d *DAG) GetNode(id string) *Node {
	if d.Nodes == nil {
		return nil
	}
	return d.Nodes[id]
}

// GetOutgoingEdges returns all edges originating from the given node.
func (d *DAG) GetOutgoingEdges(nodeID string) []*Edge {
	edges := make([]*Edge, 0)
	for _, edge := range d.Edges {
		if edge.From == nodeID {
			edges = append(edges, edge)
		}
	}
	return edges
}

// GetIncomingEdges returns all edges pointing to the given node.
func (d *DAG) GetIncomingEdges(nodeID string) []*Edge {
	edges := make([]*Edge, 0)
	for _, edge := range d.Edges {
		if edge.To == nodeID {
			edges = append(edges, edge)
		}
	}
	return edges
}

// GetSuccessors returns the IDs of all nodes that the given node points to.
func (d *DAG) GetSuccessors(nodeID string) []string {
	successors := make([]string, 0)
	for _, edge := range d.Edges {
		if edge.From == nodeID {
			successors = append(successors, edge.To)
		}
	}
	return successors
}

// GetPredecessors returns the IDs of all nodes that point to the given node.
func (d *DAG) GetPredecessors(nodeID string) []string {
	predecessors := make([]string, 0)
	for _, edge := range d.Edges {
		if edge.To == nodeID {
			predecessors = append(predecessors, edge.From)
		}
	}
	return predecessors
}

// NodeCount returns the number of nodes in the DAG.
func (d *DAG) NodeCount() int {
	return len(d.Nodes)
}

// EdgeCount returns the number of edges in the DAG.
func (d *DAG) EdgeCount() int {
	return len(d.Edges)
}

// Clone creates a deep copy of the DAG.
func (d *DAG) Clone() (*DAG, error) {
	data, err := json.Marshal(d)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal DAG: %w", err)
	}

	var clone DAG
	if err := json.Unmarshal(data, &clone); err != nil {
		return nil, fmt.Errorf("failed to unmarshal DAG: %w", err)
	}

	return &clone, nil
}

// ToJSON serializes the DAG to JSON.
func (d *DAG) ToJSON() ([]byte, error) {
	return json.MarshalIndent(d, "", "  ")
}

// FromJSON deserializes a DAG from JSON.
func FromJSON(data []byte) (*DAG, error) {
	var dag DAG
	if err := json.Unmarshal(data, &dag); err != nil {
		return nil, fmt.Errorf("failed to parse DAG JSON: %w", err)
	}

	// Initialize maps if nil
	if dag.Nodes == nil {
		dag.Nodes = make(map[string]*Node)
	}
	if dag.Metadata == nil {
		dag.Metadata = make(map[string]interface{})
	}
	if dag.Config == nil {
		dag.Config = DefaultWorkflowConfig()
	}

	return &dag, nil
}

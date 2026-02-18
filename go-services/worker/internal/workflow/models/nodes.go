package models

// OperationNodeConfig holds configuration for operation nodes.
// Operation nodes execute template-based operations on 1C databases.
type OperationNodeConfig struct {
	// OperationType specifies the operation kind (create, update, delete, query, etc.).
	OperationType string `json:"operation_type"`
	// TargetEntity is the OData entity or resource being operated on.
	TargetEntity string `json:"target_entity,omitempty"`
	// Payload contains the data to be sent with the operation.
	Payload map[string]interface{} `json:"payload,omitempty"`
	// TemplateID references the operation template.
	TemplateID string `json:"template_id,omitempty"`
}

// OperationRef describes operation template binding provenance.
type OperationRef struct {
	Alias                    string `json:"alias"`
	BindingMode              string `json:"binding_mode,omitempty"`
	TemplateExposureID       string `json:"template_exposure_id,omitempty"`
	TemplateExposureRevision int    `json:"template_exposure_revision,omitempty"`
}

// ConditionNodeConfig holds configuration for condition nodes.
// Condition nodes evaluate expressions and branch workflow execution.
type ConditionNodeConfig struct {
	// Expression is a Jinja2/template expression that evaluates to boolean.
	Expression string `json:"expression"`
	// TrueNode is the node ID to execute if expression is true.
	TrueNode string `json:"true_node"`
	// FalseNode is the node ID to execute if expression is false.
	FalseNode string `json:"false_node"`
}

// Validate checks if the condition config is valid.
func (c *ConditionNodeConfig) Validate() error {
	if c.Expression == "" {
		return ErrConditionExpressionRequired
	}
	if c.TrueNode == "" && c.FalseNode == "" {
		return ErrConditionBranchesRequired
	}
	return nil
}

// ParallelNodeConfig holds configuration for parallel nodes.
// Parallel nodes execute multiple branches concurrently.
type ParallelNodeConfig struct {
	// BranchNodes lists the node IDs to execute in parallel.
	BranchNodes []string `json:"branch_nodes"`
	// WaitAll determines if we wait for all branches (true) or any (false).
	WaitAll bool `json:"wait_all"`
	// WaitFor specifies how many branches to wait for ("all", "any", or a number).
	WaitFor string `json:"wait_for,omitempty"`
	// FailFast cancels remaining branches on first failure if true.
	FailFast bool `json:"fail_fast"`
	// MaxConcurrent limits the number of concurrent executions (0 = unlimited).
	MaxConcurrent int `json:"max_concurrent,omitempty"`
	// TimeoutSeconds is the timeout for the entire parallel execution.
	TimeoutSeconds int `json:"timeout_seconds,omitempty"`
}

// DefaultParallelConfig returns a default parallel configuration.
func DefaultParallelConfig() *ParallelNodeConfig {
	return &ParallelNodeConfig{
		BranchNodes:    []string{},
		WaitAll:        true,
		WaitFor:        "all",
		FailFast:       false,
		MaxConcurrent:  0,
		TimeoutSeconds: 300,
	}
}

// Validate checks if the parallel config is valid.
func (p *ParallelNodeConfig) Validate() error {
	if len(p.BranchNodes) == 0 {
		return ErrParallelBranchesRequired
	}
	return nil
}

// LoopMode represents the loop iteration mode.
type LoopMode string

const (
	// LoopModeCount iterates a fixed number of times.
	LoopModeCount LoopMode = "count"
	// LoopModeWhile iterates while condition is true.
	LoopModeWhile LoopMode = "while"
	// LoopModeForeach iterates over a collection.
	LoopModeForeach LoopMode = "foreach"
)

// LoopNodeConfig holds configuration for loop nodes.
// Loop nodes iterate over items, counts, or conditions.
type LoopNodeConfig struct {
	// Mode specifies the loop type: count, while, or foreach.
	Mode LoopMode `json:"mode"`
	// Count is the number of iterations (for count mode).
	Count int `json:"count,omitempty"`
	// Condition is the expression to evaluate (for while mode).
	Condition string `json:"condition,omitempty"`
	// Items is the expression returning a list (for foreach mode).
	Items string `json:"items,omitempty"`
	// LoopVar is the variable name for the current item (for foreach mode).
	LoopVar string `json:"loop_var,omitempty"`
	// BodyNode is the node ID to execute for each iteration.
	BodyNode string `json:"body_node"`
	// MaxIterations is the safety limit to prevent infinite loops.
	MaxIterations int `json:"max_iterations,omitempty"`
}

// DefaultLoopConfig returns a default loop configuration.
func DefaultLoopConfig() *LoopNodeConfig {
	return &LoopNodeConfig{
		Mode:          LoopModeCount,
		Count:         1,
		LoopVar:       "item",
		MaxIterations: 100,
	}
}

// Validate checks if the loop config is valid.
func (l *LoopNodeConfig) Validate() error {
	if l.BodyNode == "" {
		return ErrLoopBodyNodeRequired
	}

	switch l.Mode {
	case LoopModeCount:
		if l.Count <= 0 {
			return ErrLoopCountRequired
		}
	case LoopModeWhile:
		if l.Condition == "" {
			return ErrLoopConditionRequired
		}
	case LoopModeForeach:
		if l.Items == "" {
			return ErrLoopItemsRequired
		}
	default:
		return ErrLoopInvalidMode
	}

	return nil
}

// SubworkflowNodeConfig holds configuration for subworkflow nodes.
// Subworkflow nodes execute nested workflows with input/output mapping.
type SubworkflowNodeConfig struct {
	// WorkflowID is the ID of the workflow to execute.
	WorkflowID string `json:"workflow_id"`
	// InputMapping maps parent context to subworkflow context.
	// Format: {"parent.path": "subworkflow.path"}
	InputMapping map[string]string `json:"input_mapping,omitempty"`
	// OutputMapping maps subworkflow result to parent context.
	// Format: {"subworkflow.path": "parent.path"}
	OutputMapping map[string]string `json:"output_mapping,omitempty"`
	// MaxDepth limits subworkflow nesting to prevent infinite recursion.
	MaxDepth int `json:"max_depth,omitempty"`
}

// DefaultSubworkflowConfig returns a default subworkflow configuration.
func DefaultSubworkflowConfig() *SubworkflowNodeConfig {
	return &SubworkflowNodeConfig{
		InputMapping:  make(map[string]string),
		OutputMapping: make(map[string]string),
		MaxDepth:      10,
	}
}

// Validate checks if the subworkflow config is valid.
func (s *SubworkflowNodeConfig) Validate() error {
	if s.WorkflowID == "" {
		return ErrSubworkflowIDRequired
	}
	if s.MaxDepth <= 0 {
		s.MaxDepth = 10 // Apply default
	}
	return nil
}

// Configuration validation errors.
var (
	ErrConditionExpressionRequired = &ConfigError{Field: "expression", Message: "expression is required for condition nodes"}
	ErrConditionBranchesRequired   = &ConfigError{Field: "true_node/false_node", Message: "at least one branch is required for condition nodes"}
	ErrParallelBranchesRequired    = &ConfigError{Field: "branch_nodes", Message: "branch_nodes is required for parallel nodes"}
	ErrLoopBodyNodeRequired        = &ConfigError{Field: "body_node", Message: "body_node is required for loop nodes"}
	ErrLoopCountRequired           = &ConfigError{Field: "count", Message: "count must be positive for count loop mode"}
	ErrLoopConditionRequired       = &ConfigError{Field: "condition", Message: "condition is required for while loop mode"}
	ErrLoopItemsRequired           = &ConfigError{Field: "items", Message: "items is required for foreach loop mode"}
	ErrLoopInvalidMode             = &ConfigError{Field: "mode", Message: "invalid loop mode (must be count, while, or foreach)"}
	ErrSubworkflowIDRequired       = &ConfigError{Field: "workflow_id", Message: "workflow_id is required for subworkflow nodes"}
)

// ConfigError represents a configuration validation error.
type ConfigError struct {
	Field   string
	Message string
}

// Error implements the error interface.
func (e *ConfigError) Error() string {
	return e.Field + ": " + e.Message
}

// NewOperationNode creates a new operation node.
func NewOperationNode(id, name, templateID string) *Node {
	return &Node{
		ID:         id,
		Type:       NodeTypeOperation,
		Name:       name,
		TemplateID: templateID,
		Config:     DefaultNodeConfig(),
	}
}

// NewConditionNode creates a new condition node.
func NewConditionNode(id, name, expression string) *Node {
	return &Node{
		ID:   id,
		Type: NodeTypeCondition,
		Name: name,
		Config: &NodeConfig{
			TimeoutSeconds: 30,
			Expression:     expression,
		},
		ConditionConfig: &ConditionNodeConfig{
			Expression: expression,
		},
	}
}

// NewParallelNode creates a new parallel node.
func NewParallelNode(id, name string, branchNodes []string) *Node {
	return &Node{
		ID:     id,
		Type:   NodeTypeParallel,
		Name:   name,
		Config: DefaultNodeConfig(),
		ParallelConfig: &ParallelNodeConfig{
			BranchNodes:    branchNodes,
			WaitAll:        true,
			WaitFor:        "all",
			FailFast:       false,
			TimeoutSeconds: 300,
		},
	}
}

// NewLoopNode creates a new loop node.
func NewLoopNode(id, name string, mode LoopMode, bodyNode string) *Node {
	return &Node{
		ID:     id,
		Type:   NodeTypeLoop,
		Name:   name,
		Config: DefaultNodeConfig(),
		LoopConfig: &LoopNodeConfig{
			Mode:          mode,
			BodyNode:      bodyNode,
			MaxIterations: 100,
		},
	}
}

// NewSubworkflowNode creates a new subworkflow node.
func NewSubworkflowNode(id, name, workflowID string) *Node {
	return &Node{
		ID:     id,
		Type:   NodeTypeSubworkflow,
		Name:   name,
		Config: DefaultNodeConfig(),
		SubworkflowConfig: &SubworkflowNodeConfig{
			WorkflowID:    workflowID,
			InputMapping:  make(map[string]string),
			OutputMapping: make(map[string]string),
			MaxDepth:      10,
		},
	}
}

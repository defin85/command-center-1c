// Package validator provides DAG validation for workflow engine.
package validator

import (
	"fmt"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// ValidationSeverity represents the severity level of a validation issue.
type ValidationSeverity string

const (
	// SeverityError indicates a critical issue that prevents DAG execution.
	SeverityError ValidationSeverity = "error"
	// SeverityWarning indicates a non-critical issue.
	SeverityWarning ValidationSeverity = "warning"
	// SeverityInfo provides informational messages.
	SeverityInfo ValidationSeverity = "info"
)

// ValidationIssue represents a single validation problem found in the DAG.
type ValidationIssue struct {
	// Severity indicates how critical the issue is.
	Severity ValidationSeverity
	// Message describes the issue.
	Message string
	// NodeIDs lists the nodes involved in the issue.
	NodeIDs []string
	// Details provides additional context.
	Details map[string]interface{}
}

// String formats the issue as a human-readable string.
func (vi *ValidationIssue) String() string {
	s := fmt.Sprintf("[%s] %s", vi.Severity, vi.Message)
	if len(vi.NodeIDs) > 0 {
		s += fmt.Sprintf(" (nodes: %v)", vi.NodeIDs)
	}
	return s
}

// ValidationResult contains the complete validation outcome.
type ValidationResult struct {
	// IsValid is true if no errors were found.
	IsValid bool
	// Errors contains critical issues preventing execution.
	Errors []*ValidationIssue
	// Warnings contains non-critical issues.
	Warnings []*ValidationIssue
	// Info contains informational messages.
	Info []*ValidationIssue
	// TopologicalOrder contains sorted node IDs if no cycles.
	TopologicalOrder []string
	// Metadata stores additional validation information.
	Metadata map[string]interface{}
}

// NewValidationResult creates a new empty validation result.
func NewValidationResult() *ValidationResult {
	return &ValidationResult{
		IsValid:  true,
		Errors:   make([]*ValidationIssue, 0),
		Warnings: make([]*ValidationIssue, 0),
		Info:     make([]*ValidationIssue, 0),
		Metadata: make(map[string]interface{}),
	}
}

// AddError adds a critical error to the result.
func (vr *ValidationResult) AddError(message string, nodeIDs []string, details map[string]interface{}) {
	vr.IsValid = false
	vr.Errors = append(vr.Errors, &ValidationIssue{
		Severity: SeverityError,
		Message:  message,
		NodeIDs:  nodeIDs,
		Details:  details,
	})
}

// AddWarning adds a non-critical warning to the result.
func (vr *ValidationResult) AddWarning(message string, nodeIDs []string, details map[string]interface{}) {
	vr.Warnings = append(vr.Warnings, &ValidationIssue{
		Severity: SeverityWarning,
		Message:  message,
		NodeIDs:  nodeIDs,
		Details:  details,
	})
}

// AddInfo adds an informational message to the result.
func (vr *ValidationResult) AddInfo(message string, nodeIDs []string, details map[string]interface{}) {
	vr.Info = append(vr.Info, &ValidationIssue{
		Severity: SeverityInfo,
		Message:  message,
		NodeIDs:  nodeIDs,
		Details:  details,
	})
}

// Validator performs comprehensive DAG validation.
type Validator struct {
	dag           *models.DAG
	adjList       map[string][]string // forward adjacency: from -> [to, ...]
	reverseAdjList map[string][]string // reverse adjacency: to -> [from, ...]
	inDegree      map[string]int      // in-degree for each node
	outDegree     map[string]int      // out-degree for each node
}

// AllowedNodeTypes contains all valid node types.
var AllowedNodeTypes = map[models.NodeType]bool{
	models.NodeTypeOperation:   true,
	models.NodeTypeCondition:   true,
	models.NodeTypeParallel:    true,
	models.NodeTypeLoop:        true,
	models.NodeTypeSubworkflow: true,
}

// NewValidator creates a new validator for the given DAG.
func NewValidator(dag *models.DAG) *Validator {
	v := &Validator{
		dag:            dag,
		adjList:        make(map[string][]string),
		reverseAdjList: make(map[string][]string),
		inDegree:       make(map[string]int),
		outDegree:      make(map[string]int),
	}
	v.buildGraph()
	return v
}

// buildGraph constructs internal graph representation from DAG structure.
func (v *Validator) buildGraph() {
	if v.dag == nil || v.dag.Nodes == nil {
		return
	}

	// Initialize degrees for all nodes
	for nodeID := range v.dag.Nodes {
		v.inDegree[nodeID] = 0
		v.outDegree[nodeID] = 0
		v.adjList[nodeID] = make([]string, 0)
		v.reverseAdjList[nodeID] = make([]string, 0)
	}

	// Build adjacency lists from edges
	for _, edge := range v.dag.Edges {
		// Skip invalid edges (will be caught in validation)
		if _, exists := v.dag.Nodes[edge.From]; !exists {
			continue
		}
		if _, exists := v.dag.Nodes[edge.To]; !exists {
			continue
		}

		v.adjList[edge.From] = append(v.adjList[edge.From], edge.To)
		v.reverseAdjList[edge.To] = append(v.reverseAdjList[edge.To], edge.From)
		v.inDegree[edge.To]++
		v.outDegree[edge.From]++
	}
}

// Validate performs comprehensive DAG validation.
// Returns a ValidationResult with errors, warnings, and metadata.
func (v *Validator) Validate() *ValidationResult {
	result := NewValidationResult()

	// Early check for nil or empty DAG
	if v.dag == nil {
		result.AddError("DAG is nil", nil, nil)
		return result
	}
	if len(v.dag.Nodes) == 0 {
		result.AddError("DAG contains no nodes", nil, nil)
		return result
	}

	// Step 1: Check for duplicate node IDs (already enforced by map, but validate input)
	v.checkDuplicateNodes(result)

	// Step 2: Validate edge references
	v.validateEdgeReferences(result)

	// Step 3: Check for self-loops
	v.checkSelfLoops(result)

	// Step 4: Validate node types
	v.validateNodeTypes(result)

	// Step 5: Validate node configurations
	v.validateNodeConfigs(result)

	// Step 6: Topological sort (cycle detection)
	if result.IsValid {
		order := v.topologicalSort(result)
		if order != nil {
			result.TopologicalOrder = order
		}
	}

	// Step 7: Check connectivity (reachability from start nodes)
	if result.IsValid {
		v.checkConnectivity(result)
	}

	// Step 8: Count components
	if result.IsValid {
		componentCount := v.countComponents()
		result.Metadata["component_count"] = componentCount
		if componentCount > 1 {
			result.AddWarning(
				fmt.Sprintf("DAG contains %d disconnected components", componentCount),
				nil,
				map[string]interface{}{"component_count": componentCount},
			)
		}
	}

	// Step 9: Validate topology (start/end nodes)
	if result.IsValid {
		v.validateTopology(result)
	}

	// Add summary metadata
	result.Metadata["total_nodes"] = len(v.dag.Nodes)
	result.Metadata["total_edges"] = len(v.dag.Edges)
	result.Metadata["error_count"] = len(result.Errors)
	result.Metadata["warning_count"] = len(result.Warnings)

	return result
}

// checkDuplicateNodes verifies node IDs are unique.
func (v *Validator) checkDuplicateNodes(result *ValidationResult) {
	// With map storage, duplicates are inherently prevented.
	// This check is for when nodes are provided as a list during parsing.
	// The current DAG structure uses map, so this is a no-op safeguard.
}

// validateEdgeReferences ensures all edges reference existing nodes.
func (v *Validator) validateEdgeReferences(result *ValidationResult) {
	for _, edge := range v.dag.Edges {
		invalidRefs := make([]string, 0)

		if _, exists := v.dag.Nodes[edge.From]; !exists {
			invalidRefs = append(invalidRefs, edge.From)
		}
		if _, exists := v.dag.Nodes[edge.To]; !exists {
			invalidRefs = append(invalidRefs, edge.To)
		}

		if len(invalidRefs) > 0 {
			result.AddError(
				fmt.Sprintf("Edge references non-existent node(s): %s -> %s", edge.From, edge.To),
				invalidRefs,
				map[string]interface{}{"from": edge.From, "to": edge.To},
			)
		}
	}
}

// checkSelfLoops detects edges where source equals destination.
func (v *Validator) checkSelfLoops(result *ValidationResult) {
	selfLoops := make([]string, 0)

	for _, edge := range v.dag.Edges {
		if edge.From == edge.To {
			selfLoops = append(selfLoops, edge.From)
		}
	}

	if len(selfLoops) > 0 {
		result.AddError(
			fmt.Sprintf("Self-loops detected in nodes: %v", selfLoops),
			selfLoops,
			map[string]interface{}{"self_loop_nodes": selfLoops},
		)
	}
}

// validateNodeTypes ensures all nodes have valid types.
func (v *Validator) validateNodeTypes(result *ValidationResult) {
	invalidNodes := make([]string, 0)

	for nodeID, node := range v.dag.Nodes {
		if !AllowedNodeTypes[node.Type] {
			invalidNodes = append(invalidNodes, nodeID)
		}
	}

	if len(invalidNodes) > 0 {
		result.AddError(
			"Invalid node types detected",
			invalidNodes,
			map[string]interface{}{
				"invalid_nodes":  invalidNodes,
				"allowed_types": []string{"operation", "condition", "parallel", "loop", "subworkflow"},
			},
		)
	}
}

// validateNodeConfigs validates node-specific configurations.
func (v *Validator) validateNodeConfigs(result *ValidationResult) {
	for nodeID, node := range v.dag.Nodes {
		switch node.Type {
		case models.NodeTypeOperation:
			// Operation nodes require template_id
			if node.TemplateID == "" {
				result.AddError(
					fmt.Sprintf("Operation node %q missing template_id", nodeID),
					[]string{nodeID},
					nil,
				)
			}

		case models.NodeTypeCondition:
			// Condition nodes require expression
			if node.Config == nil || node.Config.Expression == "" {
				if node.ConditionConfig == nil || node.ConditionConfig.Expression == "" {
					result.AddError(
						fmt.Sprintf("Condition node %q missing expression", nodeID),
						[]string{nodeID},
						nil,
					)
				}
			}

		case models.NodeTypeParallel:
			// Parallel nodes require parallel_config
			if node.ParallelConfig == nil {
				result.AddError(
					fmt.Sprintf("Parallel node %q missing parallel_config", nodeID),
					[]string{nodeID},
					nil,
				)
			} else if err := node.ParallelConfig.Validate(); err != nil {
				result.AddError(
					fmt.Sprintf("Parallel node %q: %v", nodeID, err),
					[]string{nodeID},
					nil,
				)
			}

		case models.NodeTypeLoop:
			// Loop nodes require loop_config
			if node.LoopConfig == nil {
				result.AddError(
					fmt.Sprintf("Loop node %q missing loop_config", nodeID),
					[]string{nodeID},
					nil,
				)
			} else if err := node.LoopConfig.Validate(); err != nil {
				result.AddError(
					fmt.Sprintf("Loop node %q: %v", nodeID, err),
					[]string{nodeID},
					nil,
				)
			}

		case models.NodeTypeSubworkflow:
			// Subworkflow nodes require subworkflow_config
			if node.SubworkflowConfig == nil {
				result.AddError(
					fmt.Sprintf("Subworkflow node %q missing subworkflow_config", nodeID),
					[]string{nodeID},
					nil,
				)
			} else if err := node.SubworkflowConfig.Validate(); err != nil {
				result.AddError(
					fmt.Sprintf("Subworkflow node %q: %v", nodeID, err),
					[]string{nodeID},
					nil,
				)
			}
		}
	}
}

// topologicalSort performs Kahn's algorithm to detect cycles and produce order.
// Returns the topologically sorted node IDs, or nil if a cycle exists.
func (v *Validator) topologicalSort(result *ValidationResult) []string {
	// Create working copy of in-degree
	inDegreeCopy := make(map[string]int)
	for nodeID, degree := range v.inDegree {
		inDegreeCopy[nodeID] = degree
	}

	// Initialize queue with nodes having no incoming edges
	queue := make([]string, 0)
	for nodeID, degree := range inDegreeCopy {
		if degree == 0 {
			queue = append(queue, nodeID)
		}
	}

	order := make([]string, 0, len(v.dag.Nodes))

	for len(queue) > 0 {
		// Dequeue
		nodeID := queue[0]
		queue = queue[1:]
		order = append(order, nodeID)

		// Reduce in-degree for neighbors
		for _, neighbor := range v.adjList[nodeID] {
			inDegreeCopy[neighbor]--
			if inDegreeCopy[neighbor] == 0 {
				queue = append(queue, neighbor)
			}
		}
	}

	// If not all nodes processed, cycle exists
	if len(order) != len(v.dag.Nodes) {
		unprocessed := make([]string, 0)
		for nodeID := range v.dag.Nodes {
			found := false
			for _, processed := range order {
				if processed == nodeID {
					found = true
					break
				}
			}
			if !found {
				unprocessed = append(unprocessed, nodeID)
			}
		}

		result.AddError(
			fmt.Sprintf("Cycle detected in DAG. %d node(s) could not be processed", len(unprocessed)),
			unprocessed,
			map[string]interface{}{
				"processed_count":   len(order),
				"total_count":       len(v.dag.Nodes),
				"unprocessed_nodes": unprocessed,
			},
		)
		return nil
	}

	return order
}

// checkConnectivity verifies all nodes are reachable from start nodes.
func (v *Validator) checkConnectivity(result *ValidationResult) {
	// Find start nodes (no incoming edges)
	startNodes := make([]string, 0)
	for nodeID, degree := range v.inDegree {
		if degree == 0 {
			startNodes = append(startNodes, nodeID)
		}
	}

	if len(startNodes) == 0 {
		result.AddError("No start nodes found (all nodes have incoming edges)", nil, nil)
		return
	}

	// BFS from start nodes
	visited := make(map[string]bool)
	queue := make([]string, len(startNodes))
	copy(queue, startNodes)

	for len(queue) > 0 {
		nodeID := queue[0]
		queue = queue[1:]

		if visited[nodeID] {
			continue
		}
		visited[nodeID] = true

		for _, neighbor := range v.adjList[nodeID] {
			if !visited[neighbor] {
				queue = append(queue, neighbor)
			}
		}
	}

	// Check for unreachable nodes
	unreachable := make([]string, 0)
	for nodeID := range v.dag.Nodes {
		if !visited[nodeID] {
			unreachable = append(unreachable, nodeID)
		}
	}

	if len(unreachable) > 0 {
		result.AddError(
			fmt.Sprintf("%d node(s) are unreachable from start nodes", len(unreachable)),
			unreachable,
			map[string]interface{}{
				"unreachable_nodes": unreachable,
				"start_nodes":       startNodes,
			},
		)
	}
}

// countComponents counts weakly connected components using iterative DFS.
func (v *Validator) countComponents() int {
	visited := make(map[string]bool)
	componentCount := 0

	for startNode := range v.dag.Nodes {
		if visited[startNode] {
			continue
		}

		// Iterative DFS to avoid stack overflow
		stack := []string{startNode}
		for len(stack) > 0 {
			nodeID := stack[len(stack)-1]
			stack = stack[:len(stack)-1]

			if visited[nodeID] {
				continue
			}
			visited[nodeID] = true

			// Visit forward neighbors
			for _, neighbor := range v.adjList[nodeID] {
				if !visited[neighbor] {
					stack = append(stack, neighbor)
				}
			}

			// Visit backward neighbors (treat as undirected)
			for _, neighbor := range v.reverseAdjList[nodeID] {
				if !visited[neighbor] {
					stack = append(stack, neighbor)
				}
			}
		}

		componentCount++
	}

	return componentCount
}

// validateTopology ensures proper start and end nodes exist.
func (v *Validator) validateTopology(result *ValidationResult) {
	startNodes := make([]string, 0)
	endNodes := make([]string, 0)
	isolatedNodes := make([]string, 0)

	for nodeID := range v.dag.Nodes {
		inDeg := v.inDegree[nodeID]
		outDeg := v.outDegree[nodeID]

		if inDeg == 0 {
			startNodes = append(startNodes, nodeID)
		}
		if outDeg == 0 {
			endNodes = append(endNodes, nodeID)
		}
		// Check isolated only when we have multiple nodes
		if len(v.dag.Nodes) > 1 && inDeg == 0 && outDeg == 0 {
			isolatedNodes = append(isolatedNodes, nodeID)
		}
	}

	// Check isolated nodes
	if len(isolatedNodes) > 0 {
		result.AddError(
			fmt.Sprintf("Isolated nodes detected (no incoming or outgoing edges): %v", isolatedNodes),
			isolatedNodes,
			map[string]interface{}{"isolated_nodes": isolatedNodes},
		)
	}

	// Check start nodes
	if len(startNodes) == 0 {
		result.AddError("No start nodes found (all nodes have incoming edges)", nil, nil)
	} else if len(startNodes) > 1 {
		result.AddInfo(
			fmt.Sprintf("Multiple start nodes detected: %v", startNodes),
			startNodes,
			map[string]interface{}{"start_nodes": startNodes},
		)
	}

	// Check end nodes
	if len(endNodes) == 0 {
		result.AddError("No end nodes found (all nodes have outgoing edges)", nil, nil)
	} else if len(endNodes) > 1 {
		result.AddInfo(
			fmt.Sprintf("Multiple end nodes detected: %v", endNodes),
			endNodes,
			map[string]interface{}{"end_nodes": endNodes},
		)
	}

	// Store in metadata
	result.Metadata["start_nodes"] = startNodes
	result.Metadata["end_nodes"] = endNodes
}

// ValidateQuick performs a quick validation, returning the first error found.
// Useful for early bailout when detailed diagnostics are not needed.
func ValidateQuick(dag *models.DAG) error {
	if dag == nil {
		return workflow.ErrEmptyDAG
	}
	if len(dag.Nodes) == 0 {
		return workflow.ErrEmptyDAG
	}

	v := NewValidator(dag)
	result := v.Validate()

	if !result.IsValid && len(result.Errors) > 0 {
		return workflow.NewValidationError(result.Errors[0].Message, result.Errors[0].NodeIDs...)
	}

	return nil
}

// MustValidate validates the DAG and panics if validation fails.
// Useful for tests and initialization code.
func MustValidate(dag *models.DAG) *ValidationResult {
	v := NewValidator(dag)
	result := v.Validate()
	if !result.IsValid {
		panic(fmt.Sprintf("DAG validation failed: %v", result.Errors))
	}
	return result
}

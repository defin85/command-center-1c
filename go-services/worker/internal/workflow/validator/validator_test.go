package validator

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// Helper to create a simple linear DAG: start -> middle -> end
func createSimpleDAG() *models.DAG {
	dag := models.NewDAG("simple", "Simple Workflow")
	dag.EntryNode = "start"

	_ = dag.AddNode(models.NewOperationNode("start", "Start", "template1"))
	_ = dag.AddNode(models.NewOperationNode("middle", "Middle", "template2"))
	_ = dag.AddNode(models.NewOperationNode("end", "End", "template3"))

	_ = dag.AddEdge("start", "middle")
	_ = dag.AddEdge("middle", "end")

	return dag
}

// Helper to create a DAG with a cycle
func createCyclicDAG() *models.DAG {
	dag := models.NewDAG("cyclic", "Cyclic Workflow")
	dag.EntryNode = "a"

	_ = dag.AddNode(models.NewOperationNode("a", "A", "t1"))
	_ = dag.AddNode(models.NewOperationNode("b", "B", "t2"))
	_ = dag.AddNode(models.NewOperationNode("c", "C", "t3"))

	_ = dag.AddEdge("a", "b")
	_ = dag.AddEdge("b", "c")
	_ = dag.AddEdge("c", "a") // Creates cycle: a -> b -> c -> a

	return dag
}

// Helper to create a DAG with unreachable nodes
func createUnreachableDAG() *models.DAG {
	dag := models.NewDAG("unreachable", "Unreachable Workflow")
	dag.EntryNode = "start"

	_ = dag.AddNode(models.NewOperationNode("start", "Start", "t1"))
	_ = dag.AddNode(models.NewOperationNode("end", "End", "t2"))
	_ = dag.AddNode(models.NewOperationNode("orphan", "Orphan", "t3"))

	_ = dag.AddEdge("start", "end")
	// "orphan" has no edges, making it unreachable and isolated

	return dag
}

func TestValidator_ValidSimpleDAG(t *testing.T) {
	dag := createSimpleDAG()
	v := NewValidator(dag)
	result := v.Validate()

	assert.True(t, result.IsValid)
	assert.Empty(t, result.Errors)
	assert.NotNil(t, result.TopologicalOrder)
	assert.Len(t, result.TopologicalOrder, 3)
	assert.Equal(t, "start", result.TopologicalOrder[0])
	assert.Equal(t, "end", result.TopologicalOrder[2])
}

func TestValidator_NilDAG(t *testing.T) {
	v := NewValidator(nil)
	result := v.Validate()

	assert.False(t, result.IsValid)
	assert.NotEmpty(t, result.Errors)
	assert.Contains(t, result.Errors[0].Message, "nil")
}

func TestValidator_EmptyDAG(t *testing.T) {
	dag := models.NewDAG("empty", "Empty")
	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)
	assert.NotEmpty(t, result.Errors)
	assert.Contains(t, result.Errors[0].Message, "no nodes")
}

func TestValidator_CycleDetection(t *testing.T) {
	dag := createCyclicDAG()
	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	// Find cycle error
	var cycleError *ValidationIssue
	for _, err := range result.Errors {
		if err.Message != "" && containsWord(err.Message, "Cycle") {
			cycleError = err
			break
		}
	}

	require.NotNil(t, cycleError, "Expected cycle error")
	assert.NotEmpty(t, cycleError.NodeIDs)
	assert.Nil(t, result.TopologicalOrder)
}

func TestValidator_SelfLoop(t *testing.T) {
	dag := models.NewDAG("selfloop", "Self Loop")
	dag.EntryNode = "node1"

	_ = dag.AddNode(models.NewOperationNode("node1", "Node 1", "t1"))
	_ = dag.AddEdge("node1", "node1") // Self-loop

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var selfLoopError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "Self-loop") {
			selfLoopError = err
			break
		}
	}

	require.NotNil(t, selfLoopError)
	assert.Contains(t, selfLoopError.NodeIDs, "node1")
}

func TestValidator_InvalidEdgeReference(t *testing.T) {
	dag := models.NewDAG("invalid-edge", "Invalid Edge")
	dag.EntryNode = "start"

	_ = dag.AddNode(models.NewOperationNode("start", "Start", "t1"))
	_ = dag.AddEdge("start", "nonexistent") // Points to non-existent node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var edgeError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "non-existent") {
			edgeError = err
			break
		}
	}

	require.NotNil(t, edgeError)
}

func TestValidator_InvalidNodeType(t *testing.T) {
	dag := models.NewDAG("invalid-type", "Invalid Type")
	dag.EntryNode = "node1"

	node := &models.Node{
		ID:   "node1",
		Type: models.NodeType("invalid"),
		Name: "Invalid Node",
	}
	dag.Nodes["node1"] = node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var typeError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "Invalid node type") {
			typeError = err
			break
		}
	}

	require.NotNil(t, typeError)
	assert.Contains(t, typeError.NodeIDs, "node1")
}

func TestValidator_UnreachableNodes(t *testing.T) {
	dag := createUnreachableDAG()
	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var unreachableError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "unreachable") || containsWord(err.Message, "Isolated") {
			unreachableError = err
			break
		}
	}

	require.NotNil(t, unreachableError)
}

func TestValidator_MultipleStartNodes(t *testing.T) {
	dag := models.NewDAG("multi-start", "Multiple Starts")

	_ = dag.AddNode(models.NewOperationNode("start1", "Start 1", "t1"))
	_ = dag.AddNode(models.NewOperationNode("start2", "Start 2", "t2"))
	_ = dag.AddNode(models.NewOperationNode("end", "End", "t3"))

	_ = dag.AddEdge("start1", "end")
	_ = dag.AddEdge("start2", "end")

	v := NewValidator(dag)
	result := v.Validate()

	assert.True(t, result.IsValid) // Multiple starts are allowed

	// Should have info about multiple start nodes
	var startInfo *ValidationIssue
	for _, info := range result.Info {
		if containsWord(info.Message, "start nodes") {
			startInfo = info
			break
		}
	}

	require.NotNil(t, startInfo)
	assert.Len(t, startInfo.NodeIDs, 2)
}

func TestValidator_MultipleEndNodes(t *testing.T) {
	dag := models.NewDAG("multi-end", "Multiple Ends")

	_ = dag.AddNode(models.NewOperationNode("start", "Start", "t1"))
	_ = dag.AddNode(models.NewOperationNode("end1", "End 1", "t2"))
	_ = dag.AddNode(models.NewOperationNode("end2", "End 2", "t3"))

	_ = dag.AddEdge("start", "end1")
	_ = dag.AddEdge("start", "end2")

	v := NewValidator(dag)
	result := v.Validate()

	assert.True(t, result.IsValid) // Multiple ends are allowed

	var endInfo *ValidationIssue
	for _, info := range result.Info {
		if containsWord(info.Message, "end nodes") {
			endInfo = info
			break
		}
	}

	require.NotNil(t, endInfo)
	assert.Len(t, endInfo.NodeIDs, 2)
}

func TestValidator_DisconnectedComponents(t *testing.T) {
	dag := models.NewDAG("disconnected", "Disconnected")

	// Component 1: a -> b
	_ = dag.AddNode(models.NewOperationNode("a", "A", "t1"))
	_ = dag.AddNode(models.NewOperationNode("b", "B", "t2"))
	_ = dag.AddEdge("a", "b")

	// Component 2: c -> d (disconnected from component 1)
	// Both a and c are start nodes (in_degree=0), so both components are valid
	_ = dag.AddNode(models.NewOperationNode("c", "C", "t3"))
	_ = dag.AddNode(models.NewOperationNode("d", "D", "t4"))
	_ = dag.AddEdge("c", "d")

	v := NewValidator(dag)
	result := v.Validate()

	// DAG with multiple components is valid if each component has proper start/end nodes
	// and all nodes are reachable from their respective start nodes.
	// However, it should produce a warning about multiple components.
	assert.True(t, result.IsValid)

	componentCount, ok := result.Metadata["component_count"]
	require.True(t, ok)
	assert.Equal(t, 2, componentCount)

	// Should have warning about multiple components
	var componentWarning *ValidationIssue
	for _, w := range result.Warnings {
		if containsWord(w.Message, "components") {
			componentWarning = w
			break
		}
	}
	require.NotNil(t, componentWarning)
}

func TestValidator_OperationNodeWithoutTemplate(t *testing.T) {
	dag := models.NewDAG("no-template", "No Template")
	dag.EntryNode = "node1"

	node := &models.Node{
		ID:         "node1",
		Type:       models.NodeTypeOperation,
		Name:       "Operation without template",
		TemplateID: "", // Missing template
	}
	dag.Nodes["node1"] = node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var templateError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "template_id") {
			templateError = err
			break
		}
	}

	require.NotNil(t, templateError)
}

func TestValidator_ConditionNodeWithoutExpression(t *testing.T) {
	dag := models.NewDAG("no-expr", "No Expression")
	dag.EntryNode = "node1"

	node := &models.Node{
		ID:     "node1",
		Type:   models.NodeTypeCondition,
		Name:   "Condition without expression",
		Config: &models.NodeConfig{}, // No expression
	}
	dag.Nodes["node1"] = node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var exprError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "expression") {
			exprError = err
			break
		}
	}

	require.NotNil(t, exprError)
}

func TestValidator_ParallelNodeWithoutConfig(t *testing.T) {
	dag := models.NewDAG("no-parallel-config", "No Parallel Config")
	dag.EntryNode = "node1"

	node := &models.Node{
		ID:   "node1",
		Type: models.NodeTypeParallel,
		Name: "Parallel without config",
		// Missing ParallelConfig
	}
	dag.Nodes["node1"] = node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var configError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "parallel_config") {
			configError = err
			break
		}
	}

	require.NotNil(t, configError)
}

func TestValidator_LoopNodeWithoutConfig(t *testing.T) {
	dag := models.NewDAG("no-loop-config", "No Loop Config")
	dag.EntryNode = "node1"

	node := &models.Node{
		ID:   "node1",
		Type: models.NodeTypeLoop,
		Name: "Loop without config",
		// Missing LoopConfig
	}
	dag.Nodes["node1"] = node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var configError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "loop_config") {
			configError = err
			break
		}
	}

	require.NotNil(t, configError)
}

func TestValidator_SubworkflowNodeWithoutConfig(t *testing.T) {
	dag := models.NewDAG("no-sub-config", "No Subworkflow Config")
	dag.EntryNode = "node1"

	node := &models.Node{
		ID:   "node1",
		Type: models.NodeTypeSubworkflow,
		Name: "Subworkflow without config",
		// Missing SubworkflowConfig
	}
	dag.Nodes["node1"] = node

	v := NewValidator(dag)
	result := v.Validate()

	assert.False(t, result.IsValid)

	var configError *ValidationIssue
	for _, err := range result.Errors {
		if containsWord(err.Message, "subworkflow_config") {
			configError = err
			break
		}
	}

	require.NotNil(t, configError)
}

func TestValidator_ComplexValidWorkflow(t *testing.T) {
	dag := models.NewDAG("complex", "Complex Workflow")
	dag.EntryNode = "start"

	// Build complex workflow:
	// start -> condition -> (true: parallel, false: end)
	// parallel branches to branch1 and branch2
	// both merge to end

	_ = dag.AddNode(models.NewOperationNode("start", "Start", "t1"))

	condNode := models.NewConditionNode("condition", "Check Status", "{{ status == 'ready' }}")
	condNode.ConditionConfig.TrueNode = "parallel"
	condNode.ConditionConfig.FalseNode = "end"
	_ = dag.AddNode(condNode)

	_ = dag.AddNode(models.NewParallelNode("parallel", "Parallel", []string{"branch1", "branch2"}))
	_ = dag.AddNode(models.NewOperationNode("branch1", "Branch 1", "t2"))
	_ = dag.AddNode(models.NewOperationNode("branch2", "Branch 2", "t3"))
	_ = dag.AddNode(models.NewOperationNode("end", "End", "t4"))

	_ = dag.AddEdge("start", "condition")
	_ = dag.AddEdgeWithCondition("condition", "parallel", "{{ status == 'ready' }}")
	_ = dag.AddEdgeWithCondition("condition", "end", "{{ status != 'ready' }}")
	_ = dag.AddEdge("parallel", "branch1")
	_ = dag.AddEdge("parallel", "branch2")
	_ = dag.AddEdge("branch1", "end")
	_ = dag.AddEdge("branch2", "end")

	v := NewValidator(dag)
	result := v.Validate()

	assert.True(t, result.IsValid, "Expected valid DAG, got errors: %v", result.Errors)
	assert.NotNil(t, result.TopologicalOrder)
	assert.Equal(t, 6, result.Metadata["total_nodes"])
	assert.Equal(t, 7, result.Metadata["total_edges"])
}

func TestValidator_SingleNodeDAG(t *testing.T) {
	dag := models.NewDAG("single", "Single Node")
	dag.EntryNode = "only"

	_ = dag.AddNode(models.NewOperationNode("only", "Only Node", "t1"))

	v := NewValidator(dag)
	result := v.Validate()

	assert.True(t, result.IsValid)
	assert.Len(t, result.TopologicalOrder, 1)
}

func TestValidateQuick(t *testing.T) {
	// Valid DAG
	dag := createSimpleDAG()
	err := ValidateQuick(dag)
	assert.NoError(t, err)

	// Nil DAG
	err = ValidateQuick(nil)
	assert.Error(t, err)

	// Cyclic DAG
	cyclicDAG := createCyclicDAG()
	err = ValidateQuick(cyclicDAG)
	assert.Error(t, err)
}

func TestMustValidate_Panics(t *testing.T) {
	// Valid DAG should not panic
	dag := createSimpleDAG()
	assert.NotPanics(t, func() {
		MustValidate(dag)
	})

	// Invalid DAG should panic
	cyclicDAG := createCyclicDAG()
	assert.Panics(t, func() {
		MustValidate(cyclicDAG)
	})
}

func TestValidationResult_AddMethods(t *testing.T) {
	result := NewValidationResult()

	assert.True(t, result.IsValid)

	result.AddError("error message", []string{"node1"}, map[string]interface{}{"key": "value"})
	assert.False(t, result.IsValid)
	assert.Len(t, result.Errors, 1)
	assert.Equal(t, SeverityError, result.Errors[0].Severity)

	result.AddWarning("warning message", nil, nil)
	assert.Len(t, result.Warnings, 1)
	assert.Equal(t, SeverityWarning, result.Warnings[0].Severity)

	result.AddInfo("info message", nil, nil)
	assert.Len(t, result.Info, 1)
	assert.Equal(t, SeverityInfo, result.Info[0].Severity)
}

func TestValidationIssue_String(t *testing.T) {
	issue := &ValidationIssue{
		Severity: SeverityError,
		Message:  "Test error",
		NodeIDs:  []string{"node1", "node2"},
	}

	s := issue.String()
	assert.Contains(t, s, "error")
	assert.Contains(t, s, "Test error")
	assert.Contains(t, s, "node1")
	assert.Contains(t, s, "node2")
}

func TestValidator_Metadata(t *testing.T) {
	dag := createSimpleDAG()
	v := NewValidator(dag)
	result := v.Validate()

	assert.Equal(t, 3, result.Metadata["total_nodes"])
	assert.Equal(t, 2, result.Metadata["total_edges"])
	assert.Equal(t, 0, result.Metadata["error_count"])
	assert.Equal(t, 0, result.Metadata["warning_count"])
	assert.Equal(t, 1, result.Metadata["component_count"])

	startNodes := result.Metadata["start_nodes"].([]string)
	assert.Len(t, startNodes, 1)
	assert.Equal(t, "start", startNodes[0])

	endNodes := result.Metadata["end_nodes"].([]string)
	assert.Len(t, endNodes, 1)
	assert.Equal(t, "end", endNodes[0])
}

// Helper function to check if a string contains a word
func containsWord(s, word string) bool {
	return len(s) >= len(word) && (s == word ||
		(len(s) > len(word) && (s[:len(word)+1] == word+" " ||
			s[len(s)-len(word)-1:] == " "+word ||
			containsSubstring(s, " "+word+" ") ||
			containsSubstring(s, word))))
}

func containsSubstring(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

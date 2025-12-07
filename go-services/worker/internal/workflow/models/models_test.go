package models

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNodeType_IsValid(t *testing.T) {
	tests := []struct {
		name     string
		nodeType NodeType
		want     bool
	}{
		{"operation is valid", NodeTypeOperation, true},
		{"condition is valid", NodeTypeCondition, true},
		{"parallel is valid", NodeTypeParallel, true},
		{"loop is valid", NodeTypeLoop, true},
		{"subworkflow is valid", NodeTypeSubworkflow, true},
		{"unknown is invalid", NodeType("unknown"), false},
		{"empty is invalid", NodeType(""), false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.nodeType.IsValid()
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestNewDAG(t *testing.T) {
	dag := NewDAG("test-id", "Test DAG")

	assert.Equal(t, "test-id", dag.ID)
	assert.Equal(t, "Test DAG", dag.Name)
	assert.Equal(t, 1, dag.Version)
	assert.NotNil(t, dag.Nodes)
	assert.NotNil(t, dag.Edges)
	assert.NotNil(t, dag.Config)
	assert.NotNil(t, dag.Metadata)
	assert.Equal(t, 0, len(dag.Nodes))
	assert.Equal(t, 0, len(dag.Edges))
}

func TestDAG_AddNode(t *testing.T) {
	dag := NewDAG("test", "Test")

	node := NewOperationNode("node1", "First Node", "template1")
	err := dag.AddNode(node)
	require.NoError(t, err)
	assert.Equal(t, 1, dag.NodeCount())

	// Adding duplicate should fail
	err = dag.AddNode(node)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "already exists")

	// Adding nil should fail
	err = dag.AddNode(nil)
	assert.Error(t, err)

	// Adding node without ID should fail
	err = dag.AddNode(&Node{Name: "no-id"})
	assert.Error(t, err)
}

func TestDAG_AddEdge(t *testing.T) {
	dag := NewDAG("test", "Test")

	err := dag.AddEdge("node1", "node2")
	require.NoError(t, err)
	assert.Equal(t, 1, dag.EdgeCount())

	// Adding edge with empty from should fail
	err = dag.AddEdge("", "node2")
	assert.Error(t, err)

	// Adding edge with empty to should fail
	err = dag.AddEdge("node1", "")
	assert.Error(t, err)
}

func TestDAG_AddEdgeWithCondition(t *testing.T) {
	dag := NewDAG("test", "Test")

	err := dag.AddEdgeWithCondition("node1", "node2", "{{ result.success }}")
	require.NoError(t, err)
	assert.Equal(t, 1, dag.EdgeCount())
	assert.Equal(t, "{{ result.success }}", dag.Edges[0].Condition)
}

func TestDAG_GetNode(t *testing.T) {
	dag := NewDAG("test", "Test")
	node := NewOperationNode("node1", "First Node", "template1")
	_ = dag.AddNode(node)

	found := dag.GetNode("node1")
	assert.NotNil(t, found)
	assert.Equal(t, "node1", found.ID)

	notFound := dag.GetNode("nonexistent")
	assert.Nil(t, notFound)
}

func TestDAG_GetOutgoingEdges(t *testing.T) {
	dag := NewDAG("test", "Test")
	_ = dag.AddEdge("node1", "node2")
	_ = dag.AddEdge("node1", "node3")
	_ = dag.AddEdge("node2", "node3")

	edges := dag.GetOutgoingEdges("node1")
	assert.Len(t, edges, 2)

	edges = dag.GetOutgoingEdges("node2")
	assert.Len(t, edges, 1)

	edges = dag.GetOutgoingEdges("node3")
	assert.Len(t, edges, 0)
}

func TestDAG_GetIncomingEdges(t *testing.T) {
	dag := NewDAG("test", "Test")
	_ = dag.AddEdge("node1", "node3")
	_ = dag.AddEdge("node2", "node3")

	edges := dag.GetIncomingEdges("node3")
	assert.Len(t, edges, 2)

	edges = dag.GetIncomingEdges("node1")
	assert.Len(t, edges, 0)
}

func TestDAG_GetSuccessors(t *testing.T) {
	dag := NewDAG("test", "Test")
	_ = dag.AddEdge("node1", "node2")
	_ = dag.AddEdge("node1", "node3")

	successors := dag.GetSuccessors("node1")
	assert.Len(t, successors, 2)
	assert.Contains(t, successors, "node2")
	assert.Contains(t, successors, "node3")
}

func TestDAG_GetPredecessors(t *testing.T) {
	dag := NewDAG("test", "Test")
	_ = dag.AddEdge("node1", "node3")
	_ = dag.AddEdge("node2", "node3")

	predecessors := dag.GetPredecessors("node3")
	assert.Len(t, predecessors, 2)
	assert.Contains(t, predecessors, "node1")
	assert.Contains(t, predecessors, "node2")
}

func TestDAG_Clone(t *testing.T) {
	dag := NewDAG("test", "Test DAG")
	dag.Description = "Test description"
	_ = dag.AddNode(NewOperationNode("node1", "Node 1", "template1"))
	_ = dag.AddNode(NewOperationNode("node2", "Node 2", "template2"))
	_ = dag.AddEdge("node1", "node2")

	clone, err := dag.Clone()
	require.NoError(t, err)

	// Check deep copy
	assert.Equal(t, dag.ID, clone.ID)
	assert.Equal(t, dag.Name, clone.Name)
	assert.Equal(t, dag.NodeCount(), clone.NodeCount())
	assert.Equal(t, dag.EdgeCount(), clone.EdgeCount())

	// Modify clone and verify original unchanged
	clone.Name = "Modified"
	assert.NotEqual(t, dag.Name, clone.Name)
}

func TestDAG_JSON(t *testing.T) {
	dag := NewDAG("test", "Test DAG")
	dag.EntryNode = "node1"
	_ = dag.AddNode(NewOperationNode("node1", "Node 1", "template1"))
	_ = dag.AddNode(NewOperationNode("node2", "Node 2", "template2"))
	_ = dag.AddEdge("node1", "node2")

	// Serialize
	data, err := dag.ToJSON()
	require.NoError(t, err)
	assert.Contains(t, string(data), "test")

	// Deserialize
	parsed, err := FromJSON(data)
	require.NoError(t, err)
	assert.Equal(t, dag.ID, parsed.ID)
	assert.Equal(t, dag.Name, parsed.Name)
	assert.Equal(t, dag.NodeCount(), parsed.NodeCount())
	assert.Equal(t, dag.EdgeCount(), parsed.EdgeCount())
}

func TestFromJSON_InvalidJSON(t *testing.T) {
	_, err := FromJSON([]byte("invalid json"))
	assert.Error(t, err)
}

func TestFromJSON_EmptyNodes(t *testing.T) {
	data := `{"id": "test", "name": "Test"}`
	dag, err := FromJSON([]byte(data))
	require.NoError(t, err)
	assert.NotNil(t, dag.Nodes)
	assert.NotNil(t, dag.Config)
}

func TestRetryPolicy_GetDelayForAttempt(t *testing.T) {
	rp := &RetryPolicy{
		MaxRetries: 3,
		DelayMs:    1000,
		Backoff:    2.0,
		MaxDelayMs: 10000,
	}

	tests := []struct {
		attempt int
		want    time.Duration
	}{
		{0, 0},
		{1, 1000 * time.Millisecond},
		{2, 2000 * time.Millisecond},
		{3, 4000 * time.Millisecond},
		{4, 8000 * time.Millisecond},
		{5, 10000 * time.Millisecond}, // Capped at max
	}

	for _, tt := range tests {
		t.Run("attempt_"+string(rune('0'+tt.attempt)), func(t *testing.T) {
			got := rp.GetDelayForAttempt(tt.attempt)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestRetryPolicy_NilPolicy(t *testing.T) {
	var rp *RetryPolicy
	delay := rp.GetDelayForAttempt(1)
	assert.Equal(t, time.Duration(0), delay)
}

func TestNodeConfig_GetTimeoutDuration(t *testing.T) {
	tests := []struct {
		name   string
		config *NodeConfig
		want   time.Duration
	}{
		{"nil config", nil, 300 * time.Second},
		{"zero timeout", &NodeConfig{TimeoutSeconds: 0}, 300 * time.Second},
		{"negative timeout", &NodeConfig{TimeoutSeconds: -1}, 300 * time.Second},
		{"custom timeout", &NodeConfig{TimeoutSeconds: 60}, 60 * time.Second},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.config.GetTimeoutDuration()
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestNewOperationNode(t *testing.T) {
	node := NewOperationNode("op1", "Operation 1", "template-123")

	assert.Equal(t, "op1", node.ID)
	assert.Equal(t, "Operation 1", node.Name)
	assert.Equal(t, NodeTypeOperation, node.Type)
	assert.Equal(t, "template-123", node.TemplateID)
	assert.NotNil(t, node.Config)
}

func TestNewConditionNode(t *testing.T) {
	node := NewConditionNode("cond1", "Condition 1", "{{ result.success }}")

	assert.Equal(t, "cond1", node.ID)
	assert.Equal(t, NodeTypeCondition, node.Type)
	assert.Equal(t, "{{ result.success }}", node.Config.Expression)
	assert.NotNil(t, node.ConditionConfig)
	assert.Equal(t, "{{ result.success }}", node.ConditionConfig.Expression)
}

func TestNewParallelNode(t *testing.T) {
	branches := []string{"branch1", "branch2"}
	node := NewParallelNode("par1", "Parallel 1", branches)

	assert.Equal(t, "par1", node.ID)
	assert.Equal(t, NodeTypeParallel, node.Type)
	assert.NotNil(t, node.ParallelConfig)
	assert.Equal(t, branches, node.ParallelConfig.BranchNodes)
	assert.True(t, node.ParallelConfig.WaitAll)
}

func TestNewLoopNode(t *testing.T) {
	node := NewLoopNode("loop1", "Loop 1", LoopModeCount, "body-node")

	assert.Equal(t, "loop1", node.ID)
	assert.Equal(t, NodeTypeLoop, node.Type)
	assert.NotNil(t, node.LoopConfig)
	assert.Equal(t, LoopModeCount, node.LoopConfig.Mode)
	assert.Equal(t, "body-node", node.LoopConfig.BodyNode)
}

func TestNewSubworkflowNode(t *testing.T) {
	node := NewSubworkflowNode("sub1", "Subworkflow 1", "workflow-123")

	assert.Equal(t, "sub1", node.ID)
	assert.Equal(t, NodeTypeSubworkflow, node.Type)
	assert.NotNil(t, node.SubworkflowConfig)
	assert.Equal(t, "workflow-123", node.SubworkflowConfig.WorkflowID)
	assert.Equal(t, 10, node.SubworkflowConfig.MaxDepth)
}

func TestParallelNodeConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  *ParallelNodeConfig
		wantErr bool
	}{
		{
			name:    "valid config",
			config:  &ParallelNodeConfig{BranchNodes: []string{"a", "b"}},
			wantErr: false,
		},
		{
			name:    "empty branches",
			config:  &ParallelNodeConfig{BranchNodes: []string{}},
			wantErr: true,
		},
		{
			name:    "nil branches",
			config:  &ParallelNodeConfig{},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestLoopNodeConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  *LoopNodeConfig
		wantErr bool
	}{
		{
			name:    "valid count loop",
			config:  &LoopNodeConfig{Mode: LoopModeCount, Count: 5, BodyNode: "body"},
			wantErr: false,
		},
		{
			name:    "count loop without count",
			config:  &LoopNodeConfig{Mode: LoopModeCount, Count: 0, BodyNode: "body"},
			wantErr: true,
		},
		{
			name:    "valid while loop",
			config:  &LoopNodeConfig{Mode: LoopModeWhile, Condition: "{{ x > 0 }}", BodyNode: "body"},
			wantErr: false,
		},
		{
			name:    "while loop without condition",
			config:  &LoopNodeConfig{Mode: LoopModeWhile, BodyNode: "body"},
			wantErr: true,
		},
		{
			name:    "valid foreach loop",
			config:  &LoopNodeConfig{Mode: LoopModeForeach, Items: "items", BodyNode: "body"},
			wantErr: false,
		},
		{
			name:    "foreach loop without items",
			config:  &LoopNodeConfig{Mode: LoopModeForeach, BodyNode: "body"},
			wantErr: true,
		},
		{
			name:    "missing body node",
			config:  &LoopNodeConfig{Mode: LoopModeCount, Count: 5},
			wantErr: true,
		},
		{
			name:    "invalid mode",
			config:  &LoopNodeConfig{Mode: LoopMode("invalid"), BodyNode: "body"},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestSubworkflowNodeConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  *SubworkflowNodeConfig
		wantErr bool
	}{
		{
			name:    "valid config",
			config:  &SubworkflowNodeConfig{WorkflowID: "workflow-123"},
			wantErr: false,
		},
		{
			name:    "missing workflow ID",
			config:  &SubworkflowNodeConfig{},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestConditionNodeConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  *ConditionNodeConfig
		wantErr bool
	}{
		{
			name:    "valid config",
			config:  &ConditionNodeConfig{Expression: "{{ x > 0 }}", TrueNode: "yes"},
			wantErr: false,
		},
		{
			name:    "missing expression",
			config:  &ConditionNodeConfig{TrueNode: "yes"},
			wantErr: true,
		},
		{
			name:    "missing both branches",
			config:  &ConditionNodeConfig{Expression: "{{ x > 0 }}"},
			wantErr: true,
		},
		{
			name:    "only false node",
			config:  &ConditionNodeConfig{Expression: "{{ x > 0 }}", FalseNode: "no"},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestDAG_ComplexWorkflow(t *testing.T) {
	// Build a complex workflow:
	// start -> condition -> (true: parallel, false: end)
	// parallel -> [branch1, branch2] -> merge -> loop -> end

	dag := NewDAG("complex", "Complex Workflow")
	dag.EntryNode = "start"

	// Add nodes
	_ = dag.AddNode(NewOperationNode("start", "Start", "init-template"))
	_ = dag.AddNode(NewConditionNode("condition", "Check Status", "{{ status == 'ready' }}"))
	_ = dag.AddNode(NewParallelNode("parallel", "Parallel Tasks", []string{"branch1", "branch2"}))
	_ = dag.AddNode(NewOperationNode("branch1", "Branch 1", "task-template"))
	_ = dag.AddNode(NewOperationNode("branch2", "Branch 2", "task-template"))
	_ = dag.AddNode(NewOperationNode("merge", "Merge Results", "merge-template"))

	loopNode := NewLoopNode("loop", "Process Items", LoopModeForeach, "loop-body")
	loopNode.LoopConfig.Items = "items"
	_ = dag.AddNode(loopNode)

	_ = dag.AddNode(NewOperationNode("loop-body", "Loop Body", "process-template"))
	_ = dag.AddNode(NewOperationNode("end", "End", "cleanup-template"))

	// Add edges
	_ = dag.AddEdge("start", "condition")
	_ = dag.AddEdgeWithCondition("condition", "parallel", "{{ status == 'ready' }}")
	_ = dag.AddEdgeWithCondition("condition", "end", "{{ status != 'ready' }}")
	_ = dag.AddEdge("parallel", "branch1")
	_ = dag.AddEdge("parallel", "branch2")
	_ = dag.AddEdge("branch1", "merge")
	_ = dag.AddEdge("branch2", "merge")
	_ = dag.AddEdge("merge", "loop")
	_ = dag.AddEdge("loop", "loop-body")
	_ = dag.AddEdge("loop-body", "end")

	// Verify structure
	assert.Equal(t, 9, dag.NodeCount())
	assert.Equal(t, 10, dag.EdgeCount())

	// Verify successors
	assert.Len(t, dag.GetSuccessors("condition"), 2)
	assert.Len(t, dag.GetSuccessors("parallel"), 2)
	assert.Len(t, dag.GetPredecessors("merge"), 2)

	// Serialize and deserialize
	data, err := dag.ToJSON()
	require.NoError(t, err)

	restored, err := FromJSON(data)
	require.NoError(t, err)
	assert.Equal(t, dag.NodeCount(), restored.NodeCount())
}

func TestNode_JSONSerialization(t *testing.T) {
	node := &Node{
		ID:         "test-node",
		Type:       NodeTypeParallel,
		Name:       "Test Parallel",
		Config:     DefaultNodeConfig(),
		ParallelConfig: &ParallelNodeConfig{
			BranchNodes:    []string{"a", "b", "c"},
			WaitAll:        true,
			FailFast:       false,
			TimeoutSeconds: 300,
		},
	}

	data, err := json.Marshal(node)
	require.NoError(t, err)

	var restored Node
	err = json.Unmarshal(data, &restored)
	require.NoError(t, err)

	assert.Equal(t, node.ID, restored.ID)
	assert.Equal(t, node.Type, restored.Type)
	assert.NotNil(t, restored.ParallelConfig)
	assert.Equal(t, node.ParallelConfig.BranchNodes, restored.ParallelConfig.BranchNodes)
}

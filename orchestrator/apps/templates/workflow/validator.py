"""
DAG Validation module for Workflow Engine.

Implements comprehensive DAG validation with:
- Cycle detection (Kahn's algorithm)
- Connectivity analysis (BFS)
- Topological validation (start/end nodes)
- Edge/node reference validation
- Custom exception hierarchy for debugging
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from apps.templates.workflow.models import DAGStructure, WorkflowNode


# ============================================================================
# Validation Severity Levels
# ============================================================================


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Critical issue - DAG cannot execute
    WARNING = "warning"  # Non-critical issue - DAG can execute but may not be optimal
    INFO = "info"  # Informational - suggestions for improvement


# ============================================================================
# Validation Issue Representation
# ============================================================================


@dataclass
class ValidationIssue:
    """
    Represents a single validation issue found in the DAG.

    Attributes:
        severity: Issue severity level (ERROR, WARNING, INFO)
        message: Human-readable description of the issue
        node_ids: List of node IDs related to this issue (optional)
        details: Additional metadata about the issue (optional)
    """

    severity: ValidationSeverity
    message: str
    node_ids: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Format issue as human-readable string."""
        nodes_str = f" (nodes: {', '.join(self.node_ids)})" if self.node_ids else ""
        return f"[{self.severity.value.upper()}] {self.message}{nodes_str}"


# ============================================================================
# Validation Result Container
# ============================================================================


@dataclass
class ValidationResult:
    """
    Container for validation results with issues grouped by severity.

    Attributes:
        is_valid: True if no errors found (warnings/info allowed)
        errors: List of critical issues preventing DAG execution
        warnings: List of non-critical issues
        info: List of informational messages
        topological_order: Topologically sorted node IDs (None if cycles exist)
        metadata: Additional validation metadata
    """

    is_valid: bool = True
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)
    topological_order: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_error(
        self, message: str, node_ids: Optional[List[str]] = None, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an error issue to the validation result.

        Args:
            message: Error description
            node_ids: Related node IDs (optional)
            details: Additional metadata (optional)
        """
        self.is_valid = False
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message=message,
            node_ids=node_ids or [],
            details=details or {},
        )
        self.errors.append(issue)

    def add_warning(
        self, message: str, node_ids: Optional[List[str]] = None, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a warning issue to the validation result.

        Args:
            message: Warning description
            node_ids: Related node IDs (optional)
            details: Additional metadata (optional)
        """
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message=message,
            node_ids=node_ids or [],
            details=details or {},
        )
        self.warnings.append(issue)

    def add_info(
        self, message: str, node_ids: Optional[List[str]] = None, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an informational message to the validation result.

        Args:
            message: Info description
            node_ids: Related node IDs (optional)
            details: Additional metadata (optional)
        """
        issue = ValidationIssue(
            severity=ValidationSeverity.INFO,
            message=message,
            node_ids=node_ids or [],
            details=details or {},
        )
        self.info.append(issue)


# ============================================================================
# Custom Exceptions
# ============================================================================


class DAGValidationError(Exception):
    """Base exception for DAG validation errors."""

    def __init__(self, message: str, node_ids: Optional[List[str]] = None):
        """
        Initialize DAG validation error.

        Args:
            message: Error description
            node_ids: Related node IDs (for debugging)
        """
        self.message = message
        self.node_ids = node_ids or []
        super().__init__(self.message)


class CycleDetectedError(DAGValidationError):
    """Exception raised when a cycle is detected in the DAG."""

    def __init__(self, message: str = "Cycle detected in DAG", node_ids: Optional[List[str]] = None):
        """
        Initialize cycle detection error.

        Args:
            message: Error description
            node_ids: Node IDs involved in the cycle (if known)
        """
        super().__init__(message, node_ids)


class UnreachableNodeError(DAGValidationError):
    """Exception raised when a node is unreachable from start nodes."""

    def __init__(
        self, message: str = "Unreachable nodes detected", node_ids: Optional[List[str]] = None
    ):
        """
        Initialize unreachable node error.

        Args:
            message: Error description
            node_ids: IDs of unreachable nodes
        """
        super().__init__(message, node_ids)


class InvalidNodeTypeError(DAGValidationError):
    """Exception raised when a node has an invalid type."""

    def __init__(
        self, message: str = "Invalid node type detected", node_ids: Optional[List[str]] = None
    ):
        """
        Initialize invalid node type error.

        Args:
            message: Error description
            node_ids: Node IDs with invalid types
        """
        super().__init__(message, node_ids)


class InvalidEdgeError(DAGValidationError):
    """Exception raised when an edge references non-existent nodes."""

    def __init__(
        self, message: str = "Invalid edge detected", node_ids: Optional[List[str]] = None
    ):
        """
        Initialize invalid edge error.

        Args:
            message: Error description
            node_ids: Node IDs referenced in invalid edge
        """
        super().__init__(message, node_ids)


# ============================================================================
# DAG Validator
# ============================================================================


class DAGValidator:
    """
    Comprehensive DAG validator for workflow structures.

    Performs validation in the following order:
    1. Duplicate node ID detection
    2. Edge reference validation
    3. Self-loop detection
    4. Node type validation
    5. Cycle detection (Kahn's algorithm - O(V+E))
    6. Connectivity analysis (BFS - O(V+E))
    7. Component counting (weak connectivity)
    8. Topology validation (start/end nodes)

    Complexity:
        - Time: O(V + E) where V = nodes, E = edges
        - Space: O(V + E) for adjacency lists
    """

    ALLOWED_NODE_TYPES = {"operation", "condition", "parallel", "loop", "subworkflow"}

    def __init__(self, dag: DAGStructure):
        """
        Initialize validator with DAG structure.

        Args:
            dag: DAG structure to validate
        """
        self.dag = dag
        self.node_map: Dict[str, WorkflowNode] = {}  # node_id -> WorkflowNode
        self.adj_list: Dict[str, List[str]] = defaultdict(list)  # from -> [to, ...]
        self.reverse_adj_list: Dict[str, List[str]] = defaultdict(list)  # to -> [from, ...]
        self.in_degree: Dict[str, int] = {}  # node_id -> in-degree count
        self.out_degree: Dict[str, int] = {}  # node_id -> out-degree count

        self._build_graph()

    def _build_graph(self) -> None:
        """
        Build internal graph representation from DAG structure.

        Populates:
            - node_map: Quick node lookup
            - adj_list: Forward adjacency list
            - reverse_adj_list: Backward adjacency list
            - in_degree: In-degree count for each node
            - out_degree: Out-degree count for each node

        Complexity: O(V + E)
        """
        # Build node map
        for node in self.dag.nodes:
            self.node_map[node.id] = node
            self.in_degree[node.id] = 0
            self.out_degree[node.id] = 0

        # Build adjacency lists
        for edge in self.dag.edges:
            # Validate edge nodes exist (defensive - will be caught in _validate_edge_references)
            if edge.from_node not in self.node_map or edge.to_node not in self.node_map:
                continue  # Skip invalid edges, will be reported later

            self.adj_list[edge.from_node].append(edge.to_node)
            self.reverse_adj_list[edge.to_node].append(edge.from_node)
            self.in_degree[edge.to_node] += 1
            self.out_degree[edge.from_node] += 1

    def validate(self) -> ValidationResult:
        """
        Perform comprehensive DAG validation.

        Validation steps:
        1. Check for duplicate node IDs
        2. Validate edge references
        3. Check for self-loops
        4. Validate node types
        5. Detect cycles (Kahn's algorithm)
        6. Check connectivity (BFS)
        7. Count components (weak connectivity)
        8. Validate topology (start/end nodes)

        Returns:
            ValidationResult: Validation result with errors/warnings/info

        Complexity: O(V + E)
        """
        result = ValidationResult()

        # Early check for empty DAG
        if not self.dag.nodes:
            result.add_error("DAG contains no nodes")
            return result

        # Step 1: Check duplicate node IDs
        self._check_duplicate_nodes(result)

        # Step 2: Validate edge references
        self._validate_edge_references(result)

        # Step 3: Check self-loops
        self._check_self_loops(result)

        # Step 4: Validate node types
        self._validate_node_types(result)

        # Step 5: Topological sort (cycle detection)
        if result.is_valid:
            topological_order = self._topological_sort(result)
            if topological_order:
                result.topological_order = topological_order

        # Step 6: Check connectivity
        if result.is_valid:
            self._check_connectivity(result)

        # Step 7: Count components
        if result.is_valid:
            component_count = self._count_components()
            result.metadata["component_count"] = component_count

            if component_count > 1:
                result.add_warning(
                    f"DAG contains {component_count} disconnected components. "
                    "This may indicate isolated subgraphs.",
                    details={"component_count": component_count},
                )

        # Step 8: Validate topology
        if result.is_valid:
            self._validate_topology(result)

        # Add summary metadata
        result.metadata["total_nodes"] = len(self.dag.nodes)
        result.metadata["total_edges"] = len(self.dag.edges)
        result.metadata["error_count"] = len(result.errors)
        result.metadata["warning_count"] = len(result.warnings)

        return result

    def _check_duplicate_nodes(self, result: ValidationResult) -> None:
        """
        Check for duplicate node IDs.

        Args:
            result: ValidationResult to append issues to

        Complexity: O(V)
        """
        seen_ids: Set[str] = set()
        duplicates: List[str] = []

        for node in self.dag.nodes:
            if node.id in seen_ids:
                duplicates.append(node.id)
            else:
                seen_ids.add(node.id)

        if duplicates:
            result.add_error(
                f"Duplicate node IDs found: {', '.join(duplicates)}",
                node_ids=duplicates,
                details={"duplicate_ids": duplicates},
            )

    def _validate_edge_references(self, result: ValidationResult) -> None:
        """
        Validate all edges reference existing nodes.

        Args:
            result: ValidationResult to append issues to

        Complexity: O(E)
        """
        node_ids = set(self.node_map.keys())

        for edge in self.dag.edges:
            invalid_refs: List[str] = []

            if edge.from_node not in node_ids:
                invalid_refs.append(edge.from_node)

            if edge.to_node not in node_ids:
                invalid_refs.append(edge.to_node)

            if invalid_refs:
                result.add_error(
                    f"Edge references non-existent node(s): {edge.from_node} -> {edge.to_node}",
                    node_ids=invalid_refs,
                    details={"edge": {"from": edge.from_node, "to": edge.to_node}},
                )

    def _check_self_loops(self, result: ValidationResult) -> None:
        """
        Check for self-referencing edges (self-loops).

        Args:
            result: ValidationResult to append issues to

        Complexity: O(E)
        """
        self_loops: List[str] = []

        for edge in self.dag.edges:
            if edge.from_node == edge.to_node:
                self_loops.append(edge.from_node)

        if self_loops:
            result.add_error(
                f"Self-loops detected in nodes: {', '.join(self_loops)}",
                node_ids=self_loops,
                details={"self_loop_nodes": self_loops},
            )

    def _validate_node_types(self, result: ValidationResult) -> None:
        """
        Validate all node types are supported.

        Args:
            result: ValidationResult to append issues to

        Complexity: O(V)
        """
        invalid_nodes: List[str] = []

        for node in self.dag.nodes:
            if node.type not in self.ALLOWED_NODE_TYPES:
                invalid_nodes.append(node.id)

        if invalid_nodes:
            result.add_error(
                f"Invalid node types detected. Allowed: {self.ALLOWED_NODE_TYPES}",
                node_ids=invalid_nodes,
                details={
                    "invalid_nodes": invalid_nodes,
                    "allowed_types": list(self.ALLOWED_NODE_TYPES),
                },
            )

    def _topological_sort(self, result: ValidationResult) -> Optional[List[str]]:
        """
        Perform topological sort using Kahn's algorithm.

        Detects cycles in the DAG. If cycles exist, returns None and adds error.

        Args:
            result: ValidationResult to append issues to

        Returns:
            List[str]: Topologically sorted node IDs, or None if cycle detected

        Complexity: O(V + E)
        """
        # Create working copy of in-degree
        in_degree_copy = self.in_degree.copy()

        # Initialize queue with nodes having no incoming edges
        queue = deque([node_id for node_id, degree in in_degree_copy.items() if degree == 0])

        topological_order: List[str] = []

        while queue:
            node_id = queue.popleft()
            topological_order.append(node_id)

            # Reduce in-degree for neighbors
            for neighbor in self.adj_list[node_id]:
                in_degree_copy[neighbor] -= 1
                if in_degree_copy[neighbor] == 0:
                    queue.append(neighbor)

        # If not all nodes processed -> cycle exists
        if len(topological_order) != len(self.dag.nodes):
            unprocessed = [
                node_id for node_id in self.node_map.keys() if node_id not in topological_order
            ]

            result.add_error(
                f"Cycle detected in DAG. {len(unprocessed)} node(s) could not be processed.",
                node_ids=unprocessed,
                details={
                    "processed_count": len(topological_order),
                    "total_count": len(self.dag.nodes),
                    "unprocessed_nodes": unprocessed,
                },
            )
            return None

        return topological_order

    def _check_connectivity(self, result: ValidationResult) -> None:
        """
        Check if all nodes are reachable from start nodes using BFS.

        Args:
            result: ValidationResult to append issues to

        Complexity: O(V + E)
        """
        # Find start nodes (no incoming edges)
        start_nodes = [node_id for node_id, degree in self.in_degree.items() if degree == 0]

        if not start_nodes:
            result.add_error("No start nodes found (all nodes have incoming edges)")
            return

        # BFS from start nodes
        visited: Set[str] = set()
        queue = deque(start_nodes)

        while queue:
            node_id = queue.popleft()

            if node_id in visited:
                continue

            visited.add(node_id)

            # Add neighbors to queue
            for neighbor in self.adj_list[node_id]:
                if neighbor not in visited:
                    queue.append(neighbor)

        # Check for unreachable nodes
        all_nodes = set(self.node_map.keys())
        unreachable = all_nodes - visited

        if unreachable:
            unreachable_list = list(unreachable)
            result.add_error(
                f"{len(unreachable_list)} node(s) are unreachable from start nodes. "
                "These nodes will never execute.",
                node_ids=unreachable_list,
                details={"unreachable_nodes": unreachable_list, "start_nodes": start_nodes},
            )

    def _count_components(self) -> int:
        """
        Count weakly connected components in the DAG.

        Uses iterative DFS to find all connected components (treating edges as undirected).
        Iterative approach prevents stack overflow on large graphs.

        Returns:
            int: Number of weakly connected components

        Complexity: O(V + E)
        """
        visited: Set[str] = set()
        component_count = 0

        for start_node in self.node_map.keys():
            if start_node in visited:
                continue

            # Iterative DFS to avoid stack overflow
            stack = [start_node]
            while stack:
                node_id = stack.pop()

                if node_id in visited:
                    continue

                visited.add(node_id)

                # Visit forward neighbors
                for neighbor in self.adj_list[node_id]:
                    if neighbor not in visited:
                        stack.append(neighbor)

                # Visit backward neighbors (treat as undirected)
                for neighbor in self.reverse_adj_list[node_id]:
                    if neighbor not in visited:
                        stack.append(neighbor)

            component_count += 1

        return component_count

    def _validate_topology(self, result: ValidationResult) -> None:
        """
        Validate DAG has proper topology (start and end nodes exist).

        Args:
            result: ValidationResult to append issues to

        Complexity: O(V)
        """
        # Check for isolated nodes (0 in-degree, 0 out-degree)
        # Only check if we have multiple nodes (single node DAG is valid)
        if len(self.dag.nodes) > 1:
            isolated_nodes = [
                node_id for node_id in self.node_map.keys()
                if self.in_degree[node_id] == 0 and self.out_degree[node_id] == 0
            ]

            if isolated_nodes:
                result.add_error(
                    f"Isolated nodes detected (no incoming or outgoing edges): {', '.join(isolated_nodes)}",
                    node_ids=isolated_nodes,
                    details={"isolated_nodes": isolated_nodes},
                )

        start_nodes = [node_id for node_id, degree in self.in_degree.items() if degree == 0]
        end_nodes = [node_id for node_id, degree in self.out_degree.items() if degree == 0]

        # Check start nodes
        if not start_nodes:
            result.add_error("No start nodes found (all nodes have incoming edges)")
        elif len(start_nodes) > 1:
            result.add_info(
                f"Multiple start nodes detected: {', '.join(start_nodes)}",
                node_ids=start_nodes,
                details={"start_nodes": start_nodes},
            )

        # Check end nodes
        if not end_nodes:
            result.add_error("No end nodes found (all nodes have outgoing edges)")
        elif len(end_nodes) > 1:
            result.add_info(
                f"Multiple end nodes detected: {', '.join(end_nodes)}",
                node_ids=end_nodes,
                details={"end_nodes": end_nodes},
            )

        # Store in metadata
        result.metadata["start_nodes"] = start_nodes
        result.metadata["end_nodes"] = end_nodes

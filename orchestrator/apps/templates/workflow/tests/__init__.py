"""
Tests for Workflow Engine.

Test coverage goal: >80%
Total tests target: ~170 tests

Structure:
    - test_models.py: WorkflowTemplate, WorkflowExecution, WorkflowStepResult
    - test_validator.py: DAGValidator, cycle detection, topological sort
    - test_handlers.py: All 5 NodeHandlers
    - test_executor.py: DAGExecutor
    - test_engine.py: WorkflowEngine
    - test_integration.py: End-to-end workflow execution
"""

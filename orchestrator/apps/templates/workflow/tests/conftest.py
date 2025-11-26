# orchestrator/apps/templates/workflow/tests/conftest.py
"""
Pytest fixtures for workflow tests.
"""

import pytest
from django.contrib.auth.models import User
from apps.templates.workflow.models import WorkflowTemplate, WorkflowExecution


@pytest.fixture
def admin_user(db):
    """Create admin user for tests."""
    # Cleanup: delete existing user if present
    User.objects.filter(username='testadmin').delete()
    
    return User.objects.create_user(
        username='testadmin',
        email='test@test.com',
        password='testpass123',
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def simple_workflow_template(db, admin_user):
    """Create simple sequential workflow template."""
    return WorkflowTemplate.objects.create(
        name="Simple Test Workflow",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "step1",
                    "name": "Step 1",
                    "type": "operation",
                    "template_id": "test_op1",
                    "config": {"timeout": 30, "retries": 3}
                },
                {
                    "id": "step2",
                    "name": "Step 2",
                    "type": "operation",
                    "template_id": "test_op2",
                    "config": {"timeout": 60, "retries": 2}
                }
            ],
            "edges": [
                {"from": "step1", "to": "step2"}
            ]
        },
        config={
            "timeout_seconds": 600,
            "max_retries": 3
        },
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )


@pytest.fixture
def complex_workflow_template(db, admin_user):
    """Create complex workflow with parallel and conditions."""
    return WorkflowTemplate.objects.create(
        name="Complex Test Workflow",
        workflow_type="complex",
        dag_structure={
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "operation",
                    "template_id": "start_op",
                    "config": {"timeout": 30}
                },
                {
                    "id": "check",
                    "name": "Check Condition",
                    "type": "condition",
                    "config": {"timeout": 10}
                },
                {
                    "id": "parallel",
                    "name": "Parallel Processing",
                    "type": "parallel",
                    "config": {"timeout": 120, "parallel_limit": 5}
                },
                {
                    "id": "end",
                    "name": "End",
                    "type": "operation",
                    "template_id": "end_op",
                    "config": {"timeout": 30}
                }
            ],
            "edges": [
                {"from": "start", "to": "check"},
                {"from": "check", "to": "parallel", "condition": "true"},
                {"from": "parallel", "to": "end"}
            ]
        },
        created_by=admin_user,
        is_valid=True,
        is_active=True
    )


@pytest.fixture
def workflow_execution(db, simple_workflow_template):
    """Create workflow execution instance."""
    return simple_workflow_template.create_execution({"test_input": "value"})

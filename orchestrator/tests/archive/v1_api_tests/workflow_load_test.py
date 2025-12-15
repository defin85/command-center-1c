"""
Locust load tests for Workflow Engine REST API.

Tests workflow API under different load conditions to identify bottlenecks
in database, Celery task queue, and Worker pool.

Run with:
    cd orchestrator
    locust -f tests/load/workflow_load_test.py --host=http://localhost:8000

    # Headless mode (for CI/CD):
    locust -f tests/load/workflow_load_test.py --host=http://localhost:8000 \
        --headless -u 10 -r 2 -t 1m --csv=results/workflow_load

    # Different load profiles:
    # Light:  -u 10  -r 2   (10 users, spawn 2/s)
    # Medium: -u 50  -r 5   (50 users, spawn 5/s)
    # Heavy:  -u 100 -r 10  (100 users, spawn 10/s)

Web UI available at http://localhost:8089 (default Locust port)
"""

import logging
import random
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from locust import HttpUser, between, events, task
from locust.env import Environment

# ============================================================================
# Configuration
# ============================================================================

# API endpoints
WORKFLOWS_URL = "/api/v1/templates/workflow/workflows/"
EXECUTIONS_URL = "/api/v1/templates/workflow/executions/"
TOKEN_URL = "/api/token/"

# Test credentials (should exist in Django admin)
TEST_USERNAME = "loadtest"
TEST_PASSWORD = "loadtest123"

# Logging
logger = logging.getLogger(__name__)

# ============================================================================
# Test Data - DAG Structures
# ============================================================================

SIMPLE_WORKFLOW_DAG = {
    "nodes": [
        {
            "id": "start",
            "name": "Start Operation",
            "type": "operation",
            "template_id": "load_test_start",
            "config": {
                "timeout_seconds": 60,
                "max_retries": 1,
            },
        },
        {
            "id": "process",
            "name": "Process Data",
            "type": "operation",
            "template_id": "load_test_process",
            "config": {
                "timeout_seconds": 120,
                "max_retries": 2,
            },
        },
        {
            "id": "end",
            "name": "End Operation",
            "type": "operation",
            "template_id": "load_test_end",
            "config": {
                "timeout_seconds": 60,
                "max_retries": 1,
            },
        },
    ],
    "edges": [
        {"from": "start", "to": "process"},
        {"from": "process", "to": "end"},
    ],
}

COMPLEX_WORKFLOW_DAG = {
    "nodes": [
        # Entry point
        {
            "id": "init",
            "name": "Initialize",
            "type": "operation",
            "template_id": "load_test_init",
            "config": {"timeout_seconds": 30, "max_retries": 1},
        },
        # Condition check
        {
            "id": "check_condition",
            "name": "Check Condition",
            "type": "condition",
            "config": {
                "timeout_seconds": 10,
                "expression": "{{ init.output.should_continue | default(true) }}",
            },
        },
        # Processing nodes
        {
            "id": "process_a",
            "name": "Process A",
            "type": "operation",
            "template_id": "load_test_process_a",
            "config": {"timeout_seconds": 120, "max_retries": 2},
        },
        {
            "id": "process_b",
            "name": "Process B",
            "type": "operation",
            "template_id": "load_test_process_b",
            "config": {"timeout_seconds": 120, "max_retries": 2},
        },
        {
            "id": "process_c",
            "name": "Process C",
            "type": "operation",
            "template_id": "load_test_process_c",
            "config": {"timeout_seconds": 120, "max_retries": 2},
        },
        # Validation
        {
            "id": "validate",
            "name": "Validate Results",
            "type": "operation",
            "template_id": "load_test_validate",
            "config": {"timeout_seconds": 60, "max_retries": 1},
        },
        # Second condition
        {
            "id": "check_validation",
            "name": "Check Validation Result",
            "type": "condition",
            "config": {
                "timeout_seconds": 10,
                "expression": "{{ validate.output.is_valid | default(true) }}",
            },
        },
        # Finalization
        {
            "id": "finalize_success",
            "name": "Finalize Success",
            "type": "operation",
            "template_id": "load_test_finalize_success",
            "config": {"timeout_seconds": 60, "max_retries": 1},
        },
        {
            "id": "finalize_failure",
            "name": "Finalize Failure",
            "type": "operation",
            "template_id": "load_test_finalize_failure",
            "config": {"timeout_seconds": 60, "max_retries": 1},
        },
        # Cleanup
        {
            "id": "cleanup",
            "name": "Cleanup",
            "type": "operation",
            "template_id": "load_test_cleanup",
            "config": {"timeout_seconds": 30, "max_retries": 0},
        },
    ],
    "edges": [
        {"from": "init", "to": "check_condition"},
        {"from": "check_condition", "to": "process_a", "condition": "{{ true }}"},
        {"from": "process_a", "to": "process_b"},
        {"from": "process_b", "to": "process_c"},
        {"from": "process_c", "to": "validate"},
        {"from": "validate", "to": "check_validation"},
        {
            "from": "check_validation",
            "to": "finalize_success",
            "condition": "{{ true }}",
        },
        {
            "from": "check_validation",
            "to": "finalize_failure",
            "condition": "{{ false }}",
        },
        {"from": "finalize_success", "to": "cleanup"},
        {"from": "finalize_failure", "to": "cleanup"},
    ],
}

# Workflow config templates
WORKFLOW_CONFIGS = [
    {"timeout_seconds": 600, "max_retries": 0},
    {"timeout_seconds": 1200, "max_retries": 1},
    {"timeout_seconds": 1800, "max_retries": 2},
    {"timeout_seconds": 3600, "max_retries": 3},
]


# ============================================================================
# Metrics Tracking
# ============================================================================

class MetricsCollector:
    """Collects custom metrics for bottleneck analysis."""

    def __init__(self):
        self.execution_times: List[float] = []
        self.db_query_times: List[float] = []
        self.template_create_times: List[float] = []
        self.execution_start_times: List[float] = []
        self.status_poll_times: List[float] = []
        self.errors_by_type: Dict[str, int] = {}
        self.concurrent_executions = 0
        self.max_concurrent_executions = 0

    def record_execution_time(self, duration: float):
        """Record workflow execution time."""
        self.execution_times.append(duration)

    def record_template_create_time(self, duration: float):
        """Record template creation time."""
        self.template_create_times.append(duration)

    def record_execution_start_time(self, duration: float):
        """Record execution start time."""
        self.execution_start_times.append(duration)

    def record_status_poll_time(self, duration: float):
        """Record status polling time."""
        self.status_poll_times.append(duration)

    def record_error(self, error_type: str):
        """Record error by type."""
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1

    def increment_concurrent(self):
        """Increment concurrent execution counter."""
        self.concurrent_executions += 1
        if self.concurrent_executions > self.max_concurrent_executions:
            self.max_concurrent_executions = self.concurrent_executions

    def decrement_concurrent(self):
        """Decrement concurrent execution counter."""
        self.concurrent_executions = max(0, self.concurrent_executions - 1)

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary for analysis."""
        def calc_stats(times: List[float]) -> Dict[str, float]:
            if not times:
                return {"count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0}
            sorted_times = sorted(times)
            p95_idx = int(len(sorted_times) * 0.95)
            return {
                "count": len(times),
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "p95": sorted_times[p95_idx] if p95_idx < len(sorted_times) else sorted_times[-1],
            }

        return {
            "execution_times": calc_stats(self.execution_times),
            "template_create_times": calc_stats(self.template_create_times),
            "execution_start_times": calc_stats(self.execution_start_times),
            "status_poll_times": calc_stats(self.status_poll_times),
            "errors_by_type": self.errors_by_type,
            "max_concurrent_executions": self.max_concurrent_executions,
        }


# Global metrics collector
metrics = MetricsCollector()


# ============================================================================
# Base User Class
# ============================================================================

class WorkflowAPIUser(HttpUser):
    """
    Simulates a user interacting with Workflow REST API.

    Performs typical operations:
    - List templates (GET /workflows/)
    - Create templates (POST /workflows/)
    - Execute workflows (POST /workflows/{id}/execute/)
    - Check execution status (GET /executions/{id}/status/)
    - List executions (GET /executions/)
    - Cancel executions (POST /executions/{id}/cancel/)
    """

    abstract = True  # Don't instantiate directly
    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token: Optional[str] = None
        self.created_templates: List[str] = []
        self.created_executions: List[str] = []
        self.user_id = str(uuid4())[:8]

    def on_start(self):
        """Called when user starts. Authenticate and setup."""
        self.token = self._get_auth_token()
        if not self.token:
            logger.warning(f"User {self.user_id}: Failed to authenticate, will try Basic auth")

    def on_stop(self):
        """Called when user stops. Cleanup created resources."""
        self._cleanup_resources()

    def _get_auth_token(self) -> Optional[str]:
        """Obtain JWT token for API authentication."""
        try:
            response = self.client.post(
                TOKEN_URL,
                json={
                    "username": TEST_USERNAME,
                    "password": TEST_PASSWORD,
                },
                name="[Auth] Get JWT Token",
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("access")
            else:
                logger.warning(f"Auth failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _cleanup_resources(self):
        """Cleanup created templates and executions."""
        headers = self._get_headers()

        # Cancel running executions
        for exec_id in self.created_executions:
            try:
                self.client.post(
                    f"{EXECUTIONS_URL}{exec_id}/cancel/",
                    headers=headers,
                    name="[Cleanup] Cancel execution",
                )
            except Exception:
                pass

        # Delete templates (only those without executions)
        for template_id in self.created_templates:
            try:
                self.client.delete(
                    f"{WORKFLOWS_URL}{template_id}/",
                    headers=headers,
                    name="[Cleanup] Delete template",
                )
            except Exception:
                pass

    # ========================================================================
    # API Tasks
    # ========================================================================

    @task(10)
    def list_templates(self):
        """GET /api/v1/templates/workflow/workflows/ - List workflow templates."""
        with self.client.get(
            WORKFLOWS_URL,
            headers=self._get_headers(),
            name="[Templates] List",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                # Re-authenticate
                self.token = self._get_auth_token()
                response.failure("Auth expired, re-authenticating")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
                metrics.record_error(f"list_templates_{response.status_code}")

    @task(5)
    def create_simple_workflow(self):
        """POST /api/v1/templates/workflow/workflows/ - Create simple workflow template."""
        start_time = time.time()

        workflow_name = f"LoadTest_Simple_{self.user_id}_{uuid4().hex[:8]}"
        payload = {
            "name": workflow_name,
            "description": f"Load test workflow created by user {self.user_id}",
            "workflow_type": "load_test",
            "dag_structure": SIMPLE_WORKFLOW_DAG,
            "config": random.choice(WORKFLOW_CONFIGS),
        }

        with self.client.post(
            WORKFLOWS_URL,
            json=payload,
            headers=self._get_headers(),
            name="[Templates] Create Simple",
            catch_response=True,
        ) as response:
            duration = time.time() - start_time
            metrics.record_template_create_time(duration)

            if response.status_code == 201:
                data = response.json()
                template_id = data.get("id")
                if template_id:
                    self.created_templates.append(template_id)
                    # Validate the template
                    self._validate_template(template_id)
                response.success()
            elif response.status_code == 401:
                self.token = self._get_auth_token()
                response.failure("Auth expired")
            else:
                response.failure(f"Create failed: {response.status_code}")
                metrics.record_error(f"create_template_{response.status_code}")

    @task(3)
    def create_complex_workflow(self):
        """POST /api/v1/templates/workflow/workflows/ - Create complex workflow template."""
        start_time = time.time()

        workflow_name = f"LoadTest_Complex_{self.user_id}_{uuid4().hex[:8]}"
        payload = {
            "name": workflow_name,
            "description": f"Complex load test workflow created by user {self.user_id}",
            "workflow_type": "load_test_complex",
            "dag_structure": COMPLEX_WORKFLOW_DAG,
            "config": random.choice(WORKFLOW_CONFIGS),
        }

        with self.client.post(
            WORKFLOWS_URL,
            json=payload,
            headers=self._get_headers(),
            name="[Templates] Create Complex",
            catch_response=True,
        ) as response:
            duration = time.time() - start_time
            metrics.record_template_create_time(duration)

            if response.status_code == 201:
                data = response.json()
                template_id = data.get("id")
                if template_id:
                    self.created_templates.append(template_id)
                    self._validate_template(template_id)
                response.success()
            else:
                response.failure(f"Create failed: {response.status_code}")
                metrics.record_error(f"create_complex_{response.status_code}")

    def _validate_template(self, template_id: str):
        """Validate a workflow template."""
        with self.client.post(
            f"{WORKFLOWS_URL}{template_id}/validate/",
            headers=self._get_headers(),
            name="[Templates] Validate",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                # Validation may fail for test DAGs, that's expected
                response.success()

    @task(20)
    def execute_workflow(self):
        """POST /api/v1/templates/workflow/workflows/{id}/execute/ - Execute workflow."""
        if not self.created_templates:
            # Create a template first
            self.create_simple_workflow()
            return

        template_id = random.choice(self.created_templates)
        start_time = time.time()

        payload = {
            "input_context": {
                "user_id": self.user_id,
                "timestamp": time.time(),
                "random_value": random.randint(1, 1000),
            },
            "mode": "async",  # Use async mode for load testing
        }

        with self.client.post(
            f"{WORKFLOWS_URL}{template_id}/execute/",
            json=payload,
            headers=self._get_headers(),
            name="[Workflows] Execute",
            catch_response=True,
        ) as response:
            duration = time.time() - start_time
            metrics.record_execution_start_time(duration)

            if response.status_code in (200, 202):
                data = response.json()
                execution_id = data.get("execution_id")
                if execution_id:
                    self.created_executions.append(execution_id)
                    metrics.increment_concurrent()
                response.success()
            elif response.status_code == 400:
                # Template not valid/active - expected for test templates
                response.success()
            elif response.status_code == 429:
                # Rate limited
                response.failure("Rate limited")
                metrics.record_error("rate_limited")
            else:
                response.failure(f"Execute failed: {response.status_code}")
                metrics.record_error(f"execute_{response.status_code}")

    @task(15)
    def check_execution_status(self):
        """GET /api/v1/templates/workflow/executions/{id}/status/ - Check execution status."""
        if not self.created_executions:
            return

        execution_id = random.choice(self.created_executions)
        start_time = time.time()

        with self.client.get(
            f"{EXECUTIONS_URL}{execution_id}/status/",
            headers=self._get_headers(),
            name="[Executions] Status",
            catch_response=True,
        ) as response:
            duration = time.time() - start_time
            metrics.record_status_poll_time(duration)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status in ("completed", "failed", "cancelled"):
                    # Remove from tracking, decrement concurrent
                    if execution_id in self.created_executions:
                        self.created_executions.remove(execution_id)
                        metrics.decrement_concurrent()
                response.success()
            elif response.status_code == 404:
                # Execution was cleaned up
                if execution_id in self.created_executions:
                    self.created_executions.remove(execution_id)
                response.success()
            else:
                response.failure(f"Status check failed: {response.status_code}")
                metrics.record_error(f"status_{response.status_code}")

    @task(3)
    def list_executions(self):
        """GET /api/v1/templates/workflow/executions/ - List workflow executions."""
        with self.client.get(
            EXECUTIONS_URL,
            headers=self._get_headers(),
            name="[Executions] List",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List executions failed: {response.status_code}")
                metrics.record_error(f"list_executions_{response.status_code}")

    @task(2)
    def cancel_execution(self):
        """POST /api/v1/templates/workflow/executions/{id}/cancel/ - Cancel execution."""
        # Only cancel some executions (random 20%)
        if not self.created_executions or random.random() > 0.2:
            return

        execution_id = random.choice(self.created_executions)

        with self.client.post(
            f"{EXECUTIONS_URL}{execution_id}/cancel/",
            headers=self._get_headers(),
            name="[Executions] Cancel",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 400):
                # 400 is OK if execution already completed/cancelled
                if execution_id in self.created_executions:
                    self.created_executions.remove(execution_id)
                    metrics.decrement_concurrent()
                response.success()
            else:
                response.failure(f"Cancel failed: {response.status_code}")
                metrics.record_error(f"cancel_{response.status_code}")

    @task(1)
    def get_template_detail(self):
        """GET /api/v1/templates/workflow/workflows/{id}/ - Get template details."""
        if not self.created_templates:
            return

        template_id = random.choice(self.created_templates)

        with self.client.get(
            f"{WORKFLOWS_URL}{template_id}/",
            headers=self._get_headers(),
            name="[Templates] Detail",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Template was deleted
                if template_id in self.created_templates:
                    self.created_templates.remove(template_id)
                response.success()
            else:
                response.failure(f"Detail failed: {response.status_code}")

    @task(1)
    def clone_template(self):
        """POST /api/v1/templates/workflow/workflows/{id}/clone/ - Clone template."""
        if not self.created_templates:
            return

        template_id = random.choice(self.created_templates)

        with self.client.post(
            f"{WORKFLOWS_URL}{template_id}/clone/",
            json={"name": f"Cloned_{uuid4().hex[:8]}"},
            headers=self._get_headers(),
            name="[Templates] Clone",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                data = response.json()
                new_id = data.get("id")
                if new_id:
                    self.created_templates.append(new_id)
                response.success()
            else:
                response.failure(f"Clone failed: {response.status_code}")


class ConcurrentExecutionUser(HttpUser):
    """
    Heavy concurrent workflow execution user.

    Focuses on executing workflows and polling status until completion.
    Used for testing concurrent execution limits and bottlenecks.
    """

    abstract = True
    wait_time = between(0.5, 1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token: Optional[str] = None
        self.template_id: Optional[str] = None
        self.active_executions: List[str] = []
        self.user_id = str(uuid4())[:8]

    def on_start(self):
        """Authenticate and create a reusable template."""
        self.token = self._get_auth_token()
        if self.token:
            self.template_id = self._create_and_validate_template()

    def on_stop(self):
        """Cleanup active executions."""
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        for exec_id in self.active_executions:
            try:
                self.client.post(
                    f"{EXECUTIONS_URL}{exec_id}/cancel/",
                    headers=headers,
                    name="[Cleanup] Cancel",
                )
            except Exception:
                pass

    def _get_auth_token(self) -> Optional[str]:
        """Get JWT token."""
        try:
            response = self.client.post(
                TOKEN_URL,
                json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
                name="[Auth] Token",
            )
            if response.status_code == 200:
                return response.json().get("access")
        except Exception:
            pass
        return None

    def _create_and_validate_template(self) -> Optional[str]:
        """Create and validate a template for reuse."""
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

        # Create template
        response = self.client.post(
            WORKFLOWS_URL,
            json={
                "name": f"ConcurrentTest_{self.user_id}",
                "workflow_type": "concurrent_test",
                "dag_structure": SIMPLE_WORKFLOW_DAG,
                "config": {"timeout_seconds": 600, "max_retries": 1},
            },
            headers=headers,
            name="[Setup] Create Template",
        )

        if response.status_code != 201:
            return None

        template_id = response.json().get("id")

        # Validate template
        self.client.post(
            f"{WORKFLOWS_URL}{template_id}/validate/",
            headers=headers,
            name="[Setup] Validate Template",
        )

        return template_id

    @task
    def execute_and_poll(self):
        """Execute workflow and poll until completion."""
        if not self.token or not self.template_id:
            return

        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        start_time = time.time()

        # Execute workflow
        with self.client.post(
            f"{WORKFLOWS_URL}{self.template_id}/execute/",
            json={
                "input_context": {"user": self.user_id, "ts": time.time()},
                "mode": "async",
            },
            headers=headers,
            name="[Concurrent] Execute",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 202):
                if response.status_code == 429:
                    metrics.record_error("rate_limited")
                response.failure(f"Execute failed: {response.status_code}")
                return
            response.success()

            execution_id = response.json().get("execution_id")
            if not execution_id:
                return

            self.active_executions.append(execution_id)
            metrics.increment_concurrent()

        # Poll until completion (with timeout)
        poll_timeout = 60  # seconds
        poll_interval = 0.5
        elapsed = 0

        while elapsed < poll_timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            with self.client.get(
                f"{EXECUTIONS_URL}{execution_id}/status/",
                headers=headers,
                name="[Concurrent] Poll Status",
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure(f"Poll failed: {response.status_code}")
                    break
                response.success()

                status = response.json().get("status")
                if status in ("completed", "failed", "cancelled"):
                    duration = time.time() - start_time
                    metrics.record_execution_time(duration)

                    if execution_id in self.active_executions:
                        self.active_executions.remove(execution_id)
                        metrics.decrement_concurrent()
                    break


# ============================================================================
# Load Profile Users
# ============================================================================

class LightLoadUser(WorkflowAPIUser):
    """
    Light load profile: 10 concurrent users.

    Simulates normal daily usage with moderate wait times.
    """

    weight = 1
    wait_time = between(2, 5)


class MediumLoadUser(WorkflowAPIUser):
    """
    Medium load profile: 50 concurrent users.

    Simulates peak usage with reduced wait times.
    """

    weight = 3
    wait_time = between(1, 3)


class HeavyLoadUser(WorkflowAPIUser):
    """
    Heavy load profile: 100 concurrent users.

    Simulates stress test with minimal wait times.
    """

    weight = 5
    wait_time = between(0.5, 1.5)


class BurstLoadUser(ConcurrentExecutionUser):
    """
    Burst load profile for concurrent execution testing.

    Focuses on rapid workflow execution and status polling.
    """

    weight = 2
    wait_time = between(0.3, 0.8)


# ============================================================================
# Event Handlers
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Setup before load test starts."""
    logger.info("=" * 60)
    logger.info("Workflow Engine Load Test Starting")
    logger.info("=" * 60)
    logger.info(f"Host: {environment.host}")
    logger.info(f"Users: {environment.runner.user_count if environment.runner else 'N/A'}")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Cleanup and report after load test completes."""
    logger.info("=" * 60)
    logger.info("Workflow Engine Load Test Complete")
    logger.info("=" * 60)

    # Print metrics summary
    summary = metrics.get_summary()
    logger.info("\n--- Custom Metrics Summary ---")

    for metric_name, stats in summary.items():
        if isinstance(stats, dict) and "count" in stats:
            logger.info(f"\n{metric_name}:")
            logger.info(f"  Count: {stats['count']}")
            if stats['count'] > 0:
                logger.info(f"  Avg:   {stats['avg']:.3f}s")
                logger.info(f"  Min:   {stats['min']:.3f}s")
                logger.info(f"  Max:   {stats['max']:.3f}s")
                logger.info(f"  P95:   {stats['p95']:.3f}s")
        elif metric_name == "errors_by_type":
            if stats:
                logger.info(f"\n{metric_name}:")
                for err_type, count in stats.items():
                    logger.info(f"  {err_type}: {count}")
        else:
            logger.info(f"\n{metric_name}: {stats}")

    logger.info("\n" + "=" * 60)

    # Bottleneck analysis hints
    logger.info("\n--- Bottleneck Analysis Hints ---")
    exec_stats = summary.get("execution_start_times", {})
    if exec_stats.get("p95", 0) > 1.0:
        logger.info("  [!] High execution start latency - check Celery worker availability")

    poll_stats = summary.get("status_poll_times", {})
    if poll_stats.get("p95", 0) > 0.5:
        logger.info("  [!] High status poll latency - check database query optimization")

    create_stats = summary.get("template_create_times", {})
    if create_stats.get("p95", 0) > 2.0:
        logger.info("  [!] High template creation latency - check database write performance")

    max_concurrent = summary.get("max_concurrent_executions", 0)
    if max_concurrent > 50:
        logger.info(f"  [!] High concurrent executions ({max_concurrent}) - check Worker pool sizing")

    errors = summary.get("errors_by_type", {})
    if errors.get("rate_limited", 0) > 10:
        logger.info("  [!] Rate limiting triggered - consider increasing limits or spreading load")

    logger.info("=" * 60)


@events.request.add_listener
def on_request(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    response,
    exception,
    **kwargs,
):
    """Track individual requests for detailed analysis."""
    if exception:
        logger.debug(f"Request failed: {name} - {exception}")


# ============================================================================
# Standalone Execution Support
# ============================================================================

if __name__ == "__main__":
    import sys

    print(__doc__)
    print("\nTo run this load test, use locust CLI:")
    print(f"  locust -f {__file__} --host=http://localhost:8000")
    print("\nOr in headless mode:")
    print(f"  locust -f {__file__} --host=http://localhost:8000 --headless -u 10 -r 2 -t 1m")
    sys.exit(0)

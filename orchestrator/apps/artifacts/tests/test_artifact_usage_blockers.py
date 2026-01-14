import pytest

from apps.artifacts.models import Artifact, ArtifactKind, ArtifactUsage
from apps.artifacts.purge_blockers import find_purge_blockers
from apps.operations.models import BatchOperation
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate


@pytest.mark.django_db
def test_artifact_usage_written_for_batch_operation_on_create():
    artifact = Artifact.objects.create(
        name="usage-test-op",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
    )

    op = BatchOperation.objects.create(
        id="usage-op-1",
        name="Usage Op 1",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="test",
        payload={"file": f"artifact://artifacts/{artifact.id}/v1/file.txt"},
        config={},
    )

    assert ArtifactUsage.objects.filter(artifact=artifact, operation=op).exists()


@pytest.mark.django_db
def test_find_purge_blockers_uses_artifact_usage_fast_path():
    artifact = Artifact.objects.create(
        name="usage-fast-path",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        is_deleted=True,
    )

    op = BatchOperation.objects.create(
        id="usage-op-2",
        name="Usage Op 2",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="test",
        payload={},
        config={},
        status=BatchOperation.STATUS_QUEUED,
    )

    ArtifactUsage.objects.create(
        artifact=artifact,
        operation=op,
    )

    blockers = find_purge_blockers(artifact.id, limit=10)
    assert any(b.get("type") == "batch_operation" and b.get("id") == op.id for b in blockers)


@pytest.mark.django_db
def test_artifact_usage_written_for_workflow_execution_on_create():
    artifact = Artifact.objects.create(
        name="usage-test-wf",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
    )

    template = WorkflowTemplate.objects.create(
        name="Usage Test Workflow",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {"id": "step1", "name": "Step 1", "type": "operation", "template_id": "test_op1", "config": {}},
            ],
            "edges": [],
        },
        config={"timeout_seconds": 60, "max_retries": 0},
        is_valid=True,
        is_active=True,
    )

    execution = WorkflowExecution.objects.create(
        workflow_template=template,
        input_context={"file": f"artifact://artifacts/{artifact.id}/v1/file.txt"},
    )

    assert ArtifactUsage.objects.filter(artifact=artifact, workflow_execution=execution).exists()


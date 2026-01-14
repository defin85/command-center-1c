from __future__ import annotations

import logging
from typing import Iterable

from django.apps import apps
from django.db.models.signals import post_save

from apps.artifacts.refs import extract_artifact_ids


logger = logging.getLogger(__name__)


def _filter_existing_artifact_ids(artifact_ids: Iterable) -> list:
    Artifact = apps.get_model("artifacts", "Artifact")
    return list(Artifact.objects.filter(id__in=set(artifact_ids)).values_list("id", flat=True))


def _record_usage_for_batch_operation(operation) -> None:
    artifact_ids = set()
    artifact_ids |= extract_artifact_ids(getattr(operation, "payload", None))
    artifact_ids |= extract_artifact_ids(getattr(operation, "config", None))
    if not artifact_ids:
        return

    ArtifactUsage = apps.get_model("artifacts", "ArtifactUsage")
    for artifact_id in _filter_existing_artifact_ids(artifact_ids):
        ArtifactUsage.objects.get_or_create(
            artifact_id=artifact_id,
            operation=operation,
        )


def _record_usage_for_workflow_execution(execution) -> None:
    artifact_ids = extract_artifact_ids(getattr(execution, "input_context", None))
    if not artifact_ids:
        return

    ArtifactUsage = apps.get_model("artifacts", "ArtifactUsage")
    for artifact_id in _filter_existing_artifact_ids(artifact_ids):
        ArtifactUsage.objects.get_or_create(
            artifact_id=artifact_id,
            workflow_execution=execution,
        )


def register_artifact_usage_signals() -> None:
    BatchOperation = apps.get_model("operations", "BatchOperation")
    WorkflowExecution = apps.get_model("templates", "WorkflowExecution")

    def on_batch_operation_saved(sender, instance, created, **kwargs):
        if not created:
            return
        try:
            _record_usage_for_batch_operation(instance)
        except Exception as e:
            logger.warning("Artifact usage write failed for BatchOperation %s: %s", instance.pk, e, exc_info=True)

    def on_workflow_execution_saved(sender, instance, created, **kwargs):
        if not created:
            return
        try:
            _record_usage_for_workflow_execution(instance)
        except Exception as e:
            logger.warning("Artifact usage write failed for WorkflowExecution %s: %s", instance.pk, e, exc_info=True)

    post_save.connect(
        on_batch_operation_saved,
        sender=BatchOperation,
        dispatch_uid="artifacts.usage.batch_operation",
    )
    post_save.connect(
        on_workflow_execution_saved,
        sender=WorkflowExecution,
        dispatch_uid="artifacts.usage.workflow_execution",
    )


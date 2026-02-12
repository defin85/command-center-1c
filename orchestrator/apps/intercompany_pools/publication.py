from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.utils import timezone
from django_fsm import TransitionNotAllowed

from apps.databases.models import Database
from apps.databases.odata import ODataRequestError, session_manager

from .external_identity import (
    ExternalIdentityContext,
    resolve_external_document_identity,
    build_external_run_key,
)
from .models import (
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
)


@dataclass(frozen=True)
class PublicationSummary:
    total_targets: int
    succeeded_targets: int
    failed_targets: int
    max_attempts: int


MAX_PUBLICATION_ATTEMPTS = 5
MAX_RETRY_INTERVAL_SECONDS = 120


def publish_run_documents(
    *,
    run: PoolRun,
    entity_name: str,
    documents_by_database: Mapping[str, list[dict[str, Any]]],
    max_attempts: int = MAX_PUBLICATION_ATTEMPTS,
    retry_interval_seconds: int = 0,
    external_key_field: str = "ExternalRunKey",
) -> PublicationSummary:
    if max_attempts < 1 or max_attempts > MAX_PUBLICATION_ATTEMPTS:
        raise ValueError(f"max_attempts must be in range 1..{MAX_PUBLICATION_ATTEMPTS}")
    if retry_interval_seconds < 0:
        raise ValueError("retry_interval_seconds must be >= 0")
    if retry_interval_seconds > MAX_RETRY_INTERVAL_SECONDS:
        raise ValueError(f"retry_interval_seconds must be <= {MAX_RETRY_INTERVAL_SECONDS}")

    _ensure_run_in_publishing_state(run)
    succeeded_targets = 0
    failed_targets = 0

    for database_id, documents in documents_by_database.items():
        target_ok = _publish_target_with_retries(
            run=run,
            database_id=database_id,
            entity_name=entity_name,
            documents=documents,
            max_attempts=max_attempts,
            retry_interval_seconds=retry_interval_seconds,
            external_key_field=external_key_field,
        )
        if target_ok:
            succeeded_targets += 1
        else:
            failed_targets += 1

    summary = PublicationSummary(
        total_targets=len(documents_by_database),
        succeeded_targets=succeeded_targets,
        failed_targets=failed_targets,
        max_attempts=max_attempts,
    )
    _finish_run_publication(run=run, summary=summary)
    return summary


def retry_failed_run_documents(
    *,
    run: PoolRun,
    entity_name: str,
    documents_by_database: Mapping[str, list[dict[str, Any]]],
    max_attempts: int = MAX_PUBLICATION_ATTEMPTS,
    retry_interval_seconds: int = 0,
    external_key_field: str = "ExternalRunKey",
) -> PublicationSummary:
    failed_target_ids = _collect_failed_target_ids(run=run)
    if not failed_target_ids:
        return PublicationSummary(
            total_targets=0,
            succeeded_targets=0,
            failed_targets=0,
            max_attempts=max_attempts,
        )

    filtered_documents: dict[str, list[dict[str, Any]]] = {
        str(database_id): documents
        for database_id, documents in documents_by_database.items()
        if str(database_id) in failed_target_ids
    }
    missing_targets = sorted(failed_target_ids - set(filtered_documents))
    if missing_targets:
        missing = ", ".join(missing_targets)
        raise ValidationError(f"Missing documents for failed targets: {missing}")

    return publish_run_documents(
        run=run,
        entity_name=entity_name,
        documents_by_database=filtered_documents,
        max_attempts=max_attempts,
        retry_interval_seconds=retry_interval_seconds,
        external_key_field=external_key_field,
    )


def _ensure_run_in_publishing_state(run: PoolRun) -> None:
    if run.status == PoolRun.STATUS_PUBLISHING:
        return
    save_fields = ["status", "publishing_started_at", "updated_at"]
    if run.status == PoolRun.STATUS_VALIDATED:
        transition = run.start_publishing
    elif run.status in {PoolRun.STATUS_PARTIAL_SUCCESS, PoolRun.STATUS_FAILED}:
        transition = run.restart_publishing
        save_fields = ["status", "publishing_started_at", "completed_at", "last_error", "updated_at"]
    else:
        raise ValidationError(
            "Run must be in 'validated', 'partial_success' or 'failed' before publication."
        )
    try:
        transition()
    except TransitionNotAllowed as exc:
        raise ValidationError("Run cannot start publishing in current mode/state.") from exc
    run.save(update_fields=save_fields)


def _finish_run_publication(*, run: PoolRun, summary: PublicationSummary) -> None:
    payload = {
        "total_targets": summary.total_targets,
        "succeeded_targets": summary.succeeded_targets,
        "failed_targets": summary.failed_targets,
        "max_attempts": summary.max_attempts,
    }
    if summary.failed_targets == 0:
        run.mark_published(summary=payload)
        run.save(update_fields=["status", "publication_summary", "completed_at", "updated_at"])
        return

    if summary.succeeded_targets > 0:
        run.mark_partial_success(summary=payload)
        run.save(update_fields=["status", "publication_summary", "completed_at", "updated_at"])
        return

    run.mark_failed(error="publication_failed_all_targets", summary=payload)
    run.save(
        update_fields=[
            "status",
            "last_error",
            "publication_summary",
            "completed_at",
            "updated_at",
        ]
    )


def _publish_target_with_retries(
    *,
    run: PoolRun,
    database_id: str,
    entity_name: str,
    documents: list[dict[str, Any]],
    max_attempts: int,
    retry_interval_seconds: int,
    external_key_field: str,
) -> bool:
    database = Database.objects.filter(id=database_id, tenant=run.tenant).first()
    if database is None:
        _save_failed_attempt(
            run=run,
            database_id=database_id,
            attempt_number=1,
            entity_name=entity_name,
            error_code="database_not_found",
            error_message=f"Database '{database_id}' is unavailable for tenant '{run.tenant_id}'.",
            documents_count=len(documents),
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )
        return False

    client = session_manager.get_client(
        base_id=str(database.id),
        base_url=database.odata_url,
        username=database.username,
        password=database.password,
        timeout=database.connection_timeout,
    )

    attempt_offset = (
        PoolPublicationAttempt.objects.filter(run=run, target_database=database).aggregate(
            max_attempt=Max("attempt_number")
        )["max_attempt"]
        or 0
    )

    for local_attempt in range(1, max_attempts + 1):
        attempt_number = attempt_offset + local_attempt
        started_at = timezone.now()
        try:
            success_summary = _publish_documents_once(
                run=run,
                database=database,
                client=client,
                entity_name=entity_name,
                documents=documents,
                external_key_field=external_key_field,
            )
            PoolPublicationAttempt.objects.create(
                run=run,
                tenant=run.tenant,
                target_database=database,
                attempt_number=attempt_number,
                status=PoolPublicationAttemptStatus.SUCCESS,
                entity_name=entity_name,
                documents_count=len(documents),
                external_document_identity=success_summary["external_identity"],
                identity_strategy=success_summary["identity_strategy"],
                posted=True,
                request_summary={"documents_count": len(documents)},
                response_summary=success_summary["response_summary"],
                started_at=started_at,
                finished_at=timezone.now(),
            )
            run.add_audit_event(
                event_type="run.publication_attempt_success",
                status_before=run.status,
                status_after=run.status,
                payload={
                    "database_id": str(database.id),
                    "attempt_number": attempt_number,
                    "identity_strategy": success_summary["identity_strategy"],
                },
            )
            return True
        except Exception as exc:  # noqa: BLE001
            _save_failed_attempt(
                run=run,
                database_id=str(database.id),
                attempt_number=attempt_number,
                entity_name=entity_name,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                documents_count=len(documents),
                started_at=started_at,
                finished_at=timezone.now(),
                http_status=getattr(exc, "status_code", None),
            )
            if local_attempt < max_attempts and retry_interval_seconds > 0:
                time.sleep(retry_interval_seconds)

    return False


def _publish_documents_once(
    *,
    run: PoolRun,
    database: Database,
    client,
    entity_name: str,
    documents: list[dict[str, Any]],
    external_key_field: str,
) -> dict[str, Any]:
    identities: list[str] = []
    identity_strategy = ""

    for idx, payload in enumerate(documents):
        document_payload = dict(payload or {})
        identity_context = ExternalIdentityContext(
            run_id=str(run.id),
            target_database_id=str(database.id),
            document_kind=f"{entity_name}:{idx}",
            period_start=run.period_start,
            period_end=run.period_end,
        )
        fallback_key = build_external_run_key(identity_context)
        document_payload.setdefault(external_key_field, fallback_key)

        existing_guid = _find_existing_guid_by_external_key(
            client=client,
            entity_name=entity_name,
            external_key_field=external_key_field,
            external_key=fallback_key,
        )
        if existing_guid:
            response_payload = client.update_entity(entity_name, _guid_literal(existing_guid), document_payload)
        else:
            response_payload = client.create_entity(entity_name, document_payload)

        identity = resolve_external_document_identity(
            odata_payload=response_payload if isinstance(response_payload, dict) else {},
            context=identity_context,
        )
        identity_strategy = identity.strategy
        guid_for_posting = _resolve_guid_for_posting(
            client=client,
            entity_name=entity_name,
            identity_value=identity.value,
            identity_strategy=identity.strategy,
            external_key_field=external_key_field,
        )
        if not guid_for_posting:
            raise ODataRequestError(
                message=f"Cannot resolve GUID for posting ({identity.strategy})",
                status_code=None,
            )

        client.update_entity(entity_name, _guid_literal(guid_for_posting), {"Posted": True})
        identities.append(identity.value)

    return {
        "external_identity": identities[-1] if identities else "",
        "identity_strategy": identity_strategy,
        "response_summary": {"documents": identities, "posted": True},
    }


def _find_existing_guid_by_external_key(
    *,
    client,
    entity_name: str,
    external_key_field: str,
    external_key: str,
) -> str | None:
    escaped = external_key.replace("'", "''")
    rows = client.get_entities(
        entity_name,
        filter_query=f"{external_key_field} eq '{escaped}'",
        select_fields=["Ref_Key"],
        top=1,
    )
    if not rows:
        return None
    ref_key = rows[0].get("Ref_Key")
    return str(ref_key).strip() if ref_key else None


def _collect_failed_target_ids(*, run: PoolRun) -> set[str]:
    latest_status_by_database: dict[str, str] = {}
    attempts = PoolPublicationAttempt.objects.filter(run=run).order_by(
        "target_database_id",
        "attempt_number",
        "created_at",
    )
    for attempt in attempts:
        latest_status_by_database[str(attempt.target_database_id)] = attempt.status
    return {
        database_id
        for database_id, status in latest_status_by_database.items()
        if status == PoolPublicationAttemptStatus.FAILED
    }


def _resolve_guid_for_posting(
    *,
    client,
    entity_name: str,
    identity_value: str,
    identity_strategy: str,
    external_key_field: str,
) -> str | None:
    if identity_strategy == "guid_from_odata":
        return identity_value

    return _find_existing_guid_by_external_key(
        client=client,
        entity_name=entity_name,
        external_key_field=external_key_field,
        external_key=identity_value,
    )


def _guid_literal(guid: str) -> str:
    normalized = str(guid).strip()
    if normalized.startswith("guid'") and normalized.endswith("'"):
        return normalized
    return f"guid'{normalized}'"


def _save_failed_attempt(
    *,
    run: PoolRun,
    database_id: str,
    attempt_number: int,
    entity_name: str,
    error_code: str,
    error_message: str,
    documents_count: int,
    started_at: datetime,
    finished_at: datetime,
    http_status: int | None = None,
) -> None:
    database = Database.objects.filter(id=database_id).first()
    if database is not None:
        PoolPublicationAttempt.objects.create(
            run=run,
            tenant=run.tenant,
            target_database=database,
            attempt_number=attempt_number,
            status=PoolPublicationAttemptStatus.FAILED,
            entity_name=entity_name,
            documents_count=documents_count,
            posted=False,
            http_status=http_status,
            error_code=error_code,
            error_message=error_message,
            request_summary={"documents_count": documents_count},
            response_summary={},
            started_at=started_at,
            finished_at=finished_at,
        )

    run.add_audit_event(
        event_type="run.publication_attempt_failed",
        status_before=run.status,
        status_after=run.status,
        payload={
            "database_id": database_id,
            "attempt_number": attempt_number,
            "error_code": error_code,
            "error_message": error_message,
            "http_status": http_status,
        },
    )

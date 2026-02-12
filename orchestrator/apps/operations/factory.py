"""
BatchOperationFactory - фабрика для создания BatchOperation и связанных Task.

Используется WorkflowEngine для создания операций из шаблонов.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from django.db import transaction

from apps.databases.models import Database
from apps.operations.models import BatchOperation, Task
from apps.templates.models import OperationExposure
from apps.templates.tracing import get_current_trace_id

logger = logging.getLogger(__name__)

TARGET_SCOPE_GLOBAL = "global"


def _extract_target_scope(rendered_data: Dict[str, Any]) -> str:
    if not isinstance(rendered_data, dict):
        return ""
    options = rendered_data.get("options")
    if isinstance(options, dict):
        value = str(options.get("target_scope") or "").strip().lower()
        if value:
            return value
    return ""


def _resolve_template_exposure_ref(*, template_alias: str) -> tuple[str, Optional[int]]:
    alias = str(template_alias or "").strip()
    if not alias:
        return "", None
    row = (
        OperationExposure.objects.filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            tenant__isnull=True,
            alias=alias,
        )
        .values_list("id", "exposure_revision")
        .first()
    )
    if not row:
        return "", None
    exposure_id_raw, revision_raw = row
    exposure_id = str(exposure_id_raw) if exposure_id_raw else ""
    try:
        exposure_revision = int(revision_raw)
    except (TypeError, ValueError):
        exposure_revision = 1
    if exposure_revision < 1:
        exposure_revision = 1
    return exposure_id, exposure_revision


class BatchOperationFactory:
    """
    Фабрика для создания BatchOperation и связанных Task.

    Создает операции из шаблонов для выполнения на нескольких базах данных.
    Поддерживает как workflow-операции (с execution_id и node_id),
    так и ручные операции.
    """

    @classmethod
    def create(
        cls,
        template: Any,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        workflow_execution_id: Optional[str] = None,
        node_id: Optional[str] = None,
        created_by: str = "system"
    ) -> BatchOperation:
        """
        Создает BatchOperation и Task для каждой целевой базы данных.

        Args:
            template: Шаблон операции
            rendered_data: Данные операции после рендеринга шаблона
            target_databases: Список UUID баз данных (строки)
            workflow_execution_id: ID выполнения workflow (опционально)
            node_id: ID узла в workflow (опционально)
            created_by: Имя пользователя/системы, создавшего операцию

        Returns:
            Созданный BatchOperation

        Raises:
            ValueError: Если target_databases пустой
            Database.DoesNotExist: Если база данных не найдена
        """
        target_scope = _extract_target_scope(rendered_data)

        # Валидация
        if not target_databases and target_scope != TARGET_SCOPE_GLOBAL:
            raise ValueError("target_databases cannot be empty")

        # Генерация operation_id
        operation_id = cls._generate_operation_id(
            workflow_execution_id=workflow_execution_id,
            node_id=node_id
        )

        # Определяем имя операции
        if workflow_execution_id:
            operation_name = f"Workflow: {template.name}"
        else:
            operation_name = f"Manual: {template.name}"

        # Определяем тип операции
        operation_type = getattr(template, 'operation_type', None) or 'query'

        # Определяем целевую сущность
        target_entity = rendered_data.get("entity", getattr(template, "target_entity", None) or template.name)

        operation_payload: Dict[str, Any] = rendered_data
        operation_config: Dict[str, Any] = {}

        # Формируем метаданные
        trace_id = get_current_trace_id()
        metadata = {
            'workflow_execution_id': workflow_execution_id,
            'node_id': node_id,
        }
        if trace_id:
            metadata['trace_id'] = trace_id

        template_alias = str(template.id or "").strip()
        if template_alias:
            metadata["template_id"] = template_alias
            template_exposure_id = str(getattr(template, "exposure_id", "") or "").strip()
            template_exposure_revision_raw = getattr(template, "exposure_revision", None)
            try:
                template_exposure_revision = int(template_exposure_revision_raw)
            except (TypeError, ValueError):
                template_exposure_revision = None
            if template_exposure_revision is not None and template_exposure_revision < 1:
                template_exposure_revision = None

            if not template_exposure_id or template_exposure_revision is None:
                resolved_exposure_id, resolved_exposure_revision = _resolve_template_exposure_ref(
                    template_alias=template_alias
                )
                if not template_exposure_id:
                    template_exposure_id = resolved_exposure_id
                if template_exposure_revision is None:
                    template_exposure_revision = resolved_exposure_revision
            if template_exposure_id:
                metadata["template_exposure_id"] = template_exposure_id
            if template_exposure_revision is not None:
                metadata["template_exposure_revision"] = template_exposure_revision

        if operation_type == BatchOperation.TYPE_IBCMD_CLI:
            from apps.operations.driver_catalog_effective import get_effective_driver_catalog, resolve_driver_catalog_versions
            from apps.operations.ibcmd_cli_builder import build_ibcmd_cli_argv, build_ibcmd_cli_argv_manual

            raw_payload = rendered_data if isinstance(rendered_data, dict) else {}
            data_section = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else raw_payload
            filters_section = raw_payload.get("filters") if isinstance(raw_payload.get("filters"), dict) else {}
            options_section = raw_payload.get("options") if isinstance(raw_payload.get("options"), dict) else {}

            command_id = str(data_section.get("command_id") or "").strip()
            if not command_id:
                raise ValueError("command_id is required for ibcmd_cli templates")

            mode = str(data_section.get("mode") or "guided").strip().lower()
            if mode not in {"guided", "manual"}:
                raise ValueError("mode must be guided|manual")

            params = data_section.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")

            additional_args = data_section.get("additional_args") or []
            if not isinstance(additional_args, list):
                raise ValueError("additional_args must be an array")
            additional_args_str = [str(x).strip() for x in additional_args if x is not None and str(x).strip()]

            stdin = data_section.get("stdin")
            if stdin is None:
                stdin = ""
            stdin = str(stdin)

            connection = data_section.get("connection") if isinstance(data_section.get("connection"), dict) else {}

            confirm_dangerous = bool(data_section.get("confirm_dangerous") or False)
            timeout_seconds = data_section.get("timeout_seconds")
            if timeout_seconds is None:
                timeout_seconds = 900
            timeout_seconds = int(timeout_seconds)

            resolved = resolve_driver_catalog_versions("ibcmd")
            if resolved.base_version is None:
                raise ValueError("ibcmd catalog is not imported yet")

            effective = get_effective_driver_catalog(
                driver="ibcmd",
                base_version=resolved.base_version,
                overrides_version=resolved.overrides_version,
            )
            commands_by_id = effective.catalog.get("commands_by_id") if isinstance(effective.catalog, dict) else None
            if not isinstance(commands_by_id, dict):
                raise ValueError("ibcmd catalog is invalid")

            command = commands_by_id.get(command_id)
            if not isinstance(command, dict) or command.get("disabled") is True:
                raise ValueError(f"Unknown command_id: {command_id}")

            risk_level = str(command.get("risk_level") or "").strip().lower()
            if risk_level == "dangerous" and not confirm_dangerous:
                raise ValueError("confirm_dangerous=true is required for dangerous commands")

            try:
                builder = build_ibcmd_cli_argv_manual if mode == "manual" else build_ibcmd_cli_argv
                argv, argv_masked = builder(command=command, params=params, additional_args=additional_args_str)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc

            target_entity = "Infobase"
            operation_config = {
                "batch_size": 1,
                "timeout_seconds": timeout_seconds,
                "retry_count": 1,
                "priority": "normal",
            }
            operation_payload = {
                "data": {
                    "command_id": command_id,
                    "mode": mode,
                    "argv": argv,
                    "argv_masked": argv_masked,
                    "stdin": stdin,
                    "connection": connection,
                },
                "filters": filters_section,
                "options": options_section,
            }
            metadata.update({
                "tags": ["ibcmd", "ibcmd_cli", command_id],
                "command_id": command_id,
                "risk_level": risk_level,
                "scope": str(command.get("scope") or "").strip().lower(),
                "mode": mode,
                "catalog_base_version": str(effective.base_version),
                "catalog_base_version_id": str(effective.base_version_id),
                "catalog_overrides_version": (
                    str(effective.overrides_version) if effective.overrides_version else None
                ),
                "catalog_overrides_version_id": (
                    str(effective.overrides_version_id) if effective.overrides_version_id else None
                ),
            })

        logger.info(
            f"Creating BatchOperation: id={operation_id}, "
            f"template={template.name}, databases={len(target_databases)}"
        )

        with transaction.atomic():
            # Создаем BatchOperation
            operation = BatchOperation.objects.create(
                id=operation_id,
                name=operation_name,
                operation_type=operation_type,
                target_entity=target_entity,
                payload=operation_payload,
                config=operation_config,
                status=BatchOperation.STATUS_PENDING,
                created_by=created_by,
                metadata=metadata,
            )

            if target_scope == TARGET_SCOPE_GLOBAL:
                task_id = f"{operation_id}-global"
                Task.objects.create(
                    id=task_id,
                    batch_operation=operation,
                    database=None,
                    status=Task.STATUS_PENDING,
                )
                operation.total_tasks = 1
                operation.save(update_fields=['total_tasks', 'updated_at'])
                logger.info(
                    f"BatchOperation created: id={operation_id}, tasks=1 (global)"
                )
                return operation

            # Получаем объекты Database
            databases = list(Database.objects.filter(id__in=target_databases))

            # Проверяем, что все базы найдены
            found_ids = {db.id for db in databases}
            missing_ids = set(target_databases) - found_ids
            if missing_ids:
                logger.warning(
                    f"Some databases not found: {missing_ids}. "
                    f"Continuing with {len(databases)} databases."
                )

            # Устанавливаем M2M связь
            operation.target_databases.set(databases)

            # Bulk create Task для каждой базы
            tasks = []
            for db in databases:
                task_id = f"{operation_id}-{db.id[:8]}"
                tasks.append(Task(
                    id=task_id,
                    batch_operation=operation,
                    database=db,
                    status=Task.STATUS_PENDING,
                ))

            Task.objects.bulk_create(tasks)

            # Обновляем статистику
            operation.total_tasks = len(tasks)
            operation.save(update_fields=['total_tasks', 'updated_at'])

            logger.info(
                f"BatchOperation created: id={operation_id}, "
                f"tasks={len(tasks)}"
            )

        return operation

    @classmethod
    def _generate_operation_id(
        cls,
        workflow_execution_id: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> str:
        """
        Генерирует уникальный ID операции.

        Важно: BatchOperation.id и Task.id имеют ограничение max_length=64,
        поэтому ID должен быть коротким и не включать execution_id / node_id.
        Эти значения сохраняются в metadata.

        Формат:
          - workflow: batch-wf-{uuid4hex}
          - manual:   batch-manual-{uuid4hex}

        Args:
            workflow_execution_id: ID выполнения workflow
            node_id: ID узла в workflow

        Returns:
            Уникальный ID операции
        """
        prefix = 'batch-wf' if workflow_execution_id else 'batch-manual'
        suffix = uuid4().hex

        return f"{prefix}-{suffix}"

from typing import Optional

from django.db.models import Max, Q

from apps.databases.models import PermissionLevel
from apps.templates.models import (
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
    WorkflowTemplatePermission,
    WorkflowTemplateGroupPermission,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate


class TemplatePermissionService:
    """
    Scope/level resolution for templates and workflows.

    This service does NOT check Django capabilities (user.has_perm).
    It only resolves "what objects this user can access" and at what PermissionLevel.
    """

    @classmethod
    def get_user_level_for_operation_template(
        cls,
        user,
        template,
    ) -> Optional[int]:
        if not user or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "is_staff", False):
            return PermissionLevel.ADMIN
        template_id = str(getattr(template, "id", "") or "").strip()
        if not template_id:
            return None

        user_level = OperationExposurePermission.objects.filter(
            user=user,
            exposure__surface=OperationExposure.SURFACE_TEMPLATE,
            exposure__tenant__isnull=True,
            exposure__alias=template_id,
        ).values_list("level", flat=True).first()

        group_level = (
            OperationExposureGroupPermission.objects.filter(
                group__user=user,
                exposure__surface=OperationExposure.SURFACE_TEMPLATE,
                exposure__tenant__isnull=True,
                exposure__alias=template_id,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
        return max(levels) if levels else None

    @classmethod
    def get_user_level_for_workflow_template(
        cls,
        user,
        workflow_template: WorkflowTemplate,
    ) -> Optional[int]:
        if not user or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "is_staff", False):
            return PermissionLevel.ADMIN

        user_level = WorkflowTemplatePermission.objects.filter(
            user=user,
            workflow_template=workflow_template,
        ).values_list("level", flat=True).first()

        group_level = (
            WorkflowTemplateGroupPermission.objects.filter(
                group__user=user,
                workflow_template=workflow_template,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
        return max(levels) if levels else None

    @classmethod
    def get_user_level_for_workflow_execution(
        cls,
        user,
        execution: WorkflowExecution,
    ) -> Optional[int]:
        return cls.get_user_level_for_workflow_template(
            user, execution.workflow_template
        )

    @classmethod
    def has_operation_template_access(
        cls,
        user,
        template,
        required_level: int,
    ) -> bool:
        level = cls.get_user_level_for_operation_template(user, template)
        return level is not None and level >= required_level

    @classmethod
    def has_workflow_template_access(
        cls,
        user,
        workflow_template: WorkflowTemplate,
        required_level: int,
    ) -> bool:
        level = cls.get_user_level_for_workflow_template(user, workflow_template)
        return level is not None and level >= required_level

    @classmethod
    def filter_accessible_operation_templates(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        user_template_ids = OperationExposurePermission.objects.filter(
            user=user,
            level__gte=min_level,
            exposure__surface=OperationExposure.SURFACE_TEMPLATE,
            exposure__tenant__isnull=True,
        ).values_list("exposure__alias", flat=True)
        group_template_ids = OperationExposureGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
            exposure__surface=OperationExposure.SURFACE_TEMPLATE,
            exposure__tenant__isnull=True,
        ).values_list("exposure__alias", flat=True)
        return queryset.filter(Q(id__in=user_template_ids) | Q(id__in=group_template_ids))

    @classmethod
    def filter_accessible_workflow_templates(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        user_workflow_ids = WorkflowTemplatePermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        group_workflow_ids = WorkflowTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        return queryset.filter(Q(id__in=user_workflow_ids) | Q(id__in=group_workflow_ids))

    @classmethod
    def filter_accessible_workflow_executions(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        user_workflow_ids = WorkflowTemplatePermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        group_workflow_ids = WorkflowTemplateGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("workflow_template_id", flat=True)
        return queryset.filter(
            Q(workflow_template_id__in=user_workflow_ids)
            | Q(workflow_template_id__in=group_workflow_ids)
        )

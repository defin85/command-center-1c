"""
Common serializers for API v2.

Provides reusable serializers for error responses and other shared structures.
"""

from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""

    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""

    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class ProblemDetailsErrorSerializer(serializers.Serializer):
    """RFC 7807-style problem details response."""

    type = serializers.CharField(default="about:blank")
    title = serializers.CharField()
    status = serializers.IntegerField()
    detail = serializers.CharField()
    code = serializers.CharField()


class ExecutionBindingSerializer(serializers.Serializer):
    """
    Binding provenance for execution plan.

    IMPORTANT: This structure must never contain raw secret values.
    """

    target_ref = serializers.CharField(help_text="Where the value is applied (flag/argv index/workflow path).")
    source_ref = serializers.CharField(help_text="Where the value comes from (typed source reference).")
    resolve_at = serializers.ChoiceField(choices=["api", "worker"], help_text="Where the binding is resolved.")
    sensitive = serializers.BooleanField(help_text="True if the source is secret (value must not be stored/logged).")
    status = serializers.ChoiceField(
        choices=["applied", "skipped", "unresolved"],
        help_text="Binding status. Preview may include unresolved bindings.",
    )
    reason = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Reason for skipped/unresolved (e.g., missing_source, blocked_by_allowlist).",
    )


class ExecutionPlanSerializer(serializers.Serializer):
    """
    Safe execution plan representation.

    IMPORTANT: This structure must never contain raw secret values.
    """

    kind = serializers.ChoiceField(choices=["ibcmd_cli", "designer_cli", "workflow"])
    plan_version = serializers.IntegerField(required=False, default=1)

    argv_masked = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    stdin_masked = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    workflow_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    input_context_masked = serializers.DictField(required=False, default=dict)

    targets = serializers.DictField(
        required=False,
        default=dict,
        help_text="Execution targets summary (e.g., scope, database_ids count).",
    )
    definition = serializers.DictField(
        required=False,
        default=dict,
        help_text=(
            "Workflow definition provenance. "
            "Includes definition_key and resolved workflow template metadata."
        ),
    )
    execution_snapshot = serializers.DictField(
        required=False,
        default=dict,
        help_text=(
            "Immutable run-specific workflow snapshot. "
            "Includes period/run_input/seed and lineage metadata."
        ),
    )
    operation_bindings = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text="Pinned operation exposure snapshot used by workflow nodes.",
    )


class ExecutionPlanWithBindingsSerializer(serializers.Serializer):
    execution_plan = ExecutionPlanSerializer()
    bindings = ExecutionBindingSerializer(many=True)

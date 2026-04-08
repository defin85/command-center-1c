"""OpenAPI serializers and throttles for operations endpoints."""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.throttling import UserRateThrottle

from apps.api_v2.serializers.common import ExecutionBindingSerializer, ExecutionPlanSerializer
from apps.operations.serializers import BatchOperationSerializer, TaskSerializer
class OperationErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")

class OperationErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = OperationErrorDetailSerializer()
    request_id = serializers.CharField()
    ui_action_id = serializers.CharField(required=False)

class OperationProgressSerializer(serializers.Serializer):
    """Progress information for an operation."""
    total = serializers.IntegerField(help_text="Total number of tasks")
    completed = serializers.IntegerField(help_text="Number of completed tasks")
    failed = serializers.IntegerField(help_text="Number of failed tasks")
    pending = serializers.IntegerField(help_text="Number of pending/queued tasks")
    processing = serializers.IntegerField(help_text="Number of processing tasks")
    percent = serializers.IntegerField(help_text="Completion percentage (0-100)")

class OperationListResponseSerializer(serializers.Serializer):
    """Response for list_operations endpoint."""
    operations = BatchOperationSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of operations in current page")
    total = serializers.IntegerField(help_text="Total number of operations matching filters")

class OperationDetailResponseSerializer(serializers.Serializer):
    """Response for get_operation endpoint."""
    operation = BatchOperationSerializer()
    execution_plan = ExecutionPlanSerializer(required=False)
    bindings = ExecutionBindingSerializer(many=True, required=False)
    tasks = TaskSerializer(many=True, required=False, help_text="Task details (if include_tasks=true)")
    progress = OperationProgressSerializer()

class OperationCancelResponseSerializer(serializers.Serializer):
    """Response for cancel_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the cancelled operation")
    cancelled = serializers.BooleanField(help_text="Whether cancellation was successful")
    message = serializers.CharField(help_text="Status message")

class OperationStreamStatusSerializer(serializers.Serializer):
    """Response for operation stream status."""
    active_streams = serializers.IntegerField(help_text="Active SSE streams for current user")
    max_streams = serializers.IntegerField(help_text="Maximum allowed SSE streams")

class OperationMuxStreamStatusSerializer(serializers.Serializer):
    """Response for multiplex stream status."""
    active_streams = serializers.IntegerField(help_text="Active multiplex SSE streams for current user")
    max_streams = serializers.IntegerField(help_text="Maximum allowed multiplex SSE streams")
    active_subscriptions = serializers.IntegerField(help_text="Active operation subscriptions for user")
    max_subscriptions = serializers.IntegerField(help_text="Maximum allowed subscriptions")

class OperationCatalogItemSerializer(serializers.Serializer):
    """Operation catalog entry for Operations Center."""
    id = serializers.CharField(help_text="Catalog item identifier")
    kind = serializers.ChoiceField(choices=["operation", "template"])
    operation_type = serializers.CharField(required=False, allow_null=True)
    template_id = serializers.CharField(required=False, allow_null=True)
    label = serializers.CharField()
    description = serializers.CharField()
    driver = serializers.CharField(help_text="Driver group (ras/odata/cli/ibcmd/workflow)")
    category = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    requires_config = serializers.BooleanField()
    has_ui_form = serializers.BooleanField()
    icon = serializers.CharField(required=False, allow_null=True)
    deprecated = serializers.BooleanField()
    deprecated_message = serializers.CharField(required=False, allow_null=True)

class OperationCatalogResponseSerializer(serializers.Serializer):
    """Response for operation catalog endpoint."""
    items = OperationCatalogItemSerializer(many=True)
    count = serializers.IntegerField()

class CliCommandSerializer(serializers.Serializer):
    """Single CLI command descriptor."""
    id = serializers.CharField()
    label = serializers.CharField()
    usage = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    params = serializers.ListField(child=serializers.DictField(), required=False)
    source_section_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_section = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class CliCommandCatalogResponseSerializer(serializers.Serializer):
    """Response for CLI command catalog endpoint."""
    version = serializers.CharField()
    source = serializers.CharField()
    generated_at = serializers.CharField(required=False, allow_blank=True)
    commands = CliCommandSerializer(many=True)

class DriverCatalogV2SourceSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    doc_id = serializers.CharField(required=False, allow_blank=True)
    section_prefix = serializers.CharField(required=False, allow_blank=True)
    doc_url = serializers.CharField(required=False, allow_blank=True)
    hint = serializers.CharField(required=False, allow_blank=True)

class DriverCommandParamV2Serializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["flag", "positional"])
    flag = serializers.CharField(required=False, allow_blank=True)
    position = serializers.IntegerField(required=False, allow_null=True)
    required = serializers.BooleanField()
    expects_value = serializers.BooleanField()
    label = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    value_type = serializers.ChoiceField(
        choices=["string", "int", "float", "bool"],
        required=False,
        allow_null=True,
    )
    enum = serializers.ListField(child=serializers.CharField(), required=False)
    default = serializers.JSONField(required=False)
    repeatable = serializers.BooleanField(required=False)
    sensitive = serializers.BooleanField(required=False)
    artifact = serializers.JSONField(required=False)
    ui = serializers.JSONField(required=False)
    disabled = serializers.BooleanField(required=False)

class DriverCommandV2Serializer(serializers.Serializer):
    label = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    argv = serializers.ListField(child=serializers.CharField())
    scope = serializers.ChoiceField(choices=["per_database", "global"])
    risk_level = serializers.ChoiceField(choices=["safe", "dangerous"])
    params_by_name = serializers.DictField(child=DriverCommandParamV2Serializer(), required=False)
    ui = serializers.JSONField(required=False)
    source_section = serializers.CharField(required=False, allow_blank=True)
    disabled = serializers.BooleanField(required=False)
    permissions = serializers.JSONField(required=False)

class DriverCatalogV2Serializer(serializers.Serializer):
    catalog_version = serializers.IntegerField()
    driver = serializers.CharField()
    platform_version = serializers.CharField(required=False, allow_blank=True)
    driver_schema = serializers.DictField(required=False)
    source = DriverCatalogV2SourceSerializer(required=False)
    generated_at = serializers.CharField(required=False, allow_blank=True)
    commands_by_id = serializers.DictField(child=DriverCommandV2Serializer())

class DriverCommandsResponseV2Serializer(serializers.Serializer):
    driver = serializers.CharField()
    base_version = serializers.CharField(required=False, allow_blank=True)
    overrides_version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    generated_at = serializers.CharField(required=False, allow_blank=True)
    catalog = DriverCatalogV2Serializer()

class DriverCommandShortcutSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    driver = serializers.CharField()
    command_id = serializers.CharField()
    title = serializers.CharField()
    payload = serializers.JSONField(required=False)
    catalog_base_version = serializers.CharField(required=False, allow_blank=True)
    catalog_overrides_version = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

class ListDriverCommandShortcutsResponseSerializer(serializers.Serializer):
    items = DriverCommandShortcutSerializer(many=True)
    count = serializers.IntegerField()

class CreateDriverCommandShortcutRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=[("ibcmd", "ibcmd")])
    command_id = serializers.CharField()
    title = serializers.CharField(max_length=255)
    payload = serializers.JSONField(required=False)

class DeleteDriverCommandShortcutRequestSerializer(serializers.Serializer):
    shortcut_id = serializers.UUIDField()

class ExecuteOperationRequestSerializer(serializers.Serializer):
    """Request body for execute_operation endpoint."""
    RAS_OPERATION_TYPES = [
        ('lock_scheduled_jobs', 'Lock Scheduled Jobs'),
        ('unlock_scheduled_jobs', 'Unlock Scheduled Jobs'),
        ('block_sessions', 'Block Sessions'),
        ('unblock_sessions', 'Unblock Sessions'),
        ('terminate_sessions', 'Terminate Sessions'),
    ]
    ODATA_OPERATION_TYPES = [
        ('create', 'Create Records'),
        ('update', 'Update Records'),
        ('delete', 'Delete Records'),
        ('query', 'Query Records'),
    ]
    CLI_OPERATION_TYPES = [
        ('designer_cli', 'Designer CLI'),
    ]

    operation_type = serializers.ChoiceField(
        choices=(
            RAS_OPERATION_TYPES
            + ODATA_OPERATION_TYPES
            + CLI_OPERATION_TYPES
        ),
        help_text="Operation type to execute"
    )
    database_ids = serializers.ListField(
        child=serializers.UUIDField(format='hex_verbose'),
        min_length=1,
        max_length=500,
        help_text="List of database UUIDs"
    )
    config = serializers.DictField(
        required=False,
        default=dict,
        help_text="Operation-specific configuration (e.g., message for block_sessions)"
    )

class ExecuteOperationResponseSerializer(serializers.Serializer):
    """Response for execute_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the created operation")
    status = serializers.CharField(help_text="Operation status (queued)")
    total_tasks = serializers.IntegerField(help_text="Number of tasks created")
    message = serializers.CharField(help_text="Status message")

class ExecuteOperationThrottle(UserRateThrottle):
    """Rate limit: 30 operations per minute per user."""
    rate = '30/min'
    scope = 'execute_operation'

class IbcmdCliConnectionOfflineSerializer(serializers.Serializer):
    config = serializers.CharField(required=False, allow_blank=False)
    data = serializers.CharField(required=False, allow_blank=False)
    dbms = serializers.CharField(required=False, allow_blank=False)
    db_server = serializers.CharField(required=False, allow_blank=False)
    db_name = serializers.CharField(required=False, allow_blank=False)
    db_path = serializers.CharField(required=False, allow_blank=False)
    db_user = serializers.CharField(required=False, allow_blank=False)
    db_pwd = serializers.CharField(required=False, allow_blank=False, write_only=True)
    ftext2_data = serializers.CharField(required=False, allow_blank=False)
    ftext_data = serializers.CharField(required=False, allow_blank=False)
    lock = serializers.CharField(required=False, allow_blank=False)
    log_data = serializers.CharField(required=False, allow_blank=False)
    openid_data = serializers.CharField(required=False, allow_blank=False)
    session_data = serializers.CharField(required=False, allow_blank=False)
    stt_data = serializers.CharField(required=False, allow_blank=False)
    system = serializers.CharField(required=False, allow_blank=False)
    temp = serializers.CharField(required=False, allow_blank=False)
    users_data = serializers.CharField(required=False, allow_blank=False)

class IbcmdCliConnectionSerializer(serializers.Serializer):
    remote = serializers.CharField(required=False, allow_blank=False)
    pid = serializers.IntegerField(required=False, allow_null=True)
    offline = IbcmdCliConnectionOfflineSerializer(required=False)

class IbcmdCliIbAuthSerializer(serializers.Serializer):
    STRATEGY_CHOICES = [
        ("actor", "actor"),
        ("service", "service"),
        ("none", "none"),
    ]
    strategy = serializers.ChoiceField(choices=STRATEGY_CHOICES, required=False)

class IbcmdCliDbmsAuthSerializer(serializers.Serializer):
    STRATEGY_CHOICES = [
        ("actor", "actor"),
        ("service", "service"),
    ]
    strategy = serializers.ChoiceField(choices=STRATEGY_CHOICES, required=False)

class ExecuteIbcmdCliOperationRequestSerializer(serializers.Serializer):
    """Request body for execute_ibcmd_cli_operation endpoint."""

    MODE_CHOICES = [
        ("guided", "guided"),
        ("manual", "manual"),
    ]

    command_id = serializers.CharField(help_text="IBCMD command id from driver catalog v2")
    mode = serializers.ChoiceField(choices=MODE_CHOICES, default="guided", required=False)

    database_ids = serializers.ListField(
        child=serializers.UUIDField(format='hex_verbose'),
        required=False,
        allow_empty=True,
        max_length=500,
        help_text="Target databases for per_database commands (empty for global)",
    )
    auth_database_id = serializers.UUIDField(
        required=False,
        help_text="Anchor database for global commands (RBAC + infobase user mapping)",
    )

    connection = IbcmdCliConnectionSerializer(required=False)
    ib_auth = IbcmdCliIbAuthSerializer(required=False)
    dbms_auth = IbcmdCliDbmsAuthSerializer(required=False)
    params = serializers.DictField(required=False, default=dict)
    additional_args = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    stdin = serializers.CharField(required=False, allow_blank=True, default="")

    confirm_dangerous = serializers.BooleanField(required=False, default=False)
    timeout_seconds = serializers.IntegerField(required=False, min_value=1, max_value=3600, default=900)

class ExecuteIbcmdCliOperationThrottle(UserRateThrottle):
    """Rate limit: 10 ibcmd_cli operations per minute per user."""
    rate = '10/min'
    scope = 'execute_ibcmd_cli_operation'

class SSETicketRequestSerializer(serializers.Serializer):
    """Request body for get_stream_ticket endpoint."""
    operation_id = serializers.CharField(help_text="Operation ID to subscribe to")
    client_id = serializers.CharField(required=False, help_text="Optional client identifier")

class SSETicketResponseSerializer(serializers.Serializer):
    """Response for get_stream_ticket endpoint."""
    ticket = serializers.CharField(help_text="Short-lived ticket for SSE connection")
    expires_in = serializers.IntegerField(help_text="Seconds until ticket expires")
    stream_url = serializers.CharField(help_text="SSE endpoint URL to connect to")

class OperationMuxSubscribeSerializer(serializers.Serializer):
    """Request body for multiplex stream subscribe."""
    operation_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        help_text="Operation IDs to subscribe to",
    )

class OperationMuxUnsubscribeSerializer(serializers.Serializer):
    """Request body for multiplex stream unsubscribe."""
    operation_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        help_text="Operation IDs to unsubscribe from",
    )

class OperationMuxTicketRequestSerializer(serializers.Serializer):
    """Request body for multiplex stream ticket."""
    client_id = serializers.CharField(required=False, help_text="Optional client identifier")

class CancelOperationRequestSerializer(serializers.Serializer):
    """Request body for cancel_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the operation to cancel (UUID)")

import uuid
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from encrypted_model_fields.fields import EncryptedCharField


def generate_database_id() -> str:
    return str(uuid.uuid4())


class Cluster(models.Model):
    """
    Represents a 1C:Enterprise server cluster.

    A cluster is a logical grouping of 1C infobases managed by a single
    RAS (Remote Administration Server).

    Hierarchy:
        RAS Server (localhost:1545)
          └── Cluster (UUID, name)
              └── Infobases (many)
    """

    # Identity (from 1C or auto-generated)
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=True,  # Allow override when syncing from 1C
        help_text="Cluster UUID (auto-generated or from 1C)"
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Cluster name from 1C"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description"
    )

    # RAS Connection
    ras_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="RAS host (e.g., localhost, srv1c, 192.168.1.100)"
    )
    ras_port = models.IntegerField(
        null=True,
        blank=True,
        help_text="RAS port (default: 1545)"
    )
    ras_server = models.CharField(
        max_length=255,
        default="localhost:1545",
        help_text="RAS server address (host:port)"
    )
    ras_cluster_uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID кластера в RAS (заполняется при первой успешной синхронизации)"
    )

    # Legacy service URL (unused by worker-driven RAS operations)
    cluster_service_url = models.URLField(
        max_length=512,
        help_text="Legacy URL for cluster integrations (currently unused)"
    )

    # Cluster Authentication (optional)
    cluster_user = models.CharField(
        max_length=255,
        blank=True,
        help_text="Cluster admin username (if required)"
    )
    cluster_pwd = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text="Cluster admin password (encrypted)"
    )

    # 1C Server Ports (for DESIGNER/IBCMD)
    rmngr_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="RMNGR host (cluster manager)"
    )
    rmngr_port = models.IntegerField(
        null=True,
        blank=True,
        help_text="RMNGR port (default: 1541)"
    )
    ragent_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="RAGENT host (server agent)"
    )
    ragent_port = models.IntegerField(
        null=True,
        blank=True,
        help_text="RAGENT port (default: 1540)"
    )
    rphost_port_from = models.IntegerField(
        null=True,
        blank=True,
        help_text="RPHOST port range start (default: 1560)"
    )
    rphost_port_to = models.IntegerField(
        null=True,
        blank=True,
        help_text="RPHOST port range end (default: 1591)"
    )

    # Status
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_ERROR = 'error'
    STATUS_MAINTENANCE = 'maintenance'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_ERROR, 'Error'),
        (STATUS_MAINTENANCE, 'Maintenance'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True
    )

    # Sync tracking
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last sync timestamp"
    )
    last_sync_status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('pending', 'Pending'),
        ],
        default='pending',
        db_index=True
    )
    last_sync_error = models.TextField(
        blank=True,
        help_text="Error message from last sync"
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional cluster metadata"
    )

    # Health Check
    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Number of consecutive health check failures"
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last health check timestamp"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clusters'
        ordering = ['name']
        indexes = [
            models.Index(fields=['status', 'last_sync_status']),
            models.Index(fields=['last_sync']),
            models.Index(fields=['ras_server']),
        ]
        verbose_name = '1C Cluster'
        verbose_name_plural = '1C Clusters'
        permissions = (
            ("operate_cluster", "Can operate cluster"),
            ("manage_cluster", "Can manage cluster"),
            ("admin_cluster", "Can administer cluster"),
        )
        constraints = [
            models.UniqueConstraint(
                fields=['ras_server', 'name'],
                name='unique_cluster_per_ras_server'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.ras_server})"

    @staticmethod
    def _parse_host_port(value: str):
        if not value:
            return "", None
        if ":" not in value:
            return value, None
        host, port_str = value.rsplit(":", 1)
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = None
        return host, port

    @staticmethod
    def _compose_host_port(host: str, port: int) -> str:
        if host and port:
            return f"{host}:{port}"
        if host:
            return host
        return ""

    def _normalize_ports(self):
        if not self.ras_port:
            self.ras_port = 1545
        if not self.rmngr_port:
            self.rmngr_port = 1541
        if not self.ragent_port:
            self.ragent_port = 1540
        if not self.rphost_port_from:
            self.rphost_port_from = 1560
        if not self.rphost_port_to:
            self.rphost_port_to = 1591

    def _normalize_hosts(self):
        if self.ras_server and not self.ras_host:
            host, port = self._parse_host_port(self.ras_server)
            if host:
                self.ras_host = host
            if port and not self.ras_port:
                self.ras_port = port
        if self.ras_host:
            if not self.rmngr_host:
                self.rmngr_host = self.ras_host
            if not self.ragent_host:
                self.ragent_host = self.ras_host

    def save(self, *args, **kwargs):
        if isinstance(self.id, str):
            self.id = uuid.UUID(self.id)
        self._normalize_hosts()
        self._normalize_ports()
        if self.ras_host and self.ras_port:
            self.ras_server = self._compose_host_port(self.ras_host, self.ras_port)
        super().save(*args, **kwargs)

    @property
    def infobase_count(self) -> int:
        """Get number of infobases in this cluster."""
        return self.databases.count()

    @property
    def healthy_infobase_count(self) -> int:
        """Get number of healthy infobases."""
        return self.databases.filter(
            last_check_status=Database.HEALTH_OK
        ).count()

    @property
    def is_healthy(self) -> bool:
        """Check if cluster is healthy."""
        return (
            self.status == self.STATUS_ACTIVE and
            self.last_sync_status == 'success'
        )

    def mark_sync(self, success: bool, error_message: str = None):
        """Update last sync status."""
        self.last_sync = timezone.now()
        self.last_sync_status = 'success' if success else 'failed'

        if not success and error_message:
            self.last_sync_error = error_message
            if self.status == self.STATUS_ACTIVE:
                self.status = self.STATUS_ERROR
        else:
            self.last_sync_error = ''
            if self.status == self.STATUS_ERROR:
                self.status = self.STATUS_ACTIVE

        self.save(update_fields=[
            'last_sync',
            'last_sync_status',
            'last_sync_error',
            'status',
            'updated_at'
        ])

    def mark_health_check(self, success: bool, error_message: str = None):
        """
        Update health check status.

        Args:
            success: Whether health check succeeded
            error_message: Error message if failed (optional)
        """
        self.last_health_check = timezone.now()

        if success:
            self.consecutive_failures = 0
            if self.status == self.STATUS_ERROR:
                self.status = self.STATUS_ACTIVE  # Восстановление
            self.last_sync_error = ''
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.status = self.STATUS_ERROR
            if error_message:
                self.last_sync_error = error_message

        self.save(update_fields=[
            'last_health_check',
            'consecutive_failures',
            'status',
            'last_sync_error',
            'updated_at'
        ])


class Database(models.Model):
    """Represents a 1C database configuration with health monitoring."""

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_ERROR = 'error'
    STATUS_MAINTENANCE = 'maintenance'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_ERROR, 'Error'),
        (STATUS_MAINTENANCE, 'Maintenance'),
    ]

    HEALTH_OK = 'ok'
    HEALTH_DEGRADED = 'degraded'
    HEALTH_DOWN = 'down'
    HEALTH_UNKNOWN = 'unknown'

    HEALTH_STATUS_CHOICES = [
        (HEALTH_OK, 'OK'),
        (HEALTH_DEGRADED, 'Degraded'),
        (HEALTH_DOWN, 'Down'),
        (HEALTH_UNKNOWN, 'Unknown'),
    ]

    # Identity
    id = models.CharField(max_length=64, primary_key=True, default=generate_database_id, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)

    # Connection
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=80)
    base_name = models.CharField(
        max_length=255,
        default='',
        blank=True,
        help_text="Infobase name from 1C cluster"
    )
    odata_url = models.URLField(max_length=512)
    username = models.CharField(max_length=255)
    password = EncryptedCharField(max_length=255)  # Encrypted with FIELD_ENCRYPTION_KEY

    # 1C Server connection parameters (для DESIGNER режима)
    server_address = models.CharField(
        max_length=255,
        default='localhost',
        help_text="Адрес сервера 1С (например: localhost, srv1c, 192.168.1.100)"
    )
    server_port = models.IntegerField(
        default=1540,
        help_text="Порт сервера 1С (обычно 1540 или 1541)"
    )
    infobase_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Имя информационной базы на сервере 1С (если отличается от name)"
    )

    # RAS/Cluster metadata (для workflow управления регламентами и сессиями)
    ras_cluster_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID кластера 1С в RAS (для блокировки регламентных заданий)"
    )
    ras_infobase_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID информационной базы в RAS (может отличаться от primary key)"
    )

    # Connection Pool Settings
    max_connections = models.IntegerField(default=10, help_text="Maximum concurrent connections")
    connection_timeout = models.IntegerField(default=30, help_text="Connection timeout in seconds")

    # Cluster relationship
    cluster = models.ForeignKey(
        'Cluster',
        on_delete=models.CASCADE,
        related_name='databases',
        null=True,  # Nullable для обратной совместимости (будет убрано в миграции)
        blank=True,
        help_text="1C Cluster this infobase belongs to"
    )

    # Status & Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    version = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata")

    # Health Check
    last_check = models.DateTimeField(null=True, blank=True)
    last_check_status = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS_CHOICES,
        default=HEALTH_UNKNOWN,
        db_index=True
    )
    consecutive_failures = models.IntegerField(default=0)
    health_check_enabled = models.BooleanField(default=True)

    # Performance Tracking
    avg_response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Average response time in milliseconds"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'databases'
        ordering = ['name']
        indexes = [
            models.Index(fields=['cluster', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['last_check']),
            models.Index(fields=['consecutive_failures']),
            models.Index(fields=['base_name']),
        ]
        verbose_name = '1C Database'
        verbose_name_plural = '1C Databases'
        permissions = (
            ("operate_database", "Can operate database"),
            ("manage_database", "Can manage database"),
            ("admin_database", "Can administer database"),
        )

    def __str__(self):
        if self.cluster:
            return f"{self.name} ({self.cluster.name})"
        return self.name  # Fallback для старых записей

    def get_odata_endpoint(self, entity: str) -> str:
        """
        Construct OData endpoint URL for a specific entity.

        Args:
            entity: Entity name (e.g., 'Справочник_Пользователи')

        Returns:
            Full OData endpoint URL
        """
        base_url = self.odata_url.rstrip('/')
        return f"{base_url}/{entity}"

    def mark_health_check(self, success: bool, response_time: float = None):
        """
        Update health check status.

        Args:
            success: Whether health check succeeded
            response_time: Response time in milliseconds (optional)
        """
        self.last_check = timezone.now()

        if success:
            self.last_check_status = self.HEALTH_OK
            self.consecutive_failures = 0

            if response_time is not None:
                # Calculate moving average (simple exponential smoothing)
                if self.avg_response_time is None:
                    self.avg_response_time = response_time
                else:
                    alpha = 0.3  # Smoothing factor
                    self.avg_response_time = (alpha * response_time) + ((1 - alpha) * self.avg_response_time)
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.last_check_status = self.HEALTH_DOWN
            else:
                self.last_check_status = self.HEALTH_DEGRADED

        self.save(update_fields=[
            'last_check',
            'last_check_status',
            'consecutive_failures',
            'avg_response_time',
            'updated_at'
        ])

    @property
    def is_healthy(self) -> bool:
        """Check if database is healthy."""
        return self.last_check_status == self.HEALTH_OK

    @property
    def connection_string(self) -> str:
        """Get connection info (without password)."""
        return f"{self.username}@{self.host}:{self.port}/{self.base_name}"

    @property
    def connection_string_1c(self) -> str:
        """
        Генерирует connection string для подключения через DESIGNER.
        Формат: Srvr="server:port";Ref="infobase_name";
        """
        # Используем infobase_name если задано, иначе name
        ib_name = self.infobase_name if self.infobase_name else self.name
        if self.cluster and self.cluster.rmngr_host and self.cluster.rmngr_port:
            server_part = f"{self.cluster.rmngr_host}:{self.cluster.rmngr_port}"
        elif self.server_port and self.server_address:
            if self.server_port != 1540:
                server_part = f"{self.server_address}:{self.server_port}"
            else:
                server_part = self.server_address
        else:
            server_part = self.server_address

        return f'Srvr="{server_part}";Ref="{ib_name}";'

    @property
    def designer_path(self) -> str:
        """
        Генерирует путь для параметра /S в DESIGNER.
        Формат: server\infobase или server:port\infobase
        """
        ib_name = self.infobase_name if self.infobase_name else self.name
        if self.cluster and self.cluster.rmngr_host and self.cluster.rmngr_port:
            return f"{self.cluster.rmngr_host}:{self.cluster.rmngr_port}\\{ib_name}"
        if self.server_port and self.server_port != 1540:
            return f"{self.server_address}:{self.server_port}\\{ib_name}"
        return f"{self.server_address}\\{ib_name}"


class DatabaseGroup(models.Model):
    """Represents a group of databases for bulk operations."""

    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    databases = models.ManyToManyField(Database, related_name='groups')
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'database_groups'
        ordering = ['name']
        verbose_name = 'Database Group'
        verbose_name_plural = 'Database Groups'

    def __str__(self):
        return self.name

    @property
    def database_count(self) -> int:
        """Get number of databases in group."""
        return self.databases.count()

    @property
    def healthy_count(self) -> int:
        """Get number of healthy databases in group."""
        return self.databases.filter(
            last_check_status=Database.HEALTH_OK
        ).count()


class StatusHistory(models.Model):
    """История изменений статусов для всех типов объектов"""

    # Generic Foreign Key для поддержки разных типов объектов
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Статусные данные
    old_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    reason = models.TextField(blank=True)  # Причина смены
    metadata = models.JSONField(default=dict)  # response_time, error_message и т.д.

    # Timestamps
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'status_history'
        indexes = [
            models.Index(fields=['content_type', 'object_id', '-changed_at']),
            models.Index(fields=['new_status', '-changed_at']),
        ]
        ordering = ['-changed_at']
        verbose_name = 'Status History'
        verbose_name_plural = 'Status Histories'

    def __str__(self):
        return f"{self.content_type} {self.object_id}: {self.old_status} → {self.new_status}"


# =============================================================================
# RBAC Models for Database Access Control
# =============================================================================

class PermissionLevel(models.IntegerChoices):
    """
    Hierarchical permission levels. Higher includes all lower.

    - VIEW (10): Read-only access
    - OPERATE (20): Execute operations (lock/unlock/block/terminate)
    - MANAGE (30): Edit settings, install extensions
    - ADMIN (40): Full control including delete
    """
    VIEW = 10, 'View'
    OPERATE = 20, 'Operate'
    MANAGE = 30, 'Manage'
    ADMIN = 40, 'Admin'


class ClusterPermission(models.Model):
    """
    User permission for an entire cluster.
    Grants access to all databases within the cluster.
    """
    from django.conf import settings as django_settings

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cluster_permissions'
    )
    cluster = models.ForeignKey(
        'Cluster',
        on_delete=models.CASCADE,
        related_name='user_permissions'
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW
    )

    # Audit fields
    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'databases_cluster_permissions'
        unique_together = ['user', 'cluster']
        indexes = [
            models.Index(fields=['user', 'cluster'], name='cp_user_cluster_idx'),
            models.Index(fields=['cluster', 'level'], name='cp_cluster_level_idx'),
        ]
        permissions = (
            ("manage_rbac", "Can manage RBAC"),
        )

    def __str__(self):
        return f"{self.user.username} -> {self.cluster.name} ({self.get_level_display()})"


class DatabasePermission(models.Model):
    """
    User permission for a specific database.
    Takes precedence over cluster-level permission (max of both).
    """
    from django.conf import settings as django_settings

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='database_permissions'
    )
    database = models.ForeignKey(
        'Database',
        on_delete=models.CASCADE,
        related_name='user_permissions'
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW
    )

    # Audit fields
    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'databases_database_permissions'
        unique_together = ['user', 'database']
        indexes = [
            models.Index(fields=['user', 'database'], name='dp_user_db_idx'),
            models.Index(fields=['database', 'level'], name='dp_db_level_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.database.name} ({self.get_level_display()})"


# =============================================================================
# Infobase Users (manual mapping)
# =============================================================================

class InfobaseAuthType(models.TextChoices):
    LOCAL = "local", "Local"
    AD = "ad", "Active Directory"
    SERVICE = "service", "Service"
    OTHER = "other", "Other"


class InfobaseUserMapping(models.Model):
    """Manual mapping between CC users and 1C infobase users."""

    from django.conf import settings as django_settings

    database = models.ForeignKey(
        'Database',
        on_delete=models.CASCADE,
        related_name='ib_user_mappings'
    )
    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ib_user_mappings'
    )
    ib_username = models.CharField(max_length=128)
    ib_display_name = models.CharField(max_length=255, blank=True)
    ib_roles = models.JSONField(default=list, blank=True)
    ib_password = EncryptedCharField(max_length=255, blank=True)
    auth_type = models.CharField(
        max_length=32,
        choices=InfobaseAuthType.choices,
        default=InfobaseAuthType.LOCAL,
    )
    is_service = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ib_user_mappings_created'
    )
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ib_user_mappings_updated'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'databases_ib_user_mappings'
        unique_together = ['database', 'ib_username']
        indexes = [
            models.Index(fields=['database', 'ib_username'], name='ib_user_db_name_idx'),
            models.Index(fields=['database', 'auth_type'], name='ib_user_db_auth_idx'),
        ]

    def __str__(self):
        return f"{self.database.name}: {self.ib_username}"

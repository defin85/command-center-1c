import uuid
from typing import Optional
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from encrypted_model_fields.fields import EncryptedCharField


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
    ras_server = models.CharField(
        max_length=255,
        default="localhost:1545",
        help_text="RAS server address (host:port)"
    )

    # Installation Service
    cluster_service_url = models.URLField(
        max_length=512,
        help_text="URL of installation-service managing this cluster"
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
        constraints = [
            models.UniqueConstraint(
                fields=['ras_server', 'name'],
                name='unique_cluster_per_ras_server'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.ras_server})"

    @property
    def infobase_count(self) -> int:
        """Get number of infobases in this cluster."""
        return self.databases.count()

    @property
    def healthy_infobase_count(self) -> int:
        """Get number of healthy infobases."""
        return self.databases.filter(
            last_check_status='ok',
            status=Database.STATUS_ACTIVE
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
    id = models.CharField(max_length=64, primary_key=True)
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

            # НОВОЕ: Восстановление из ERROR в ACTIVE
            if self.status == self.STATUS_ERROR:
                self.status = self.STATUS_ACTIVE

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
                self.status = self.STATUS_ERROR
            else:
                self.last_check_status = self.HEALTH_DEGRADED

        self.save(update_fields=[
            'last_check',
            'last_check_status',
            'consecutive_failures',
            'avg_response_time',
            'status',
            'updated_at'
        ])

    @property
    def is_healthy(self) -> bool:
        """Check if database is healthy."""
        return self.last_check_status == self.HEALTH_OK and self.status == self.STATUS_ACTIVE

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

        # Добавляем порт только если не default (1540)
        if self.server_port and self.server_port != 1540:
            server_part = f"{self.server_address}:{self.server_port}"
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

        if self.server_port and self.server_port != 1540:
            return f"{self.server_address}:{self.server_port}\\{ib_name}"
        else:
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
            last_check_status=Database.HEALTH_OK,
            status=Database.STATUS_ACTIVE
        ).count()


class ExtensionInstallation(models.Model):
    """Статус установки расширения на базу 1С"""

    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    database = models.ForeignKey(
        Database,
        on_delete=models.CASCADE,
        related_name='extension_installations'
    )
    extension_name = models.CharField(max_length=255, default="ODataAutoConfig")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'databases_extension_installation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['database', 'extension_name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['database', 'extension_name'],
                condition=models.Q(status__in=['pending', 'in_progress']),
                name='unique_active_installation'
            )
        ]

    def __str__(self):
        return f"{self.extension_name} on {self.database.name} - {self.status}"


class BatchService(models.Model):
    """
    Represents a Batch Service instance for parallel batch operations.

    Batch Service is a Go microservice that handles parallel batch operations
    across multiple 1C databases using goroutine pools and OData protocol.

    Hierarchy:
        BatchService (URL)
          └── Manages parallel batch operations for multiple databases
    """

    # Status Choices (unified with Cluster/Database)
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

    # Health Status Choices
    HEALTH_HEALTHY = 'healthy'
    HEALTH_UNHEALTHY = 'unhealthy'
    HEALTH_UNKNOWN = 'unknown'

    HEALTH_STATUS_CHOICES = [
        (HEALTH_HEALTHY, 'Healthy'),
        (HEALTH_UNHEALTHY, 'Unhealthy'),
        (HEALTH_UNKNOWN, 'Unknown'),
    ]

    # Identity
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Batch Service UUID"
    )
    name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Batch Service instance name"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description"
    )

    # Connection
    url = models.URLField(
        max_length=512,
        unique=True,
        help_text="Batch Service endpoint URL (e.g., http://localhost:8087)"
    )

    # Status (NEW - unified with Cluster/Database)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
        help_text="Service status (unified with Cluster/Database)"
    )

    # Health Check
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last health check timestamp"
    )
    last_health_status = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS_CHOICES,
        default=HEALTH_UNKNOWN,
        db_index=True,
        help_text="Result of last health check"
    )
    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Number of consecutive health check failures"
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (e.g., last_error, performance stats)"
    )

    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="Creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    class Meta:
        db_table = 'batch_services'
        ordering = ['name']  # Removed '-status' (alphabetic sorting is not semantic)
        indexes = [
            models.Index(fields=['status', 'last_health_status']),
            models.Index(fields=['last_health_check']),
        ]
        verbose_name = 'Batch Service'
        verbose_name_plural = 'Batch Services'

    def __str__(self):
        status = self.get_status_display().upper()
        return f"{self.name} ({status})"

    @property
    def is_active_compat(self) -> bool:
        """
        Backward compatibility property.
        Returns True if status='active'.
        """
        return self.status == self.STATUS_ACTIVE

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy and available."""
        return (
            self.status == self.STATUS_ACTIVE and
            self.last_health_status == self.HEALTH_HEALTHY
        )

    def mark_health_check(self, success: bool, error_message: str = None):
        """
        Mark health check result and update status.

        Auto-recovery pattern (same as Cluster):
        - 3 consecutive failures → status='error' (automatic)
        - Success when status='error' → status='active' (automatic recovery)

        Args:
            success: Whether health check succeeded
            error_message: Error message if failed (optional)
        """
        self.last_health_check = timezone.now()

        if success:
            self.consecutive_failures = 0
            self.last_health_status = self.HEALTH_HEALTHY

            # Auto-recovery from ERROR status
            if self.status == self.STATUS_ERROR:
                self.status = self.STATUS_ACTIVE

            # Clear last error on success
            if 'last_error' in self.metadata:
                del self.metadata['last_error']
        else:
            self.consecutive_failures += 1

            if self.consecutive_failures >= 3:
                self.last_health_status = self.HEALTH_UNHEALTHY
                # Mark as ERROR after 3 consecutive failures
                self.status = self.STATUS_ERROR
            else:
                self.last_health_status = self.HEALTH_UNHEALTHY

            # Store error message in metadata
            if error_message:
                self.metadata['last_error'] = error_message

        self.save(update_fields=[
            'last_health_check',
            'last_health_status',
            'consecutive_failures',
            'status',
            'metadata',
            'updated_at'
        ])

    @classmethod
    def get_active(cls) -> Optional['BatchService']:
        """
        Get first active and healthy BatchService instance.

        Returns:
            First active and healthy BatchService or None if not found
        """
        return cls.objects.filter(
            status=cls.STATUS_ACTIVE,
            last_health_status=cls.HEALTH_HEALTHY
        ).first()

    @classmethod
    def get_or_raise(cls, service_id: str = None) -> 'BatchService':
        """
        Get active BatchService instance or raise error.

        Args:
            service_id: Optional service UUID to get specific service

        Returns:
            Active and healthy BatchService

        Raises:
            ValueError: If no active BatchService found
        """
        if service_id:
            try:
                service = cls.objects.get(id=service_id, status=cls.STATUS_ACTIVE)
                return service
            except cls.DoesNotExist:
                raise ValueError(f"Active BatchService with id={service_id} not found")

        service = cls.get_active()
        if not service:
            raise ValueError(
                "No active Batch Service available. "
                "Please configure and activate a BatchService instance."
            )
        return service


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

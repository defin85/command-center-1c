import uuid
from django.db import models
from django.utils import timezone
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

    def mark_health_check(self, success: bool, response_time: float = None, error_message: str = None):
        """
        Update health check status.

        Args:
            success: Whether health check succeeded
            response_time: Response time in milliseconds (optional)
            error_message: Error message if failed (optional)
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

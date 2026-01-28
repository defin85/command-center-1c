import uuid

from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField


def generate_database_id() -> str:
    return str(uuid.uuid4())


class Database(models.Model):
    """Represents a 1C database configuration with health monitoring."""

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_ERROR = "error"
    STATUS_MAINTENANCE = "maintenance"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_ERROR, "Error"),
        (STATUS_MAINTENANCE, "Maintenance"),
    ]

    HEALTH_OK = "ok"
    HEALTH_DEGRADED = "degraded"
    HEALTH_DOWN = "down"
    HEALTH_UNKNOWN = "unknown"

    HEALTH_STATUS_CHOICES = [
        (HEALTH_OK, "OK"),
        (HEALTH_DEGRADED, "Degraded"),
        (HEALTH_DOWN, "Down"),
        (HEALTH_UNKNOWN, "Unknown"),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=generate_database_id, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)

    host = models.CharField(max_length=255)
    port = models.IntegerField(default=80)
    base_name = models.CharField(
        max_length=255,
        default="",
        blank=True,
        help_text="Infobase name from 1C cluster",
    )
    odata_url = models.URLField(max_length=512)
    username = models.CharField(max_length=255)
    password = EncryptedCharField(max_length=255)

    server_address = models.CharField(
        max_length=255,
        default="localhost",
        help_text="Адрес сервера 1С (например: localhost, srv1c, 192.168.1.100)",
    )
    server_port = models.IntegerField(
        default=1540,
        help_text="Порт сервера 1С (обычно 1540 или 1541)",
    )
    infobase_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Имя информационной базы на сервере 1С (если отличается от name)",
    )

    ras_cluster_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID кластера 1С в RAS (для блокировки регламентных заданий)",
    )
    ras_infobase_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID информационной базы в RAS (может отличаться от primary key)",
    )

    max_connections = models.IntegerField(default=10, help_text="Maximum concurrent connections")
    connection_timeout = models.IntegerField(default=30, help_text="Connection timeout in seconds")

    cluster = models.ForeignKey(
        "Cluster",
        on_delete=models.CASCADE,
        related_name="databases",
        null=True,
        blank=True,
        help_text="1C Cluster this infobase belongs to",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    version = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata")

    last_check = models.DateTimeField(null=True, blank=True)
    last_check_status = models.CharField(
        max_length=20,
        choices=HEALTH_STATUS_CHOICES,
        default=HEALTH_UNKNOWN,
        db_index=True,
    )
    consecutive_failures = models.IntegerField(default=0)
    health_check_enabled = models.BooleanField(default=True)

    avg_response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Average response time in milliseconds",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databases"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["cluster", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["last_check"]),
            models.Index(fields=["consecutive_failures"]),
            models.Index(fields=["base_name"]),
        ]
        verbose_name = "1C Database"
        verbose_name_plural = "1C Databases"
        permissions = (
            ("operate_database", "Can operate database"),
            ("manage_database", "Can manage database"),
            ("admin_database", "Can administer database"),
        )

    def __str__(self):
        if self.cluster:
            return f"{self.name} ({self.cluster.name})"
        return self.name

    def get_odata_endpoint(self, entity: str) -> str:
        base_url = self.odata_url.rstrip("/")
        return f"{base_url}/{entity}"

    def mark_health_check(self, success: bool, response_time: float = None):
        self.last_check = timezone.now()

        if success:
            self.last_check_status = self.HEALTH_OK
            self.consecutive_failures = 0

            if response_time is not None:
                if self.avg_response_time is None:
                    self.avg_response_time = response_time
                else:
                    alpha = 0.3
                    self.avg_response_time = (alpha * response_time) + (
                        (1 - alpha) * self.avg_response_time
                    )
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.last_check_status = self.HEALTH_DOWN
            else:
                self.last_check_status = self.HEALTH_DEGRADED

        self.save(
            update_fields=[
                "last_check",
                "last_check_status",
                "consecutive_failures",
                "avg_response_time",
                "updated_at",
            ]
        )

    @property
    def is_healthy(self) -> bool:
        return self.last_check_status == self.HEALTH_OK

    @property
    def connection_string(self) -> str:
        return f"{self.username}@{self.host}:{self.port}/{self.base_name}"

    @property
    def connection_string_1c(self) -> str:
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

        return f'Srvr=\"{server_part}\";Ref=\"{ib_name}\";'

    @property
    def designer_path(self) -> str:
        ib_name = self.infobase_name if self.infobase_name else self.name
        if self.cluster and self.cluster.rmngr_host and self.cluster.rmngr_port:
            return f"{self.cluster.rmngr_host}:{self.cluster.rmngr_port}\\{ib_name}"
        if self.server_port and self.server_port != 1540:
            return f"{self.server_address}:{self.server_port}\\{ib_name}"
        return f"{self.server_address}\\{ib_name}"

import uuid

from django.apps import apps
from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField


class Cluster(models.Model):
    """
    Represents a 1C:Enterprise server cluster.

    A cluster is a logical grouping of 1C infobases managed by a single
    RAS (Remote Administration Server).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=True,
        help_text="Cluster UUID (auto-generated or from 1C)",
    )
    name = models.CharField(max_length=255, db_index=True, help_text="Cluster name from 1C")
    description = models.TextField(blank=True, help_text="Optional description")

    ras_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="RAS host (e.g., localhost, srv1c, 192.168.1.100)",
    )
    ras_port = models.IntegerField(null=True, blank=True, help_text="RAS port (default: 1545)")
    ras_server = models.CharField(
        max_length=255,
        default="localhost:1545",
        help_text="RAS server address (host:port)",
    )
    ras_cluster_uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID кластера в RAS (заполняется при первой успешной синхронизации)",
    )

    cluster_service_url = models.URLField(
        max_length=512,
        help_text="Legacy URL for cluster integrations (currently unused)",
    )

    cluster_user = models.CharField(
        max_length=255,
        blank=True,
        help_text="Cluster admin username (if required)",
    )
    cluster_pwd = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text="Cluster admin password (encrypted)",
    )

    rmngr_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="RMNGR host (cluster manager)",
    )
    rmngr_port = models.IntegerField(null=True, blank=True, help_text="RMNGR port (default: 1541)")
    ragent_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="RAGENT host (server agent)",
    )
    ragent_port = models.IntegerField(null=True, blank=True, help_text="RAGENT port (default: 1540)")
    rphost_port_from = models.IntegerField(
        null=True, blank=True, help_text="RPHOST port range start (default: 1560)"
    )
    rphost_port_to = models.IntegerField(
        null=True, blank=True, help_text="RPHOST port range end (default: 1591)"
    )

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

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    last_sync = models.DateTimeField(null=True, blank=True, help_text="Last sync timestamp")
    last_sync_status = models.CharField(
        max_length=20,
        choices=[
            ("success", "Success"),
            ("failed", "Failed"),
            ("pending", "Pending"),
        ],
        default="pending",
        db_index=True,
    )
    last_sync_error = models.TextField(blank=True, help_text="Error message from last sync")

    metadata = models.JSONField(default=dict, blank=True, help_text="Additional cluster metadata")

    consecutive_failures = models.IntegerField(
        default=0, help_text="Number of consecutive health check failures"
    )
    last_health_check = models.DateTimeField(
        null=True, blank=True, help_text="Last health check timestamp"
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clusters"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "last_sync_status"]),
            models.Index(fields=["last_sync"]),
            models.Index(fields=["ras_server"]),
        ]
        verbose_name = "1C Cluster"
        verbose_name_plural = "1C Clusters"
        permissions = (
            ("operate_cluster", "Can operate cluster"),
            ("manage_cluster", "Can manage cluster"),
            ("admin_cluster", "Can administer cluster"),
        )
        constraints = [
            models.UniqueConstraint(
                fields=["ras_server", "name"],
                name="unique_cluster_per_ras_server",
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
        return self.databases.count()

    @property
    def healthy_infobase_count(self) -> int:
        DatabaseModel = apps.get_model("databases", "Database")
        ok_status = getattr(DatabaseModel, "HEALTH_OK", "ok")
        return self.databases.filter(last_check_status=ok_status).count()

    @property
    def is_healthy(self) -> bool:
        return self.status == self.STATUS_ACTIVE and self.last_sync_status == "success"

    def mark_sync(self, success: bool, error_message: str = None):
        self.last_sync = timezone.now()
        self.last_sync_status = "success" if success else "failed"

        if not success and error_message:
            self.last_sync_error = error_message
            if self.status == self.STATUS_ACTIVE:
                self.status = self.STATUS_ERROR
        else:
            self.last_sync_error = ""
            if self.status == self.STATUS_ERROR:
                self.status = self.STATUS_ACTIVE

        self.save(
            update_fields=[
                "last_sync",
                "last_sync_status",
                "last_sync_error",
                "status",
                "updated_at",
            ]
        )

    def mark_health_check(self, success: bool, error_message: str = None):
        self.last_health_check = timezone.now()

        if success:
            self.consecutive_failures = 0
            if self.status == self.STATUS_ERROR:
                self.status = self.STATUS_ACTIVE
            self.last_sync_error = ""
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.status = self.STATUS_ERROR
            if error_message:
                self.last_sync_error = error_message

        self.save(
            update_fields=[
                "last_health_check",
                "consecutive_failures",
                "status",
                "last_sync_error",
                "updated_at",
            ]
        )


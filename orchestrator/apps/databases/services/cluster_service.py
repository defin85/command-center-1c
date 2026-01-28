from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Tuple

from django.utils import timezone

from ..models import Cluster, Database

logger = logging.getLogger(__name__)


class ClusterService:
    """Service for managing 1C clusters and syncing infobases."""

    @staticmethod
    def _import_infobases(cluster: Cluster, infobases: list) -> Tuple[int, int, int]:
        """
        Import infobases into Database model from dict format.

        Args:
            cluster: Cluster instance
            infobases: List of infobase dictionaries (legacy format)

        Returns:
            (created_count, updated_count, error_count)
        """
        logger.info(f"Importing {len(infobases)} infobases for cluster {cluster.name}")

        created_count = 0
        updated_count = 0
        error_count = 0

        for ib in infobases:
            try:
                ib_uuid = ib.get("uuid")
                ib_name = ib.get("name")

                if not ib_uuid or not ib_name:
                    logger.warning(f"Skipping infobase with missing uuid or name: {ib}")
                    error_count += 1
                    continue

                db_server = ib.get("db_server", "")
                host = ClusterService._parse_host(db_server)
                odata_url = ClusterService._build_odata_url(ib, default_host=host)

                metadata = {
                    "dbms": ib.get("dbms", ""),
                    "db_server": db_server,
                    "db_name": ib.get("db_name", ""),
                    "db_user": ib.get("db_user", ""),
                    "security_level": ib.get("security_level", 0),
                    "connection_string": ib.get("connection_string", ""),
                    "locale": ib.get("locale", ""),
                    "imported_from_cluster": True,
                    "import_timestamp": timezone.now().isoformat(),
                    "ras_server": cluster.ras_server,
                    "cluster_id": str(cluster.id),
                    "cluster_name": cluster.name,
                }

                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults={
                        "name": ib_name,
                        "description": ib.get("description", ""),
                        "host": host or "localhost",
                        "port": 80,
                        "base_name": ib_name,
                        "odata_url": odata_url,
                        "username": "",
                        "password": "",
                        "cluster": cluster,
                        "metadata": metadata,
                    },
                )
                if created:
                    database.status = Database.STATUS_INACTIVE
                    database.save(update_fields=["status", "updated_at"])

                if created:
                    created_count += 1
                    logger.info(f"Created database: {ib_name} (id={ib_uuid})")
                else:
                    updated_count += 1
                    logger.info(f"Updated database: {ib_name} (id={ib_uuid})")

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import infobase {ib.get('name', 'unknown')}: " f"{type(e).__name__}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Import completed: created={created_count}, updated={updated_count}, " f"errors={error_count}"
        )

        return created_count, updated_count, error_count

    @staticmethod
    def _parse_host(db_server: str) -> str:
        """
        Extract host from db_server string.

        Examples:
            'sql-server\\SQLEXPRESS' -> 'sql-server'
            'localhost' -> 'localhost'
            '' -> ''

        Args:
            db_server: Database server string from 1C

        Returns:
            Host part of the server string
        """
        if not db_server:
            return ""

        parts = db_server.split("\\")
        return parts[0]

    @staticmethod
    def _build_odata_url(ib: dict, default_host: str) -> str:
        """
        Build OData URL for infobase (legacy dict format).

        Format: http://host/base_name/odata/standard.odata/

        Args:
            ib: Infobase dictionary (legacy format)
            default_host: Default host to use if not specified in ib

        Returns:
            OData URL string
        """
        base_name = ib.get("name", "")
        host = default_host or "localhost"

        return f"http://{host}/{base_name}/odata/standard.odata/"

    @staticmethod
    def import_infobases_from_dict(
        cluster: Cluster,
        infobases: List[Dict[str, Any]],
    ) -> Tuple[int, int, int]:
        """
        Import infobases into Database model from dict format (Worker response).

        This method is used by EventSubscriber to import infobases received
        from Go Worker in cluster-synced event.

        Args:
            cluster: Cluster instance
            infobases: List of infobase dictionaries from Worker with format:
                {
                    'uuid': 'infobase-uuid',
                    'name': 'TestBase',
                    'dbms': 'PostgreSQL',
                    'db_server': 'localhost',
                    'db_name': 'testbase',
                    'locale': 'ru_RU',
                    'info_available': True,             # optional
                    'info_error': 'access denied',       # optional
                    'sessions_deny': False,
                    'scheduled_jobs_deny': False,
                    'denied_from': '2025-01-01T00:00:00Z',  # optional
                    'denied_to': '2025-01-02T00:00:00Z',    # optional
                    'denied_message': 'Maintenance'          # optional
                }

        Returns:
            (created_count, updated_count, error_count)
        """
        logger.info(f"Importing {len(infobases)} infobases for cluster {cluster.name}")

        created_count = 0
        updated_count = 0
        error_count = 0

        for ib in infobases:
            try:
                ib_uuid = ib.get("uuid")
                ib_name = ib.get("name")

                if not ib_uuid or not ib_name:
                    logger.warning(f"Skipping infobase with missing uuid or name: {ib}")
                    error_count += 1
                    continue

                infobase_uuid = None
                try:
                    infobase_uuid = uuid.UUID(str(ib_uuid))
                except (ValueError, TypeError, AttributeError):
                    infobase_uuid = None

                existing_db = Database.objects.filter(id=ib_uuid).first()
                existing_metadata: Dict[str, Any] = {}
                if existing_db and isinstance(existing_db.metadata, dict):
                    existing_metadata = dict(existing_db.metadata)

                info_available = ib.get("info_available", True)
                info_error = ib.get("info_error")

                # Parse host from db_server (only when info is available)
                db_server = ib.get("db_server", "")
                if info_available:
                    host = ClusterService._parse_host(db_server)
                    odata_url = ClusterService._build_odata_url(ib, default_host=host)
                    base_name = ib_name
                elif existing_db:
                    host = existing_db.host
                    odata_url = existing_db.odata_url
                    base_name = existing_db.base_name
                    if not db_server:
                        db_server = existing_metadata.get("db_server", "")
                else:
                    host = ClusterService._parse_host(db_server)
                    odata_url = ClusterService._build_odata_url(ib, default_host=host)
                    base_name = ib_name

                base_metadata = {
                    "imported_from_cluster": True,
                    "import_timestamp": timezone.now().isoformat(),
                    "ras_server": cluster.ras_server,
                    "cluster_id": str(cluster.id),
                    "cluster_name": cluster.name,
                    "api_version": "worker",
                    "info_available": bool(info_available),
                }
                if info_error:
                    base_metadata["info_error"] = info_error

                # Prepare metadata
                if info_available:
                    metadata = {
                        "dbms": ib.get("dbms", ""),
                        "db_server": db_server,
                        "db_name": ib.get("db_name", ""),
                        "locale": ib.get("locale", ""),
                        "sessions_deny": ib.get("sessions_deny", False),
                        "scheduled_jobs_deny": ib.get("scheduled_jobs_deny", False),
                    }
                    metadata.update(base_metadata)

                    # Add denied_from/denied_to if set
                    if ib.get("denied_from"):
                        metadata["denied_from"] = ib["denied_from"]
                    if ib.get("denied_to"):
                        metadata["denied_to"] = ib["denied_to"]
                    if ib.get("denied_message"):
                        metadata["denied_message"] = ib["denied_message"]
                    if ib.get("permission_code"):
                        metadata["permission_code"] = ib["permission_code"]
                    if ib.get("denied_parameter"):
                        metadata["denied_parameter"] = ib["denied_parameter"]
                else:
                    metadata = dict(existing_metadata) if existing_metadata else {}
                    for key in (
                        "sessions_deny",
                        "scheduled_jobs_deny",
                        "denied_from",
                        "denied_to",
                        "denied_message",
                        "permission_code",
                        "denied_parameter",
                        "info_error",
                    ):
                        metadata.pop(key, None)
                    metadata.update(base_metadata)

                # Create or update Database.
                # IMPORTANT: do not override operator-set status on update.
                defaults: Dict[str, Any] = {
                    "name": ib_name,
                    "description": "",
                    "host": host or "localhost",
                    "port": 80,
                    "base_name": base_name,
                    "odata_url": odata_url,
                    "username": "",
                    "password": "",
                    "cluster": cluster,
                    "metadata": metadata,
                }
                if cluster.ras_cluster_uuid:
                    defaults["ras_cluster_id"] = cluster.ras_cluster_uuid
                if infobase_uuid:
                    defaults["ras_infobase_id"] = infobase_uuid

                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults=defaults,
                )
                if created:
                    database.status = Database.STATUS_INACTIVE
                    database.save(update_fields=["status", "updated_at"])

                if created:
                    created_count += 1
                    logger.info(f"Created database: {ib_name} (id={ib_uuid})")
                else:
                    updated_count += 1
                    logger.debug(f"Updated database: {ib_name} (id={ib_uuid})")

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import infobase {ib.get('name', 'unknown')}: " f"{type(e).__name__}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Import completed: created={created_count}, updated={updated_count}, " f"errors={error_count}"
        )

        return created_count, updated_count, error_count


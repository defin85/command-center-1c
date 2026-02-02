import uuid
from typing import Any, Dict

from .runtime import logger


class CommandHandlersMixin:
    def handle_get_cluster_info(self, data: Dict[str, Any], correlation_id: str) -> None:
        from apps.databases.models import Database

        request_correlation_id = data.get("correlation_id", correlation_id)
        database_id = data.get("database_id", "")

        logger.info(
            "Processing get-cluster-info request: database_id=%s, correlation_id=%s",
            database_id,
            request_correlation_id,
        )

        response = {
            "correlation_id": request_correlation_id,
            "database_id": database_id,
            "cluster_id": "",
            "ras_server": "",
            "ras_cluster_uuid": "",
            "infobase_id": "",
            "success": "false",
            "error": "",
        }

        try:
            try:
                database = Database.objects.select_related("cluster").get(pk=database_id)
            except Database.DoesNotExist:
                response["error"] = f"Database {database_id} not found"
                logger.warning("Database not found: %s", database_id)
                self._publish_cluster_info_response(response)
                return

            if not database.cluster:
                response["error"] = f"Database {database_id} has no cluster configured"
                logger.warning("No cluster for database: %s", database_id)
                self._publish_cluster_info_response(response)
                return

            cluster = database.cluster

            ras_cluster_uuid = cluster.ras_cluster_uuid or database.ras_cluster_id
            if not ras_cluster_uuid:
                response["error"] = (
                    f"Cluster {cluster.name} has no ras_cluster_uuid configured. "
                    "Run sync_cluster first or set manually in admin."
                )
                logger.warning(
                    "No ras_cluster_uuid for cluster %s (database: %s)",
                    cluster.name,
                    database_id,
                )
                self._publish_cluster_info_response(response)
                return

            infobase_uuid = database.ras_infobase_id
            if not infobase_uuid:
                try:
                    infobase_uuid = uuid.UUID(str(database.id))
                except (ValueError, TypeError, AttributeError):
                    infobase_uuid = None
            if not infobase_uuid:
                response["error"] = (
                    f"Database {database_id} has no ras_infobase_id configured. "
                    "Run sync_cluster first."
                )
                logger.warning("No ras_infobase_id for database %s", database_id)
                self._publish_cluster_info_response(response)
                return

            response["cluster_id"] = str(ras_cluster_uuid)
            response["ras_server"] = cluster.ras_server or ""
            response["ras_cluster_uuid"] = str(ras_cluster_uuid)
            response["infobase_id"] = str(infobase_uuid)
            response["success"] = "true"
            response["error"] = ""

            logger.info(
                "Cluster info resolved: database_id=%s, ras_cluster_uuid=%s, infobase_id=%s",
                database_id,
                ras_cluster_uuid,
                infobase_uuid,
            )

        except Exception as e:
            response["error"] = f"Internal error: {str(e)}"
            logger.error("Error handling get-cluster-info: %s", e, exc_info=True)

        self._publish_cluster_info_response(response)

    def _publish_cluster_info_response(self, response: Dict[str, str]) -> None:
        response_stream = "events:orchestrator:cluster-info-response"
        try:
            self.redis_client.xadd(response_stream, response)
            logger.debug(
                "Published cluster-info response: correlation_id=%s, success=%s",
                response.get("correlation_id"),
                response.get("success"),
            )
        except Exception as e:
            logger.error("Failed to publish cluster-info response: %s", e, exc_info=True)

    def handle_get_database_credentials(self, data: Dict[str, Any], correlation_id: str) -> None:
        from django.contrib.auth import get_user_model

        from apps.databases.encryption import encrypt_credentials_for_transport
        from apps.databases.models import Database
        from apps.databases.models import DbmsUserMapping
        from apps.databases.models import InfobaseUserMapping

        request_correlation_id = data.get("correlation_id", correlation_id)
        database_id = data.get("database_id", "")
        created_by = (data.get("created_by") or "").strip()
        ib_auth_strategy = str(data.get("ib_auth_strategy") or "").strip().lower()
        dbms_auth_strategy = str(data.get("dbms_auth_strategy") or "").strip().lower()
        if dbms_auth_strategy not in {"actor", "service", ""}:
            dbms_auth_strategy = ""

        logger.info(
            "Processing get-database-credentials request: database_id=%s, correlation_id=%s",
            database_id,
            request_correlation_id,
        )

        response = {
            "correlation_id": request_correlation_id,
            "database_id": database_id,
            "success": "false",
            "error": "",
            "encrypted_data": "",
            "nonce": "",
            "expires_at": "",
            "encryption_version": "",
        }

        try:
            try:
                database = Database.objects.select_related("cluster").get(id=database_id)
            except Database.DoesNotExist:
                response["error"] = f"Database {database_id} not found"
                logger.warning("Database not found: %s", database_id)
                self._publish_database_credentials_response(response)
                return

            ib_username = ""
            ib_password = ""
            if ib_auth_strategy == "service":
                mapping = (
                    InfobaseUserMapping.objects.filter(
                        database=database,
                        is_service=True,
                        user__isnull=True,
                    ).first()
                )
                if mapping:
                    ib_username = mapping.ib_username
                    ib_password = mapping.ib_password
            elif created_by:
                user_model = get_user_model()
                user = user_model.objects.filter(username=created_by).first()
                if user:
                    mapping = InfobaseUserMapping.objects.filter(database=database, user=user).first()
                    if mapping:
                        ib_username = mapping.ib_username
                        ib_password = mapping.ib_password

            db_user = ""
            db_password = ""
            if dbms_auth_strategy == "service":
                dbms_mapping = (
                    DbmsUserMapping.objects.filter(
                        database=database,
                        is_service=True,
                        user__isnull=True,
                    ).first()
                )
                if dbms_mapping:
                    db_user = dbms_mapping.db_username
                    db_password = dbms_mapping.db_password
            elif created_by:
                user_model = get_user_model()
                user = user_model.objects.filter(username=created_by).first()
                if user:
                    dbms_mapping = DbmsUserMapping.objects.filter(database=database, user=user).first()
                    if dbms_mapping:
                        db_user = dbms_mapping.db_username
                        db_password = dbms_mapping.db_password

            if not database.cluster:
                response["error"] = "Database cluster is not configured"
                logger.warning(
                    "Database %s has no cluster configured for DESIGNER credentials",
                    database_id,
                )
                self._publish_database_credentials_response(response)
                return

            cluster = database.cluster
            rmngr_host = (cluster.rmngr_host or "").strip()
            rmngr_port = cluster.rmngr_port or 0
            if not rmngr_host or not rmngr_port:
                response["error"] = "Cluster RMNGR host/port is not configured"
                logger.warning("Cluster %s has no RMNGR host/port configured", cluster.id)
                self._publish_database_credentials_response(response)
                return

            credentials_dict = {
                "database_id": str(database.id),
                "odata_url": database.odata_url,
                "username": database.username,
                "password": database.password,
                "ib_username": ib_username,
                "ib_password": ib_password,
                "dbms": (database.metadata or {}).get("dbms", ""),
                "db_server": (database.metadata or {}).get("db_server", ""),
                "db_name": (database.metadata or {}).get("db_name", ""),
                "db_user": db_user,
                "db_password": db_password,
                "host": database.host,
                "port": database.port,
                "base_name": database.base_name,
                "server_address": rmngr_host,
                "server_port": rmngr_port,
                "infobase_name": database.infobase_name or database.name,
            }
            ibcmd_connection = (database.metadata or {}).get("ibcmd_connection")
            if isinstance(ibcmd_connection, dict):
                raw = dict(ibcmd_connection)

                remote_raw = raw.get("remote")
                if remote_raw in (None, ""):
                    remote_raw = raw.get("remote_url")
                remote = str(remote_raw).strip() if remote_raw not in (None, "") else ""
                if remote and not remote.lower().startswith("ssh://"):
                    remote = ""

                pid_raw = raw.get("pid")
                pid = pid_raw if isinstance(pid_raw, int) and pid_raw > 0 else None

                offline_in = raw.get("offline")
                offline: dict[str, str] | None = None
                if isinstance(offline_in, dict):
                    offline_safe: dict[str, str] = {}
                    for k, v in offline_in.items():
                        key = str(k).strip()
                        if not key:
                            continue
                        lowered = key.lower()
                        if lowered in ("db_user", "db_pwd", "db_password"):
                            continue
                        if v in (None, ""):
                            continue
                        rendered = str(v).strip()
                        if not rendered:
                            continue
                        offline_safe[key] = rendered
                    offline = offline_safe or None

                safe_profile: dict[str, object] = {}
                if remote:
                    safe_profile["remote"] = remote
                if pid is not None:
                    safe_profile["pid"] = pid
                if offline:
                    safe_profile["offline"] = offline

                credentials_dict["ibcmd_connection"] = safe_profile

            encrypted_payload = encrypt_credentials_for_transport(credentials_dict)

            response["success"] = "true"
            response["error"] = ""
            response["encrypted_data"] = encrypted_payload.get("encrypted_data", "")
            response["nonce"] = encrypted_payload.get("nonce", "")
            response["expires_at"] = encrypted_payload.get("expires_at", "")
            response["encryption_version"] = encrypted_payload.get("encryption_version", "")

        except Exception as e:
            response["error"] = f"Internal error: {str(e)}"
            logger.error("Error handling get-database-credentials: %s", e, exc_info=True)

        self._publish_database_credentials_response(response)

    def _publish_database_credentials_response(self, response: Dict[str, str]) -> None:
        response_stream = "events:orchestrator:database-credentials-response"
        try:
            self.redis_client.xadd(response_stream, response)
            logger.debug(
                "Published database-credentials response: correlation_id=%s, success=%s",
                response.get("correlation_id"),
                response.get("success"),
            )
        except Exception as e:
            logger.error(
                "Failed to publish database-credentials response: %s",
                e,
                exc_info=True,
            )

import uuid
from typing import Any, Dict

from .runtime import logger


PUBLICATION_CREDENTIALS_PURPOSE = "pool_publication_odata"
IB_AUTH_STRATEGY_ACTOR = "actor"
IB_AUTH_STRATEGY_SERVICE = "service"
_VALID_IB_AUTH_STRATEGIES = {IB_AUTH_STRATEGY_ACTOR, IB_AUTH_STRATEGY_SERVICE, "none", ""}

ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED = "ODATA_MAPPING_NOT_CONFIGURED"
ERROR_CODE_ODATA_MAPPING_AMBIGUOUS = "ODATA_MAPPING_AMBIGUOUS"
ERROR_CODE_ODATA_PUBLICATION_AUTH_CONTEXT_INVALID = "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID"
RESOLUTION_OUTCOME_ACTOR_SUCCESS = "actor_success"
RESOLUTION_OUTCOME_SERVICE_SUCCESS = "service_success"
RESOLUTION_OUTCOME_MISSING_MAPPING = "missing_mapping"
RESOLUTION_OUTCOME_AMBIGUOUS_MAPPING = "ambiguous_mapping"
RESOLUTION_OUTCOME_INVALID_AUTH_CONTEXT = "invalid_auth_context"

ERROR_CODE_TO_RESOLUTION_OUTCOME = {
    ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED: RESOLUTION_OUTCOME_MISSING_MAPPING,
    ERROR_CODE_ODATA_MAPPING_AMBIGUOUS: RESOLUTION_OUTCOME_AMBIGUOUS_MAPPING,
    ERROR_CODE_ODATA_PUBLICATION_AUTH_CONTEXT_INVALID: RESOLUTION_OUTCOME_INVALID_AUTH_CONTEXT,
}


class CredentialsResolutionError(Exception):
    def __init__(self, *, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "").strip()
        self.message = str(message or "").strip()

    @property
    def response_error(self) -> str:
        if self.code and self.message:
            return f"{self.code}: {self.message}"
        return self.code or self.message


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
        credentials_purpose = str(data.get("credentials_purpose") or "").strip().lower()
        publication_mapping_only = credentials_purpose == PUBLICATION_CREDENTIALS_PURPOSE
        ib_auth_strategy = str(data.get("ib_auth_strategy") or "").strip().lower()
        if ib_auth_strategy not in _VALID_IB_AUTH_STRATEGIES:
            ib_auth_strategy = ""
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
            "error_code": "",
            "resolution_outcome": "",
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

            odata_username = database.username
            odata_password = database.password
            ib_username = ""
            ib_password = ""
            if publication_mapping_only:
                try:
                    mapping = self._resolve_publication_infobase_mapping(
                        database=database,
                        created_by=created_by,
                        ib_auth_strategy=ib_auth_strategy,
                        user_model=get_user_model(),
                        infobase_mapping_model=InfobaseUserMapping,
                    )
                except CredentialsResolutionError as resolution_error:
                    response["error_code"] = resolution_error.code
                    response["error"] = resolution_error.response_error
                    response["resolution_outcome"] = ERROR_CODE_TO_RESOLUTION_OUTCOME.get(
                        resolution_error.code,
                        RESOLUTION_OUTCOME_MISSING_MAPPING,
                    )
                    logger.warning(
                        (
                            "Publication credentials mapping lookup failed: "
                            "database_id=%s, strategy=%s, created_by=%s, code=%s, resolution_outcome=%s"
                        ),
                        database_id,
                        ib_auth_strategy,
                        created_by,
                        resolution_error.code,
                        response["resolution_outcome"],
                    )
                    self._publish_database_credentials_response(response)
                    return
                odata_username = mapping.ib_username
                odata_password = mapping.ib_password
                ib_username = mapping.ib_username
                ib_password = mapping.ib_password
                response["resolution_outcome"] = (
                    RESOLUTION_OUTCOME_ACTOR_SUCCESS
                    if ib_auth_strategy == IB_AUTH_STRATEGY_ACTOR
                    else RESOLUTION_OUTCOME_SERVICE_SUCCESS
                )
            else:
                if ib_auth_strategy == IB_AUTH_STRATEGY_SERVICE:
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
                "username": odata_username,
                "password": odata_password,
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
            if response["resolution_outcome"]:
                logger.info(
                    (
                        "Publication credentials mapping resolved: "
                        "database_id=%s, strategy=%s, created_by=%s, resolution_outcome=%s"
                    ),
                    database_id,
                    ib_auth_strategy,
                    created_by,
                    response["resolution_outcome"],
                )

        except Exception as e:
            response["error"] = f"Internal error: {str(e)}"
            logger.error("Error handling get-database-credentials: %s", e, exc_info=True)

        self._publish_database_credentials_response(response)

    def _resolve_publication_infobase_mapping(
        self,
        *,
        database,
        created_by: str,
        ib_auth_strategy: str,
        user_model,
        infobase_mapping_model,
    ):
        strategy = str(ib_auth_strategy or "").strip().lower()
        if strategy not in {IB_AUTH_STRATEGY_ACTOR, IB_AUTH_STRATEGY_SERVICE}:
            raise CredentialsResolutionError(
                code=ERROR_CODE_ODATA_PUBLICATION_AUTH_CONTEXT_INVALID,
                message="ib_auth_strategy must be actor|service for pool publication credentials lookup",
            )

        if strategy == IB_AUTH_STRATEGY_ACTOR:
            actor = str(created_by or "").strip()
            if not actor:
                raise CredentialsResolutionError(
                    code=ERROR_CODE_ODATA_PUBLICATION_AUTH_CONTEXT_INVALID,
                    message="created_by is required when ib_auth_strategy=actor",
                )
            user = user_model.objects.filter(username=actor).only("id").first()
            if user is None:
                raise CredentialsResolutionError(
                    code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
                    message=f"infobase user mapping is not configured for created_by={actor}",
                )
            queryset = infobase_mapping_model.objects.filter(database=database, user=user)
        else:
            queryset = infobase_mapping_model.objects.filter(
                database=database,
                is_service=True,
                user__isnull=True,
            )

        candidates = list(queryset.only("id", "ib_username", "ib_password")[:2])
        if not candidates:
            raise CredentialsResolutionError(
                code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
                message=(
                    "service infobase user mapping is not configured"
                    if strategy == IB_AUTH_STRATEGY_SERVICE
                    else f"infobase user mapping is not configured for created_by={created_by}"
                ),
            )
        if len(candidates) > 1:
            raise CredentialsResolutionError(
                code=ERROR_CODE_ODATA_MAPPING_AMBIGUOUS,
                message="multiple infobase user mappings found for publication auth context",
            )
        mapping = candidates[0]
        if not str(mapping.ib_username or "").strip() or not str(mapping.ib_password or "").strip():
            raise CredentialsResolutionError(
                code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
                message="infobase mapping must contain non-empty username and password for publication auth",
            )
        return mapping

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

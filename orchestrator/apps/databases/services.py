"""Business logic for databases."""

import logging
import uuid
from typing import Dict, List, Any, Tuple, Optional
from django.db import transaction
from django.utils import timezone

from .models import Database, DatabaseGroup, Cluster
from .odata import session_manager, ODataError

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing databases and performing health checks."""

    @staticmethod
    def health_check_database(database: Database) -> Dict[str, Any]:
        """
        Выполняет health check одной базы 1С.

        Args:
            database: Database instance для проверки

        Returns:
            Dict с результатами health check:
            {
                'healthy': bool,
                'response_time': float,
                'error': str (если есть),
                'status_code': int
            }
        """
        logger.info(f"Starting health check for database: {database.name}")

        start_time = timezone.now()
        result = {
            'healthy': False,
            'response_time': 0.0,
            'error': None,
            'status_code': None
        }

        try:
            # Получаем OData client из session manager
            client = session_manager.get_client(
                base_id=str(database.id),
                base_url=database.odata_url,
                username=database.username,
                password=database.password,
                timeout=database.connection_timeout
            )

            # Выполняем health check (простой GET запрос к metadata)
            health_result = client.health_check()

            # Вычисляем время ответа
            end_time = timezone.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds

            result.update({
                'healthy': health_result,
                'response_time': response_time,
                'status_code': 200 if health_result else 500
            })

            # Используем существующий метод вместо дублирования
            database.mark_health_check(
                success=True,
                response_time=response_time
            )

            logger.info(
                f"Database {database.name} health check: OK "
                f"(response_time={response_time:.3f}ms)"
            )

        except ODataError as e:
            # OData-specific errors
            error_msg = str(e)
            result['error'] = error_msg

            database.mark_health_check(
                success=False,
                response_time=None
            )

            logger.warning(
                f"Database {database.name} health check: FAILED "
                f"(ODataError: {error_msg})"
            )

        except Exception as e:
            # Unexpected errors
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            result['error'] = error_msg

            database.mark_health_check(
                success=False,
                response_time=None
            )

            logger.error(
                f"Database {database.name} health check: ERROR "
                f"({error_msg})",
                exc_info=True
            )

        return result

    @staticmethod
    def health_check_group(group: DatabaseGroup) -> Dict[str, Any]:
        """
        Выполняет health check для всех баз в группе.

        Args:
            group: DatabaseGroup instance

        Returns:
            Dict с агрегированными результатами:
            {
                'total': int,
                'healthy': int,
                'unhealthy': int,
                'results': List[Dict]
            }
        """
        logger.info(f"Starting health check for group: {group.name}")

        databases = group.databases.all()
        results = []
        healthy_count = 0

        for db in databases:
            result = DatabaseService.health_check_database(db)
            results.append({
                'database_id': str(db.id),
                'database_name': db.name,
                **result
            })
            if result['healthy']:
                healthy_count += 1

        summary = {
            'group_name': group.name,
            'total': len(databases),
            'healthy': healthy_count,
            'unhealthy': len(databases) - healthy_count,
            'results': results
        }

        logger.info(
            f"Health check completed for group {group.name}: "
            f"{healthy_count}/{len(databases)} healthy"
        )

        return summary

    @staticmethod
    def bulk_create_databases(databases_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Массовое создание баз данных.

        Args:
            databases_data: List of dicts с данными для создания баз

        Returns:
            Dict с результатами:
            {
                'created': int,
                'failed': int,
                'errors': List[str]
            }
        """
        logger.info(f"Starting bulk create for {len(databases_data)} databases")

        created_count = 0
        failed_count = 0
        errors = []

        for db_data in databases_data:
            try:
                with transaction.atomic():
                    database = Database.objects.create(**db_data)
                    created_count += 1
                    logger.info(f"Created database: {database.name}")
            except Exception as e:
                failed_count += 1
                error_msg = f"Failed to create database {db_data.get('name', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        result = {
            'created': created_count,
            'failed': failed_count,
            'errors': errors
        }

        logger.info(
            f"Bulk create completed: {created_count} created, {failed_count} failed"
        )

        return result


class ODataOperationService:
    """Service for performing OData operations on 1C databases."""

    @staticmethod
    def create_entity(
        database: Database,
        entity_type: str,
        entity_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Создает сущность в базе 1С через OData.

        Args:
            database: Database instance
            entity_type: Тип сущности ('Catalog', 'Document', 'InformationRegister')
            entity_name: Имя сущности (например, 'Пользователи')
            data: Dict с данными для создания

        Returns:
            Dict с результатом:
            {
                'success': bool,
                'data': Dict (если success=True),
                'error': str (если success=False)
            }
        """
        logger.info(
            f"Creating entity {entity_type}_{entity_name} in database {database.name}"
        )

        result = {
            'success': False,
            'data': None,
            'error': None
        }

        try:
            # Получаем OData client
            client = session_manager.get_client(database)

            # Формируем entity set name (например: 'Catalog_Пользователи')
            entity_set = f"{entity_type}_{entity_name}"

            # Создаем сущность
            created_entity = client.create_entity(entity_set, data)

            result.update({
                'success': True,
                'data': created_entity
            })

            logger.info(
                f"Successfully created entity {entity_set} in {database.name}"
            )

        except ODataError as e:
            error_msg = str(e)
            result['error'] = error_msg
            logger.error(
                f"Failed to create entity {entity_type}_{entity_name} "
                f"in {database.name}: {error_msg}",
                exc_info=True
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result['error'] = error_msg
            logger.error(
                f"Unexpected error creating entity in {database.name}: {error_msg}",
                exc_info=True
            )

        return result

    @staticmethod
    def get_entities(
        database: Database,
        entity_type: str,
        entity_name: str,
        filter_query: str = None
    ) -> Dict[str, Any]:
        """
        Получает список сущностей из базы 1С.

        Args:
            database: Database instance
            entity_type: Тип сущности
            entity_name: Имя сущности
            filter_query: OData $filter query (optional)

        Returns:
            Dict с результатом:
            {
                'success': bool,
                'data': List[Dict] (если success=True),
                'count': int,
                'error': str (если success=False)
            }
        """
        logger.info(
            f"Getting entities {entity_type}_{entity_name} from database {database.name}"
        )

        result = {
            'success': False,
            'data': None,
            'count': 0,
            'error': None
        }

        try:
            # Получаем OData client
            client = session_manager.get_client(database)

            # Формируем entity set name
            entity_set = f"{entity_type}_{entity_name}"

            # Получаем сущности
            params = {}
            if filter_query:
                params['$filter'] = filter_query

            entities = client.get_entities(entity_set, params=params)

            result.update({
                'success': True,
                'data': entities.get('value', []),
                'count': len(entities.get('value', []))
            })

            logger.info(
                f"Successfully retrieved {result['count']} entities "
                f"from {database.name}"
            )

        except ODataError as e:
            error_msg = str(e)
            result['error'] = error_msg
            logger.error(
                f"Failed to get entities {entity_type}_{entity_name} "
                f"from {database.name}: {error_msg}",
                exc_info=True
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            result['error'] = error_msg
            logger.error(
                f"Unexpected error getting entities from {database.name}: {error_msg}",
                exc_info=True
            )

        return result


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
                ib_uuid = ib.get('uuid')
                ib_name = ib.get('name')

                if not ib_uuid or not ib_name:
                    logger.warning(f"Skipping infobase with missing uuid or name: {ib}")
                    error_count += 1
                    continue

                db_server = ib.get('db_server', '')
                host = ClusterService._parse_host(db_server)
                odata_url = ClusterService._build_odata_url(ib, default_host=host)

                metadata = {
                    'dbms': ib.get('dbms', ''),
                    'db_server': db_server,
                    'db_name': ib.get('db_name', ''),
                    'db_user': ib.get('db_user', ''),
                    'security_level': ib.get('security_level', 0),
                    'connection_string': ib.get('connection_string', ''),
                    'locale': ib.get('locale', ''),
                    'imported_from_cluster': True,
                    'import_timestamp': timezone.now().isoformat(),
                    'ras_server': cluster.ras_server,
                    'cluster_id': str(cluster.id),
                    'cluster_name': cluster.name,
                }

                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults={
                        'name': ib_name,
                        'description': ib.get('description', ''),
                        'host': host or 'localhost',
                        'port': 80,
                        'base_name': ib_name,
                        'odata_url': odata_url,
                        'username': '',
                        'password': '',
                        'cluster': cluster,
                        'metadata': metadata,
                    }
                )
                if created:
                    database.status = Database.STATUS_INACTIVE
                    database.save(update_fields=['status', 'updated_at'])

                if created:
                    created_count += 1
                    logger.info(f"Created database: {ib_name} (id={ib_uuid})")
                else:
                    updated_count += 1
                    logger.info(f"Updated database: {ib_name} (id={ib_uuid})")

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import infobase {ib.get('name', 'unknown')}: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True
                )

        logger.info(
            f"Import completed: created={created_count}, updated={updated_count}, "
            f"errors={error_count}"
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
            return ''

        parts = db_server.split('\\')
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
        base_name = ib.get('name', '')
        host = default_host or 'localhost'

        return f"http://{host}/{base_name}/odata/standard.odata/"

    @staticmethod
    def import_infobases_from_dict(
        cluster: Cluster,
        infobases: List[Dict[str, Any]]
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
                ib_uuid = ib.get('uuid')
                ib_name = ib.get('name')

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

                info_available = ib.get('info_available', True)
                info_error = ib.get('info_error')

                # Parse host from db_server (only when info is available)
                db_server = ib.get('db_server', '')
                if info_available:
                    host = ClusterService._parse_host(db_server)
                    odata_url = ClusterService._build_odata_url(ib, default_host=host)
                    base_name = ib_name
                elif existing_db:
                    host = existing_db.host
                    odata_url = existing_db.odata_url
                    base_name = existing_db.base_name
                    if not db_server:
                        db_server = existing_metadata.get('db_server', '')
                else:
                    host = ClusterService._parse_host(db_server)
                    odata_url = ClusterService._build_odata_url(ib, default_host=host)
                    base_name = ib_name

                base_metadata = {
                    'imported_from_cluster': True,
                    'import_timestamp': timezone.now().isoformat(),
                    'ras_server': cluster.ras_server,
                    'cluster_id': str(cluster.id),
                    'cluster_name': cluster.name,
                    'api_version': 'worker',
                    'info_available': bool(info_available),
                }
                if info_error:
                    base_metadata['info_error'] = info_error

                # Prepare metadata
                if info_available:
                    metadata = {
                        'dbms': ib.get('dbms', ''),
                        'db_server': db_server,
                        'db_name': ib.get('db_name', ''),
                        'locale': ib.get('locale', ''),
                        'sessions_deny': ib.get('sessions_deny', False),
                        'scheduled_jobs_deny': ib.get('scheduled_jobs_deny', False),
                    }
                    metadata.update(base_metadata)

                    # Add denied_from/denied_to if set
                    if ib.get('denied_from'):
                        metadata['denied_from'] = ib['denied_from']
                    if ib.get('denied_to'):
                        metadata['denied_to'] = ib['denied_to']
                    if ib.get('denied_message'):
                        metadata['denied_message'] = ib['denied_message']
                    if ib.get('permission_code'):
                        metadata['permission_code'] = ib['permission_code']
                    if ib.get('denied_parameter'):
                        metadata['denied_parameter'] = ib['denied_parameter']
                else:
                    metadata = dict(existing_metadata) if existing_metadata else {}
                    for key in (
                        'sessions_deny',
                        'scheduled_jobs_deny',
                        'denied_from',
                        'denied_to',
                        'denied_message',
                        'permission_code',
                        'denied_parameter',
                        'info_error',
                    ):
                        metadata.pop(key, None)
                    metadata.update(base_metadata)

                # Create or update Database.
                # IMPORTANT: do not override operator-set status on update.
                defaults = {
                    'name': ib_name,
                    'description': '',
                    'host': host or 'localhost',
                    'port': 80,
                    'base_name': base_name,
                    'odata_url': odata_url,
                    'username': '',
                    'password': '',
                    'cluster': cluster,
                    'metadata': metadata,
                }
                if cluster.ras_cluster_uuid:
                    defaults['ras_cluster_id'] = cluster.ras_cluster_uuid
                if infobase_uuid:
                    defaults['ras_infobase_id'] = infobase_uuid

                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults=defaults,
                )
                if created:
                    database.status = Database.STATUS_INACTIVE
                    database.save(update_fields=['status', 'updated_at'])

                if created:
                    created_count += 1
                    logger.info(f"Created database: {ib_name} (id={ib_uuid})")
                else:
                    updated_count += 1
                    logger.debug(f"Updated database: {ib_name} (id={ib_uuid})")

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import infobase {ib.get('name', 'unknown')}: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True
                )

        logger.info(
            f"Import completed: created={created_count}, updated={updated_count}, "
            f"errors={error_count}"
        )

        return created_count, updated_count, error_count


# =============================================================================
# Permission Service for RBAC
# =============================================================================

class PermissionService:
    """
    Centralized permission checking for databases and clusters.

    Resolution order:
    1. Superuser -> Full access (ADMIN level)
    2. DatabasePermission (direct) -> Use if exists
    3. ClusterPermission (inherited) -> Use if database has cluster
    4. No permission -> Deny (None)

    Final level = max(database_level, cluster_level)

    OPTIMIZED: Uses batch loading to avoid N+1 queries.
    """

    @classmethod
    def _get_user_permission_maps(
        cls,
        user,
        database_ids: List[str] = None,
        cluster_ids: List[str] = None
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Load all permissions for user in batch.

        Returns:
            (database_permissions, cluster_permissions) - dicts mapping ID to level
        """
        from .models import ClusterPermission, DatabasePermission

        db_permissions: Dict[str, int] = {}
        cluster_permissions: Dict[str, int] = {}

        # Load database permissions in one query
        if database_ids:
            db_perms = DatabasePermission.objects.filter(
                user=user,
                database_id__in=database_ids
            ).values_list('database_id', 'level')

            db_permissions = {str(db_id): level for db_id, level in db_perms}

        # Load cluster permissions in one query
        if cluster_ids:
            cluster_perms = ClusterPermission.objects.filter(
                user=user,
                cluster_id__in=cluster_ids
            ).values_list('cluster_id', 'level')

            cluster_permissions = {str(c_id): level for c_id, level in cluster_perms}

        return db_permissions, cluster_permissions

    @classmethod
    def get_user_levels_for_databases_bulk(
        cls,
        user,
        databases: List[Database]
    ) -> Dict[str, Optional[int]]:
        """
        Get permission levels for multiple databases in batch (2-3 queries total).

        Args:
            user: User instance
            databases: List of Database instances (must have cluster_id loaded)

        Returns:
            Dict mapping database_id (str) to permission level (int or None)
        """
        from .models import PermissionLevel

        if user.is_superuser:
            return {str(db.id): PermissionLevel.ADMIN for db in databases}

        # Collect IDs
        database_ids = [str(db.id) for db in databases]
        cluster_ids = list({
            str(db.cluster_id) for db in databases
            if db.cluster_id is not None
        })

        # Batch load permissions (2 queries)
        db_perms, cluster_perms = cls._get_user_permission_maps(
            user, database_ids, cluster_ids
        )

        # Calculate effective levels
        result: Dict[str, Optional[int]] = {}
        for db in databases:
            db_id = str(db.id)
            levels = []

            # Direct database permission
            if db_id in db_perms:
                levels.append(db_perms[db_id])

            # Inherited cluster permission
            if db.cluster_id:
                cluster_id = str(db.cluster_id)
                if cluster_id in cluster_perms:
                    levels.append(cluster_perms[cluster_id])

            result[db_id] = max(levels) if levels else None

        return result

    @classmethod
    def get_user_level_for_database(
        cls,
        user,
        database: Database
    ) -> Optional[int]:
        """
        Get effective permission level for user on database.

        Returns:
            Permission level (int) or None if no access
        """
        # For single database, use bulk method with list of one
        levels = cls.get_user_levels_for_databases_bulk(user, [database])
        return levels.get(str(database.id))

    @classmethod
    def get_user_level_for_cluster(
        cls,
        user,
        cluster: Cluster
    ) -> 'Optional[int]':
        """Get permission level for user on cluster."""
        from .models import ClusterPermission, PermissionLevel

        if user.is_superuser:
            return PermissionLevel.ADMIN

        return ClusterPermission.objects.filter(
            user=user,
            cluster=cluster
        ).values_list('level', flat=True).first()

    @classmethod
    def has_permission(
        cls,
        user,
        database: Database,
        required_level: int
    ) -> bool:
        """Check if user has required level on database."""
        user_level = cls.get_user_level_for_database(user, database)
        return user_level is not None and user_level >= required_level

    @classmethod
    def filter_accessible_databases(
        cls,
        user,
        queryset,
        min_level: int = None
    ):
        """
        Filter queryset to only databases user can access.

        Usage:
            qs = Database.objects.all()
            qs = PermissionService.filter_accessible_databases(user, qs)
        """
        from django.db.models import Q
        from .models import ClusterPermission, DatabasePermission, PermissionLevel

        if min_level is None:
            min_level = PermissionLevel.VIEW

        if user.is_superuser:
            return queryset

        # Get database IDs with direct permission
        db_ids = DatabasePermission.objects.filter(
            user=user,
            level__gte=min_level
        ).values_list('database_id', flat=True)

        # Get cluster IDs with permission
        cluster_ids = ClusterPermission.objects.filter(
            user=user,
            level__gte=min_level
        ).values_list('cluster_id', flat=True)

        return queryset.filter(
            Q(id__in=db_ids) | Q(cluster_id__in=cluster_ids)
        )

    @classmethod
    def check_bulk_permission(
        cls,
        user,
        database_ids: List[str],
        required_level: int
    ) -> Tuple[bool, List[str]]:
        """
        Check permission for multiple databases (OPTIMIZED - O(3) queries).

        Returns:
            (all_allowed: bool, denied_ids: List[str])
        """
        if user.is_superuser:
            return True, []

        # Fetch databases with cluster info (1 query)
        databases = list(Database.objects.filter(
            id__in=database_ids
        ).select_related('cluster').only('id', 'cluster_id'))

        # Batch check permissions (2 queries)
        levels = cls.get_user_levels_for_databases_bulk(user, databases)

        # Find denied
        denied = []
        found_ids = set()

        for db in databases:
            db_id = str(db.id)
            found_ids.add(db_id)

            level = levels.get(db_id)
            if level is None or level < required_level:
                denied.append(db_id)

        # Check for missing/invalid database IDs
        for db_id in database_ids:
            if str(db_id) not in found_ids:
                denied.append(str(db_id))

        return len(denied) == 0, denied

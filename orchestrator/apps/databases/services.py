"""Business logic for databases."""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime
from django.db import transaction, OperationalError
from django.utils import timezone

from .models import Database, DatabaseGroup, Cluster
from .odata import ODataClient, session_manager, ODataError
from .clients import ClusterServiceClient

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

            # Обновляем информацию в базе
            with transaction.atomic():
                database.last_check = timezone.now()
                database.last_check_status = Database.HEALTH_OK
                database.consecutive_failures = 0

                # Обновляем среднее время ответа (простое скользящее среднее)
                if database.avg_response_time is None:
                    database.avg_response_time = response_time
                else:
                    # Взвешенное среднее: 70% старое значение + 30% новое
                    database.avg_response_time = (
                        0.7 * database.avg_response_time + 0.3 * response_time
                    )

                database.save(update_fields=[
                    'last_check',
                    'last_check_status',
                    'consecutive_failures',
                    'avg_response_time',
                    'updated_at'
                ])

            logger.info(
                f"Health check successful for {database.name}: "
                f"{response_time:.3f}s"
            )

        except ODataError as e:
            # OData-specific errors
            error_msg = str(e)
            result['error'] = error_msg

            with transaction.atomic():
                database.last_check = timezone.now()
                database.last_check_status = Database.HEALTH_DOWN
                database.consecutive_failures += 1
                database.save(update_fields=[
                    'last_check',
                    'last_check_status',
                    'consecutive_failures',
                    'updated_at'
                ])

            logger.error(
                f"Health check failed for {database.name}: {error_msg}",
                exc_info=True
            )

        except Exception as e:
            # Unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            result['error'] = error_msg

            with transaction.atomic():
                database.last_check = timezone.now()
                database.last_check_status = Database.HEALTH_DOWN
                database.consecutive_failures += 1
                database.save(update_fields=[
                    'last_check',
                    'last_check_status',
                    'consecutive_failures',
                    'updated_at'
                ])

            logger.error(
                f"Unexpected error during health check for {database.name}: {error_msg}",
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
    def create_from_ras(
        ras_server: str,
        installation_service_url: str,
        cluster_user: str = None,
        cluster_pwd: str = None
    ) -> Cluster:
        """
        Create Cluster by connecting to RAS server.

        Steps:
        1. Connect to installation-service
        2. Health check
        3. Call get_infobases (detailed=False) to get cluster_id and cluster_name
        4. Check if cluster already exists
        5. Create Cluster object

        Args:
            ras_server: RAS server address (host:port)
            installation_service_url: URL of installation-service
            cluster_user: Cluster admin username (optional)
            cluster_pwd: Cluster admin password (optional)

        Returns:
            Created Cluster instance

        Raises:
            ValueError: If cluster already exists or connection fails
            Exception: On other errors
        """
        logger.info(
            f"Creating cluster from RAS server: {ras_server}, "
            f"installation_service: {installation_service_url}"
        )

        try:
            # Connect to installation-service
            with ClusterServiceClient(base_url=installation_service_url) as client:
                # Health check
                logger.info(f"Performing health check for installation-service: {installation_service_url}")
                if not client.health_check():
                    raise ValueError(
                        f"Installation-service is not available at {installation_service_url}"
                    )

                logger.info("Health check passed, fetching cluster info from RAS")

                # Get cluster info (detailed=False for faster response)
                result = client.get_infobases(
                    server=ras_server,
                    cluster_user=cluster_user or None,
                    cluster_pwd=cluster_pwd or None,
                    detailed=False
                )

                cluster_id = result.get('cluster_id')
                cluster_name = result.get('cluster_name')

                if not cluster_id or not cluster_name:
                    raise ValueError(
                        f"Invalid response from installation-service: "
                        f"missing cluster_id or cluster_name"
                    )

                logger.info(
                    f"Retrieved cluster info: id={cluster_id}, name={cluster_name}, "
                    f"infobases_count={result.get('total_count', 0)}"
                )

                # Check if cluster already exists
                if Cluster.objects.filter(id=cluster_id).exists():
                    raise ValueError(
                        f"Cluster with id='{cluster_id}' already exists. "
                        f"Use sync_infobases() to update existing cluster."
                    )

                # Check uniqueness constraint (ras_server + name)
                if Cluster.objects.filter(ras_server=ras_server, name=cluster_name).exists():
                    raise ValueError(
                        f"Cluster with ras_server='{ras_server}' and name='{cluster_name}' "
                        f"already exists"
                    )

                # Create Cluster object
                cluster = Cluster.objects.create(
                    id=cluster_id,
                    name=cluster_name,
                    ras_server=ras_server,
                    installation_service_url=installation_service_url,
                    cluster_user=cluster_user or '',
                    cluster_pwd=cluster_pwd or '',
                    status=Cluster.STATUS_ACTIVE,
                    last_sync_status='pending',
                    metadata={
                        'infobase_count': result.get('total_count', 0),
                        'created_via': 'create_from_ras',
                        'initial_fetch_duration_ms': result.get('duration_ms', 0),
                    }
                )

                logger.info(
                    f"Successfully created cluster: {cluster.name} (id={cluster.id}), "
                    f"status={cluster.status}"
                )

                return cluster

        except ValueError:
            # Re-raise ValueError as-is
            raise

        except Exception as e:
            logger.error(
                f"Failed to create cluster from RAS {ras_server}: {type(e).__name__}: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    @transaction.atomic
    def sync_infobases(cluster: Cluster) -> Dict[str, int]:
        """
        Sync infobases from cluster.
        Uses SELECT FOR UPDATE to prevent concurrent syncs on same cluster.

        Steps:
        1. Lock cluster row with select_for_update()
        2. Check if already syncing
        3. Mark as pending
        4. Connect to installation-service
        5. Health check
        6. Call get_infobases (detailed=True)
        7. Call _import_infobases() to create/update Database records
        8. Mark cluster.mark_sync(success=True/False)

        Args:
            cluster: Cluster instance to sync

        Returns:
            {
                'created': 5,
                'updated': 10,
                'errors': 0
            }

        Raises:
            ValueError: If cluster is already being synced
            Exception: On sync errors
        """
        logger.info(f"Starting sync for cluster: {cluster.name} (id={cluster.id})")

        # Lock the cluster row to prevent concurrent syncs
        # Use nowait=True to immediately reject if cluster is already locked
        try:
            cluster = Cluster.objects.select_for_update(nowait=True).get(pk=cluster.pk)
        except OperationalError:
            raise ValueError(
                f"Cluster {cluster.name} is already being synced by another process. "
                f"Please wait for the current sync to complete."
            )

        # Check if already syncing (safety net for crash scenarios)
        if cluster.last_sync_status == 'pending':
            raise ValueError(
                f"Cluster {cluster.name} appears to be stuck in 'pending' state. "
                f"This may indicate a previous sync process crashed. "
                f"Please check the sync status or reset it manually."
            )

        # Mark as pending
        cluster.last_sync_status = 'pending'
        cluster.save(update_fields=['last_sync_status'])

        try:
            # Connect to installation-service
            with ClusterServiceClient(base_url=cluster.installation_service_url) as client:
                # Health check
                logger.info(
                    f"Performing health check for installation-service: "
                    f"{cluster.installation_service_url}"
                )
                if not client.health_check():
                    raise ValueError(
                        f"Installation-service is not available at "
                        f"{cluster.installation_service_url}"
                    )

                logger.info("Health check passed, fetching detailed infobases info")

                # Get detailed infobases info
                result = client.get_infobases(
                    server=cluster.ras_server,
                    cluster_user=cluster.cluster_user or None,
                    cluster_pwd=cluster.cluster_pwd or None,
                    detailed=True  # Get full information
                )

                infobases = result.get('infobases', [])
                logger.info(f"Retrieved {len(infobases)} infobases from cluster")

                # Import infobases into Database model
                created_count, updated_count, error_count = ClusterService._import_infobases(
                    cluster=cluster,
                    infobases=infobases
                )

                # Mark sync as successful
                cluster.mark_sync(success=True)

                # Update metadata with sync info
                cluster.metadata.update({
                    'last_sync_infobase_count': len(infobases),
                    'last_sync_duration_ms': result.get('duration_ms', 0),
                })
                cluster.save(update_fields=['metadata', 'updated_at'])

                summary = {
                    'created': created_count,
                    'updated': updated_count,
                    'errors': error_count
                }

                logger.info(
                    f"Sync completed for cluster {cluster.name}: "
                    f"created={created_count}, updated={updated_count}, errors={error_count}"
                )

                return summary

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(
                f"Failed to sync infobases for cluster {cluster.name}: {error_msg}",
                exc_info=True
            )

            # Mark sync as failed
            cluster.mark_sync(success=False, error_message=error_msg)

            # Re-raise exception
            raise

    @staticmethod
    def _import_infobases(cluster: Cluster, infobases: list) -> Tuple[int, int, int]:
        """
        Import infobases into Database model.

        For each infobase:
        1. Build OData URL using _build_odata_url()
        2. Parse host from db_server using _parse_host()
        3. Create/update Database using update_or_create()
        4. Fill metadata with all available info

        Args:
            cluster: Cluster instance
            infobases: List of infobase dictionaries from installation-service

        Returns:
            (created_count, updated_count, error_count)
        """
        logger.info(f"Importing {len(infobases)} infobases for cluster {cluster.name}")

        created_count = 0
        updated_count = 0
        error_count = 0

        for ib in infobases:
            try:
                # Extract infobase data
                ib_uuid = ib.get('uuid')
                ib_name = ib.get('name')

                if not ib_uuid or not ib_name:
                    logger.warning(f"Skipping infobase with missing uuid or name: {ib}")
                    error_count += 1
                    continue

                # Parse host from db_server
                db_server = ib.get('db_server', '')
                host = ClusterService._parse_host(db_server)

                # Build OData URL
                odata_url = ClusterService._build_odata_url(ib, default_host=host)

                # Prepare metadata
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
                    'cluster_id': str(cluster.id),  # Convert UUID to string for JSON
                    'cluster_name': cluster.name,
                }

                # Create or update Database
                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults={
                        'name': ib_name,
                        'description': ib.get('description', ''),
                        'host': host or 'localhost',
                        'port': 80,  # Default HTTP port
                        'base_name': ib_name,
                        'odata_url': odata_url,
                        'username': '',  # Will be set manually by admin
                        'password': '',  # Will be set manually by admin
                        'cluster': cluster,
                        'status': Database.STATUS_INACTIVE,  # Inactive until credentials configured
                        'metadata': metadata,
                    }
                )

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

        # Split by backslash (SQL Server instance separator)
        parts = db_server.split('\\')
        return parts[0]

    @staticmethod
    def _build_odata_url(ib: dict, default_host: str) -> str:
        """
        Build OData URL for infobase.

        Format: http://host/base_name/odata/standard.odata/

        Args:
            ib: Infobase dictionary from installation-service
            default_host: Default host to use if not specified in ib

        Returns:
            OData URL string
        """
        base_name = ib.get('name', '')
        host = default_host or 'localhost'

        # Build OData URL
        # Format: http://host/base_name/odata/standard.odata/
        odata_url = f"http://{host}/{base_name}/odata/standard.odata/"

        return odata_url

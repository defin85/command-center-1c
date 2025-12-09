"""Business logic for databases."""

import logging
from typing import Dict, List, Any, Tuple, Optional
from django.db import transaction, OperationalError
from django.utils import timezone

from .models import Database, DatabaseGroup, Cluster
from .odata import session_manager, ODataError
from .clients import RasAdapterClient, RasAdapterError
from .clients.generated.ras_adapter_api_client.models import (
    Infobase,
    InfobasesResponse,
    ClustersResponse,
)
from .clients.generated.ras_adapter_api_client.types import UNSET

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
    def create_from_ras(
        ras_server: str,
        ras_adapter_url: str = None,
        cluster_user: str = None,
        cluster_pwd: str = None
    ) -> Cluster:
        """
        Create Cluster by connecting to RAS server via RAS Adapter.

        Steps:
        1. Connect to RAS Adapter
        2. Health check
        3. Call list_clusters_v2 to get cluster info
        4. Check if cluster already exists
        5. Create Cluster object

        Args:
            ras_server: RAS server address (host:port)
            ras_adapter_url: URL of RAS Adapter (default: from settings)
            cluster_user: Cluster admin username (optional, stored for future use)
            cluster_pwd: Cluster admin password (optional, stored for future use)

        Returns:
            Created Cluster instance

        Raises:
            ValueError: If cluster already exists or connection fails
            RasAdapterError: On RAS Adapter errors
        """
        logger.info(f"Creating cluster from RAS server: {ras_server}")

        try:
            with RasAdapterClient(base_url=ras_adapter_url) as client:
                # Health check
                logger.info("Performing RAS Adapter health check")
                if not client.health_check():
                    raise ValueError("RAS Adapter is not available")

                logger.info("Health check passed, fetching clusters from RAS")

                # Get clusters from RAS server
                clusters_response: ClustersResponse = client.list_clusters(server=ras_server)

                if clusters_response.count == 0:
                    raise ValueError(f"No clusters found on RAS server {ras_server}")

                # Use first cluster (typically there's only one per RAS server)
                cluster_data = clusters_response.clusters[0]
                cluster_id = str(cluster_data.uuid)
                cluster_name = cluster_data.name

                logger.info(
                    f"Retrieved cluster info: id={cluster_id}, name={cluster_name}, "
                    f"total_clusters={clusters_response.count}"
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

                # Get infobase count for metadata
                try:
                    infobases_response = client.list_infobases(cluster_id=cluster_id)
                    infobase_count = infobases_response.count
                except Exception as e:
                    logger.warning(f"Could not get infobase count: {e}")
                    infobase_count = 0

                # Create Cluster object
                # Note: cluster_service_url now points to RAS Adapter
                from django.conf import settings
                adapter_url = ras_adapter_url or getattr(
                    settings, 'RAS_ADAPTER_URL', 'http://localhost:8188'
                )

                cluster = Cluster.objects.create(
                    id=cluster_id,
                    name=cluster_name,
                    ras_server=ras_server,
                    cluster_service_url=adapter_url,
                    cluster_user=cluster_user or '',
                    cluster_pwd=cluster_pwd or '',
                    status=Cluster.STATUS_ACTIVE,
                    last_sync_status='pending',
                    metadata={
                        'infobase_count': infobase_count,
                        'created_via': 'create_from_ras_v2',
                        'cluster_host': cluster_data.host,
                        'cluster_port': cluster_data.port,
                    }
                )

                logger.info(
                    f"Successfully created cluster: {cluster.name} (id={cluster.id}), "
                    f"status={cluster.status}"
                )

                return cluster

        except ValueError:
            raise

        except RasAdapterError as e:
            logger.error(f"RAS Adapter error creating cluster: {e}")
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
        Sync infobases from cluster using RAS Adapter v2 API.
        Uses SELECT FOR UPDATE to prevent concurrent syncs on same cluster.

        Steps:
        1. Lock cluster row with select_for_update()
        2. Check if already syncing
        3. Mark as pending
        4. Connect to RAS Adapter
        5. Health check
        6. Call list_infobases_v2
        7. Call _import_infobases_v2() to create/update Database records
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
            RasAdapterError: On RAS Adapter errors
        """
        logger.info(f"Starting sync for cluster: {cluster.name} (id={cluster.id})")

        # Lock the cluster row to prevent concurrent syncs
        try:
            cluster = Cluster.objects.select_for_update(nowait=True).get(pk=cluster.pk)
        except OperationalError:
            raise ValueError(
                f"Cluster {cluster.name} is already being synced by another process. "
                f"Please wait for the current sync to complete."
            )

        # Mark as pending (or confirm already pending from view)
        # Note: select_for_update(nowait=True) above handles concurrent sync protection
        if cluster.last_sync_status != 'pending':
            cluster.last_sync_status = 'pending'
            cluster.save(update_fields=['last_sync_status'])

        try:
            # Connect to RAS Adapter
            with RasAdapterClient(base_url=cluster.cluster_service_url) as client:
                # Health check
                logger.info(f"Performing RAS Adapter health check: {cluster.cluster_service_url}")
                if not client.health_check():
                    raise ValueError(
                        f"RAS Adapter is not available at {cluster.cluster_service_url}"
                    )

                logger.info("Health check passed, resolving RAS cluster UUID")

                # If ras_cluster_uuid is already saved, use it directly
                if cluster.ras_cluster_uuid:
                    ras_cluster_uuid = str(cluster.ras_cluster_uuid)
                    logger.info(
                        f"Using saved RAS cluster UUID: {ras_cluster_uuid}"
                    )
                else:
                    # Need to resolve UUID from RAS - get list of clusters
                    logger.info("No saved RAS cluster UUID, fetching from RAS")
                    clusters_response = client.list_clusters(server=cluster.ras_server)

                    if not clusters_response.clusters:
                        raise ValueError(f"No clusters found on RAS server {cluster.ras_server}")

                    # Find the cluster - use first one if only one exists, otherwise match by name
                    ras_cluster = None
                    if len(clusters_response.clusters) == 1:
                        ras_cluster = clusters_response.clusters[0]
                        logger.info(
                            f"Single cluster on RAS server, using: {ras_cluster.name}"
                        )
                    else:
                        # Try to match by name
                        for c in clusters_response.clusters:
                            if c.name == cluster.name:
                                ras_cluster = c
                                logger.info(
                                    f"Matched cluster by name: {ras_cluster.name}"
                                )
                                break

                        if not ras_cluster:
                            # Cannot auto-resolve - require manual configuration
                            available_clusters = [
                                f"'{c.name}' (uuid={c.uuid})"
                                for c in clusters_response.clusters
                            ]
                            raise ValueError(
                                f"Cannot auto-match cluster '{cluster.name}' on RAS server. "
                                f"Multiple clusters available: {', '.join(available_clusters)}. "
                                f"Please set 'ras_cluster_uuid' field manually in admin panel "
                                f"to specify which RAS cluster to use."
                            )

                    ras_cluster_uuid = str(ras_cluster.uuid)

                    # Save the resolved UUID for future syncs
                    cluster.ras_cluster_uuid = ras_cluster.uuid
                    cluster.save(update_fields=['ras_cluster_uuid', 'updated_at'])
                    logger.info(
                        f"Saved RAS cluster UUID: {ras_cluster_uuid} for cluster {cluster.name}"
                    )

                # Get infobases using v2 API with correct RAS cluster UUID
                infobases_response: InfobasesResponse = client.list_infobases(
                    cluster_id=ras_cluster_uuid
                )

                logger.info(f"Retrieved {infobases_response.count} infobases from cluster")

                # Import infobases into Database model using v2 types
                created_count, updated_count, error_count = ClusterService._import_infobases_v2(
                    cluster=cluster,
                    infobases=infobases_response.infobases
                )

                # Mark sync as successful
                cluster.mark_sync(success=True)

                # Update metadata with sync info
                cluster.metadata.update({
                    'last_sync_infobase_count': infobases_response.count,
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
            raise

    @staticmethod
    def _import_infobases_v2(
        cluster: Cluster,
        infobases: List[Infobase]
    ) -> Tuple[int, int, int]:
        """
        Import infobases into Database model using v2 Infobase types.

        For each infobase:
        1. Build OData URL using _build_odata_url_v2()
        2. Parse host from db_server using _parse_host()
        3. Create/update Database using update_or_create()
        4. Fill metadata with all available info from v2 type

        Args:
            cluster: Cluster instance
            infobases: List of Infobase objects from RAS Adapter v2 API

        Returns:
            (created_count, updated_count, error_count)
        """
        logger.info(f"Importing {len(infobases)} infobases for cluster {cluster.name}")

        created_count = 0
        updated_count = 0
        error_count = 0

        for ib in infobases:
            try:
                # v2 types have direct attribute access
                ib_uuid = str(ib.uuid)
                ib_name = ib.name

                if not ib_uuid or not ib_name:
                    logger.warning("Skipping infobase with missing uuid or name")
                    error_count += 1
                    continue

                # Parse host from db_server (handle UNSET)
                db_server = ib.db_server if not isinstance(ib.db_server, type(UNSET)) else ''
                host = ClusterService._parse_host(db_server)

                # Build OData URL
                odata_url = ClusterService._build_odata_url_v2(ib, default_host=host)

                # Get optional fields (handle UNSET)
                db_name = ib.db_name if not isinstance(ib.db_name, type(UNSET)) else ''
                locale = ib.locale if not isinstance(ib.locale, type(UNSET)) else ''

                # Prepare metadata with v2 fields
                metadata = {
                    'dbms': ib.dbms,
                    'db_server': db_server,
                    'db_name': db_name,
                    'locale': locale,
                    'sessions_deny': ib.sessions_deny,
                    'scheduled_jobs_deny': ib.scheduled_jobs_deny,
                    'imported_from_cluster': True,
                    'import_timestamp': timezone.now().isoformat(),
                    'ras_server': cluster.ras_server,
                    'cluster_id': str(cluster.id),
                    'cluster_name': cluster.name,
                    'api_version': 'v2',
                }

                # Add denied_from/denied_to if set
                if not isinstance(ib.denied_from, type(UNSET)) and ib.denied_from:
                    metadata['denied_from'] = ib.denied_from.isoformat()
                if not isinstance(ib.denied_to, type(UNSET)) and ib.denied_to:
                    metadata['denied_to'] = ib.denied_to.isoformat()
                if not isinstance(ib.denied_message, type(UNSET)) and ib.denied_message:
                    metadata['denied_message'] = ib.denied_message

                # Create or update Database
                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults={
                        'name': ib_name,
                        'description': '',  # v2 API doesn't have description
                        'host': host or 'localhost',
                        'port': 80,
                        'base_name': ib_name,
                        'odata_url': odata_url,
                        'username': '',
                        'password': '',
                        'cluster': cluster,
                        'status': Database.STATUS_INACTIVE,
                        'metadata': metadata,
                    }
                )

                if created:
                    created_count += 1
                    logger.info(f"Created database: {ib_name} (id={ib_uuid})")
                else:
                    updated_count += 1
                    logger.debug(f"Updated database: {ib_name} (id={ib_uuid})")

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import infobase {getattr(ib, 'name', 'unknown')}: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True
                )

        logger.info(
            f"Import completed: created={created_count}, updated={updated_count}, "
            f"errors={error_count}"
        )

        return created_count, updated_count, error_count

    @staticmethod
    def _import_infobases(cluster: Cluster, infobases: list) -> Tuple[int, int, int]:
        """
        Import infobases into Database model (legacy dict format).

        DEPRECATED: Use _import_infobases_v2() with Infobase objects instead.

        Args:
            cluster: Cluster instance
            infobases: List of infobase dictionaries (legacy format)

        Returns:
            (created_count, updated_count, error_count)
        """
        logger.warning(
            "_import_infobases() is deprecated. Use _import_infobases_v2() with v2 types."
        )
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
                        'status': Database.STATUS_INACTIVE,
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

        parts = db_server.split('\\')
        return parts[0]

    @staticmethod
    def _build_odata_url_v2(ib: Infobase, default_host: str) -> str:
        """
        Build OData URL for infobase using v2 Infobase type.

        Format: http://host/base_name/odata/standard.odata/

        Args:
            ib: Infobase object from RAS Adapter v2 API
            default_host: Default host to use if db_server is not set

        Returns:
            OData URL string
        """
        base_name = ib.name
        host = default_host or 'localhost'

        return f"http://{host}/{base_name}/odata/standard.odata/"

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
                    'locale': ib.get('locale', ''),
                    'sessions_deny': ib.get('sessions_deny', False),
                    'scheduled_jobs_deny': ib.get('scheduled_jobs_deny', False),
                    'imported_from_cluster': True,
                    'import_timestamp': timezone.now().isoformat(),
                    'ras_server': cluster.ras_server,
                    'cluster_id': str(cluster.id),
                    'cluster_name': cluster.name,
                    'api_version': 'worker',
                }

                # Add denied_from/denied_to if set
                if ib.get('denied_from'):
                    metadata['denied_from'] = ib['denied_from']
                if ib.get('denied_to'):
                    metadata['denied_to'] = ib['denied_to']
                if ib.get('denied_message'):
                    metadata['denied_message'] = ib['denied_message']

                # Create or update Database
                database, created = Database.objects.update_or_create(
                    id=ib_uuid,
                    defaults={
                        'name': ib_name,
                        'description': '',
                        'host': host or 'localhost',
                        'port': 80,
                        'base_name': ib_name,
                        'odata_url': odata_url,
                        'username': '',
                        'password': '',
                        'cluster': cluster,
                        'status': Database.STATUS_INACTIVE,
                        'metadata': metadata,
                    }
                )

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

from typing import Any, Dict

from django.db import transaction

from apps.operations.redis_client import redis_client

from .flow import get_workflow_metadata, publish_completion_flow
from . import runtime


class ClusterEventHandlersMixin:
    def handle_cluster_synced(self, payload: Dict[str, Any], correlation_id: str) -> None:
        from apps.databases.models import Cluster
        from apps.databases.services import ClusterService
        from apps.operations.models import BatchOperation

        operation_id = payload.get("operation_id")
        cluster_id = payload.get("cluster_id")
        ras_cluster_uuid = payload.get("ras_cluster_uuid")
        infobases = payload.get("infobases", [])
        success = payload.get("success", False)
        error = payload.get("error")

        runtime.logger.info(
            "Cluster synced event: cluster_id=%s, operation_id=%s, success=%s, "
            "infobases_count=%s, correlation_id=%s",
            cluster_id,
            operation_id,
            success,
            len(infobases),
            correlation_id,
        )

        try:
            with transaction.atomic():
                try:
                    cluster = Cluster.objects.select_for_update().get(id=cluster_id)
                except Cluster.DoesNotExist:
                    runtime.logger.error("Cluster not found: %s", cluster_id)
                    return

                if success:
                    if ras_cluster_uuid and not cluster.ras_cluster_uuid:
                        cluster.ras_cluster_uuid = ras_cluster_uuid
                        cluster.save(update_fields=["ras_cluster_uuid", "updated_at"])
                        runtime.logger.info(
                            "Updated ras_cluster_uuid for cluster %s: %s",
                            cluster.name,
                            ras_cluster_uuid,
                        )

                    if infobases:
                        created, updated, errors = ClusterService.import_infobases_from_dict(
                            cluster=cluster,
                            infobases=infobases,
                        )
                        runtime.logger.info(
                            "Imported infobases for cluster %s: created=%s, updated=%s, errors=%s",
                            cluster.name,
                            created,
                            updated,
                            errors,
                        )

                    cluster.mark_sync(success=True)
                else:
                    error_msg = error or "Unknown error from Worker"
                    cluster.mark_sync(success=False, error_message=error_msg)
                    runtime.logger.error(
                        "Cluster sync failed: cluster=%s, error=%s",
                        cluster.name,
                        error_msg,
                    )

                if operation_id:
                    try:
                        batch_op = BatchOperation.objects.get(id=operation_id)
                        if success:
                            batch_op.status = BatchOperation.STATUS_COMPLETED
                            batch_op.metadata["sync_result"] = {
                                "infobases_count": len(infobases),
                                "ras_cluster_uuid": ras_cluster_uuid,
                            }
                        else:
                            batch_op.status = BatchOperation.STATUS_FAILED
                            batch_op.metadata["error"] = error

                        batch_op.save(update_fields=["status", "metadata", "updated_at"])
                        workflow_metadata = get_workflow_metadata(batch_op)
                        try:
                            runtime.operations_redis_client.add_timeline_event(
                                operation_id,
                                event="operation.completed" if success else "operation.failed",
                                service="event-subscriber",
                                metadata={
                                    "status": batch_op.status,
                                    "cluster_id": str(cluster_id),
                                    "error": error if not success else None,
                                    **workflow_metadata,
                                },
                            )
                        except Exception:
                            pass

                        publish_completion_flow(
                            operation_id=operation_id,
                            operation_type=batch_op.operation_type,
                            operation_name=batch_op.name,
                            status="completed" if success else "failed",
                            message="Cluster sync completed"
                            if success
                            else "Cluster sync failed",
                            metadata={
                                "cluster_id": str(cluster_id),
                                "error": error if not success else None,
                                **workflow_metadata,
                            },
                        )
                        runtime.logger.info(
                            "Updated BatchOperation %s status: %s",
                            operation_id,
                            batch_op.status,
                        )
                    except BatchOperation.DoesNotExist:
                        runtime.logger.debug(
                            "BatchOperation not found: %s (may be direct sync without BatchOperation)",
                            operation_id,
                        )

        except Exception as e:
            runtime.logger.error(
                "Error handling cluster-synced event: %s", e, exc_info=True
            )
        finally:
            if cluster_id:
                sync_lock_key = f"sync_cluster:{cluster_id}"
                redis_client.release_lock(sync_lock_key)
                runtime.logger.debug("Released sync lock for cluster %s", cluster_id)

    def handle_clusters_discovered(self, payload: Dict[str, Any], correlation_id: str) -> None:
        from apps.databases.models import Cluster
        from apps.operations.models import BatchOperation

        operation_id = payload.get("operation_id")
        ras_server = payload.get("ras_server")
        clusters_data = payload.get("clusters", [])
        success = payload.get("success", False)
        error = payload.get("error")

        runtime.logger.info(
            "Clusters discovered event: ras_server=%s, operation_id=%s, success=%s, "
            "clusters_count=%s, correlation_id=%s",
            ras_server,
            operation_id,
            success,
            len(clusters_data),
            correlation_id,
        )

        created = 0
        updated = 0

        try:
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

            ras_host, ras_port = _parse_host_port(ras_server or "")
            ras_port = ras_port or 1545
            with transaction.atomic():
                if success and clusters_data:
                    for cluster_data in clusters_data:
                        cluster_uuid = cluster_data.get("uuid")
                        cluster_name = cluster_data.get("name", "Unknown")

                        cluster_service_url = (
                            f"http://{ras_server}" if ras_server else "http://localhost"
                        )
                        rmngr_host = (cluster_data.get("host") or ras_host or "").strip()
                        rmngr_port = cluster_data.get("port") or 1541
                        ragent_host = rmngr_host or ras_host or ""

                        cluster, is_new = Cluster.objects.get_or_create(
                            ras_cluster_uuid=cluster_uuid,
                            defaults={
                                "name": cluster_name,
                                "ras_server": ras_server,
                                "ras_host": ras_host,
                                "ras_port": ras_port,
                                "rmngr_host": rmngr_host,
                                "rmngr_port": rmngr_port,
                                "ragent_host": ragent_host,
                                "ragent_port": 1540,
                                "rphost_port_from": 1560,
                                "rphost_port_to": 1591,
                                "cluster_service_url": cluster_service_url,
                                "status": "active",
                                "metadata": cluster_data,
                            },
                        )

                        if not is_new:
                            updates = {
                                "name": cluster_name,
                                "ras_server": ras_server,
                                "ras_host": ras_host,
                                "ras_port": ras_port,
                                "cluster_service_url": cluster_service_url,
                                "status": "active",
                                "metadata": cluster_data,
                            }
                            if not cluster.rmngr_host and rmngr_host:
                                updates["rmngr_host"] = rmngr_host
                            if not cluster.rmngr_port and rmngr_port:
                                updates["rmngr_port"] = rmngr_port
                            if not cluster.ragent_host and ragent_host:
                                updates["ragent_host"] = ragent_host
                            if not cluster.ragent_port:
                                updates["ragent_port"] = 1540
                            if not cluster.rphost_port_from:
                                updates["rphost_port_from"] = 1560
                            if not cluster.rphost_port_to:
                                updates["rphost_port_to"] = 1591
                            Cluster.objects.filter(pk=cluster.pk).update(**updates)

                        if is_new:
                            created += 1
                            runtime.logger.info(
                                "Created new cluster: %s (uuid=%s, ras_server=%s)",
                                cluster_name,
                                cluster_uuid,
                                ras_server,
                            )
                        else:
                            updated += 1
                            runtime.logger.info(
                                "Updated cluster: %s (uuid=%s, ras_server=%s)",
                                cluster_name,
                                cluster_uuid,
                                ras_server,
                            )

                if operation_id:
                    try:
                        batch_op = BatchOperation.objects.get(id=operation_id)
                        if success:
                            batch_op.status = BatchOperation.STATUS_COMPLETED
                            batch_op.metadata["discovery_result"] = {
                                "clusters_found": len(clusters_data),
                                "created": created,
                                "updated": updated,
                            }
                        else:
                            batch_op.status = BatchOperation.STATUS_FAILED
                            batch_op.metadata["error"] = error
                        batch_op.save(update_fields=["status", "metadata", "updated_at"])

                        workflow_metadata = get_workflow_metadata(batch_op)
                        try:
                            runtime.operations_redis_client.add_timeline_event(
                                operation_id,
                                event="operation.completed" if success else "operation.failed",
                                service="event-subscriber",
                                metadata={
                                    "status": batch_op.status,
                                    "ras_server": ras_server,
                                    "clusters_found": len(clusters_data),
                                    "created": created,
                                    "updated": updated,
                                    "error": error if not success else None,
                                    **workflow_metadata,
                                },
                            )
                        except Exception:
                            pass

                        publish_completion_flow(
                            operation_id=operation_id,
                            operation_type=batch_op.operation_type,
                            operation_name=batch_op.name,
                            status="completed" if success else "failed",
                            message="Clusters discovery completed"
                            if success
                            else "Clusters discovery failed",
                            metadata={
                                "ras_server": ras_server,
                                "clusters_found": len(clusters_data),
                                "error": error if not success else None,
                                **workflow_metadata,
                            },
                        )
                        runtime.logger.info(
                            "Updated BatchOperation %s status: %s",
                            operation_id,
                            batch_op.status,
                        )
                    except BatchOperation.DoesNotExist:
                        runtime.logger.debug("BatchOperation not found: %s", operation_id)

        except Exception as e:
            runtime.logger.error(
                "Error handling clusters-discovered event: %s", e, exc_info=True
            )
        finally:
            if ras_server:
                discover_lock_key = f"discover_clusters:{ras_server}"
                redis_client.release_lock(discover_lock_key)
                runtime.logger.debug("Released discover lock for ras_server %s", ras_server)

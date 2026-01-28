# orchestrator/apps/templates/tests/test_registry_thread_safety.py
"""
Tests for thread-safe singleton access.
"""

from threading import Thread, Lock

from apps.templates.registry import (
    get_registry,
    OperationType,
    BackendType,
    TargetEntity,
    OperationTypeRegistry,
)


class TestOperationTypeRegistryThreadSafety:
    """Tests for thread-safe singleton access."""

    def test_concurrent_singleton_access(self):
        """Test concurrent access to singleton returns same instance."""
        instances = []
        lock = Lock()

        def get_instance():
            instance = OperationTypeRegistry()
            with lock:
                instances.append(instance)

        threads = [Thread(target=get_instance) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(instances) == 10
        for instance in instances[1:]:
            assert instance is instances[0]

    def test_concurrent_get_registry(self):
        """Test concurrent access via get_registry()."""
        instances = []
        lock = Lock()

        def get_registry_instance():
            instance = get_registry()
            with lock:
                instances.append(instance)

        threads = [Thread(target=get_registry_instance) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(instances) == 10
        for instance in instances[1:]:
            assert instance is instances[0]

    def test_concurrent_registration(self):
        """Test concurrent registration of operations."""
        registry = get_registry()
        registry.clear()

        def register_operation(op_id):
            op = OperationType(
                id=op_id,
                name=f'Op {op_id}',
                description='',
                backend=BackendType.RAS,
                target_entity=TargetEntity.INFOBASE,
            )
            registry.register(op)

        threads = [Thread(target=register_operation, args=(f'op_{i}',)) for i in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should be registered
        assert len(registry.get_all()) == 10

        registry.clear()


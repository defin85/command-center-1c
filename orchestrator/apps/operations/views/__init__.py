"""
Views module for operations app.

This package handles the split between:
- service_mesh.py (new Service Mesh monitoring views)
- ../views.py (legacy operations views like BatchOperationViewSet)
"""
import sys
import os

# First import service_mesh views
from .service_mesh import (
    ServiceMeshMetricsView,
    ServiceMeshHistoryView,
    ServiceMeshOperationsView,
)

# Then dynamically load the parent views.py module to get BatchOperationViewSet
# We need to do this carefully to avoid infinite recursion
try:
    # Try to import from the parent directory's views.py file directly
    _parent_dir = os.path.dirname(os.path.dirname(__file__))
    _views_py_path = os.path.join(_parent_dir, 'views.py')

    import importlib.util
    if os.path.exists(_views_py_path):
        spec = importlib.util.spec_from_file_location(
            'apps.operations._views_module',
            _views_py_path
        )
        _views_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_views_module)

        BatchOperationViewSet = _views_module.BatchOperationViewSet
        operation_callback = _views_module.operation_callback
        operation_stream = _views_module.operation_stream
    else:
        # Fallback: create dummy classes
        BatchOperationViewSet = None
        operation_callback = None
        operation_stream = None
except Exception:
    # If loading fails, set to None
    BatchOperationViewSet = None
    operation_callback = None
    operation_stream = None

__all__ = [
    'ServiceMeshMetricsView',
    'ServiceMeshHistoryView',
    'ServiceMeshOperationsView',
    'BatchOperationViewSet',
    'operation_callback',
    'operation_stream',
]

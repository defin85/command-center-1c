"""
API v2 - Action-based REST API for CommandCenter1C.

This module provides a unified API with action-based routing:
- /api/v2/databases/list-databases/
- /api/v2/clusters/sync-cluster/
- etc.

All endpoints follow the pattern: /{resource}/{action}/
"""

default_app_config = 'apps.api_v2.apps.ApiV2Config'

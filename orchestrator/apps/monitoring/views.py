"""
System monitoring API views.
"""

import asyncio

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .services import SystemHealthService

import logging

logger = logging.getLogger(__name__)


class SystemHealthViewSet(viewsets.ViewSet):
    """
    ViewSet for system health monitoring.
    
    Endpoints:
        GET /system/health - Get overall system health status
    """
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'], url_path='health')
    def health(self, request):
        """
        Get system health status for all monitored services.
        
        Returns cached status if available (TTL 10 seconds),
        otherwise performs fresh health check.
        """
        try:
            # Run async health check
            health_data = asyncio.run(SystemHealthService.get_or_check_health())
            return Response(health_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to get system health',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

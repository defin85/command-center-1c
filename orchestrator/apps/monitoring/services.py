"""
System Health Check Service.
Asynchronously checks all monitored services and caches results.
"""

import asyncio
import time
from typing import Dict, Any, Optional

import aiohttp
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

import logging

logger = logging.getLogger(__name__)


class SystemHealthService:
    """Service for checking health of all system components."""
    
    CACHE_KEY = "system:health"
    CACHE_TTL = 10  # seconds
    REQUEST_TIMEOUT = 3  # seconds
    
    @classmethod
    async def _check_http_service(cls, service_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check health of HTTP service.
        
        Args:
            service_config: Service configuration with 'name', 'health_url', etc.
            
        Returns:
            Service health status dict
        """
        start_time = time.time()
        result = {
            'name': service_config['name'],
            'type': service_config.get('type', 'backend'),
            'url': service_config.get('health_url'),
            'status': 'offline',
            'response_time_ms': None,
            'last_check': timezone.now().isoformat(),
            'details': {}
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=cls.REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(service_config['health_url']) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    result['response_time_ms'] = response_time_ms
                    
                    if response.status == 200:
                        result['status'] = 'online'
                        # Try to parse JSON response for details
                        try:
                            data = await response.json()
                            result['details'] = data
                        except Exception:
                            pass
                    else:
                        result['status'] = 'degraded'
                        result['details'] = {'http_status': response.status}
                        
        except asyncio.TimeoutError:
            result['details'] = {'error': 'timeout'}
            logger.warning(f"Service {service_config['name']} health check timeout")
        except aiohttp.ClientError as e:
            result['details'] = {'error': str(e)}
            logger.warning(f"Service {service_config['name']} health check failed: {e}")
        except Exception as e:
            result['details'] = {'error': str(e)}
            logger.error(f"Unexpected error checking {service_config['name']}: {e}")
            
        return result
    
    @classmethod
    async def _check_database_async(cls) -> Dict[str, Any]:
        """Check PostgreSQL database connection (async wrapper)."""
        
        @sync_to_async
        def _do_check():
            start_time = time.time()
            result = {
                'name': 'PostgreSQL',
                'type': 'infrastructure',
                'status': 'offline',
                'response_time_ms': None,
                'last_check': timezone.now().isoformat(),
                'details': {}
            }
            
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                
                response_time_ms = int((time.time() - start_time) * 1000)
                result['response_time_ms'] = response_time_ms
                result['status'] = 'online'
                result['details'] = {
                    'vendor': connection.vendor,
                    'database': str(connection.settings_dict.get('NAME', ''))
                }
            except Exception as e:
                result['details'] = {'error': str(e)}
                logger.error(f"Database health check failed: {e}")
                
            return result
        
        return await _do_check()
    
    @classmethod
    async def _check_redis_async(cls) -> Dict[str, Any]:
        """Check Redis connection (async wrapper)."""
        
        @sync_to_async
        def _do_check():
            start_time = time.time()
            result = {
                'name': 'Redis',
                'type': 'infrastructure',
                'status': 'offline',
                'response_time_ms': None,
                'last_check': timezone.now().isoformat(),
                'details': {}
            }
            
            try:
                # Use Django cache to ping Redis
                cache.set('health_check_ping', '1', timeout=1)
                value = cache.get('health_check_ping')
                
                response_time_ms = int((time.time() - start_time) * 1000)
                result['response_time_ms'] = response_time_ms
                
                if value == '1':
                    result['status'] = 'online'
                else:
                    result['status'] = 'degraded'
                    result['details'] = {'error': 'ping failed'}
                    
            except Exception as e:
                result['details'] = {'error': str(e)}
                logger.error(f"Redis health check failed: {e}")
                
            return result
        
        return await _do_check()
    
    @classmethod
    async def check_all_services(cls) -> Dict[str, Any]:
        """
        Check all monitored services asynchronously.
        
        Returns:
            Health status dict with all services and statistics
        """
        services_to_check = getattr(settings, 'MONITORED_SERVICES', [])
        
        # Create async tasks for HTTP services
        http_tasks = [
            cls._check_http_service(service)
            for service in services_to_check
            if service.get('health_url')
        ]
        
        # Run all HTTP checks in parallel
        http_results = await asyncio.gather(*http_tasks, return_exceptions=True)
        
        # Filter out exceptions and convert to dict
        services = []
        for result in http_results:
            if isinstance(result, Exception):
                logger.error(f"Service check raised exception: {result}")
            else:
                services.append(result)
        
        # Add async infrastructure checks
        db_result = await cls._check_database_async()
        redis_result = await cls._check_redis_async()
        services.append(db_result)
        services.append(redis_result)
        
        # Calculate statistics
        total = len(services)
        online = sum(1 for s in services if s['status'] == 'online')
        offline = sum(1 for s in services if s['status'] == 'offline')
        degraded = sum(1 for s in services if s['status'] == 'degraded')
        
        # Determine overall status
        critical_services = [
            service['name'] for service in services_to_check 
            if service.get('critical', False)
        ]
        critical_offline = [
            s for s in services 
            if s['name'] in critical_services and s['status'] != 'online'
        ]
        
        if critical_offline:
            overall_status = 'critical'
        elif offline > 0 or degraded > 0:
            overall_status = 'degraded'
        else:
            overall_status = 'healthy'
        
        return {
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall_status,
            'services': services,
            'statistics': {
                'total': total,
                'online': online,
                'offline': offline,
                'degraded': degraded
            }
        }
    
    @classmethod
    def get_cached_health(cls) -> Optional[Dict[str, Any]]:
        """
        Get cached health status.
        
        Returns:
            Cached health status or None if not cached
        """
        return cache.get(cls.CACHE_KEY)
    
    @classmethod
    def set_cached_health(cls, health_data: Dict[str, Any]) -> None:
        """Cache health status."""
        cache.set(cls.CACHE_KEY, health_data, cls.CACHE_TTL)
    
    @classmethod
    async def get_or_check_health(cls) -> Dict[str, Any]:
        """
        Get health status from cache or check all services.
        
        Returns:
            Health status dict
        """
        cached = cls.get_cached_health()
        if cached:
            logger.debug("Returning cached health status")
            return cached
        
        logger.info("Performing fresh health check")
        health_data = await cls.check_all_services()
        cls.set_cached_health(health_data)
        
        return health_data

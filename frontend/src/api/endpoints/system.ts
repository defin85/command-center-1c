/**
 * System monitoring API endpoints
 *
 * @deprecated This module is deprecated. Use `@/api/adapters/system` instead.
 * Migration: Replace imports from 'endpoints/system' with 'adapters/system'.
 * Scheduled for removal in v3.0.0.
 */

import { apiClient } from '../client';

export interface ServiceHealth {
    name: string;
    type: string;
    url?: string;
    status: 'online' | 'offline' | 'degraded';
    response_time_ms: number | null;
    last_check: string;
    details?: Record<string, any>;
}

export interface SystemHealthStatistics {
    total: number;
    online: number;
    offline: number;
    degraded: number;
}

export interface SystemHealthResponse {
    timestamp: string;
    overall_status: 'healthy' | 'degraded' | 'critical';
    services: ServiceHealth[];
    statistics: SystemHealthStatistics;
}

/**
 * Get system health status for all monitored services
 */
export const getSystemHealth = async (): Promise<SystemHealthResponse> => {
    // v2 migration: trailing slash for Django DRF compatibility
    const response = await apiClient.get<SystemHealthResponse>('/system/health/');
    return response.data;
};

export const systemApi = {
    getHealth: getSystemHealth,
};

export default systemApi;

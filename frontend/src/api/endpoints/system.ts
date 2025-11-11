/**
 * System monitoring API endpoints
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
    const response = await apiClient.get<SystemHealthResponse>('/system/health');
    return response.data;
};

export const systemApi = {
    getHealth: getSystemHealth,
};

export default systemApi;

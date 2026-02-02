export type ServiceName =
  | 'frontend'
  | 'api-gateway'
  | 'orchestrator'
  | 'worker'
  | 'minio'

export interface KnownService {
  name: ServiceName
  title: string
  url?: string
  healthPath?: string
}

function envUrl(key: string): string | undefined {
  const v = (import.meta.env as Record<string, unknown>)[key]
  if (typeof v !== 'string') return undefined
  const trimmed = v.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

import { getBaseHost } from '../api/baseUrl'

const baseHost = getBaseHost()

export const KNOWN_SERVICES: KnownService[] = [
  {
    name: 'frontend',
    title: 'Frontend',
    url: envUrl('VITE_FRONTEND_URL') ?? `http://${baseHost}:15173`,
  },
  {
    name: 'api-gateway',
    title: 'API Gateway',
    url: envUrl('VITE_API_GATEWAY_URL') ?? `http://${baseHost}:8180`,
    healthPath: '/health',
  },
  {
    name: 'orchestrator',
    title: 'Orchestrator',
    url: envUrl('VITE_ORCHESTRATOR_URL') ?? `http://${baseHost}:8200`,
    healthPath: '/health',
  },
  {
    name: 'worker',
    title: 'Worker',
    url: envUrl('VITE_WORKER_URL') ?? `http://${baseHost}:9091`,
    healthPath: '/health',
  },
  {
    name: 'minio',
    title: 'MinIO',
    url: envUrl('VITE_MINIO_URL') ?? `http://${baseHost}:9000`,
    healthPath: '/minio/health/ready',
  },
]

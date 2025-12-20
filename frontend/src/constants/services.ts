export type ServiceName =
  | 'frontend'
  | 'api-gateway'
  | 'orchestrator'
  | 'worker'
  | 'ras-adapter'

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

export const KNOWN_SERVICES: KnownService[] = [
  {
    name: 'frontend',
    title: 'Frontend',
    url: envUrl('VITE_FRONTEND_URL') ?? 'http://localhost:5173',
  },
  {
    name: 'api-gateway',
    title: 'API Gateway',
    url: envUrl('VITE_API_GATEWAY_URL') ?? 'http://localhost:8180',
    healthPath: '/health',
  },
  {
    name: 'orchestrator',
    title: 'Orchestrator',
    url: envUrl('VITE_ORCHESTRATOR_URL') ?? 'http://localhost:8200',
    healthPath: '/health',
  },
  {
    name: 'worker',
    title: 'Worker',
    url: envUrl('VITE_WORKER_URL') ?? 'http://localhost:9091',
    healthPath: '/health',
  },
  {
    name: 'ras-adapter',
    title: 'RAS Adapter',
    url: envUrl('VITE_RAS_ADAPTER_URL') ?? 'http://localhost:8188',
    healthPath: '/health',
  },
]

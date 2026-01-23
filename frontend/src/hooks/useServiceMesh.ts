import { useCallback, useEffect, useState } from 'react'
import type {
  ServiceMetrics,
  ServiceConnection,
  ServiceStatus,
  OperationFlowEvent,
} from '../types/serviceMesh'
import { serviceMeshManager, type InvalidationEvent } from '../stores/serviceMeshManager'

export interface UseServiceMeshResult {
  services: ServiceMetrics[]
  connections: ServiceConnection[]
  overallHealth: ServiceStatus
  timestamp: string | null
  isConnected: boolean
  connectionError: string | null
  reconnectAttempts: number
  refresh: () => void
  setUpdateInterval: (seconds: number) => void
  disconnect: () => void
  activeOperation: OperationFlowEvent | null
  operationHistory: OperationFlowEvent[]
  lastInvalidation: InvalidationEvent | null
}

export const useServiceMesh = (options?: { enabled?: boolean }): UseServiceMeshResult => {
  const enabled = options?.enabled ?? true
  const [state, setState] = useState(() => serviceMeshManager.getState())

  useEffect(() => {
    if (!enabled) return
    const unsubscribe = serviceMeshManager.subscribe(setState)
    return () => unsubscribe()
  }, [enabled])

  useEffect(() => {
    if (!enabled) return
    serviceMeshManager.start()
    return () => {
      serviceMeshManager.stop()
    }
  }, [enabled])

  const refresh = useCallback(() => {
    serviceMeshManager.refresh()
  }, [])

  const setUpdateInterval = useCallback((seconds: number) => {
    serviceMeshManager.setUpdateInterval(seconds)
  }, [])

  const disconnect = useCallback(() => {
    serviceMeshManager.disconnect()
  }, [])

  return {
    services: state.services,
    connections: state.connections,
    overallHealth: state.overallHealth,
    timestamp: state.timestamp,
    isConnected: state.isConnected,
    connectionError: state.connectionError,
    reconnectAttempts: state.reconnectAttempts,
    refresh,
    setUpdateInterval,
    disconnect,
    activeOperation: state.activeOperation,
    operationHistory: state.operationHistory,
    lastInvalidation: state.lastInvalidation,
  }
}

export default useServiceMesh

import { useCallback, useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { databaseStreamManager } from '../stores/databaseStreamManager'

interface UseDatabaseStreamInvalidationOptions {
  clusterId?: string | null
  enabled?: boolean
}

export const useDatabaseStreamInvalidation = ({
  clusterId: _clusterId,
  enabled = true,
}: UseDatabaseStreamInvalidationOptions) => {
  const queryClient = useQueryClient()
  const [state, setState] = useState(() => databaseStreamManager.getState())

  useEffect(() => {
    const unsubscribe = databaseStreamManager.subscribe(setState)
    return () => unsubscribe()
  }, [])

  useEffect(() => {
    databaseStreamManager.setQueryClient(queryClient)
  }, [queryClient])

  useEffect(() => {
    if (!enabled) return
    databaseStreamManager.start()
    return () => {
      databaseStreamManager.stop()
    }
  }, [enabled])

  const reconnect = useCallback(() => {
    if (!enabled) return
    databaseStreamManager.reconnect()
  }, [enabled])

  return {
    isConnected: state.isConnected,
    isConnecting: state.isConnecting,
    error: state.error,
    cooldownSeconds: state.cooldownSeconds,
    reconnect,
  }
}

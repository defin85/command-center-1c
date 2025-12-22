import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { buildDatabaseStreamUrl, getDatabaseStreamTicket } from '../api/databasesStream'
import { queryKeys } from '../api/queries'

const RECONNECT_INITIAL_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
const INVALIDATION_DEBOUNCE_MS = 1000

interface DatabaseStreamEvent {
  version?: string
  type?: string
  action?: string
  database_id?: string
  cluster_id?: string | null
  timestamp?: string
}

interface UseDatabaseStreamInvalidationOptions {
  clusterId?: string | null
  enabled?: boolean
}

export const useDatabaseStreamInvalidation = ({
  clusterId,
  enabled = true,
}: UseDatabaseStreamInvalidationOptions) => {
  const queryClient = useQueryClient()
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectDelayRef = useRef(RECONNECT_INITIAL_DELAY)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const invalidateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isActiveRef = useRef(false)
  const connectRef = useRef<() => void>(() => {})

  const scheduleInvalidation = useCallback(() => {
    if (invalidateTimeoutRef.current) return
    invalidateTimeoutRef.current = setTimeout(() => {
      invalidateTimeoutRef.current = null
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    }, INVALIDATION_DEBOUNCE_MS)
  }, [queryClient])

  const scheduleReconnect = useCallback(() => {
    if (!isActiveRef.current || reconnectTimeoutRef.current) return

    const delay = reconnectDelayRef.current
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectTimeoutRef.current = null
      reconnectDelayRef.current = Math.min(
        reconnectDelayRef.current * 2,
        RECONNECT_MAX_DELAY
      )
      connectRef.current()
    }, delay)
  }, [])

  const connect = useCallback(async () => {
    if (!enabled || !isActiveRef.current) return

    try {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      const { stream_url } = await getDatabaseStreamTicket(clusterId)
      const url = buildDatabaseStreamUrl(stream_url)
      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setIsConnected(true)
        setError(null)
        reconnectDelayRef.current = RECONNECT_INITIAL_DELAY
        scheduleInvalidation()
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as DatabaseStreamEvent

          if (data.type === 'database_stream_connected') {
            scheduleInvalidation()
            return
          }

          if (data.type === 'database_update') {
            scheduleInvalidation()
          }
        } catch {
          // Ignore malformed events
        }
      }

      eventSource.onerror = () => {
        setIsConnected(false)
        setError('Connection lost. Reconnecting...')
        eventSource.close()
        eventSourceRef.current = null
        scheduleReconnect()
      }
    } catch (err) {
      setIsConnected(false)
      setError('Failed to connect to database stream')
      scheduleReconnect()
    }
  }, [clusterId, enabled, scheduleInvalidation, scheduleReconnect])

  useEffect(() => {
    connectRef.current = () => {
      void connect()
    }
  }, [connect])

  useEffect(() => {
    isActiveRef.current = true
    if (enabled) {
      void connect()
    }

    return () => {
      isActiveRef.current = false
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (invalidateTimeoutRef.current) {
        clearTimeout(invalidateTimeoutRef.current)
        invalidateTimeoutRef.current = null
      }
      setIsConnected(false)
    }
  }, [connect, enabled])

  return {
    isConnected,
    error,
  }
}

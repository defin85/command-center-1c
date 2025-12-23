import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { buildDatabaseStreamUrl, getDatabaseStreamTicket } from '../api/databasesStream'
import { openSseStream } from '../api/sse'
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

  const streamCloseRef = useRef<(() => void) | null>(null)
  const reconnectDelayRef = useRef(RECONNECT_INITIAL_DELAY)
  const lastEventIdRef = useRef<string | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const invalidateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cooldownUntilRef = useRef<number>(0)
  const isActiveRef = useRef(false)
  const isConnectingRef = useRef(false)
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

    const baseDelay = reconnectDelayRef.current
    const jitter = Math.floor(Math.random() * 250)
    const delay = Math.min(baseDelay + jitter, RECONNECT_MAX_DELAY)
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
    if (isConnectingRef.current) return

    const now = Date.now()
    if (now < cooldownUntilRef.current) {
      const remaining = cooldownUntilRef.current - now
      if (!reconnectTimeoutRef.current) {
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null
          connectRef.current()
        }, remaining)
      }
      return
    }

    isConnectingRef.current = true

    try {
      if (streamCloseRef.current) {
        streamCloseRef.current()
        streamCloseRef.current = null
      }

      const token = localStorage.getItem('auth_token')
      if (!token) {
        setIsConnected(false)
        setError('Authentication required')
        scheduleReconnect()
        return
      }

      const { stream_url } = await getDatabaseStreamTicket(clusterId)
      const url = buildDatabaseStreamUrl(stream_url)
      const lastEventId = lastEventIdRef.current
      const closeStream = openSseStream(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
        },
        connectTimeoutMs: 10000,
        onOpen: () => {
          setIsConnected(true)
          setError(null)
          reconnectDelayRef.current = RECONNECT_INITIAL_DELAY
          isConnectingRef.current = false
          scheduleInvalidation()
        },
        onMessage: (message) => {
          try {
            if (message.id) {
              lastEventIdRef.current = message.id
            }
            const data = JSON.parse(message.data) as DatabaseStreamEvent

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
        },
        onError: (err) => {
          const errorStatus = (err as { status?: number } | undefined)?.status
          if (errorStatus === 429) {
            const cooldownMs = 60_000
            cooldownUntilRef.current = Date.now() + cooldownMs
            setError(`Stream busy. Retry in ~${Math.ceil(cooldownMs / 1000)}s`)
            if (streamCloseRef.current) {
              streamCloseRef.current()
              streamCloseRef.current = null
            }
            isConnectingRef.current = false
            scheduleReconnect()
            return
          }
          setIsConnected(false)
          setError('Connection lost. Reconnecting...')
          if (streamCloseRef.current) {
            streamCloseRef.current()
            streamCloseRef.current = null
          }
          isConnectingRef.current = false
          scheduleReconnect()
        },
      })

      streamCloseRef.current = closeStream
    } catch (err) {
      const status = (err as { response?: { status?: number; headers?: Record<string, string> } })?.response?.status
      if (status === 429) {
        const retryAfterHeader = (err as { response?: { headers?: Record<string, string> } })?.response?.headers?.['retry-after']
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : NaN
        const cooldownMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 60_000
        cooldownUntilRef.current = Date.now() + cooldownMs
        setError(`Stream busy. Retry in ~${Math.ceil(cooldownMs / 1000)}s`)
        isConnectingRef.current = false
        scheduleReconnect()
        return
      }
      setIsConnected(false)
      setError('Failed to connect to database stream')
      isConnectingRef.current = false
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
      if (streamCloseRef.current) {
        streamCloseRef.current()
        streamCloseRef.current = null
      }
      lastEventIdRef.current = null
      cooldownUntilRef.current = 0
      isConnectingRef.current = false
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

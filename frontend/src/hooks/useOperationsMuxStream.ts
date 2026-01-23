import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getStreamMuxTicket,
  subscribeOperationStreams,
  unsubscribeOperationStreams,
} from '../api/operations'
import { buildStreamUrl, openSseStream } from '../api/sse'
import type { TimelineStreamEvent } from './useOperationTimelineStream'

const RECONNECT_INITIAL_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000

let globalCooldownUntil = 0

const applyGlobalCooldown = (cooldownMs: number) => {
  if (cooldownMs <= 0) return
  const next = Date.now() + cooldownMs
  if (next > globalCooldownUntil) {
    globalCooldownUntil = next
  }
}

const getGlobalCooldownRemaining = () =>
  Math.max(0, globalCooldownUntil - Date.now())

const getClientId = (): string => {
  const key = 'cc1c_mux_client_id'
  const existing = sessionStorage.getItem(key)
  if (existing) return existing
  const generated =
    (globalThis.crypto && 'randomUUID' in globalThis.crypto)
      ? globalThis.crypto.randomUUID()
      : `client-${Math.random().toString(36).slice(2)}`
  sessionStorage.setItem(key, generated)
  return generated
}

type StreamErrorPayload = {
  error?: string
}

const isTimelineEvent = (data: unknown): data is TimelineStreamEvent => {
  if (typeof data !== 'object' || data === null) return false
  const record = data as Record<string, unknown>
  return (
    typeof record.operation_id === 'string' &&
    typeof record.event === 'string' &&
    typeof record.service === 'string'
  )
}

const getErrorMessage = (data: unknown): string | null => {
  if (typeof data !== 'object' || data === null) return null
  const record = data as StreamErrorPayload
  return typeof record.error === 'string' ? record.error : null
}

export const useOperationsMuxStream = (
  operationIds: string[]
): {
  lastEvent: TimelineStreamEvent | null
  error: string | null
  isConnected: boolean
} => {
  const [lastEvent, setLastEvent] = useState<TimelineStreamEvent | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const streamCloseRef = useRef<(() => void) | null>(null)
  const reconnectDelayRef = useRef(RECONNECT_INITIAL_DELAY)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cooldownUntilRef = useRef<number>(0)
  const isActiveRef = useRef(false)
  const isConnectingRef = useRef(false)
  const connectRef = useRef<() => void>(() => {})
  const currentIdsRef = useRef<Set<string>>(new Set())

  const scheduleReconnect = useCallback(() => {
    if (!isActiveRef.current || reconnectTimeoutRef.current) {
      return
    }
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
    if (!isActiveRef.current || operationIds.length === 0) {
      return
    }
    if (isConnectingRef.current) {
      return
    }
    const now = Date.now()
    const globalRemaining = getGlobalCooldownRemaining()
    if (globalRemaining > 0) {
      cooldownUntilRef.current = Math.max(
        cooldownUntilRef.current,
        now + globalRemaining
      )
    }
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

      const { stream_url } = await getStreamMuxTicket(getClientId())
      const url = buildStreamUrl(stream_url)
      const closeStream = openSseStream(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        connectTimeoutMs: 10000,
        onOpen: async () => {
          setIsConnected(true)
          setError(null)
          reconnectDelayRef.current = RECONNECT_INITIAL_DELAY
          isConnectingRef.current = false
          await subscribeOperationStreams(operationIds)
        },
        onMessage: (message) => {
          try {
            const data: unknown = JSON.parse(message.data)
            const streamError = getErrorMessage(data)
            if (streamError) {
              setError(streamError)
              return
            }
            if (!isTimelineEvent(data)) {
              return
            }
            setLastEvent(data)
            setError(null)
          } catch (err) {
            console.error('Failed to parse SSE event:', err)
            setError('Failed to parse event data')
          }
        },
        onError: (err) => {
          const errorStatus = (err as { status?: number } | undefined)?.status
          if (errorStatus === 429) {
            const cooldownMs = 60_000
            cooldownUntilRef.current = Date.now() + cooldownMs
            applyGlobalCooldown(cooldownMs)
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
          setError('Connection lost. Reconnecting\u2026')
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
      const response = (err as { response?: { status?: number; headers?: Record<string, string> } })?.response
      const status = response?.status
      if (status === 429) {
        const retryAfterHeader = response?.headers?.['retry-after']
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : NaN
        const cooldownMs = Number.isFinite(retryAfterSeconds) ? retryAfterSeconds * 1000 : 60_000
        cooldownUntilRef.current = Date.now() + cooldownMs
        applyGlobalCooldown(cooldownMs)
        setError(`Stream busy. Retry in ~${Math.ceil(cooldownMs / 1000)}s`)
        isConnectingRef.current = false
        scheduleReconnect()
        return
      }
      setIsConnected(false)
      setError('Failed to connect to operation stream')
      isConnectingRef.current = false
      scheduleReconnect()
    }
  }, [operationIds, scheduleReconnect])

  useEffect(() => {
    connectRef.current = () => {
      void connect()
    }
  }, [connect])

  useEffect(() => {
    isActiveRef.current = true
    setLastEvent(null)
    setError(null)
    reconnectDelayRef.current = RECONNECT_INITIAL_DELAY
    cooldownUntilRef.current = 0

    if (operationIds.length === 0) {
      setIsConnected(false)
      return () => {
        isActiveRef.current = false
      }
    }

    void connect()

    return () => {
      isActiveRef.current = false
      if (streamCloseRef.current) {
        streamCloseRef.current()
        streamCloseRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }
  }, [connect, operationIds])

  useEffect(() => {
    const nextSet = new Set(operationIds)
    const prevSet = currentIdsRef.current
    const toSubscribe: string[] = []
    const toUnsubscribe: string[] = []

    nextSet.forEach((id) => {
      if (!prevSet.has(id)) {
        toSubscribe.push(id)
      }
    })
    prevSet.forEach((id) => {
      if (!nextSet.has(id)) {
        toUnsubscribe.push(id)
      }
    })

    currentIdsRef.current = nextSet

    if (toSubscribe.length > 0) {
      void subscribeOperationStreams(toSubscribe)
    }
    if (toUnsubscribe.length > 0) {
      void unsubscribeOperationStreams(toUnsubscribe)
    }
  }, [operationIds])

  useEffect(() => {
    return () => {
      const existing = Array.from(currentIdsRef.current)
      if (existing.length > 0) {
        void unsubscribeOperationStreams(existing)
      }
    }
  }, [])

  return { lastEvent, error, isConnected }
}

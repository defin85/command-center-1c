import { useEffect, useState } from 'react'

export interface WorkflowEvent {
  version: string
  operation_id: string
  timestamp: string
  state: string
  microservice: string
  message: string
  metadata?: Record<string, any>
}

export interface UseOperationStreamResult {
  events: WorkflowEvent[]
  currentState: string
  error: string | null
  isConnected: boolean
}

export const useOperationStream = (
  operationId: string | null
): UseOperationStreamResult => {
  const [events, setEvents] = useState<WorkflowEvent[]>([])
  const [currentState, setCurrentState] = useState<string>('PENDING')
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState<boolean>(false)

  const MAX_EVENTS = 1000

  useEffect(() => {
    // Reset state when operationId changes
    setEvents([])
    setCurrentState('PENDING')
    setError(null)

    if (!operationId) {
      return
    }

    let eventSource: EventSource | null = null

    const connect = () => {
      // Get JWT token from localStorage
      const token = localStorage.getItem('auth_token')
      if (!token) {
        setError('Authentication required')
        return
      }

      // EventSource doesn't support custom headers, so we pass token via query parameter
      // v2 endpoint uses query params for both operation_id and token
      const url = `/api/v2/operations/stream/?operation_id=${operationId}&token=${token}`
      eventSource = new EventSource(url)

      eventSource.onopen = () => {
        setIsConnected(true)
        setError(null)
        console.log('SSE connection established')
      }

      eventSource.onmessage = (event) => {
        try {
          const data: WorkflowEvent = JSON.parse(event.data)

          // Check for error
          if ('error' in data) {
            setError((data as any).error)
            eventSource?.close()
            return
          }

          setEvents((prev) => {
            const updated = [...prev, data]
            return updated.length > MAX_EVENTS
              ? updated.slice(-MAX_EVENTS)
              : updated
          })
          setCurrentState(data.state)
          setError(null)
        } catch (err) {
          console.error('Failed to parse SSE event:', err)
          setError('Failed to parse event data')
        }
      }

      eventSource.onerror = (err) => {
        console.error('SSE connection error:', err)
        setIsConnected(false)
        setError('Connection lost. Reconnecting...')
        // Browser will auto-reconnect
      }
    }

    connect()

    // Cleanup
    return () => {
      if (eventSource) {
        eventSource.close()
        setIsConnected(false)
      }
    }
  }, [operationId])

  return {
    events,
    currentState,
    error,
    isConnected,
  }
}

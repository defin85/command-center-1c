import { getApiBaseUrl } from './baseUrl'

export interface SSEMessage {
  data: string
  event?: string
  id?: string
  retry?: number
}

export interface SSEOptions {
  headers?: Record<string, string>
  onOpen?: (response: Response) => void
  onMessage: (message: SSEMessage) => void
  onError?: (error: unknown) => void
  connectTimeoutMs?: number
}

export const buildStreamUrl = (streamUrl: string): string => {
  if (streamUrl.startsWith('http://') || streamUrl.startsWith('https://')) {
    return streamUrl
  }
  return `${getApiBaseUrl()}${streamUrl}`
}

const parseSseEvent = (rawEvent: string): SSEMessage | null => {
  if (!rawEvent) {
    return null
  }

  const dataLines: string[] = []
  let eventType: string | undefined
  let id: string | undefined
  let retry: number | undefined

  for (const line of rawEvent.split('\n')) {
    if (!line || line.startsWith(':')) {
      continue
    }

    if (line.startsWith('data:')) {
      let value = line.slice(5)
      if (value.startsWith(' ')) {
        value = value.slice(1)
      }
      dataLines.push(value)
      continue
    }

    if (line.startsWith('event:')) {
      let value = line.slice(6)
      if (value.startsWith(' ')) {
        value = value.slice(1)
      }
      eventType = value
      continue
    }

    if (line.startsWith('id:')) {
      let value = line.slice(3)
      if (value.startsWith(' ')) {
        value = value.slice(1)
      }
      id = value
      continue
    }

    if (line.startsWith('retry:')) {
      const value = line.slice(6).trim()
      const parsed = Number.parseInt(value, 10)
      if (!Number.isNaN(parsed)) {
        retry = parsed
      }
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  return {
    data: dataLines.join('\n'),
    event: eventType,
    id,
    retry,
  }
}

export const openSseStream = (url: string, options: SSEOptions): (() => void) => {
  const controller = new AbortController()
  const { onMessage, onOpen, onError, headers } = options
  const connectTimeoutMs = options.connectTimeoutMs ?? 10000
  let closed = false
  let connectTimeout: ReturnType<typeof setTimeout> | null = null

  const close = () => {
    closed = true
    if (connectTimeout) {
      clearTimeout(connectTimeout)
      connectTimeout = null
    }
    controller.abort()
  }

  const reportError = (error: unknown) => {
    if (closed || controller.signal.aborted) {
      return
    }
    if (connectTimeout) {
      clearTimeout(connectTimeout)
      connectTimeout = null
    }
    if (onError) {
      onError(error)
    }
  }

  const start = async () => {
    try {
      if (connectTimeoutMs > 0) {
        connectTimeout = setTimeout(() => {
          reportError(new Error('SSE connection timed out'))
          close()
        }, connectTimeoutMs)
      }

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Accept: 'text/event-stream, application/json',
          ...headers,
        },
        credentials: 'include',
        signal: controller.signal,
      })

      if (!response.ok) {
        if (connectTimeout) {
          clearTimeout(connectTimeout)
          connectTimeout = null
        }
        const error = new Error(`SSE request failed with status ${response.status}`)
        ;(error as { status?: number }).status = response.status
        reportError(error)
        return
      }

      if (onOpen) {
        onOpen(response)
      }
      if (connectTimeout) {
        clearTimeout(connectTimeout)
        connectTimeout = null
      }

      if (!response.body) {
        reportError(new Error('SSE response has no body'))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r/g, '')

        let boundaryIndex = buffer.indexOf('\n\n')
        while (boundaryIndex !== -1) {
          const rawEvent = buffer.slice(0, boundaryIndex)
          buffer = buffer.slice(boundaryIndex + 2)

          const parsed = parseSseEvent(rawEvent)
          if (parsed) {
            onMessage(parsed)
          }

          boundaryIndex = buffer.indexOf('\n\n')
        }
      }

      reportError(new Error('SSE stream closed'))
    } catch (error) {
      reportError(error)
    }
  }

  void start()
  return close
}

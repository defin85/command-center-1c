import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

// API Gateway base URL (without path prefix - generated code includes full paths)
// Port 8180 - outside Windows reserved range (8013-8112)
import { getApiBaseUrl } from './baseUrl'
import {
  createApiErrorDetail,
  resolveApiErrorPolicy,
  shouldDispatchGlobalApiError,
  type ApiErrorDetail,
} from './apiErrorPolicy'
import {
  buildUiProblemCorrelation,
  completeUiHttpRequest,
  startUiHttpRequest,
} from '../observability/uiActionJournal'
import { LOCALE_REQUEST_HEADER } from '../i18n/constants'
import { resolveLocalizedApiErrorMessage } from '../i18n/errorMessages'
import { getCurrentAppLocale } from '../i18n/localeStore'

const API_BASE_URL = getApiBaseUrl()

// Token refresh endpoint (goes through API Gateway to Django)
const TOKEN_REFRESH_URL = `${API_BASE_URL}/api/token/refresh/`
const REQUEST_ID_HEADER = 'X-Request-ID'
const UI_ACTION_ID_HEADER = 'X-UI-Action-ID'

// Custom event for API errors (used by global error handler in App.tsx)
export const API_ERROR_EVENT = 'api:error'

// Dispatch API error event for global handling
export function dispatchApiError(error: ApiErrorDetail) {
  window.dispatchEvent(new CustomEvent(API_ERROR_EVENT, { detail: error }))
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  // Important for CORS with credentials
  withCredentials: true,
})

export const setAuthToken = (token?: string | null) => {
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    delete apiClient.defaults.headers.common.Authorization
  }
}

setAuthToken(localStorage.getItem('auth_token'))

// Token refresh state management
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string | null) => void
  reject: (error: Error) => void
}> = []

// Process queued requests after token refresh
const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

const setHeader = (headers: InternalAxiosRequestConfig['headers'], name: string, value: string) => {
  if (!headers) {
    return
  }
  if (typeof (headers as { set?: (header: string, nextValue: string) => void }).set === 'function') {
    ;(headers as { set: (header: string, nextValue: string) => void }).set(name, value)
    return
  }
  ;(headers as Record<string, string>)[name] = value
}

const deleteHeader = (headers: InternalAxiosRequestConfig['headers'], name: string) => {
  if (!headers) {
    return
  }
  if (typeof (headers as { delete?: (header: string) => void }).delete === 'function') {
    ;(headers as { delete: (header: string) => void }).delete(name)
    return
  }
  delete (headers as Record<string, string>)[name]
}

const getHeaderValue = (headers: unknown, name: string): string | undefined => {
  if (!headers || typeof headers !== 'object') {
    return undefined
  }

  const normalizedName = name.toLowerCase()
  for (const [headerName, headerValue] of Object.entries(headers as Record<string, unknown>)) {
    if (headerName.toLowerCase() !== normalizedName) {
      continue
    }
    if (typeof headerValue === 'string') {
      return headerValue
    }
    if (Array.isArray(headerValue)) {
      return headerValue.find((value) => typeof value === 'string')
    }
  }
  return undefined
}

const finalizeObservedRequest = ({
  config,
  status,
  data,
  headers,
  failed,
}: {
  config?: InternalAxiosRequestConfig
  status?: number
  data?: unknown
  headers?: unknown
  failed?: boolean
}) => {
  const observedRequest = config?.cc1cObservedRequest
  if (!observedRequest || !config) {
    return
  }

  const problem = buildUiProblemCorrelation({
    ...(data && typeof data === 'object' ? data as Record<string, unknown> : {}),
    request_id: getHeaderValue(headers, REQUEST_ID_HEADER) ?? (data as { request_id?: unknown } | undefined)?.request_id,
    ui_action_id: getHeaderValue(headers, UI_ACTION_ID_HEADER) ?? (data as { ui_action_id?: unknown } | undefined)?.ui_action_id,
  })

  completeUiHttpRequest({
    requestId: observedRequest.requestId,
    uiActionId: observedRequest.uiActionId,
    method: observedRequest.method,
    path: observedRequest.path,
    status,
    failed,
    problem,
  })
  delete config.cc1cObservedRequest
}

// Attempt to refresh the access token
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    return null
  }

  try {
    const response = await axios.post(TOKEN_REFRESH_URL, {
      refresh: refreshToken,
    })

    const { access, refresh } = response.data
    localStorage.setItem('auth_token', access)
    setAuthToken(access)
    if (refresh) {
      // Django SimpleJWT rotates refresh tokens
      localStorage.setItem('refresh_token', refresh)
    }
    return access
  } catch (_error) {
    // Refresh failed - clear tokens and redirect to login
    localStorage.removeItem('auth_token')
    localStorage.removeItem('refresh_token')
    setAuthToken(null)
    return null
  }
}

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Ensure trailing slash (Django convention)
    // This normalizes all requests to match Django URL patterns
    if (config.url && !config.url.endsWith('/') && !config.url.includes('?')) {
      config.url += '/'
    }

    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    if (token) {
      setHeader(config.headers, 'Authorization', `Bearer ${token}`)
    }

    // Tenant context (optional)
    const tenantId = localStorage.getItem('active_tenant_id')
    if (tenantId) {
      setHeader(config.headers, 'X-CC1C-Tenant-ID', tenantId)
    }

    const locale = getCurrentAppLocale()
    if (locale) {
      setHeader(config.headers, LOCALE_REQUEST_HEADER, locale)
    }

    // Remove Content-Type for FormData (axios will set it with boundary)
    if (config.data instanceof FormData) {
      deleteHeader(config.headers, 'Content-Type')
    }

    if (!config.cc1cObservedRequest) {
      const observedRequest = startUiHttpRequest({
        method: config.method,
        path: config.url,
      })
      config.cc1cObservedRequest = {
        requestId: observedRequest.requestId,
        uiActionId: observedRequest.uiActionId,
        method: config.method?.toUpperCase(),
        path: config.url,
      }
    }

    setHeader(config.headers, REQUEST_ID_HEADER, config.cc1cObservedRequest.requestId)
    setHeader(config.headers, UI_ACTION_ID_HEADER, config.cc1cObservedRequest.uiActionId)

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor with token refresh and error handling
apiClient.interceptors.response.use(
  (response) => {
    finalizeObservedRequest({
      config: response.config,
      status: response.status,
      data: response.data,
      headers: response.headers,
    })
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const skipGlobalError = Boolean((originalRequest as { skipGlobalError?: boolean } | undefined)?.skipGlobalError)
    const errorPolicy = resolveApiErrorPolicy({
      errorPolicy: originalRequest?.errorPolicy,
      skipGlobalError,
    })

    // Handle 401 Unauthorized with token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Check if this is a token-related error (not just missing auth)
      const errorData = error.response.data as { error?: string; code?: string } | undefined
      const isTokenExpired = errorData?.code === 'token_not_valid' ||
                             errorData?.error?.includes('expired') ||
                             errorData?.error?.includes('invalid')

      // If no refresh token or not a token error, redirect to login
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken || !isTokenExpired) {
        finalizeObservedRequest({
          config: originalRequest,
          status: error.response?.status,
          data: error.response?.data,
          headers: error.response?.headers,
          failed: true,
        })
        localStorage.removeItem('auth_token')
        localStorage.removeItem('refresh_token')
        setAuthToken(null)

        // Dispatch error event before redirect
        dispatchApiError(createApiErrorDetail({
          message: resolveLocalizedApiErrorMessage({
            code: 'SESSION_EXPIRED',
            status: 401,
          }),
          status: 401,
          code: 'SESSION_EXPIRED',
          method: originalRequest?.method,
          path: originalRequest?.url,
          errorPolicy,
        }))

        window.location.href = '/login'
        return Promise.reject(error)
      }

      // If already refreshing, queue this request
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            if (token) {
              setHeader(originalRequest.headers, 'Authorization', `Bearer ${token}`)
              return apiClient(originalRequest)
            }
            return Promise.reject(error)
          })
          .catch((err) => {
            finalizeObservedRequest({
              config: originalRequest,
              status: error.response?.status,
              data: error.response?.data,
              headers: error.response?.headers,
              failed: true,
            })
            return Promise.reject(err)
          })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const newToken = await refreshAccessToken()

        if (newToken) {
          // Success - process queued requests and retry original
          processQueue(null, newToken)
          setHeader(originalRequest.headers, 'Authorization', `Bearer ${newToken}`)
          setAuthToken(newToken)
          return apiClient(originalRequest)
        } else {
          // Refresh failed
          processQueue(new Error('Token refresh failed'), null)
          finalizeObservedRequest({
            config: originalRequest,
            status: error.response?.status,
            data: error.response?.data,
            headers: error.response?.headers,
            failed: true,
          })
          window.location.href = '/login'
          return Promise.reject(error)
        }
      } catch (refreshError) {
        processQueue(refreshError as Error, null)
        finalizeObservedRequest({
          config: originalRequest,
          status: error.response?.status,
          data: error.response?.data,
          headers: error.response?.headers,
          failed: true,
        })
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Handle other errors - dispatch to global error handler

    // Skip canceled/aborted requests (component unmount, navigation, etc.)
    if (error.name === 'CanceledError' || error.name === 'AbortError') {
      finalizeObservedRequest({
        config: originalRequest,
        status: error.response?.status,
        data: error.response?.data,
        headers: error.response?.headers,
      })
      return Promise.reject(error)
    }

    const status = error.response?.status
    const errorData = error.response?.data as {
      error?: string | { message?: string }
      message?: string
      detail?: string
      code?: string
    } | undefined

    // Build user-friendly error message
    let message = 'Unexpected error.'
    if (errorData?.error) {
      if (typeof errorData.error === 'string') {
        message = errorData.error
      } else if (typeof errorData.error === 'object' && errorData.error.message) {
        message = errorData.error.message
      }
    } else if (errorData?.message) {
      message = errorData.message
    } else if (errorData?.detail) {
      message = errorData.detail
    } else if (error.message) {
      message = error.message
    }

    // Map status codes to user-friendly messages
    if (status === 403) {
      message = resolveLocalizedApiErrorMessage({
        status,
        code: errorData?.code,
        detail: errorData?.detail,
        fallbackMessage: message,
      })
    } else if (status === 404) {
      message = resolveLocalizedApiErrorMessage({
        status,
        code: errorData?.code,
        detail: errorData?.detail,
        fallbackMessage: message,
      })
    } else if (status === 500) {
      message = resolveLocalizedApiErrorMessage({
        status,
        code: errorData?.code,
        detail: errorData?.detail,
        fallbackMessage: message,
      })
    } else if (status === 502 || status === 503 || status === 504) {
      message = resolveLocalizedApiErrorMessage({
        status,
        code: errorData?.code,
        detail: errorData?.detail,
        fallbackMessage: message,
      })
    } else if (!error.response) {
      message = resolveLocalizedApiErrorMessage({
        detail: error.message,
        fallbackMessage: message,
      })
    } else {
      message = resolveLocalizedApiErrorMessage({
        status,
        code: errorData?.code,
        detail: errorData?.detail,
        fallbackMessage: message,
      })
    }

    finalizeObservedRequest({
      config: originalRequest,
      status,
      data: error.response?.data,
      headers: error.response?.headers,
      failed: !error.response,
    })

    if (!skipGlobalError) {
      if (shouldDispatchGlobalApiError({ errorPolicy, skipGlobalError })) {
        dispatchApiError(createApiErrorDetail({
          message,
          status,
          code: errorData?.code,
          details: errorData,
          method: originalRequest?.method,
          path: originalRequest?.url,
          errorPolicy,
        }))
      }
    }

    return Promise.reject(error)
  }
)

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

// v2 migration: update default API URL to v2
// Port 8180 - outside Windows reserved range (8013-8112)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8180/api/v2'

// Token refresh endpoint (goes through API Gateway to Django)
const TOKEN_REFRESH_URL = 'http://localhost:8180/api/token/refresh/'

// Custom event for API errors (used by global error handler in App.tsx)
export const API_ERROR_EVENT = 'api:error'

// Dispatch API error event for global handling
export function dispatchApiError(error: {
  message: string
  status?: number
  code?: string
  details?: unknown
}) {
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
    if (refresh) {
      // Django SimpleJWT rotates refresh tokens
      localStorage.setItem('refresh_token', refresh)
    }
    return access
  } catch (error) {
    // Refresh failed - clear tokens and redirect to login
    localStorage.removeItem('auth_token')
    localStorage.removeItem('refresh_token')
    return null
  }
}

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Remove Content-Type for FormData (axios will set it with boundary)
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor with token refresh and error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

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
        localStorage.removeItem('auth_token')
        localStorage.removeItem('refresh_token')

        // Dispatch error event before redirect
        dispatchApiError({
          message: 'Session expired. Please log in again.',
          status: 401,
          code: 'SESSION_EXPIRED',
        })

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
              originalRequest.headers.Authorization = `Bearer ${token}`
              return apiClient(originalRequest)
            }
            return Promise.reject(error)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const newToken = await refreshAccessToken()

        if (newToken) {
          // Success - process queued requests and retry original
          processQueue(null, newToken)
          originalRequest.headers.Authorization = `Bearer ${newToken}`
          return apiClient(originalRequest)
        } else {
          // Refresh failed
          processQueue(new Error('Token refresh failed'), null)
          window.location.href = '/login'
          return Promise.reject(error)
        }
      } catch (refreshError) {
        processQueue(refreshError as Error, null)
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Handle other errors - dispatch to global error handler
    const status = error.response?.status
    const errorData = error.response?.data as { error?: string; message?: string; detail?: string } | undefined

    // Build user-friendly error message
    let message = 'An error occurred'
    if (errorData?.error) {
      message = errorData.error
    } else if (errorData?.message) {
      message = errorData.message
    } else if (errorData?.detail) {
      message = errorData.detail
    } else if (error.message) {
      message = error.message
    }

    // Map status codes to user-friendly messages
    if (status === 403) {
      message = 'Access denied. You do not have permission for this action.'
    } else if (status === 404) {
      message = 'Resource not found.'
    } else if (status === 500) {
      message = 'Server error. Please try again later.'
    } else if (status === 502 || status === 503 || status === 504) {
      message = 'Service temporarily unavailable. Please try again.'
    } else if (!error.response) {
      message = 'Network error. Please check your connection.'
    }

    // Dispatch error event for global handling
    dispatchApiError({
      message,
      status,
      code: (errorData as { code?: string })?.code,
      details: errorData,
    })

    return Promise.reject(error)
  }
)

import 'axios'

import type { ApiErrorPolicy } from './apiErrorPolicy'

declare module 'axios' {
  interface AxiosRequestConfig<_D = unknown> {
    errorPolicy?: ApiErrorPolicy
    skipGlobalError?: boolean
  }

  interface InternalAxiosRequestConfig<_D = unknown> {
    errorPolicy?: ApiErrorPolicy
    skipGlobalError?: boolean
  }
}

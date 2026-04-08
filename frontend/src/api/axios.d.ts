import 'axios'

import type { ApiErrorPolicy } from './apiErrorPolicy'

type Cc1cObservedRequest = {
  requestId: string
  uiActionId: string
  method?: string
  path?: string
}

declare module 'axios' {
  interface AxiosRequestConfig<_D = unknown> {
    errorPolicy?: ApiErrorPolicy
    skipGlobalError?: boolean
    cc1cObservedRequest?: Cc1cObservedRequest
  }

  interface InternalAxiosRequestConfig<_D = unknown> {
    errorPolicy?: ApiErrorPolicy
    skipGlobalError?: boolean
    cc1cObservedRequest?: Cc1cObservedRequest
  }
}

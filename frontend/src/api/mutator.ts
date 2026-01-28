/**
 * Custom Axios instance mutator for Orval.
 */
import { AxiosError, AxiosRequestConfig } from 'axios'
import { apiClient } from './client'

export type CancellablePromise<T> = Promise<T> & {
  cancel: () => void
}

export const customInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): CancellablePromise<T> => {
  const externalSignal = options?.signal
  const controller = externalSignal ? undefined : new AbortController()
  const signal = externalSignal ?? controller?.signal

  const promise = apiClient
    .request<T>({
      ...config,
      ...options,
      signal,
    })
    .then(({ data }) => data) as CancellablePromise<T>

  promise.cancel = () => {
    controller?.abort()
  }

  return promise
}

// Types for Orval integration
export type ErrorType<Error> = AxiosError<Error>
export type BodyType<BodyData> = BodyData

export default customInstance

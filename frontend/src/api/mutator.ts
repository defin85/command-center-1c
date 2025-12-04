/**
 * Custom Axios instance mutator for Orval.
 */
import { AxiosError, AxiosRequestConfig } from 'axios'
import { apiClient } from './client'

export const customInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> => {
  const controller = new AbortController()

  const promise = apiClient({
    ...config,
    ...options,
    signal: controller.signal,
  }).then(({ data }) => data as T)

  // @ts-expect-error - adding cancel property for React Query
  promise.cancel = () => {
    controller.abort()
  }

  return promise
}

// Types for Orval integration
export type ErrorType<Error> = AxiosError<Error>
export type BodyType<BodyData> = BodyData

export default customInstance

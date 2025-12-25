import 'axios'

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipGlobalError?: boolean
  }
}

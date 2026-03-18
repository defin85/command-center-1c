import { QueryClient } from '@tanstack/react-query'
import { getQueryPolicy } from './queryRuntime'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: getQueryPolicy('background'),
  },
})

export const resetQueryClient = () => {
  queryClient.cancelQueries()
  queryClient.clear()
}

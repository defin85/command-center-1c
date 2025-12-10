import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,        // 30 сек - данные свежие
      gcTime: 5 * 60 * 1000,       // 5 мин - держать в кэше
      retry: 2,                     // 2 retry
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  },
})

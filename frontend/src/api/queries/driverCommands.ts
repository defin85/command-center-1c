import { useQuery } from '@tanstack/react-query'

import { fetchDriverCommands, type DriverCommandsResponseV2, type DriverName } from '../driverCommands'
import { queryKeys } from './index'

export function useDriverCommands(driver: DriverName, enabled = true) {
  return useQuery<DriverCommandsResponseV2, Error>({
    queryKey: queryKeys.driverCommands.byDriver(driver),
    queryFn: ({ signal }) => fetchDriverCommands(driver, signal),
    enabled,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  })
}

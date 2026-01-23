import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { CreateDriverCommandShortcutRequest, DriverCommandShortcutDriver } from '../commandShortcuts'
import {
  createDriverCommandShortcut,
  deleteDriverCommandShortcut,
  listDriverCommandShortcuts,
} from '../commandShortcuts'
import { queryKeys } from './queryKeys'

export function useDriverCommandShortcuts(driver: DriverCommandShortcutDriver, enabled = true) {
  return useQuery({
    queryKey: queryKeys.commandShortcuts.byDriver(driver),
    queryFn: () => listDriverCommandShortcuts(driver),
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useCreateDriverCommandShortcut(driver: DriverCommandShortcutDriver) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateDriverCommandShortcutRequest) => createDriverCommandShortcut(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commandShortcuts.byDriver(driver) })
    },
  })
}

export function useDeleteDriverCommandShortcut(driver: DriverCommandShortcutDriver) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (shortcutId: string) => deleteDriverCommandShortcut(shortcutId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.commandShortcuts.byDriver(driver) })
    },
  })
}

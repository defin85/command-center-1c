import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { useShellBootstrap } from '../api/queries/shellBootstrap'
import { getAuthToken, subscribeAuthChange } from '../lib/authState'

type ShellBootstrapQuery = ReturnType<typeof useShellBootstrap>

type ShellRuntimeContextValue = {
  authToken: string | null
  hasAuthToken: boolean
  shellBootstrapQuery: ShellBootstrapQuery
}

const ShellRuntimeContext = createContext<ShellRuntimeContextValue | null>(null)

export function ShellRuntimeProvider({ children }: { children: ReactNode }) {
  const [authToken, setAuthToken] = useState(() => getAuthToken())
  const hasAuthToken = Boolean(authToken)
  const shellBootstrapQuery = useShellBootstrap({ enabled: hasAuthToken })

  useEffect(() => {
    return subscribeAuthChange(() => {
      setAuthToken(getAuthToken())
    })
  }, [])

  const value = useMemo<ShellRuntimeContextValue>(() => ({
    authToken,
    hasAuthToken,
    shellBootstrapQuery,
  }), [authToken, hasAuthToken, shellBootstrapQuery])

  return (
    <ShellRuntimeContext.Provider value={value}>
      {children}
    </ShellRuntimeContext.Provider>
  )
}

export function useShellRuntime(): ShellRuntimeContextValue {
  const value = useContext(ShellRuntimeContext)
  if (!value) {
    throw new Error('useShellRuntime must be used within ShellRuntimeProvider')
  }
  return value
}

export function useOptionalShellRuntime(): ShellRuntimeContextValue | null {
  return useContext(ShellRuntimeContext)
}

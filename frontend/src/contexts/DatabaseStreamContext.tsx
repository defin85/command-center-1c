/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext } from 'react'
import { useDatabaseStreamInvalidation } from '../hooks/useDatabaseStreamInvalidation'
import { useAuthz } from '../authz'

type DatabaseStreamStatus = {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  cooldownSeconds: number
  reconnect: () => void
}

const DatabaseStreamContext = createContext<DatabaseStreamStatus | null>(null)

export const DatabaseStreamProvider = ({ children }: { children: React.ReactNode }) => {
  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const authz = useAuthz()
  const isStaff = authz.isStaff
  const isAuthzReady = !authz.isLoading
  const streamStatus = useDatabaseStreamInvalidation({
    clusterId: null,
    enabled: hasToken && isAuthzReady && isStaff,
  })

  return (
    <DatabaseStreamContext.Provider value={streamStatus}>
      {children}
    </DatabaseStreamContext.Provider>
  )
}

export const useDatabaseStreamStatus = (): DatabaseStreamStatus => {
  const context = useContext(DatabaseStreamContext)
  if (!context) {
    return {
      isConnected: false,
      isConnecting: false,
      error: null,
      cooldownSeconds: 0,
      reconnect: () => {},
    }
  }
  return context
}

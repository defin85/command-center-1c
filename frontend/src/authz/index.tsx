import { createContext, useContext, useMemo } from 'react'

import { useMe } from '../api/queries/me'
import { useEffectiveAccess } from '../api/queries/rbac'

export type AccessLevel = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'

const ACCESS_RANK: Record<AccessLevel, number> = {
  VIEW: 1,
  OPERATE: 2,
  MANAGE: 3,
  ADMIN: 4,
}

const normalizeLevel = (value?: string | null): AccessLevel | null => {
  if (!value) return null
  if (value === 'VIEW' || value === 'OPERATE' || value === 'MANAGE' || value === 'ADMIN') {
    return value
  }
  return null
}

const hasLevel = (current: AccessLevel | null | undefined, required: AccessLevel): boolean => {
  if (!current) return false
  return ACCESS_RANK[current] >= ACCESS_RANK[required]
}

type AuthzContextValue = {
  isStaff: boolean
  isLoading: boolean
  canDatabase: (databaseId: string | null | undefined, required: AccessLevel) => boolean
  canCluster: (clusterId: string | null | undefined, required: AccessLevel) => boolean
  canAnyDatabase: (required: AccessLevel) => boolean
  canAnyCluster: (required: AccessLevel) => boolean
  getDatabaseLevel: (databaseId: string | null | undefined) => AccessLevel | null
  getClusterLevel: (clusterId: string | null | undefined) => AccessLevel | null
}

const AuthzContext = createContext<AuthzContextValue | null>(null)

export const AuthzProvider = ({ children }: { children: React.ReactNode }) => {
  const hasToken = Boolean(localStorage.getItem('auth_token'))
  const meQuery = useMe({ enabled: hasToken })
  const accessQuery = useEffectiveAccess(undefined, {
    includeDatabases: true,
    includeClusters: true,
    enabled: hasToken,
  })

  const isStaff = Boolean(meQuery.data?.is_staff)
  const isLoading = Boolean(hasToken && (meQuery.isLoading || accessQuery.isLoading))

  const { databaseLevels, clusterLevels } = useMemo(() => {
    const dbLevels = new Map<string, AccessLevel>()
    const clLevels = new Map<string, AccessLevel>()
    const data = accessQuery.data
    if (!data) {
      return { databaseLevels: dbLevels, clusterLevels: clLevels }
    }

    data.databases?.forEach((item) => {
      const level = normalizeLevel(item.level)
      if (level) {
        dbLevels.set(item.database.id, level)
      }
    })

    data.clusters?.forEach((item) => {
      const level = normalizeLevel(item.level)
      if (level) {
        clLevels.set(item.cluster.id, level)
      }
    })

    return { databaseLevels: dbLevels, clusterLevels: clLevels }
  }, [accessQuery.data])

  const getDatabaseLevel = (databaseId: string | null | undefined): AccessLevel | null => {
    if (!databaseId) return null
    return databaseLevels.get(databaseId) ?? null
  }

  const getClusterLevel = (clusterId: string | null | undefined): AccessLevel | null => {
    if (!clusterId) return null
    return clusterLevels.get(clusterId) ?? null
  }

  const canDatabase = (databaseId: string | null | undefined, required: AccessLevel): boolean => {
    if (isStaff) return true
    const level = getDatabaseLevel(databaseId)
    return hasLevel(level, required)
  }

  const canCluster = (clusterId: string | null | undefined, required: AccessLevel): boolean => {
    if (isStaff) return true
    const level = getClusterLevel(clusterId)
    return hasLevel(level, required)
  }

  const canAnyDatabase = (required: AccessLevel): boolean => {
    if (isStaff) return true
    for (const level of databaseLevels.values()) {
      if (hasLevel(level, required)) return true
    }
    return false
  }

  const canAnyCluster = (required: AccessLevel): boolean => {
    if (isStaff) return true
    for (const level of clusterLevels.values()) {
      if (hasLevel(level, required)) return true
    }
    return false
  }

  const value: AuthzContextValue = {
    isStaff,
    isLoading,
    canDatabase,
    canCluster,
    canAnyDatabase,
    canAnyCluster,
    getDatabaseLevel,
    getClusterLevel,
  }

  return <AuthzContext.Provider value={value}>{children}</AuthzContext.Provider>
}

export const useAuthz = () => {
  const context = useContext(AuthzContext)
  if (!context) {
    throw new Error('useAuthz must be used within AuthzProvider')
  }
  return context
}

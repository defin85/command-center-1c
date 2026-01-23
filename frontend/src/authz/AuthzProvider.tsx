import type { ReactNode } from 'react'
import { useMemo } from 'react'

import { useMe } from '../api/queries/me'
import { useEffectiveAccess } from '../api/queries/rbac'
import { AuthzContext, hasLevel, normalizeLevel, type AccessLevel, type AuthzContextValue } from './context'

export const AuthzProvider = ({ children }: { children: ReactNode }) => {
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


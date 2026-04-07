export type ClusterWorkspaceContext = 'inspect' | 'create' | 'edit' | 'credentials' | 'discover'

const DEFAULT_CLUSTER_CONTEXT: ClusterWorkspaceContext = 'inspect'

export const parseClusterContext = (value: string | null): ClusterWorkspaceContext => (
  value === 'create'
  || value === 'edit'
  || value === 'credentials'
  || value === 'discover'
    ? value
    : DEFAULT_CLUSTER_CONTEXT
)

type ResolveClusterWorkspaceContextOptions = {
  requestedContextParam: string | null
  hasSelectedCluster: boolean
  authzResolved: boolean
  canCreateCluster: boolean
  canDiscover: boolean
  canManageSelectedCluster: boolean
}

type ResolvedClusterWorkspaceContext = {
  activeContext: ClusterWorkspaceContext
  canonicalContextParam: string | null
}

const buildInspectFallback = (hasSelectedCluster: boolean): ResolvedClusterWorkspaceContext => ({
  activeContext: DEFAULT_CLUSTER_CONTEXT,
  canonicalContextParam: hasSelectedCluster ? DEFAULT_CLUSTER_CONTEXT : null,
})

export const resolveClusterWorkspaceContext = ({
  requestedContextParam,
  hasSelectedCluster,
  authzResolved,
  canCreateCluster,
  canDiscover,
  canManageSelectedCluster,
}: ResolveClusterWorkspaceContextOptions): ResolvedClusterWorkspaceContext => {
  if (requestedContextParam === null) {
    return {
      activeContext: DEFAULT_CLUSTER_CONTEXT,
      canonicalContextParam: null,
    }
  }

  const requestedContext = parseClusterContext(requestedContextParam)

  if (requestedContext === 'create') {
    if (!authzResolved) {
      return { activeContext: DEFAULT_CLUSTER_CONTEXT, canonicalContextParam: requestedContext }
    }
    return canCreateCluster
      ? { activeContext: requestedContext, canonicalContextParam: requestedContext }
      : buildInspectFallback(hasSelectedCluster)
  }

  if (requestedContext === 'discover') {
    if (!authzResolved) {
      return { activeContext: DEFAULT_CLUSTER_CONTEXT, canonicalContextParam: requestedContext }
    }
    return canDiscover
      ? { activeContext: requestedContext, canonicalContextParam: requestedContext }
      : buildInspectFallback(hasSelectedCluster)
  }

  if (requestedContext === 'edit' || requestedContext === 'credentials') {
    if (!hasSelectedCluster) {
      return buildInspectFallback(false)
    }
    if (!authzResolved) {
      return { activeContext: DEFAULT_CLUSTER_CONTEXT, canonicalContextParam: requestedContext }
    }
    return hasSelectedCluster && canManageSelectedCluster
      ? { activeContext: requestedContext, canonicalContextParam: requestedContext }
      : buildInspectFallback(hasSelectedCluster)
  }

  return {
    activeContext: DEFAULT_CLUSTER_CONTEXT,
    canonicalContextParam: hasSelectedCluster ? DEFAULT_CLUSTER_CONTEXT : null,
  }
}

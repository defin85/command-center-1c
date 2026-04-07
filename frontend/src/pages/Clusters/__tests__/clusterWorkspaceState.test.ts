import { describe, expect, it } from 'vitest'

import { resolveClusterWorkspaceContext } from '../clusterWorkspaceState'

describe('resolveClusterWorkspaceContext', () => {
  it('keeps create and discover contexts only for staff-backed routes', () => {
    expect(resolveClusterWorkspaceContext({
      requestedContextParam: 'create',
      hasSelectedCluster: false,
      authzResolved: true,
      canCreateCluster: true,
      canDiscover: false,
      canManageSelectedCluster: false,
    })).toEqual({
      activeContext: 'create',
      canonicalContextParam: 'create',
    })

    expect(resolveClusterWorkspaceContext({
      requestedContextParam: 'discover',
      hasSelectedCluster: false,
      authzResolved: true,
      canCreateCluster: false,
      canDiscover: false,
      canManageSelectedCluster: false,
    })).toEqual({
      activeContext: 'inspect',
      canonicalContextParam: null,
    })
  })

  it('falls back to inspect when edit or credentials contexts lack manage access', () => {
    expect(resolveClusterWorkspaceContext({
      requestedContextParam: 'edit',
      hasSelectedCluster: true,
      authzResolved: true,
      canCreateCluster: false,
      canDiscover: false,
      canManageSelectedCluster: false,
    })).toEqual({
      activeContext: 'inspect',
      canonicalContextParam: 'inspect',
    })

    expect(resolveClusterWorkspaceContext({
      requestedContextParam: 'credentials',
      hasSelectedCluster: false,
      authzResolved: true,
      canCreateCluster: false,
      canDiscover: false,
      canManageSelectedCluster: true,
    })).toEqual({
      activeContext: 'inspect',
      canonicalContextParam: null,
    })
  })

  it('keeps inspect as the default active context without mutating URLs that omit context', () => {
    expect(resolveClusterWorkspaceContext({
      requestedContextParam: null,
      hasSelectedCluster: true,
      authzResolved: true,
      canCreateCluster: false,
      canDiscover: false,
      canManageSelectedCluster: false,
    })).toEqual({
      activeContext: 'inspect',
      canonicalContextParam: null,
    })
  })

  it('keeps mutating context params stable while authz bootstrap is still loading', () => {
    expect(resolveClusterWorkspaceContext({
      requestedContextParam: 'edit',
      hasSelectedCluster: true,
      authzResolved: false,
      canCreateCluster: false,
      canDiscover: false,
      canManageSelectedCluster: false,
    })).toEqual({
      activeContext: 'inspect',
      canonicalContextParam: 'edit',
    })

    expect(resolveClusterWorkspaceContext({
      requestedContextParam: 'create',
      hasSelectedCluster: false,
      authzResolved: false,
      canCreateCluster: false,
      canDiscover: false,
      canManageSelectedCluster: false,
    })).toEqual({
      activeContext: 'inspect',
      canonicalContextParam: 'create',
    })
  })
})

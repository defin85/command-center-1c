import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import {
  getCompactMasterPaneGovernance,
  getRouteModulesByLintProfile,
  routeGovernancePathSet,
  shellSurfaceFilePathSet,
} from './src/uiGovernanceInventory.js'

const contextAwareAntdImports = [
  {
    name: 'antd',
    importNames: ['message', 'notification'],
    message: 'Use `const { message, notification } = App.useApp()` from `antd` instead of static imports.',
  },
]

const competingFoundationImportPatterns = [
  {
    group: ['@mui/*', '@radix-ui/*', '@headlessui/react'],
    message: 'Ant-based UI platform is the only approved primary foundation for platform migrations in this repository.',
  },
]

const canonicalPageContainerImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Row', 'Col', 'Spin', 'Table', 'Tag'],
    message: 'Canonical pilot pages must compose through `src/components/platform` primitives instead of raw Ant layout/data containers.',
  },
]

const canonicalPilotModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Row', 'Col', 'Table', 'Tag'],
    message: 'Migrated Decisions and Binding Profile modules must compose through `src/components/platform` primitives instead of raw Ant layout/data containers.',
  },
]

const operationalWorkspaceModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Row', 'Col', 'Spin', 'Table', 'Tag'],
    message: 'Operational workspace modules must compose through `src/components/platform` primitives instead of raw Ant layout/data containers.',
  },
]

const privilegedWorkspaceRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs'],
    message: 'Privileged admin/support and settings routes must compose through `WorkspacePage`, `PageHeader`, platform-owned catalog/detail primitives, and platform secondary shells instead of raw Ant route containers.',
  },
]

const dashboardRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Row', 'Col', 'Spin', 'Table', 'Tag', 'Divider'],
    message: 'Dashboard route must compose through `DashboardPage` and platform-owned sections instead of raw Ant layout/data containers.',
  },
]

const operationsRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Row', 'Col', 'Spin', 'Table'],
    message: 'Operations route must compose through `WorkspacePage`, `MasterDetailShell`, and platform-owned secondary surfaces instead of raw Ant layout/data containers.',
  },
]

const databasesRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Row', 'Col', 'Spin', 'Table', 'Breadcrumb'],
    message: 'Databases route must compose through `WorkspacePage`, `MasterDetailShell`, and platform-owned management surfaces instead of raw Ant layout/data containers.',
  },
]

const clustersRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Modal', 'Row', 'Col', 'Spin', 'Table', 'Tabs'],
    message: 'Clusters route must compose through `WorkspacePage`, `PageHeader`, `MasterDetailShell`, and canonical secondary shells instead of raw Ant route containers.',
  },
]

const observabilityRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Empty', 'Layout', 'Modal', 'Row', 'Col', 'Spin', 'Table', 'Tabs'],
    message: 'Infra observability routes must compose through `WorkspacePage`, `PageHeader`, and platform-owned diagnostics surfaces instead of raw Ant route containers.',
  },
]

const poolCatalogRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs', 'Tag'],
    message: 'Pool catalog route must compose through `WorkspacePage`, platform-owned task surfaces, and canonical secondary shells instead of raw Ant route containers.',
  },
]

const poolRunsRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Collapse', 'Descriptions', 'Row', 'Col', 'Table', 'Tabs', 'Tag'],
    message: 'Pool runs route must compose through `WorkspacePage`, stage-aware platform surfaces, and mobile-safe inspect flows instead of raw Ant route containers.',
  },
]

const poolSchemaTemplatesRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs', 'Tag'],
    message: 'Pool schema templates route must compose through `WorkspacePage`, `MasterDetailShell`, and `ModalFormShell` instead of raw Ant route containers.',
  },
]

const poolMasterDataRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs', 'Tag'],
    message: 'Pool master-data route must compose through `WorkspacePage`, `MasterDetailShell`, and platform-owned multi-zone surfaces instead of raw Ant route containers.',
  },
]

const templatesRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs'],
    message: 'Templates route must compose through `WorkspacePage`, `MasterDetailShell`, and canonical authoring surfaces instead of raw Ant route containers.',
  },
]

const workflowListRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs'],
    message: 'Workflow library route must compose through `WorkspacePage`, `MasterDetailShell`, and canonical catalog/detail shells instead of raw Ant route containers.',
  },
]

const workflowExecutionsRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Table', 'Tabs'],
    message: 'Workflow executions route must compose through `WorkspacePage`, `MasterDetailShell`, and canonical diagnostics shells instead of raw Ant route containers.',
  },
]

const workflowDesignerRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Layout', 'Modal', 'Row', 'Col', 'Table', 'Tabs'],
    message: 'Workflow designer route must compose through `WorkspacePage`, `PageHeader`, and canonical platform-owned secondary shells instead of raw Ant route containers.',
  },
]

const workflowMonitorRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Layout', 'Modal', 'Row', 'Col', 'Table', 'Tabs'],
    message: 'Workflow monitor route must compose through `WorkspacePage`, `PageHeader`, and responsive diagnostics surfaces instead of raw Ant route containers.',
  },
]

const topologyTemplatesRouteModuleImports = [
  {
    name: 'antd',
    importNames: ['Card', 'Drawer', 'Modal', 'Row', 'Col', 'Tabs'],
    message: 'Topology templates route must compose through `WorkspacePage`, `MasterDetailShell`, and canonical authoring surfaces instead of raw Ant route containers.',
  },
]

const databasesSecondarySurfaceImports = [
  {
    name: 'antd',
    importNames: ['Modal'],
    message: 'Databases modal management flows must use `ModalFormShell` from `src/components/platform` instead of raw `Modal`.',
  },
  {
    name: 'antd',
    importNames: ['Drawer'],
    message: 'Databases drawer management flows must use `DrawerFormShell` from `src/components/platform` instead of raw `Drawer`.',
  },
]

const noStaticModalMethodsRule = {
  selector: "MemberExpression[object.name='Modal'][property.name=/^(confirm|info|success|error|warning)$/]",
  message: 'Use `const { modal } = App.useApp()` and call `modal.confirm/info/...` instead of `Modal.*` static methods.',
}

const shellSafeInternalNavigationRules = [
  {
    selector: "JSXOpeningElement[name.name='Button'] > JSXAttribute[name.name='href']",
    message: 'Authenticated internal handoff must use `RouteButton` or explicit router navigation instead of `Button href`.',
  },
  {
    selector: "JSXOpeningElement[name.object.name='Breadcrumb'][name.property.name='Item'] > JSXAttribute[name.name='href']",
    message: 'Authenticated internal handoff must use `react-router-dom` links instead of `Breadcrumb.Item href`.',
  },
]

const trackedPlatformShellImportNames = new Set(['ModalFormShell', 'DrawerFormShell', 'ModalSurfaceShell', 'DrawerSurfaceShell'])
const platformFormShellImportNames = new Set(['ModalFormShell', 'DrawerFormShell'])
const platformShellRestrictedAntdImports = new Map([
  ['Descriptions', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe summary rows instead of raw `Descriptions`.'],
  ['Table', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe list/summary surfaces instead of raw `Table`.'],
  ['Card', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe detail/layout primitives instead of raw `Card`.'],
  ['Row', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe detail/layout primitives instead of raw `Row`.'],
  ['Col', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe detail/layout primitives instead of raw `Col`.'],
  ['Tabs', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe task surfaces instead of raw `Tabs`.'],
  ['Collapse', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe disclosure surfaces instead of raw `Collapse`.'],
  ['Tag', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe status/summary chips instead of raw `Tag`.'],
  ['Divider', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe spacing/separators instead of raw `Divider`.'],
])
const routePrimaryShellForbiddenHtmlTags = new Set(['div', 'section', 'main', 'aside', 'article'])

const normalizeInventoryPath = (value) => value.replace(/\\/g, '/')
const resolveFrontendRelativePath = (filename) => (
  normalizeInventoryPath(filename).split('/frontend/').pop() ?? normalizeInventoryPath(filename)
)
const filePathMatchesInventory = (filename, relativePath) => {
  const normalizedFilename = normalizeInventoryPath(filename)
  return normalizedFilename === relativePath || normalizedFilename.endsWith(`/${relativePath}`)
}

const getJsxIdentifierName = (node) => (node?.type === 'JSXIdentifier' ? node.name : null)
const getJsxTagRootName = (node) => {
  if (!node) {
    return null
  }

  if (node.type === 'JSXIdentifier') {
    return node.name
  }

  if (node.type === 'JSXMemberExpression') {
    return getJsxTagRootName(node.object)
  }

  if (node.type === 'JSXNamespacedName') {
    return getJsxIdentifierName(node.namespace)
  }

  return null
}
const getStaticJsxAttributeValue = (attributes, attributeName) => {
  const attributeList = Array.isArray(attributes) ? attributes : attributes?.attributes
  if (!Array.isArray(attributeList)) {
    return { found: false, value: null }
  }

  for (const attribute of attributeList) {
    if (attribute.type !== 'JSXAttribute') {
      continue
    }

    if (getJsxIdentifierName(attribute.name) !== attributeName || !attribute.value) {
      continue
    }

    if (attribute.value.type === 'Literal' && typeof attribute.value.value === 'string') {
      return { found: true, value: attribute.value.value }
    }

    if (
      attribute.value.type === 'JSXExpressionContainer'
      && attribute.value.expression?.type === 'TemplateLiteral'
      && attribute.value.expression.expressions.length === 0
      && attribute.value.expression.quasis.length === 1
    ) {
      return { found: true, value: attribute.value.expression.quasis[0].value.cooked ?? null }
    }

    if (
      attribute.value.type === 'JSXExpressionContainer'
      && attribute.value.expression?.type === 'Literal'
      && typeof attribute.value.expression.value === 'string'
    ) {
      return { found: true, value: attribute.value.expression.value }
    }

    return { found: true, value: null }
  }

  return { found: false, value: null }
}

const getJsxAttributeExpression = (attributes, attributeName) => {
  const attributeList = Array.isArray(attributes) ? attributes : attributes?.attributes
  if (!Array.isArray(attributeList)) {
    return null
  }

  for (const attribute of attributeList) {
    if (attribute.type !== 'JSXAttribute') {
      continue
    }

    if (getJsxIdentifierName(attribute.name) !== attributeName || !attribute.value) {
      continue
    }

    if (attribute.value.type === 'JSXExpressionContainer') {
      return attribute.value.expression ?? null
    }
  }

  return null
}

const getObjectExpressionPropertyValue = (expression, propertyName) => {
  if (!expression || expression.type !== 'ObjectExpression') {
    return null
  }

  for (const property of expression.properties) {
    if (property.type !== 'Property' || property.computed) {
      continue
    }

    const keyName = property.key.type === 'Identifier'
      ? property.key.name
      : property.key.type === 'Literal' && typeof property.key.value === 'string'
        ? property.key.value
        : null

    if (keyName === propertyName) {
      return property.value
    }
  }

  return null
}

const expressionIsHorizontalOverflowDependency = (expression) => {
  if (!expression) {
    return false
  }

  if (expression.type === 'Literal') {
    return expression.value === 'auto' || expression.value === 'scroll'
  }

  if (
    expression.type === 'TemplateLiteral'
    && expression.expressions.length === 0
    && expression.quasis.length === 1
  ) {
    const cooked = expression.quasis[0].value.cooked
    return cooked === 'auto' || cooked === 'scroll'
  }

  if (expression.type === 'ObjectExpression') {
    return getObjectExpressionPropertyValue(expression, 'x') !== null
  }

  return false
}

const visitJsxExpressionTree = (node, visitor) => {
  if (!node) {
    return
  }

  visitor(node)

  if (node.type === 'JSXElement') {
    visitJsxExpressionTree(node.openingElement, visitor)
    node.children.forEach((child) => visitJsxExpressionTree(child, visitor))
    return
  }

  if (node.type === 'JSXFragment') {
    node.children.forEach((child) => visitJsxExpressionTree(child, visitor))
    return
  }

  if (node.type === 'JSXExpressionContainer') {
    visitJsxExpressionTree(node.expression, visitor)
    return
  }

  if (node.type === 'ConditionalExpression') {
    visitJsxExpressionTree(node.consequent, visitor)
    visitJsxExpressionTree(node.alternate, visitor)
    return
  }

  if (node.type === 'LogicalExpression') {
    visitJsxExpressionTree(node.left, visitor)
    visitJsxExpressionTree(node.right, visitor)
    return
  }

  if (node.type === 'SequenceExpression') {
    node.expressions.forEach((expression) => visitJsxExpressionTree(expression, visitor))
    return
  }

  if (node.type === 'ArrayExpression') {
    node.elements.forEach((element) => visitJsxExpressionTree(element, visitor))
  }
}

const uiPlatformLocalPlugin = {
  rules: {
    'no-legacy-containers-in-platform-shell-modules': {
      meta: {
        type: 'problem',
        schema: [],
      },
      create(context) {
        const sourceCode = context.getSourceCode()
        const platformShellLocalNames = new Set()
        const restrictedAntdLocalNames = new Map()

        const hasPlatformShellAncestor = (node) => sourceCode.getAncestors(node).some((ancestor) => (
          ancestor.type === 'JSXElement'
          && platformShellLocalNames.has(getJsxTagRootName(ancestor.openingElement.name))
        ))

        const reportForbiddenShellNode = (node) => {
          const tagRootName = getJsxTagRootName(node.name)
          const message = restrictedAntdLocalNames.get(tagRootName)
          if (!message || !hasPlatformShellAncestor(node)) {
            return
          }

          context.report({
            node,
            message,
          })
        }

        return {
          ImportDeclaration(node) {
            const source = typeof node.source.value === 'string' ? node.source.value : ''
            if (source.includes('components/platform')) {
              for (const specifier of node.specifiers) {
                if (
                  specifier.type === 'ImportSpecifier'
                  && platformFormShellImportNames.has(specifier.imported.name)
                ) {
                  platformShellLocalNames.add(specifier.local.name)
                }
              }
            }

            if (source !== 'antd') {
              return
            }

            for (const specifier of node.specifiers) {
              if (specifier.type !== 'ImportSpecifier') {
                continue
              }
              const message = platformShellRestrictedAntdImports.get(specifier.imported.name)
              if (message) {
                restrictedAntdLocalNames.set(specifier.local.name, message)
              }
            }
          },
          JSXOpeningElement: reportForbiddenShellNode,
          JSXSelfClosingElement: reportForbiddenShellNode,
        }
      },
    },
    'app-routes-must-exist-in-governance-inventory': {
      meta: {
        type: 'problem',
        schema: [],
      },
      create(context) {
        const filename = typeof context.filename === 'string' ? context.filename : context.getFilename()
        if (!filePathMatchesInventory(filename, 'src/App.tsx')) {
          return {}
        }

        const routePaths = new Set()
        /** @type {import('estree').Node[]} */
        const nonLiteralPathNodes = []
        const collectRoutePath = (node) => {
          if (getJsxIdentifierName(node.name) !== 'Route') {
            return
          }

          const routePathAttribute = getStaticJsxAttributeValue(node.attributes, 'path')
          if (!routePathAttribute.found) {
            return
          }

          if (!routePathAttribute.value) {
            nonLiteralPathNodes.push(node)
            return
          }

          routePaths.add(routePathAttribute.value)
        }

        return {
          JSXOpeningElement: collectRoutePath,
          JSXSelfClosingElement: collectRoutePath,
          'Program:exit'(node) {
            for (const routeNode of nonLiteralPathNodes) {
              context.report({
                node: routeNode,
                message: 'Route path in src/App.tsx must stay a static string literal so governance inventory can classify it.',
              })
            }

            for (const routePath of routePaths) {
              if (routeGovernancePathSet.has(routePath)) {
                continue
              }

              context.report({
                node,
                message: `Route path "${routePath}" must be classified in src/uiGovernanceInventory.js.`,
              })
            }
          },
        }
      },
    },
    'platform-shell-modules-must-exist-in-governance-inventory': {
      meta: {
        type: 'problem',
        schema: [],
      },
      create(context) {
        const filename = typeof context.filename === 'string' ? context.filename : context.getFilename()
        if (/\.test\.[jt]sx?$/.test(filename)) {
          return {}
        }

        const relativePath = normalizeInventoryPath(filename).split('/frontend/').pop() ?? normalizeInventoryPath(filename)
        let usesPlatformShell = false

        return {
          ImportDeclaration(node) {
            const source = typeof node.source.value === 'string' ? node.source.value : ''
            if (!source.includes('components/platform')) {
              return
            }

            for (const specifier of node.specifiers) {
              if (
                specifier.type === 'ImportSpecifier'
                && trackedPlatformShellImportNames.has(specifier.imported.name)
              ) {
                usesPlatformShell = true
              }
            }
          },
          'Program:exit'(node) {
            if (!usesPlatformShell) {
              return
            }
            if (shellSurfaceFilePathSet.has(relativePath)) {
              return
            }

            context.report({
              node,
              message: `Platform shell module "${relativePath}" must be classified in src/uiGovernanceInventory.js.`,
            })
          },
        }
      },
    },
    'compact-master-pane-must-use-entity-list': {
      meta: {
        type: 'problem',
        schema: [],
      },
      create(context) {
        const filename = typeof context.filename === 'string' ? context.filename : context.getFilename()
        if (/\.test\.[jt]sx?$/.test(filename)) {
          return {}
        }

        const relativePath = resolveFrontendRelativePath(filename)
        const compactMasterPaneGovernance = getCompactMasterPaneGovernance(relativePath)
        if (!compactMasterPaneGovernance) {
          return {}
        }

        const masterDetailShellLocalNames = new Set()
        const entityListLocalNames = new Set()
        const forbiddenMasterPaneLocalNames = new Map()
        const routeReason = compactMasterPaneGovernance.reason
        let hasCompactEntityList = false

        const inspectListExpression = (expression) => {
          const violations = []

          const visit = (current) => {
            if (!current) {
              return
            }

            if (current.type === 'JSXElement') {
              visit(current.openingElement)
              current.children.forEach(visit)
              return
            }

            if (current.type === 'JSXFragment') {
              current.children.forEach(visit)
              return
            }

            if (current.type === 'JSXOpeningElement' || current.type === 'JSXSelfClosingElement') {
              const tagRootName = getJsxTagRootName(current.name)
              if (entityListLocalNames.has(tagRootName)) {
                hasCompactEntityList = true
              }

              const forbiddenComponentLabel = forbiddenMasterPaneLocalNames.get(tagRootName)
              if (forbiddenComponentLabel) {
                violations.push({
                  node: current,
                  message: `${routeReason} MasterDetail list must not use ${forbiddenComponentLabel} as the primary selection surface.`,
                })
              }

              const styleExpression = getJsxAttributeExpression(current.attributes, 'style')
              if (
                expressionIsHorizontalOverflowDependency(
                  getObjectExpressionPropertyValue(styleExpression, 'overflowX')
                )
              ) {
                violations.push({
                  node: current,
                  message: `${routeReason} MasterDetail list must not depend on horizontal overflow inside the master pane.`,
                })
              }

              const scrollExpression = getJsxAttributeExpression(current.attributes, 'scroll')
              if (expressionIsHorizontalOverflowDependency(scrollExpression)) {
                violations.push({
                  node: current,
                  message: `${routeReason} MasterDetail list must not depend on horizontal overflow inside the master pane.`,
                })
              }
              return
            }

            if (current.type === 'JSXExpressionContainer') {
              visit(current.expression)
              return
            }

            if (current.type === 'ConditionalExpression') {
              visit(current.consequent)
              visit(current.alternate)
              return
            }

            if (current.type === 'LogicalExpression') {
              visit(current.left)
              visit(current.right)
              return
            }

            if (current.type === 'SequenceExpression') {
              current.expressions.forEach(visit)
              return
            }

            if (current.type === 'ArrayExpression') {
              current.elements.forEach(visit)
              return
            }
          }

          visit(expression)
          return violations
        }

        const inspectMasterDetailShell = (node) => {
          if (!masterDetailShellLocalNames.has(getJsxTagRootName(node.name))) {
            return
          }

          const listExpression = getJsxAttributeExpression(node.attributes, 'list')
          const violations = inspectListExpression(listExpression)
          for (const violation of violations) {
            context.report(violation)
          }
        }

        return {
          ImportDeclaration(node) {
            const source = typeof node.source.value === 'string' ? node.source.value : ''
            if (source.includes('components/platform')) {
              for (const specifier of node.specifiers) {
                if (specifier.type !== 'ImportSpecifier') {
                  continue
                }
                if (specifier.imported.name === 'MasterDetailShell') {
                  masterDetailShellLocalNames.add(specifier.local.name)
                }
                if (specifier.imported.name === 'EntityList') {
                  entityListLocalNames.add(specifier.local.name)
                }
                if (specifier.imported.name === 'EntityTable') {
                  forbiddenMasterPaneLocalNames.set(specifier.local.name, '`EntityTable`')
                }
              }
            }

            if (source.includes('components/table/TableToolkit')) {
              for (const specifier of node.specifiers) {
                if (specifier.type === 'ImportSpecifier' && specifier.imported.name === 'TableToolkit') {
                  forbiddenMasterPaneLocalNames.set(specifier.local.name, '`TableToolkit`')
                }
              }
            }

            if (source !== 'antd') {
              return
            }

            for (const specifier of node.specifiers) {
              if (specifier.type === 'ImportSpecifier' && specifier.imported.name === 'Table') {
                forbiddenMasterPaneLocalNames.set(specifier.local.name, 'raw `Table`')
              }
            }
          },
          JSXOpeningElement: inspectMasterDetailShell,
          JSXSelfClosingElement: inspectMasterDetailShell,
          'Program:exit'(node) {
            if (hasCompactEntityList) {
              return
            }

            context.report({
              node,
              message: `${routeReason} MasterDetail list must compose through \`EntityList\` as the compact primary selection surface.`,
            })
          },
        }
      },
    },
    'route-modules-must-keep-platform-primary-composition': {
      meta: {
        type: 'problem',
        schema: [],
      },
      create(context) {
        const filename = typeof context.filename === 'string' ? context.filename : context.getFilename()
        const relativeFilename = resolveFrontendRelativePath(filename)

        const clusterRouteFile = 'src/pages/Clusters/Clusters.tsx'
        const systemStatusRouteFile = 'src/pages/SystemStatus/SystemStatus.tsx'
        const serviceMeshRouteFile = 'src/pages/ServiceMesh/ServiceMeshPage.tsx'

        const contract = filePathMatchesInventory(relativeFilename, clusterRouteFile)
          ? {
            routeLabel: 'Clusters route',
            requireWorkspacePage: true,
            requirePageHeader: true,
            requireMasterDetailShell: true,
            requireEntityList: true,
            requireEntityDetails: true,
            requireServiceMeshTab: false,
          }
          : filePathMatchesInventory(relativeFilename, systemStatusRouteFile)
            ? {
              routeLabel: 'System status route',
              requireWorkspacePage: true,
              requirePageHeader: true,
              requireMasterDetailShell: true,
              requireEntityList: true,
              requireEntityDetails: true,
              requireServiceMeshTab: false,
            }
            : filePathMatchesInventory(relativeFilename, serviceMeshRouteFile)
              ? {
                routeLabel: 'Service mesh route',
                requireWorkspacePage: true,
                requirePageHeader: true,
                requireMasterDetailShell: false,
                requireEntityList: false,
                requireEntityDetails: false,
                requireServiceMeshTab: true,
              }
              : null

        if (!contract) {
          return {}
        }

        const workspacePageLocalNames = new Set()
        const pageHeaderLocalNames = new Set()
        const masterDetailShellLocalNames = new Set()
        const entityListLocalNames = new Set()
        const entityDetailsLocalNames = new Set()
        const serviceMeshTabLocalNames = new Set()

        let hasWorkspacePage = false
        let hasPageHeader = false
        let hasMasterDetailShell = false
        let hasEntityListInMasterDetail = false
        let hasEntityDetailsInMasterDetail = false
        let hasServiceMeshTab = false

        const trackRequiredTagUsage = (tagRootName) => {
          if (workspacePageLocalNames.has(tagRootName)) {
            hasWorkspacePage = true
          }
          if (pageHeaderLocalNames.has(tagRootName)) {
            hasPageHeader = true
          }
          if (serviceMeshTabLocalNames.has(tagRootName)) {
            hasServiceMeshTab = true
          }
        }

        const inspectMasterDetailShell = (node) => {
          if (!masterDetailShellLocalNames.has(getJsxTagRootName(node.name))) {
            return
          }

          hasMasterDetailShell = true

          const listExpression = getJsxAttributeExpression(node.attributes, 'list')
          visitJsxExpressionTree(listExpression, (expressionNode) => {
            if (
              (expressionNode.type === 'JSXOpeningElement' || expressionNode.type === 'JSXSelfClosingElement')
              && entityListLocalNames.has(getJsxTagRootName(expressionNode.name))
            ) {
              hasEntityListInMasterDetail = true
            }
          })

          const detailExpression = getJsxAttributeExpression(node.attributes, 'detail')
          visitJsxExpressionTree(detailExpression, (expressionNode) => {
            if (
              (expressionNode.type === 'JSXOpeningElement' || expressionNode.type === 'JSXSelfClosingElement')
              && entityDetailsLocalNames.has(getJsxTagRootName(expressionNode.name))
            ) {
              hasEntityDetailsInMasterDetail = true
            }
          })
        }

        const inspectOpeningElement = (node) => {
          const tagRootName = getJsxTagRootName(node.name)
          trackRequiredTagUsage(tagRootName)
          inspectMasterDetailShell(node)

          if (!routePrimaryShellForbiddenHtmlTags.has(tagRootName)) {
            return
          }

          context.report({
            node,
            message: `${contract.routeLabel} must not fall back to raw \`${tagRootName}\`-based custom shell composition; keep the primary route layout in platform primitives.`,
          })
        }

        return {
          ImportDeclaration(node) {
            const source = typeof node.source.value === 'string' ? node.source.value : ''
            if (source.includes('components/platform')) {
              for (const specifier of node.specifiers) {
                if (specifier.type !== 'ImportSpecifier') {
                  continue
                }

                if (specifier.imported.name === 'WorkspacePage') {
                  workspacePageLocalNames.add(specifier.local.name)
                }
                if (specifier.imported.name === 'PageHeader') {
                  pageHeaderLocalNames.add(specifier.local.name)
                }
                if (specifier.imported.name === 'MasterDetailShell') {
                  masterDetailShellLocalNames.add(specifier.local.name)
                }
                if (specifier.imported.name === 'EntityList') {
                  entityListLocalNames.add(specifier.local.name)
                }
                if (specifier.imported.name === 'EntityDetails') {
                  entityDetailsLocalNames.add(specifier.local.name)
                }
              }
            }

            if (filePathMatchesInventory(relativeFilename, serviceMeshRouteFile) && source.includes('components/service-mesh/ServiceMeshTab')) {
              for (const specifier of node.specifiers) {
                if (specifier.type === 'ImportDefaultSpecifier' || specifier.type === 'ImportSpecifier') {
                  serviceMeshTabLocalNames.add(specifier.local.name)
                }
              }
            }
          },
          JSXOpeningElement: inspectOpeningElement,
          JSXSelfClosingElement: inspectOpeningElement,
          'Program:exit'(node) {
            if (contract.requireWorkspacePage && !hasWorkspacePage) {
              context.report({
                node,
                message: `${contract.routeLabel} must render through \`WorkspacePage\` at the route level.`,
              })
            }

            if (contract.requirePageHeader && !hasPageHeader) {
              context.report({
                node,
                message: `${contract.routeLabel} must render through \`PageHeader\` at the route level.`,
              })
            }

            if (contract.requireMasterDetailShell && !hasMasterDetailShell) {
              context.report({
                node,
                message: `${contract.routeLabel} must keep \`MasterDetailShell\` as the primary catalog/detail composition.`,
              })
            }

            if (contract.requireEntityList && !hasEntityListInMasterDetail) {
              context.report({
                node,
                message: `${contract.routeLabel} must compose the primary catalog through \`EntityList\` inside \`MasterDetailShell\`.`,
              })
            }

            if (contract.requireEntityDetails && !hasEntityDetailsInMasterDetail) {
              context.report({
                node,
                message: `${contract.routeLabel} must compose the primary diagnostics/detail surface through \`EntityDetails\` inside \`MasterDetailShell\`.`,
              })
            }

            if (contract.requireServiceMeshTab && !hasServiceMeshTab) {
              context.report({
                node,
                message: `${contract.routeLabel} must keep \`ServiceMeshTab\` as the primary realtime surface inside \`WorkspacePage\`.`,
              })
            }
          },
        }
      },
    },
  },
}

const buildRouteRestrictedImportsOverride = (lintProfile, paths) => {
  const files = getRouteModulesByLintProfile(lintProfile)
  if (files.length === 0) {
    return null
  }

  return {
    files,
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...paths,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  }
}

const inventoryDrivenRouteOverrides = [
  buildRouteRestrictedImportsOverride('privileged-workspace-route', privilegedWorkspaceRouteModuleImports),
  buildRouteRestrictedImportsOverride('canonical-page-route', canonicalPageContainerImports),
  buildRouteRestrictedImportsOverride('dashboard-route', dashboardRouteModuleImports),
  buildRouteRestrictedImportsOverride('operations-route', operationsRouteModuleImports),
  buildRouteRestrictedImportsOverride('databases-route', databasesRouteModuleImports),
  buildRouteRestrictedImportsOverride('clusters-route', clustersRouteModuleImports),
  buildRouteRestrictedImportsOverride('observability-route', observabilityRouteModuleImports),
  buildRouteRestrictedImportsOverride('pool-catalog-route', poolCatalogRouteModuleImports),
  buildRouteRestrictedImportsOverride('pool-runs-route', poolRunsRouteModuleImports),
  buildRouteRestrictedImportsOverride('pool-schema-templates-route', poolSchemaTemplatesRouteModuleImports),
  buildRouteRestrictedImportsOverride('pool-master-data-route', poolMasterDataRouteModuleImports),
  buildRouteRestrictedImportsOverride('topology-templates-route', topologyTemplatesRouteModuleImports),
  buildRouteRestrictedImportsOverride('templates-route', templatesRouteModuleImports),
  buildRouteRestrictedImportsOverride('workflow-list-route', workflowListRouteModuleImports),
  buildRouteRestrictedImportsOverride('workflow-executions-route', workflowExecutionsRouteModuleImports),
  buildRouteRestrictedImportsOverride('workflow-designer-route', workflowDesignerRouteModuleImports),
  buildRouteRestrictedImportsOverride('workflow-monitor-route', workflowMonitorRouteModuleImports),
].filter(Boolean)

export default tseslint.config(
  { ignores: ['dist', 'src/api/generated/**'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'ui-platform-local': uiPlatformLocalPlugin,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Keep legacy lint behavior while using eslint@9:
      // these newer react-hooks rules generate broad refactor requirements.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/set-state-in-render': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],

      // Strict null/undefined safety rules (non-type-aware for faster linting)
      '@typescript-eslint/no-non-null-assertion': 'warn',
      // Note: prefer-optional-chain and prefer-nullish-coalescing require type info
      // Use TypeScript strict mode in tsconfig.json instead

      // Catch potential runtime errors
      'no-unsafe-optional-chaining': 'error',
      '@typescript-eslint/no-unnecessary-condition': 'off', // Requires type-aware linting

      // Array access safety
      '@typescript-eslint/no-unsafe-member-access': 'off', // Too noisy
      '@typescript-eslint/no-unsafe-call': 'off',

      // General safety
      'no-constant-binary-expression': 'error',
      'no-self-compare': 'error',
      'no-template-curly-in-string': 'warn',
      'no-unmodified-loop-condition': 'error',

      // Unused variables (already in tsconfig but good to have in ESLint too)
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_'
      }],

      // Downgrade any to warning - fix gradually, not all at once
      '@typescript-eslint/no-explicit-any': 'warn',

      // Ant Design context-aware APIs:
      // forbid static imports that bypass dynamic theme/context; use `App.useApp()` instead.
      'no-restricted-imports': ['error', {
        paths: contextAwareAntdImports,
        patterns: competingFoundationImportPatterns,
      }],
      'ui-platform-local/no-legacy-containers-in-platform-shell-modules': 'error',
      'ui-platform-local/app-routes-must-exist-in-governance-inventory': 'error',
      'ui-platform-local/platform-shell-modules-must-exist-in-governance-inventory': 'error',
      'ui-platform-local/compact-master-pane-must-use-entity-list': 'error',
      'ui-platform-local/route-modules-must-keep-platform-primary-composition': 'error',
      'no-restricted-syntax': ['error', noStaticModalMethodsRule],
    },
  },
  {
    files: [
      'src/pages/Decisions/DecisionsPage.tsx',
      'src/pages/Decisions/DecisionCatalogPanel.tsx',
      'src/pages/Decisions/DecisionDetailPanel.tsx',
      'src/pages/Pools/PoolBindingProfilesPage.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...canonicalPageContainerImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Decisions/*Panel.tsx',
      'src/pages/Decisions/*Viewer.tsx',
      'src/pages/Pools/PoolBindingProfiles*.tsx',
      'src/pages/Pools/BindingProfile*.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...canonicalPilotModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Pools/PoolBindingProfilesEditorModal.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          {
            name: 'antd',
            importNames: ['Modal'],
            message: 'Binding profile authoring must use `ModalFormShell` from `src/components/platform` instead of raw `Modal`.',
          },
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Dashboard/**/*Workspace*.tsx',
      'src/pages/Operations/**/*Workspace*.tsx',
      'src/pages/Databases/**/*Workspace*.tsx',
      'src/pages/Pools/**/*Workspace*.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...operationalWorkspaceModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Decisions/DecisionsPage.tsx',
      'src/pages/Dashboard/Dashboard.tsx',
      'src/pages/Databases/Databases.tsx',
      'src/pages/Operations/OperationsPage.tsx',
      'src/pages/Pools/PoolBindingProfilesEditorModal.tsx',
      'src/pages/Pools/PoolRunsPage.tsx',
      'src/pages/Pools/PoolWorkflowBindingsEditor.tsx',
    ],
    rules: {
      'no-restricted-syntax': ['error', noStaticModalMethodsRule, ...shellSafeInternalNavigationRules],
    },
  },
  ...inventoryDrivenRouteOverrides,
  {
    files: [
      'src/pages/Databases/components/DatabaseCredentialsModal.tsx',
      'src/pages/Databases/components/DatabaseDbmsMetadataModal.tsx',
      'src/pages/Databases/components/DatabaseIbcmdConnectionProfileModal.tsx',
      'src/pages/Databases/components/DatabaseMetadataManagementDrawer.tsx',
      'src/pages/Databases/components/ExtensionsDrawer.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...databasesSecondarySurfaceImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
)

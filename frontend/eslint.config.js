import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

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

const platformShellImportNames = new Set(['ModalFormShell', 'DrawerFormShell'])
const platformShellRestrictedAntdImports = new Map([
  ['Descriptions', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe summary rows instead of raw `Descriptions`.'],
  ['Table', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe list/summary surfaces instead of raw `Table`.'],
  ['Card', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe detail/layout primitives instead of raw `Card`.'],
  ['Row', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe detail/layout primitives instead of raw `Row`.'],
  ['Col', 'Modules using `ModalFormShell` or `DrawerFormShell` must use platform-safe detail/layout primitives instead of raw `Col`.'],
])

const uiPlatformLocalPlugin = {
  rules: {
    'no-legacy-containers-in-platform-shell-modules': {
      meta: {
        type: 'problem',
        schema: [],
      },
      create(context) {
        const filename = typeof context.filename === 'string' ? context.filename : context.getFilename()
        const isShellSurfaceFile = /(?:Modal|Drawer)\.tsx$/.test(filename)
        let usesPlatformShell = false
        /** @type {Array<{ node: import('estree').Node, message: string }>} */
        const offenders = []

        return {
          ImportDeclaration(node) {
            const source = typeof node.source.value === 'string' ? node.source.value : ''
            if (source.includes('components/platform')) {
              for (const specifier of node.specifiers) {
                if (
                  specifier.type === 'ImportSpecifier'
                  && platformShellImportNames.has(specifier.imported.name)
                ) {
                  usesPlatformShell = true
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
                offenders.push({ node: specifier, message })
              }
            }
          },
          'Program:exit'() {
            if (!isShellSurfaceFile || !usesPlatformShell) {
              return
            }

            for (const offender of offenders) {
              context.report({
                node: offender.node,
                message: offender.message,
              })
            }
          },
        }
      },
    },
  },
}

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
  {
    files: [
      'src/pages/Dashboard/Dashboard.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...dashboardRouteModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Operations/OperationsPage.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...operationsRouteModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Databases/Databases.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...databasesRouteModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Pools/PoolCatalogPage.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...poolCatalogRouteModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
  {
    files: [
      'src/pages/Pools/PoolRunsPage.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          ...contextAwareAntdImports,
          ...poolRunsRouteModuleImports,
        ],
        patterns: competingFoundationImportPatterns,
      }],
    },
  },
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

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
      'no-restricted-syntax': ['error', {
        selector: "MemberExpression[object.name='Modal'][property.name=/^(confirm|info|success|error|warning)$/]",
        message: 'Use `const { modal } = App.useApp()` and call `modal.confirm/info/...` instead of `Modal.*` static methods.',
      }],
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
)

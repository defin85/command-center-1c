import { defineConfig } from 'orval'

export default defineConfig({
  orchestrator: {
    input: {
      target: '../contracts/orchestrator/openapi.yaml',
      // Filter only v2 API endpoints
      filters: {
        tags: ['v2'],
      },
    },
    output: {
      mode: 'tags-split',
      target: './src/api/generated',
      schemas: './src/api/generated/model',
      client: 'axios',
      // Use existing apiClient with all interceptors
      override: {
        mutator: {
          path: './src/api/mutator.ts',
          name: 'customInstance',
        },
        // Use more readable operation names
        operationName: (operation, _route, verb) => {
          // Convert operationId like v2_workflows_list_workflows_retrieve -> listWorkflows
          const opId = operation.operationId || ''
          // Remove v2_ prefix and _retrieve/_create/_update/_destroy suffixes
          let name = opId
            .replace(/^v2_/, '')
            .replace(/_(retrieve|create|update|destroy|list)$/, '')

          // Convert snake_case to camelCase
          name = name.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())

          // Add verb prefix based on HTTP method to avoid duplicates
          // e.g., POST /delete-cluster -> postDeleteCluster, DELETE /delete-cluster -> deleteDeleteCluster
          const verbMap: Record<string, string> = {
            get: 'get',
            post: 'post',
            put: 'put',
            patch: 'patch',
            delete: 'del',
          }
          const verbPrefix = verbMap[verb] || verb

          // Check if name already starts with a verb-like prefix
          const startsWithVerb = /^(get|list|create|update|delete|post|put|patch)/.test(name.toLowerCase())

          if (!startsWithVerb) {
            name = verbPrefix + name.charAt(0).toUpperCase() + name.slice(1)
          }

          return name
        },
      },
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
  apiGateway: {
    input: {
      target: '../contracts/api-gateway/openapi.yaml',
      filters: {
        tags: ['tracing'],
      },
    },
    output: {
      mode: 'single',
      target: './src/api/generated-gateway/index.ts',
      schemas: './src/api/generated-gateway/model',
      client: 'axios',
      override: {
        mutator: {
          path: './src/api/mutator.ts',
          name: 'customInstance',
        },
        operationName: (operation, _route, verb) => {
          const opId = operation.operationId || ''
          let name = opId.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
          const verbMap: Record<string, string> = {
            get: 'get',
            post: 'post',
            put: 'put',
            patch: 'patch',
            delete: 'del',
          }
          const verbPrefix = verbMap[verb] || verb
          const startsWithVerb = /^(get|list|create|update|delete|post|put|patch)/.test(name.toLowerCase())
          if (!startsWithVerb) {
            name = verbPrefix + name.charAt(0).toUpperCase() + name.slice(1)
          }
          return name
        },
      },
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
})

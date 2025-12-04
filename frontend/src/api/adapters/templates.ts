/**
 * Operation Templates API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides functions for Operation Templates management
 * 3. Maps parameters to the v2 action-based endpoints
 *
 * Operation Templates are used in Workflow Designer for configuring
 * operation nodes with predefined parameters and behaviors.
 */

import { customInstance } from '../mutator'
// Re-export generated types for direct use
import type {
  OperationTemplate as GeneratedOperationTemplate,
  OperationTemplateTemplateData,
  PaginatedOperationTemplateList,
} from '../generated/model'

// ============================================================================
// Types
// ============================================================================

/**
 * Operation Template list item (lightweight for dropdowns).
 */
export interface OperationTemplateListItem {
  id: string
  name: string
  operation_type: string
  description?: string
}

/**
 * Full Operation Template with all fields.
 */
export interface OperationTemplate {
  id: string
  name: string
  description?: string
  operation_type: string
  target_entity: string
  template_data?: OperationTemplateTemplateData
  is_active: boolean
  created_at: string
  updated_at: string
}

/**
 * Parameters for listing templates.
 */
export interface OperationTemplateListParams {
  operation_type?: string
  target_entity?: string
  is_active?: boolean
  limit?: number
  offset?: number
}

/**
 * Create operation template request.
 */
export interface OperationTemplateCreate {
  name: string
  description?: string
  operation_type: string
  target_entity: string
  template_data?: OperationTemplateTemplateData
  is_active?: boolean
}

/**
 * Update operation template request.
 */
export interface OperationTemplateUpdate {
  name?: string
  description?: string
  operation_type?: string
  target_entity?: string
  template_data?: OperationTemplateTemplateData
  is_active?: boolean
}

/**
 * Response from list-templates endpoint.
 */
export interface ListTemplatesResponse {
  templates: OperationTemplate[]
  count: number
}

// Re-export generated types for advanced use cases
export type {
  GeneratedOperationTemplate,
  OperationTemplateTemplateData,
  PaginatedOperationTemplateList,
}

// ============================================================================
// Type Transformations
// ============================================================================

/**
 * Convert generated OperationTemplate to local format.
 */
function convertToLocal(template: GeneratedOperationTemplate): OperationTemplate {
  return {
    id: template.id,
    name: template.name,
    description: template.description,
    operation_type: template.operation_type,
    target_entity: template.target_entity,
    template_data: template.template_data,
    is_active: template.is_active ?? true,
    created_at: template.created_at,
    updated_at: template.updated_at,
  }
}

/**
 * Convert to lightweight list item format for dropdowns.
 */
function convertToListItem(template: GeneratedOperationTemplate): OperationTemplateListItem {
  return {
    id: template.id,
    name: template.name,
    operation_type: template.operation_type,
    description: template.description,
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List operation templates with optional filtering.
 * GET /api/v2/templates/list-templates/
 *
 * @param params - Optional filtering parameters
 * @returns List of operation templates
 */
export const listTemplates = async (
  params?: OperationTemplateListParams
): Promise<OperationTemplate[]> => {
  const response = await customInstance<ListTemplatesResponse>({
    url: '/api/v2/templates/list-templates/',
    method: 'GET',
    params: {
      operation_type: params?.operation_type,
      target_entity: params?.target_entity,
      is_active: params?.is_active,
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  })

  const templates = response.templates ?? (response as unknown as GeneratedOperationTemplate[])
  return templates.map(convertToLocal)
}

/**
 * List all operation templates for dropdown selection.
 * Convenience function that returns lightweight items.
 *
 * @returns List of operation templates for dropdowns
 */
export const listOperationTemplates = async (): Promise<OperationTemplateListItem[]> => {
  const response = await customInstance<ListTemplatesResponse>({
    url: '/api/v2/templates/list-templates/',
    method: 'GET',
    params: { limit: 1000 }, // Get all for dropdown
  })

  const templates = response.templates ?? (response as unknown as GeneratedOperationTemplate[])
  return templates.map(convertToListItem)
}

/**
 * Get a single operation template by ID.
 * GET /api/v2/templates/get-template/?template_id=X
 *
 * Note: This endpoint may not be implemented yet in the backend.
 * Check API documentation for availability.
 *
 * @param id - Template UUID
 * @returns Full operation template
 */
export const getTemplate = async (id: string): Promise<OperationTemplate> => {
  interface GetTemplateResponse {
    template: GeneratedOperationTemplate
  }

  const response = await customInstance<GetTemplateResponse>({
    url: '/api/v2/templates/get-template/',
    method: 'GET',
    params: { template_id: id },
  })

  const template = response.template ?? (response as unknown as GeneratedOperationTemplate)
  return convertToLocal(template)
}

/**
 * Create a new operation template.
 * POST /api/v2/templates/create-template/
 *
 * Note: This endpoint may not be implemented yet in the backend.
 * Check API documentation for availability.
 *
 * @param data - Template data
 * @returns Created operation template
 */
export const createTemplate = async (
  data: OperationTemplateCreate
): Promise<OperationTemplate> => {
  interface CreateTemplateResponse {
    template: GeneratedOperationTemplate
    message: string
  }

  const response = await customInstance<CreateTemplateResponse>({
    url: '/api/v2/templates/create-template/',
    method: 'POST',
    data,
  })

  const template = response.template ?? (response as unknown as GeneratedOperationTemplate)
  return convertToLocal(template)
}

/**
 * Update an existing operation template.
 * POST /api/v2/templates/update-template/
 *
 * Note: This endpoint may not be implemented yet in the backend.
 * Check API documentation for availability.
 *
 * @param id - Template UUID
 * @param data - Fields to update
 * @returns Updated operation template
 */
export const updateTemplate = async (
  id: string,
  data: OperationTemplateUpdate
): Promise<OperationTemplate> => {
  interface UpdateTemplateResponse {
    template: GeneratedOperationTemplate
    message: string
  }

  const response = await customInstance<UpdateTemplateResponse>({
    url: '/api/v2/templates/update-template/',
    method: 'POST',
    data: { template_id: id, ...data },
  })

  const template = response.template ?? (response as unknown as GeneratedOperationTemplate)
  return convertToLocal(template)
}

/**
 * Delete an operation template.
 * POST /api/v2/templates/delete-template/
 *
 * Note: This endpoint may not be implemented yet in the backend.
 * Check API documentation for availability.
 *
 * @param id - Template UUID
 * @param force - Force deletion even if template is in use
 */
export const deleteTemplate = async (id: string, force = false): Promise<void> => {
  await customInstance<{ template_id: string; deleted: boolean; message: string }>({
    url: '/api/v2/templates/delete-template/',
    method: 'POST',
    data: { template_id: id, force },
  })
}

// ============================================================================
// Legacy API object (for backward compatibility)
// ============================================================================

/**
 * @deprecated Use individual functions instead.
 * This object maintains backward compatibility with old code patterns.
 */
export const templatesApi = {
  list: listTemplates,
  listForDropdown: listOperationTemplates,
  get: getTemplate,
  create: createTemplate,
  update: updateTemplate,
  delete: deleteTemplate,
}

export default templatesApi

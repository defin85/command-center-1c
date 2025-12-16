/**
 * Files API Client
 *
 * API client for file upload, download, and management operations.
 */

import type { AxiosProgressEvent } from 'axios'

import { getV2 } from './generated'

const api = getV2()

/**
 * File upload response from API.
 */
export interface FileUploadResponse {
  /** Unique file identifier */
  file_id: string
  /** Original filename */
  filename: string
  /** File size in bytes */
  size: number
  /** MIME type */
  content_type: string
  /** Upload timestamp */
  uploaded_at: string
  /** When file expires (optional) */
  expires_at?: string
}

/**
 * Progress callback type.
 */
type ProgressCallback = (percent: number) => void

/**
 * Files API client.
 */
export const filesApi = {
  /**
   * Upload a file.
   *
   * @param file - File to upload
   * @param purpose - Purpose/category of the file (e.g., 'extension', 'form_attachment')
   * @param expiryHours - Hours until file expires (optional)
   * @param onProgress - Progress callback (optional)
   * @returns Upload response with file_id
   */
  upload: async (
    file: File,
    purpose: string,
    expiryHours?: number,
    onProgress?: ProgressCallback
  ): Promise<FileUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('purpose', purpose)

    if (expiryHours !== undefined) {
      formData.append('expiry_hours', String(expiryHours))
    }

    const response = await api.postFilesUpload(
      {
        purpose,
        expiry_hours: expiryHours,
      },
      {
        data: formData,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (event: AxiosProgressEvent) => {
          if (onProgress && event.total) {
            const percent = Math.round((event.loaded * 100) / event.total)
            onProgress(percent)
          }
        },
      },
    )

    return response as unknown as FileUploadResponse
  },

  /**
   * Delete a file by ID.
   *
   * @param fileId - File ID to delete
   */
  delete: async (fileId: string): Promise<void> => {
    await api.delFilesDelete(fileId)
  },

  /**
   * Get download URL for a file.
   *
   * @param fileId - File ID
   * @returns Full download URL
   */
  getDownloadUrl: (fileId: string): string => {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8180'
    return `${baseUrl}/api/v2/files/download/${fileId}/`
  },

  /**
   * Download a file directly.
   *
   * @param fileId - File ID to download
   * @returns Blob of the file content
   */
  download: async (fileId: string): Promise<Blob> => {
    return api.getFilesDownload(fileId, { responseType: 'blob' }) as unknown as Blob
  },
}

export default filesApi

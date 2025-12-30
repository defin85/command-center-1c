/**
 * FileFieldRenderer Component
 *
 * Renders file upload fields using Ant Design Upload.
 * Integrates with files API for upload/delete operations.
 */

import { useState, useRef, useEffect } from 'react'
import { App, Upload, Button, Progress } from 'antd'
import {
  UploadOutlined,
  DeleteOutlined,
  FileOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import type { UploadFile, UploadChangeParam } from 'antd/es/upload/interface'
import type { FieldRendererProps } from '../types'
import { filesApi } from '../../../api/files'
import { PurposeEnum } from '../../../api/generated/model'

/**
 * Validate file type against accept pattern.
 * Supports both extension patterns (e.g., '.pdf') and MIME type patterns (e.g., 'image/*').
 */
function isValidFileType(file: File, accept: string): boolean {
  if (accept === '*') {
    return true
  }

  const acceptedTypes = accept.split(',').map(t => t.trim().toLowerCase())
  const fileExt = `.${file.name.split('.').pop()?.toLowerCase() || ''}`
  const fileMime = file.type.toLowerCase()

  return acceptedTypes.some(accepted => {
    // Extension pattern (e.g., '.pdf', '.doc')
    if (accepted.startsWith('.')) {
      return accepted === fileExt
    }
    // Wildcard MIME pattern (e.g., 'image/*')
    if (accepted.endsWith('/*')) {
      const mimePrefix = accepted.replace('/*', '')
      return fileMime.startsWith(mimePrefix)
    }
    // Exact MIME type (e.g., 'application/pdf')
    return fileMime === accepted
  })
}

/**
 * Renderer for file upload fields.
 * Features:
 * - Single file upload
 * - Progress indication
 * - File type restriction via x-file-accept
 * - File size limit via x-file-max-size
 * - Proper cleanup on unmount (AbortController)
 */
export function FileFieldRenderer({
  name,
  schema,
  value,
  onChange,
  disabled,
  uploadedFileId,
  onFileUpload,
  onFileRemove,
}: FieldRendererProps) {
  const { message } = App.useApp()
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [fileList, setFileList] = useState<UploadFile[]>(() => {
    // Initialize with existing file if present
    if (uploadedFileId && value) {
      return [
        {
          uid: uploadedFileId,
          name: value as string,
          status: 'done',
        },
      ]
    }
    return []
  })

  // AbortController for cancelling uploads on unmount
  const abortControllerRef = useRef<AbortController | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [])

  // Get file restrictions from schema
  const accept = schema['x-file-accept'] || '*'
  const maxSize = schema['x-file-max-size'] || 10 * 1024 * 1024 // Default 10MB

  /**
   * Handle file upload.
   */
  const handleUpload = async (file: File) => {
    // Check file type
    if (!isValidFileType(file, accept)) {
      message.error(`File type not allowed. Accepted: ${accept}`)
      return false
    }

    // Check file size
    if (file.size > maxSize) {
      const maxSizeMB = Math.round(maxSize / (1024 * 1024))
      message.error(`File size must be less than ${maxSizeMB}MB`)
      return false
    }

    // Create new AbortController for this upload
    abortControllerRef.current = new AbortController()

    setUploading(true)
    setProgress(0)

    try {
      // Upload file with progress tracking
      const response = await filesApi.upload(file, PurposeEnum.operation_input, undefined, (percent) => {
        // Check if aborted before updating state
        if (!abortControllerRef.current?.signal.aborted) {
          setProgress(percent)
        }
      })

      // Check if aborted before updating state
      if (abortControllerRef.current?.signal.aborted) {
        return false
      }

      // Update state
      setFileList([
        {
          uid: response.file_id,
          name: file.name,
          status: 'done',
        },
      ])

      // Notify parent
      onChange(file.name)
      onFileUpload?.(response.file_id)

      message.success('File uploaded successfully')
    } catch (error) {
      // Only handle error if not aborted
      if (!abortControllerRef.current?.signal.aborted) {
        console.error('Upload failed:', error)
        message.error('File upload failed')
        setFileList([])
      }
    } finally {
      // Only update state if not aborted
      if (!abortControllerRef.current?.signal.aborted) {
        setUploading(false)
        setProgress(0)
      }
    }

    // Prevent default upload behavior
    return false
  }

  /**
   * Handle file removal.
   */
  const handleRemove = async () => {
    if (uploadedFileId) {
      try {
        await filesApi.delete(uploadedFileId)
      } catch (error) {
        console.error('Failed to delete file:', error)
        // Continue with removal even if delete fails
      }
    }

    setFileList([])
    onChange(null)
    onFileRemove?.()
  }

  /**
   * Handle upload change events.
   */
  const handleChange = (info: UploadChangeParam) => {
    // Only update fileList for status changes
    if (info.file.status) {
      setFileList(info.fileList)
    }
  }

  // Show progress during upload
  if (uploading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <LoadingOutlined />
        <Progress percent={progress} size="small" style={{ flex: 1 }} />
      </div>
    )
  }

  // Show uploaded file
  if (fileList.length > 0) {
    const file = fileList[0]
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '4px 8px',
          background: '#f5f5f5',
          borderRadius: 4,
        }}
      >
        <FileOutlined />
        <span style={{ flex: 1 }}>{file.name}</span>
        {!disabled && (
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={handleRemove}
            aria-label={`Remove file ${file.name}`}
          />
        )}
      </div>
    )
  }

  // Show upload button
  return (
    <Upload
      id={name}
      accept={accept}
      fileList={fileList}
      beforeUpload={handleUpload}
      onChange={handleChange}
      onRemove={handleRemove}
      disabled={disabled}
      maxCount={1}
      showUploadList={false}
    >
      <Button icon={<UploadOutlined />} disabled={disabled}>
        Select File
      </Button>
    </Upload>
  )
}

export default FileFieldRenderer

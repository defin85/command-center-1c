/**
 * Extension Storage API endpoints
 */

import { apiClient } from '../client';

export interface ExtensionFile {
    filename: string;
    size: number;
    modified_at: string;
    path: string;
}

export interface ExtensionStorageResponse {
    extensions: ExtensionFile[];
    count: number;
}

/**
 * Get list of extension files in storage
 */
export const listExtensions = async (): Promise<ExtensionFile[]> => {
    const response = await apiClient.get<ExtensionStorageResponse>('/api/v2/extensions/list-storage/');
    return response.data.extensions;
};

/**
 * Upload extension file to storage
 */
export const uploadExtension = async (
    file: File,
    filename?: string
): Promise<{ message: string; file: ExtensionFile }> => {
    const formData = new FormData();
    formData.append('file', file);
    if (filename) {
        formData.append('filename', filename);
    }

    const response = await apiClient.post<{ message: string; file: ExtensionFile }>(
        '/api/v2/extensions/upload-extension/',
        formData
    );
    return response.data;
};

/**
 * Delete extension file from storage
 */
export const deleteExtension = async (filename: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(
        `/api/v2/extensions/delete-extension/?filename=${encodeURIComponent(filename)}`
    );
    return response.data;
};

export const extensionStorageApi = {
    list: listExtensions,
    upload: uploadExtension,
    delete: deleteExtension,
};

export default extensionStorageApi;

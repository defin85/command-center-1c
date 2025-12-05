/**
 * Extension Storage API endpoints
 */

import { apiClient } from '../client';

export interface ExtensionFile {
    name: string;
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
    const response = await apiClient.get<ExtensionStorageResponse>('/api/v1/extensions/storage/');
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
        '/api/v1/extensions/upload/',
        formData
    );
    return response.data;
};

/**
 * Delete extension file from storage
 */
export const deleteExtension = async (filename: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(
        `/api/v1/extensions/storage/${filename}/`
    );
    return response.data;
};

export const extensionStorageApi = {
    list: listExtensions,
    upload: uploadExtension,
    delete: deleteExtension,
};

export default extensionStorageApi;

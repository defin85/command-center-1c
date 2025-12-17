/**
 * Extension file selector component with storage support
 */

import { useState, useEffect } from 'react';
import { App, Form, Select, Upload, Button, Space, Spin } from 'antd';
import { UploadOutlined, ReloadOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd';
import { extensionStorageApi, type ExtensionFile } from '../../api/endpoints/extensionStorage';

interface ExtensionFileSelectorProps {
    value?: { name: string; path: string };
    onChange?: (value: { name: string; path: string }) => void;
}

export const ExtensionFileSelector: React.FC<ExtensionFileSelectorProps> = ({
    value,
    onChange,
}) => {
    const { message } = App.useApp();
    const [extensions, setExtensions] = useState<ExtensionFile[]>([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [fileList, setFileList] = useState<UploadFile[]>([]);

    const fetchExtensions = async () => {
        try {
            setLoading(true);
            const data = await extensionStorageApi.list();
            setExtensions(data);
        } catch (error) {
            console.error('Failed to load extensions:', error);
            message.error('Не удалось загрузить список файлов');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchExtensions();
    }, []);

    const handleUpload = async () => {
        if (fileList.length === 0) {
            message.warning('Выберите файл');
            return;
        }

        const file = fileList[0];
        if (!file.originFileObj) {
            message.error('Ошибка загрузки файла');
            return;
        }

        try {
            setUploading(true);
            const result = await extensionStorageApi.upload(file.originFileObj);
            message.success(result.message);
            setFileList([]);

            // Обновить список файлов
            await fetchExtensions();

            // Автоматически выбрать загруженный файл
            if (onChange) {
                onChange({
                    name: result.file.filename.replace('.cfe', ''),
                    path: result.file.path,
                });
            }
        } catch (error: unknown) {
            const maybe = error as { response?: { data?: { error?: string } } } | null
            console.error('Upload failed:', error);
            message.error(maybe?.response?.data?.error || 'Ошибка загрузки файла');
        } finally {
            setUploading(false);
        }
    };

    const handleSelectChange = (selectedPath: string) => {
        const selected = extensions.find((ext) => ext.path === selectedPath);
        if (selected && onChange) {
            onChange({
                name: selected.filename.replace('.cfe', ''),
                path: selected.path,
            });
        }
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const formatDate = (timestamp: string | number): string => {
        // Handle both ISO string and Unix timestamp
        const date = typeof timestamp === 'string' && timestamp.includes('-')
            ? new Date(timestamp)
            : new Date(parseFloat(timestamp.toString()) * 1000);

        return date.toLocaleDateString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <Space direction="vertical" style={{ width: '100%' }}>
            <Form.Item label="Файл расширения" style={{ marginBottom: 8 }}>
                <Space.Compact style={{ width: '100%' }}>
                    <Select
                        style={{ flex: 1 }}
                        placeholder="Выберите файл из хранилища"
                        value={value?.path}
                        onChange={handleSelectChange}
                        loading={loading}
                        notFoundContent={loading ? <Spin size="small" /> : 'Нет файлов'}
                        optionLabelProp="label"
                    >
                        {extensions.map((ext) => (
                            <Select.Option
                                key={ext.path}
                                value={ext.path}
                                label={ext.filename}
                            >
                                <div style={{ padding: '4px 0' }}>
                                    <div style={{ fontWeight: 500 }}>{ext.filename}</div>
                                    <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                                        {formatFileSize(ext.size)} • {formatDate(ext.modified_at)}
                                    </div>
                                </div>
                            </Select.Option>
                        ))}
                    </Select>
                    <Button icon={<ReloadOutlined />} onClick={fetchExtensions} loading={loading}>
                        Обновить
                    </Button>
                </Space.Compact>
            </Form.Item>

            <Form.Item label="Или загрузить новый файл" style={{ marginBottom: 0 }}>
                <Space.Compact style={{ width: '100%' }}>
                    <Upload
                        fileList={fileList}
                        onChange={({ fileList }) => setFileList(fileList)}
                        beforeUpload={() => false}
                        accept=".cfe"
                        maxCount={1}
                    >
                        <Button icon={<UploadOutlined />} style={{ flex: 1 }}>
                            Выбрать файл .cfe
                        </Button>
                    </Upload>
                    <Button
                        type="primary"
                        onClick={handleUpload}
                        loading={uploading}
                        disabled={fileList.length === 0}
                    >
                        Загрузить
                    </Button>
                </Space.Compact>
            </Form.Item>

            {value && (
                <div style={{ fontSize: 12, color: '#666' }}>
                    Выбрано: <strong>{value.name}.cfe</strong>
                </div>
            )}
        </Space>
    );
};

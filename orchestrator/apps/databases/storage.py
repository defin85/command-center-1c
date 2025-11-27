"""
Extension Storage Service.
Управление файлами расширений (.cfe) на сервере.
"""

from pathlib import Path
from typing import List, Dict, Any
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

import logging

logger = logging.getLogger(__name__)


class ExtensionStorageService:
    """Сервис для работы с хранилищем расширений."""
    
    @staticmethod
    def get_storage_path() -> Path:
        """Получить путь к директории хранилища."""
        storage_path = getattr(settings, 'EXTENSION_STORAGE_PATH', None)
        if not storage_path:
            # Default path
            storage_path = Path(settings.BASE_DIR).parent / 'storage' / 'extensions'
        else:
            storage_path = Path(storage_path)
        
        # Создать директорию если не существует
        storage_path.mkdir(parents=True, exist_ok=True)
        
        return storage_path
    
    @classmethod
    def list_extensions(cls) -> List[Dict[str, Any]]:
        """
        Получить список всех файлов расширений в хранилище.
        
        Returns:
            List of dicts with file info: name, size, modified_at, path
        """
        storage_path = cls.get_storage_path()
        extensions = []
        
        try:
            # Рекурсивный поиск .cfe файлов
            for file_path in storage_path.rglob('*.cfe'):
                if file_path.is_file():
                    stat = file_path.stat()
                    extensions.append({
                        'name': file_path.name,
                        'size': stat.st_size,
                        'modified_at': stat.st_mtime,
                        'path': str(file_path),
                    })
            
            # Сортировать по дате изменения (новые сначала)
            extensions.sort(key=lambda x: x['modified_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list extensions: {e}")
        
        return extensions
    
    @classmethod
    def save_extension(cls, file: UploadedFile, filename: str = None) -> Dict[str, Any]:
        """
        Сохранить загруженный файл расширения.
        
        Args:
            file: Uploaded file object
            filename: Optional custom filename (will use original if not provided)
            
        Returns:
            Dict with file info: name, size, path
        """
        storage_path = cls.get_storage_path()
        
        # Использовать оригинальное имя если не указано
        if not filename:
            filename = file.name
        
        # Убедиться что расширение .cfe
        if not filename.lower().endswith('.cfe'):
            raise ValueError("File must have .cfe extension")
        
        # Sanitize filename (удалить опасные символы)
        filename = Path(filename).name  # Убрать path traversal
        
        dest_path = storage_path / filename
        
        # Сохранить файл
        with open(dest_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        stat = dest_path.stat()
        
        logger.info(f"Saved extension file: {filename} ({stat.st_size} bytes)")
        
        return {
            'name': filename,
            'size': stat.st_size,
            'path': str(dest_path),
        }
    
    @classmethod
    def delete_extension(cls, filename: str) -> bool:
        """
        Удалить файл расширения из хранилища.
        
        Args:
            filename: Name of file to delete
            
        Returns:
            True if deleted, False if not found
        """
        storage_path = cls.get_storage_path()
        
        # Sanitize filename
        filename = Path(filename).name
        
        file_path = storage_path / filename
        
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted extension file: {filename}")
            return True
        else:
            logger.warning(f"Extension file not found: {filename}")
            return False
    
    @classmethod
    def get_extension_path(cls, filename: str) -> str:
        """
        Получить полный путь к файлу расширения.
        
        Args:
            filename: Name of extension file
            
        Returns:
            Full path to file
            
        Raises:
            FileNotFoundError if file doesn't exist
        """
        storage_path = cls.get_storage_path()
        
        # Sanitize filename
        filename = Path(filename).name
        
        file_path = storage_path / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Extension file not found: {filename}")
        
        return str(file_path)

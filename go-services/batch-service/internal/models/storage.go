package models

import "time"

// StoredExtension представляет метаданные сохраненного .cfe файла расширения
type StoredExtension struct {
	FileName      string    `json:"file_name"`       // Имя файла (например, ODataAutoConfig_v1.0.5.cfe)
	ExtensionName string    `json:"extension_name"`  // Имя расширения (например, ODataAutoConfig)
	Version       string    `json:"version"`         // Semantic version (например, 1.0.5)
	Author        string    `json:"author,omitempty"` // Автор загрузки (опционально)
	SizeBytes     int64     `json:"size_bytes"`      // Размер файла в байтах
	ChecksumMD5   string    `json:"checksum_md5"`    // MD5 checksum для целостности
	UploadedAt    time.Time `json:"uploaded_at"`     // Дата и время загрузки
	FilePath      string    `json:"file_path"`       // Полный путь к файлу в storage
}

// StorageListResponse представляет ответ со списком расширений в storage
type StorageListResponse struct {
	Extensions []StoredExtension `json:"extensions"` // Список расширений
	TotalCount int               `json:"total_count"` // Общее количество
}

// UploadResponse представляет ответ при успешной загрузке файла
type UploadResponse struct {
	Success     bool      `json:"success"`       // Статус операции
	FileName    string    `json:"file_name"`     // Имя загруженного файла
	Path        string    `json:"path"`          // Путь к файлу в storage
	SizeBytes   int64     `json:"size_bytes"`    // Размер файла
	ChecksumMD5 string    `json:"checksum_md5"`  // MD5 checksum
	UploadedAt  time.Time `json:"uploaded_at"`   // Время загрузки
}

// DeleteResponse представляет ответ при удалении файла
type DeleteResponse struct {
	Success     bool   `json:"success"`       // Статус операции
	Message     string `json:"message"`       // Сообщение об успехе
	DeletedFile string `json:"deleted_file"`  // Имя удаленного файла
}

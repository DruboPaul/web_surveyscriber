import { useState, useRef } from "react";

export default function ImageUploader({ onBatchReady }) {
    const [files, setFiles] = useState([]);
    const [previews, setPreviews] = useState([]);
    const [isDragging, setIsDragging] = useState(false);
    const [uploadMode, setUploadMode] = useState("files"); // "files" or "folder"
    const fileInputRef = useRef(null);
    const folderInputRef = useRef(null);

    const handleFiles = (selectedFiles) => {
        console.log("📂 Selected raw files:", selectedFiles);

        // Accept all common image formats
        const imageExtensions = [
            '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif',
            '.tiff', '.tif', '.jfif', '.heic', '.heif',
            '.ico', '.svg', '.avif', '.raw', '.cr2', '.nef', '.arw',
            '.dng', '.orf', '.rw2', '.pef', '.srw', '.pgm', '.ppm', '.pbm'
        ];

        const fileArray = Array.from(selectedFiles).filter(file => {
            // Check by extension
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            const hasImageExtension = imageExtensions.includes(ext);

            // Also check by MIME type as fallback
            const hasImageMimeType = file.type && file.type.startsWith('image/');

            const isImage = hasImageExtension || hasImageMimeType;
            if (!isImage) console.warn(`⚠️ Skipped non-image: ${file.name} (type: ${file.type})`);
            return isImage;
        });

        console.log("✅ Valid images:", fileArray);

        setFiles(fileArray);

        // Generate previews
        const previewUrls = fileArray.map(file => URL.createObjectURL(file));
        setPreviews(previewUrls);

        onBatchReady(fileArray);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        // Get files from dataTransfer
        const droppedFiles = e.dataTransfer?.files;
        if (droppedFiles && droppedFiles.length > 0) {
            console.log('📥 Files dropped:', droppedFiles.length);
            handleFiles(droppedFiles);
        } else {
            console.warn('⚠️ No files in drop event');
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    const handleDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const removeFile = (index) => {
        const newFiles = files.filter((_, i) => i !== index);
        const newPreviews = previews.filter((_, i) => i !== index);
        setFiles(newFiles);
        setPreviews(newPreviews);
        onBatchReady(newFiles);
    };

    const handleUploadClick = () => {
        if (uploadMode === "folder") {
            folderInputRef.current?.click();
        } else {
            fileInputRef.current?.click();
        }
    };

    return (
        <div className="image-uploader">
            {/* Upload Mode Toggle */}
            <div className="upload-mode-toggle">
                <button
                    className={`mode-btn ${uploadMode === 'files' ? 'active' : ''}`}
                    onClick={() => setUploadMode('files')}
                >
                    📄 Upload Files
                </button>
                <button
                    className={`mode-btn ${uploadMode === 'folder' ? 'active' : ''}`}
                    onClick={() => setUploadMode('folder')}
                >
                    📁 Upload Folder
                </button>
            </div>

            <div
                className={`drop-zone ${isDragging ? 'dragging' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onClick={handleUploadClick}
            >
                <div className="drop-content">
                    <span className="upload-icon">{uploadMode === 'folder' ? '📁' : '📷'}</span>
                    <p>
                        {uploadMode === 'folder'
                            ? 'Click to select a folder with survey images'
                            : 'Drag & drop survey images here'}
                    </p>
                    <p className="hint">or click to browse</p>
                    <p className="formats">Supports: All image formats (JPG, PNG, GIF, WebP, TIFF, etc.)</p>
                </div>
                {/* Regular file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={(e) => handleFiles(e.target.files)}
                    style={{ display: 'none' }}
                />
                {/* Folder input */}
                <input
                    ref={folderInputRef}
                    type="file"
                    webkitdirectory=""
                    mozdirectory=""
                    directory=""
                    multiple
                    onChange={(e) => handleFiles(e.target.files)}
                    style={{ display: 'none' }}
                />
            </div>

            {previews.length > 0 && (
                <div className="preview-grid">
                    {previews.map((url, i) => (
                        <div key={i} className="preview-item">
                            <img src={url} alt={`Preview ${i + 1}`} />
                            <button
                                className="remove-preview"
                                onClick={() => removeFile(i)}
                            >
                                ✕
                            </button>
                            <span className="file-name">{files[i]?.name}</span>
                        </div>
                    ))}
                </div>
            )}

            {files.length > 0 && (
                <>
                    <div className="file-count">
                        {files.length} image{files.length > 1 ? 's' : ''} selected
                    </div>
                    <button
                        className="clear-all-btn"
                        onClick={() => {
                            setFiles([]);
                            setPreviews([]);
                            onBatchReady([]);
                        }}
                    >
                        🗑️ Clear All
                    </button>
                </>
            )}
        </div>
    );
}

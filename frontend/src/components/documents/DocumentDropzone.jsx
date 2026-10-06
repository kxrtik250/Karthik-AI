import { useState, useRef } from "react";
import Spinner from "../common/Spinner";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".md"];
const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB

export default function DocumentDropzone({ onUpload, isUploading = false }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const fileInputRef = useRef(null);

  function validateFile(file) {
    if (!file) return false;

    const lowerName = file.name.toLowerCase();
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!hasValidExt) {
      setValidationError(
        `Unsupported file type. Please upload a PDF, DOCX, PPTX, TXT, or MD file.`
      );
      return false;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      setValidationError(
        `File size (${sizeMb} MB) exceeds maximum allowed limit of 25 MB.`
      );
      return false;
    }

    setValidationError(null);
    return true;
  }

  function handleFileSelected(file) {
    if (validateFile(file)) {
      onUpload(file);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragOver(false);

    if (isUploading) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  }

  function handleDragOver(e) {
    e.preventDefault();
    if (!isUploading) {
      setIsDragOver(true);
    }
  }

  function handleDragLeave(e) {
    e.preventDefault();
    setIsDragOver(false);
  }

  return (
    <div className="dropzone-container">
      <div
        className={`dropzone-box ${isDragOver ? "dropzone-active" : ""} ${
          isUploading ? "dropzone-uploading" : ""
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !isUploading) {
            fileInputRef.current?.click();
          }
        }}
        aria-label="Upload document dropzone"
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden-file-input"
          accept=".pdf,.docx,.pptx,.txt,.md"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFileSelected(e.target.files[0]);
              e.target.value = ""; // reset for re-uploading same filename
            }
          }}
          disabled={isUploading}
        />

        <div className="dropzone-content">
          {isUploading ? (
            <div className="dropzone-upload-state">
              <Spinner size="lg" label="Uploading document..." />
              <p className="dropzone-prompt">Uploading & calculating checksum...</p>
            </div>
          ) : (
            <>
              <div className="dropzone-icon" aria-hidden="true">
                📁
              </div>
              <p className="dropzone-prompt">
                <strong>Click to browse</strong> or drag & drop documents here
              </p>
              <p className="dropzone-hint">
                Supported: PDF, DOCX, PPTX, TXT, Markdown (Max 25 MB)
              </p>
            </>
          )}
        </div>
      </div>

      {validationError && (
        <div className="validation-error-banner" role="alert">
          <span>⚠️ {validationError}</span>
          <button
            type="button"
            className="error-dismiss-btn"
            onClick={() => setValidationError(null)}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}

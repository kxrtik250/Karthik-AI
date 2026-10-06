import DocumentDropzone from "./DocumentDropzone";
import DocumentTable from "./DocumentTable";
import Spinner from "../common/Spinner";

export default function DocumentsView({
  documents,
  isLoading,
  isUploading,
  uploadError,
  onUpload,
  onDelete,
  isDeletingId,
  onClearError,
}) {
  const completedDocs = documents.filter((d) => d.status === "completed");
  const totalChunks = documents.reduce((sum, d) => sum + (d.total_chunks || 0), 0);

  return (
    <div className="documents-view">
      <div className="view-header">
        <div>
          <h2 className="view-title">Knowledge Documents</h2>
          <p className="view-subtitle">
            Upload PDFs, DOCX, PPTX, or text files to ingest into pgvector for AI semantic search.
          </p>
        </div>

        <div className="doc-stats">
          <div className="stat-pill">
            <span className="stat-num">{completedDocs.length}</span>
            <span className="stat-label">Indexed Documents</span>
          </div>
          <div className="stat-pill">
            <span className="stat-num">{totalChunks}</span>
            <span className="stat-label">Vector Chunks</span>
          </div>
        </div>
      </div>

      {uploadError && (
        <div className="error-banner" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <span className="error-text">{uploadError}</span>
          {onClearError && (
            <button
              type="button"
              className="error-dismiss-btn"
              onClick={onClearError}
              aria-label="Dismiss error"
            >
              ✕
            </button>
          )}
        </div>
      )}

      <div className="documents-section">
        <DocumentDropzone onUpload={onUpload} isUploading={isUploading} />
      </div>

      <div className="documents-section">
        <div className="section-title-row">
          <h3 className="section-title">Uploaded Files ({documents.length})</h3>
          {isLoading && <Spinner size="sm" label="Refreshing documents..." />}
        </div>

        <DocumentTable
          documents={documents}
          onDelete={onDelete}
          isDeletingId={isDeletingId}
        />
      </div>
    </div>
  );
}

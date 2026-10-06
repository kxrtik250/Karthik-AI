import { useState } from "react";
import Badge from "../common/Badge";
import Spinner from "../common/Spinner";
import EmptyState from "../common/EmptyState";

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function DocumentTable({ documents, onDelete, isDeletingId }) {
  const [docToDelete, setDocToDelete] = useState(null);

  if (!documents || documents.length === 0) {
    return (
      <EmptyState
        icon="📄"
        title="No documents uploaded yet"
        description="Upload resumes, project notes, or syllabus presentations to power your AI assistant's memory."
      />
    );
  }

  function handleConfirmDelete() {
    if (docToDelete) {
      onDelete(docToDelete.id);
      setDocToDelete(null);
    }
  }

  return (
    <div className="doc-table-container">
      <div className="table-wrapper">
        <table className="doc-table">
          <thead>
            <tr>
              <th scope="col">File Name</th>
              <th scope="col">Type</th>
              <th scope="col">Size</th>
              <th scope="col">Pages / Chunks</th>
              <th scope="col">Status</th>
              <th scope="col">Uploaded</th>
              <th scope="col" className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const isDeleting = isDeletingId === doc.id;
              const isProcessing = doc.status === "processing" || doc.status === "pending";

              return (
                <tr key={doc.id} className="doc-row">
                  <td className="doc-name-cell">
                    <span className="doc-icon" aria-hidden="true">
                      {doc.file_type === "pdf" ? "📕" : doc.file_type === "pptx" ? "📊" : "📄"}
                    </span>
                    <span className="doc-filename" title={doc.original_filename}>
                      {doc.original_filename}
                    </span>
                  </td>

                  <td>
                    <span className="type-tag">{doc.file_type.toUpperCase()}</span>
                  </td>

                  <td className="text-muted">{formatBytes(doc.file_size)}</td>

                  <td>
                    <span className="meta-pages">
                      {doc.total_pages ? `${doc.total_pages} pg` : "—"}
                    </span>
                    <span className="meta-chunks text-muted">
                      {" "}({doc.total_chunks || 0} chunks)
                    </span>
                  </td>

                  <td>
                    {isProcessing ? (
                      <span className="status-pill status-processing">
                        <Spinner size="xs" label="Processing..." />
                        Processing...
                      </span>
                    ) : doc.status === "completed" ? (
                      <span className="status-pill status-completed">
                        ✓ Ready
                      </span>
                    ) : (
                      <span
                        className="status-pill status-failed"
                        title={doc.error_message || "Processing failed"}
                      >
                        ✕ Failed
                      </span>
                    )}
                    {doc.error_message && (
                      <p className="doc-error-hint" title={doc.error_message}>
                        {doc.error_message.slice(0, 50)}...
                      </p>
                    )}
                  </td>

                  <td className="text-muted text-sm">
                    {new Date(doc.created_at).toLocaleDateString([], {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </td>

                  <td className="text-right">
                    <button
                      type="button"
                      className="btn-icon-danger"
                      onClick={() => setDocToDelete(doc)}
                      disabled={isDeleting}
                      title="Delete document"
                      aria-label={`Delete ${doc.original_filename}`}
                    >
                      {isDeleting ? <Spinner size="xs" label="Deleting..." /> : "🗑️"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {docToDelete && (
        <div className="modal-backdrop" onClick={() => setDocToDelete(null)}>
          <div
            className="modal-content delete-confirm-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3 className="modal-title">Delete Document?</h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setDocToDelete(null)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete <strong>{docToDelete.original_filename}</strong>?
              </p>
              <p className="delete-modal-warning">
                This will permanently delete the file and all indexed pgvector chunks.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDocToDelete(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDelete}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

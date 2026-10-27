import { useEffect } from "react";

export default function CitationModal({ citation, onClose }) {
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!citation) return null;

  const hasScore =
    typeof citation.similarity_score === "number" &&
    Number.isFinite(citation.similarity_score) &&
    citation.similarity_score > 0;
  const scorePct = hasScore ? Math.round(citation.similarity_score * 100) : null;

  const hasValidPage =
    citation.page_number !== null &&
    citation.page_number !== undefined &&
    typeof citation.page_number === "number" &&
    citation.page_number > 0;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-group">
            <span className="source-tag">Source {citation.source_index}</span>
            <h3 id="citation-title" className="modal-title">
              {citation.filename}
            </h3>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close details"
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="citation-meta-grid">
            <div className="meta-item">
              <span className="meta-label">Location:</span>
              <span className="meta-value">
                {hasValidPage
                  ? `Page / Slide ${citation.page_number}`
                  : "Entire document / Section"}
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Relevance Match:</span>
              <span className="meta-value score-highlight">
                {scorePct !== null ? `${scorePct}%` : "Document Reference"}
              </span>
            </div>
            <div className="meta-item">
              <span className="meta-label">Document ID:</span>
              <span className="meta-value mono-id">{citation.document_id}</span>
            </div>
          </div>

          <div className="citation-snippet-section">
            <h4 className="snippet-heading">Retrieved Passage Snippet</h4>
            <div className="snippet-box">
              <p>{citation.snippet}</p>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

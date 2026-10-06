export default function CitationTray({ citations, onSelectCitation }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="citation-tray">
      <span className="citation-tray-label">Referenced Sources:</span>
      <div className="citation-chips">
        {citations.map((cite, idx) => {
          const score = Math.round(cite.similarity_score * 100);
          const location = cite.page_number ? `p. ${cite.page_number}` : null;

          return (
            <button
              key={cite.document_id + "-" + (cite.chunk_index ?? idx)}
              type="button"
              className="citation-chip"
              onClick={() => onSelectCitation(cite)}
              title={`Click to view snippet from ${cite.filename}`}
            >
              <span className="chip-icon" aria-hidden="true">📄</span>
              <span className="chip-name">{cite.filename}</span>
              {location && <span className="chip-page">{location}</span>}
              <span className="chip-score">{score}%</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

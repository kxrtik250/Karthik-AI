export default function PreparationModal({ plan, onClose }) {
  if (!plan) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">
              Interview Preparation Plan: {plan.company_name}
            </h2>
            <p className="modal-subtitle">Role: {plan.role}</p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close preparation modal"
          >
            ✕
          </button>
        </div>

        <div className="modal-body prep-modal-body">
          {/* Quick Highlights Bar */}
          <div className="prep-highlights-bar">
            {plan.selection_process && plan.selection_process.length > 0 && (
              <div className="prep-highlight-item">
                <span className="prep-hl-label">Selection Rounds:</span>
                <div className="chips-wrap">
                  {plan.selection_process.map((r, idx) => (
                    <span key={idx} className="chip chip-info chip-xs">
                      {idx + 1}. {r}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {plan.key_skills_to_prepare && plan.key_skills_to_prepare.length > 0 && (
              <div className="prep-highlight-item">
                <span className="prep-hl-label">Skills to Revise:</span>
                <div className="chips-wrap">
                  {plan.key_skills_to_prepare.map((s, idx) => (
                    <span key={idx} className="chip chip-danger chip-xs">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {plan.matching_projects && plan.matching_projects.length > 0 && (
              <div className="prep-highlight-item">
                <span className="prep-hl-label">Highlight Projects:</span>
                <div className="chips-wrap">
                  {plan.matching_projects.map((p, idx) => (
                    <span key={idx} className="chip chip-success chip-xs">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Detailed Roadmap */}
          <div className="prep-strategy-content">
            <h3 className="prep-strategy-heading">Comprehensive Preparation Roadmap</h3>
            <div className="prep-text-box">
              <pre className="prep-pre-text">{plan.preparation_advice}</pre>
            </div>
          </div>

          {/* Document Sources Used */}
          {plan.relevant_document_sources && plan.relevant_document_sources.length > 0 && (
            <div className="prep-sources-footer">
              <span className="prep-sources-label">Grounded in uploaded documents:</span>
              <span className="prep-sources-list">
                {plan.relevant_document_sources.join(", ")}
              </span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

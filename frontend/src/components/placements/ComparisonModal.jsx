export default function ComparisonModal({ comparison, onClose }) {
  if (!comparison) return null;

  const { drive, eligibility, skill_match, matching_projects, matching_certifications } = comparison;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">
              Profile Comparison: {drive.company?.name || "Company"}
            </h2>
            <p className="modal-subtitle">Role: {drive.role}</p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close comparison modal"
          >
            ✕
          </button>
        </div>

        <div className="modal-body comparison-modal-body">
          {/* Eligibility Section */}
          <div className="comparison-section">
            <div className="comparison-section-header">
              <h3>Eligibility Assessment</h3>
              <span
                className={`badge ${
                  eligibility.status === "ELIGIBLE"
                    ? "badge-success"
                    : eligibility.status === "NOT_ELIGIBLE"
                    ? "badge-danger"
                    : "badge-warning"
                }`}
              >
                {eligibility.status}
              </span>
            </div>

            <div className="criteria-table-container">
              <table className="criteria-table">
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th>Requirement</th>
                    <th>Your Profile</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {eligibility.criteria.map((c, idx) => (
                    <tr key={idx}>
                      <td className="criteria-name">
                        {c.criterion === "cgpa" && "CGPA"}
                        {c.criterion === "branch" && "Eligible Branches"}
                        {c.criterion === "graduation_year" && "Graduation Year"}
                        {c.criterion === "backlog" && "Backlog Policy"}
                        {c.criterion === "profile" && "Profile"}
                      </td>
                      <td>
                        {Array.isArray(c.required)
                          ? c.required.join(", ")
                          : c.required !== null && c.required !== undefined
                          ? String(c.required)
                          : "None"}
                      </td>
                      <td>
                        {c.actual !== null && c.actual !== undefined
                          ? String(c.actual)
                          : "Not recorded"}
                      </td>
                      <td>
                        <span
                          className={`status-pill ${
                            c.status === "eligible"
                              ? "pill-success"
                              : c.status === "not_eligible"
                              ? "pill-danger"
                              : c.status === "unknown"
                              ? "pill-warning"
                              : "pill-neutral"
                          }`}
                        >
                          {c.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Skill Matching Section */}
          <div className="comparison-section">
            <div className="comparison-section-header">
              <h3>Skill Match Breakdown</h3>
              <span className="badge badge-info">
                {skill_match.overall_match_percentage.toFixed(0)}% Overall Match
              </span>
            </div>

            <div className="skills-match-grid">
              <div className="skills-match-col">
                <h4 className="match-col-title match-success">
                  ✓ Matching Required ({skill_match.matching_required.length})
                </h4>
                <div className="chips-wrap">
                  {skill_match.matching_required.length === 0 ? (
                    <span className="empty-hint">None</span>
                  ) : (
                    skill_match.matching_required.map((s, idx) => (
                      <span key={idx} className="chip chip-success">
                        {s}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="skills-match-col">
                <h4 className="match-col-title match-danger">
                  ✕ Missing Required ({skill_match.missing_required.length})
                </h4>
                <div className="chips-wrap">
                  {skill_match.missing_required.length === 0 ? (
                    <span className="empty-hint">All required skills met!</span>
                  ) : (
                    skill_match.missing_required.map((s, idx) => (
                      <span key={idx} className="chip chip-danger">
                        {s}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>

            {(skill_match.matching_preferred.length > 0 ||
              skill_match.missing_preferred.length > 0) && (
              <div className="skills-match-grid" style={{ marginTop: "1rem" }}>
                <div className="skills-match-col">
                  <h4 className="match-col-title match-preferred">
                    ★ Matching Preferred ({skill_match.matching_preferred.length})
                  </h4>
                  <div className="chips-wrap">
                    {skill_match.matching_preferred.map((s, idx) => (
                      <span key={idx} className="chip chip-preferred">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="skills-match-col">
                  <h4 className="match-col-title match-muted">
                    Missing Preferred ({skill_match.missing_preferred.length})
                  </h4>
                  <div className="chips-wrap">
                    {skill_match.missing_preferred.map((s, idx) => (
                      <span key={idx} className="chip chip-muted">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Relevant Projects Section */}
          <div className="comparison-section">
            <h3>Relevant Portfolio Projects</h3>
            {matching_projects.length === 0 ? (
              <p className="empty-hint">No projects matching this drive's required technologies.</p>
            ) : (
              <div className="matching-projects-list">
                {matching_projects.map((p) => (
                  <div key={p.id} className="matching-project-card">
                    <div className="matching-project-header">
                      <span className="matching-project-name">{p.name}</span>
                      {p.role && <span className="matching-project-role">({p.role})</span>}
                    </div>
                    <div className="matching-tech-chips">
                      <span className="tech-label">Matched Tech:</span>
                      {p.matched_technologies.map((t, idx) => (
                        <span key={idx} className="chip chip-success chip-xs">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Relevant Certifications */}
          {matching_certifications.length > 0 && (
            <div className="comparison-section">
              <h3>Relevant Certifications</h3>
              <div className="matching-certs-list">
                {matching_certifications.map((c) => (
                  <div key={c.id} className="matching-cert-item">
                    <span className="cert-badge">🏅</span>
                    <span>
                      <strong>{c.name}</strong> by {c.issuer}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
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

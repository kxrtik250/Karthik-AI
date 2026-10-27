import { useState, useEffect } from "react";
import Spinner from "../common/Spinner";
import { optimizeResume } from "../../api/resume";

export default function ResumeStudioModal({ isOpen, onClose, drive = null }) {
  const [activeTab, setActiveTab] = useState("analysis"); // "analysis" | "bullets" | "preview" | "custom_input"
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // Custom JD input state
  const [targetRole, setTargetRole] = useState(drive?.role || "Software Engineer");
  const [customJdText, setCustomJdText] = useState("");
  const [copiedKey, setCopiedKey] = useState(null);

  const fetchOptimization = async (customRole = null, customText = null) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await optimizeResume({
        drive_id: drive?.id || null,
        target_role: customRole || drive?.role || targetRole || "Software Engineer",
        custom_jd_text: customText !== null ? customText : (drive ? null : customJdText),
      });
      setResult(data);
      setActiveTab("analysis");
    } catch (err) {
      setError(err.message || "Failed to analyze and optimize resume.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setCopiedKey(null);
      setTargetRole(drive?.role || "Software Engineer");
      setCustomJdText("");

      if (drive) {
        fetchOptimization(drive.role, null);
      } else {
        // Start on custom input mode if no drive selected
        setActiveTab("custom_input");
        setResult(null);
      }
    }
  }, [isOpen, drive]);

  if (!isOpen) return null;

  const companyTitle = drive?.company?.name || result?.company_name || "Target Placement";
  const roleTitle = drive?.role || result?.target_role || targetRole;

  const handleCopy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleDownloadMarkdown = () => {
    if (!result?.full_resume_markdown) return;
    const blob = new Blob([result.full_resume_markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Resume_${roleTitle.replace(/\s+/g, "_")}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-container modal-lg resume-studio-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h2 className="modal-title">📄 Resume Optimizer & ATS Studio</h2>
              {result && (
                <span className="badge badge-success">
                  {result.ats_analysis.ats_match_percentage}% ATS Match
                </span>
              )}
            </div>
            <p className="modal-subtitle">
              {companyTitle} — {roleTitle}
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close resume studio"
          >
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="placements-controls-bar" style={{ padding: "0.6rem 1.5rem" }}>
          <div className="tab-pill-group">
            <button
              type="button"
              className={`tab-pill ${activeTab === "analysis" ? "active" : ""}`}
              onClick={() => setActiveTab("analysis")}
              disabled={!result}
            >
              ★ ATS Keyword Match
            </button>
            <button
              type="button"
              className={`tab-pill ${activeTab === "bullets" ? "active" : ""}`}
              onClick={() => setActiveTab("bullets")}
              disabled={!result}
            >
              🛠️ Tailored Project Bullets
            </button>
            <button
              type="button"
              className={`tab-pill ${activeTab === "preview" ? "active" : ""}`}
              onClick={() => setActiveTab("preview")}
              disabled={!result}
            >
              📄 Full ATS Resume Preview
            </button>
            <button
              type="button"
              className={`tab-pill ${activeTab === "custom_input" ? "active" : ""}`}
              onClick={() => setActiveTab("custom_input")}
            >
              ⚙️ Custom Job Description
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body resume-modal-body">
          {error && (
            <div className="alert alert-danger" style={{ marginBottom: "1rem" }}>
              <span>{error}</span>
            </div>
          )}

          {isLoading ? (
            <div className="placements-loading-state" style={{ padding: "3rem" }}>
              <Spinner size="lg" />
              <p>Analyzing ATS keyword alignment and tailoring grounded project bullets...</p>
            </div>
          ) : (
            <>
              {/* TAB 1: Custom JD Input */}
              {activeTab === "custom_input" && (
                <div className="resume-custom-input-pane">
                  <p className="interview-intro-text">
                    Paste a job description or list of required skills below to evaluate your verified
                    profile against specific corporate or off-campus openings:
                  </p>
                  <div className="form-group" style={{ marginBottom: "1rem" }}>
                    <label className="form-label" style={{ fontWeight: 600 }}>
                      Target Role / Job Title:
                    </label>
                    <input
                      type="text"
                      className="input-search"
                      style={{ width: "100%" }}
                      placeholder="e.g. Full Stack Developer, Backend Systems Engineer"
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                    <label className="form-label" style={{ fontWeight: 600 }}>
                      Paste Job Description / Requirements:
                    </label>
                    <textarea
                      className="interview-answer-textarea"
                      rows={6}
                      placeholder="Paste JD text with required technical skills, responsibilities, or qualifications..."
                      value={customJdText}
                      onChange={(e) => setCustomJdText(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => fetchOptimization(targetRole, customJdText)}
                    disabled={isLoading}
                  >
                    Analyze & Generate ATS Resume →
                  </button>
                </div>
              )}

              {/* TAB 2: ATS Keyword Match & Gap Analysis */}
              {activeTab === "analysis" && result && (
                <div className="resume-analysis-pane">
                  {/* Score KPI Bar */}
                  <div className="eval-score-banner">
                    <div className="eval-score-circle">
                      <span className="eval-score-num">
                        {Math.round(result.ats_analysis.ats_match_percentage)}%
                      </span>
                      <span className="eval-score-den">MATCH</span>
                    </div>
                    <div>
                      <h3 className="eval-score-title">
                        {result.ats_analysis.ats_match_percentage >= 70
                          ? "High ATS Keyword Alignment"
                          : result.ats_analysis.ats_match_percentage >= 45
                          ? "Moderate Alignment — Good Technical Core"
                          : "Foundational Match — Focus on Transferable Skills"}
                      </h3>
                      <p className="eval-score-subtitle">
                        Matched against verified profile skills and documented project technologies.
                      </p>
                    </div>
                  </div>

                  {/* Keywords Comparison Grid */}
                  <div className="resume-keywords-grid">
                    <div className="eval-card eval-card-strengths">
                      <h4 className="eval-card-title">
                        ✓ Matched Technical Keywords ({result.ats_analysis.matched_skills.length})
                      </h4>
                      <div className="chips-wrap" style={{ marginTop: "0.5rem" }}>
                        {result.ats_analysis.matched_skills.map((s, idx) => (
                          <span key={idx} className="chip chip-success chip-xs">
                            ✓ {s}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="eval-card eval-card-improvements">
                      <h4 className="eval-card-title">
                        ⚡ Missing JD Keywords ({result.ats_analysis.missing_skills.length})
                      </h4>
                      <div className="chips-wrap" style={{ marginTop: "0.5rem" }}>
                        {result.ats_analysis.missing_skills.length > 0 ? (
                          result.ats_analysis.missing_skills.map((s, idx) => (
                            <span key={idx} className="chip chip-danger chip-xs">
                              {s}
                            </span>
                          ))
                        ) : (
                          <span style={{ fontSize: "0.82rem", color: "#6b7280" }}>
                            None! All required keywords present.
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Recommendations */}
                  <div className="eval-card" style={{ marginTop: "1rem" }}>
                    <h4 className="eval-card-title">🎯 Strategic Recommendations</h4>
                    <ul className="eval-bullet-list">
                      {result.ats_analysis.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* TAB 3: Tailored Project Bullets */}
              {activeTab === "bullets" && result && (
                <div className="resume-bullets-pane">
                  <div className="interview-grounding-notice" style={{ marginBottom: "1.25rem" }}>
                    <span className="notice-icon">🛡️</span>
                    <span>
                      <strong>Strict Project Grounding:</strong> These bullet points are engineered
                      strictly around your verified technologies (Python, SQL, JS, Git) and documented
                      features without inventing unbuilt functionality.
                    </span>
                  </div>

                  {result.tailored_projects.map((tp, idx) => {
                    const bulletsText = tp.bullet_points.map((b) => `• ${b}`).join("\n");
                    const isCopied = copiedKey === `proj_${idx}`;
                    return (
                      <div key={idx} className="tailored-project-card">
                        <div className="tailored-project-header">
                          <div>
                            <h3 className="tailored-project-title">
                              {tp.project_name} —{" "}
                              <span style={{ fontWeight: 400, color: "#6b7280" }}>{tp.role}</span>
                            </h3>
                            <div className="chips-wrap" style={{ marginTop: "0.25rem" }}>
                              {tp.technologies_used.map((t, i) => (
                                <span key={i} className="skill-chip">
                                  {t}
                                </span>
                              ))}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleCopy(bulletsText, `proj_${idx}`)}
                          >
                            {isCopied ? "✓ Copied!" : "📋 Copy Bullets"}
                          </button>
                        </div>

                        <ul className="tailored-bullets-list">
                          {tp.bullet_points.map((b, bIdx) => (
                            <li key={bIdx}>{b}</li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* TAB 4: Full ATS Resume Preview */}
              {activeTab === "preview" && result && (
                <div className="resume-preview-pane">
                  <div className="resume-preview-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleCopy(result.full_resume_markdown, "full_resume")}
                    >
                      {copiedKey === "full_resume" ? "✓ Copied to Clipboard!" : "📋 Copy Markdown"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleDownloadMarkdown}
                    >
                      ⬇ Download .md Resume
                    </button>
                  </div>
                  <pre className="resume-markdown-box">
                    {result.full_resume_markdown}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

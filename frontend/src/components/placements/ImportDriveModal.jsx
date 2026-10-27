import { useState } from "react";
import Spinner from "../common/Spinner";
import {
  extractPlacementFromText,
  extractPlacementFromDocument,
  extractAndCreatePlacement,
} from "../../api/placements";

export default function ImportDriveModal({
  isOpen,
  onClose,
  documents = [],
  onSaved,
}) {
  const [sourceMode, setSourceMode] = useState("document"); // "document" | "text"
  const [selectedDocId, setSelectedDocId] = useState("");
  const [rawText, setRawText] = useState("");
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [extractError, setExtractError] = useState(null);
  const [extractedData, setExtractedData] = useState(null);

  if (!isOpen) return null;

  const completedDocs = documents.filter((d) => d.status === "completed");

  const handleExtract = async () => {
    setExtractError(null);
    setIsExtracting(true);

    try {
      let data = null;
      if (sourceMode === "document") {
        if (!selectedDocId) {
          throw new Error("Please select an uploaded document from the list.");
        }
        data = await extractPlacementFromDocument(selectedDocId);
      } else {
        if (!rawText.trim() || rawText.trim().length < 10) {
          throw new Error("Please paste at least 10 characters of circular / JD text.");
        }
        data = await extractPlacementFromText(rawText.trim(), "Pasted Notice");
      }

      // Convert lists to comma-separated strings for easy editing in form inputs
      setExtractedData({
        ...data,
        eligible_branches_str: (data.eligible_branches || []).join(", "),
        required_skills_str: (data.required_skills || []).join(", "),
        preferred_skills_str: (data.preferred_skills || []).join(", "),
        selection_process_str: (data.selection_process || []).join(" → "),
      });
    } catch (err) {
      console.error("Extraction error:", err);
      setExtractError(err.message || "Failed to extract placement drive details.");
    } finally {
      setIsExtracting(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!extractedData) return;

    setIsSaving(true);
    setExtractError(null);

    try {
      // Re-format strings back into arrays
      const branches = extractedData.eligible_branches_str
        ? extractedData.eligible_branches_str
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : null;

      const reqSkills = extractedData.required_skills_str
        ? extractedData.required_skills_str
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : null;

      const prefSkills = extractedData.preferred_skills_str
        ? extractedData.preferred_skills_str
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : null;

      const rounds = extractedData.selection_process_str
        ? extractedData.selection_process_str
            .split(/→|,/)
            .map((s) => s.trim())
            .filter(Boolean)
        : null;

      const drivePayload = {
        company_name: extractedData.company_name.trim(),
        role: extractedData.role.trim(),
        status: extractedData.status || "interested",
        deadline: extractedData.deadline || null,
        compensation: extractedData.compensation || null,
        employment_type: extractedData.employment_type || null,
        location: extractedData.location || null,
        notes: extractedData.notes || null,
        min_cgpa: extractedData.min_cgpa ? parseFloat(extractedData.min_cgpa) : null,
        eligible_branches: branches,
        graduation_year: extractedData.graduation_year ? parseInt(extractedData.graduation_year, 10) : null,
        required_skills: reqSkills,
        preferred_skills: prefSkills,
        backlog_allowed: Boolean(extractedData.backlog_allowed),
        selection_process: rounds,
        tier: extractedData.tier || null,
        source_document_id: extractedData.source_document_id || null,
        source_filename: extractedData.source_filename || null,
      };

      await extractAndCreatePlacement(drivePayload, true);
      if (onSaved) onSaved();
      onClose();
    } catch (err) {
      console.error("Save extracted drive error:", err);
      setExtractError(err.message || "Failed to save placement drive.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setExtractedData(null);
    setExtractError(null);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-container modal-lg import-drive-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "780px" }}
      >
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Import Placement Drive from Circular / JD</h2>
            <p className="modal-subtitle">
              Automatically extract company criteria, eligibility, skills, and rounds from documents.
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {extractError && (
            <div className="alert alert-danger" style={{ marginBottom: "1rem" }}>
              <span>{extractError}</span>
            </div>
          )}

          {!extractedData ? (
            /* STEP 1: Select Source & Extract */
            <div className="import-source-container">
              <div className="tab-pill-group" style={{ marginBottom: "1.25rem" }}>
                <button
                  type="button"
                  className={`tab-pill ${sourceMode === "document" ? "active" : ""}`}
                  onClick={() => setSourceMode("document")}
                >
                  📄 From Knowledge Documents ({completedDocs.length})
                </button>
                <button
                  type="button"
                  className={`tab-pill ${sourceMode === "text" ? "active" : ""}`}
                  onClick={() => setSourceMode("text")}
                >
                  ✍ Paste Circular / JD Text
                </button>
              </div>

              {sourceMode === "document" ? (
                <div className="form-group" style={{ marginBottom: "1.5rem" }}>
                  <label htmlFor="doc-select" className="form-label" style={{ fontWeight: 600 }}>
                    Select an Uploaded Document:
                  </label>
                  {completedDocs.length === 0 ? (
                    <p className="text-muted" style={{ fontSize: "0.9rem" }}>
                      No completed documents found in Knowledge Documents. You can upload one in the Documents tab or paste the text below.
                    </p>
                  ) : (
                    <select
                      id="doc-select"
                      className="form-control"
                      value={selectedDocId}
                      onChange={(e) => setSelectedDocId(e.target.value)}
                    >
                      <option value="">-- Choose a document --</option>
                      {completedDocs.map((doc) => (
                        <option key={doc.id} value={doc.id}>
                          {doc.original_filename} ({doc.total_pages || 1} pages, {doc.total_chunks || 0} chunks)
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              ) : (
                <div className="form-group" style={{ marginBottom: "1.5rem" }}>
                  <label htmlFor="raw-text" className="form-label" style={{ fontWeight: 600 }}>
                    Paste Placement Notice / Circular / JD Content:
                  </label>
                  <textarea
                    id="raw-text"
                    className="form-control"
                    rows={8}
                    placeholder="Paste email circular, campus recruitment notice, or job description details here..."
                    value={rawText}
                    onChange={(e) => setRawText(e.target.value)}
                  />
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onClose}
                  disabled={isExtracting}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleExtract}
                  disabled={isExtracting || (sourceMode === "document" && !selectedDocId) || (sourceMode === "text" && !rawText.trim())}
                >
                  {isExtracting ? (
                    <>
                      <Spinner size="sm" /> Analyzing & Extracting...
                    </>
                  ) : (
                    "⚡ Extract Drive Details"
                  )}
                </button>
              </div>
            </div>
          ) : (
            /* STEP 2: Review and Save Form */
            <form onSubmit={handleSave} className="import-review-form">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "var(--color-bg-secondary, #f8fafc)",
                  padding: "0.75rem 1rem",
                  borderRadius: "6px",
                  marginBottom: "1.25rem",
                }}
              >
                <div>
                  <span style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #64748b)" }}>
                    Source: {extractedData.source_filename || "Pasted Notice"}
                  </span>
                  <span
                    className="badge badge-success"
                    style={{ marginLeft: "0.75rem", fontSize: "0.75rem" }}
                  >
                    Confidence: {Math.round((extractedData.confidence_score || 1) * 100)}%
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-outline-secondary btn-sm"
                  onClick={handleReset}
                >
                  ← Re-extract
                </button>
              </div>

              <div className="grid-2-col" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Company Name *</label>
                  <input
                    type="text"
                    required
                    className="form-control"
                    value={extractedData.company_name}
                    onChange={(e) => setExtractedData({ ...extractedData, company_name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Job Role / Designation *</label>
                  <input
                    type="text"
                    required
                    className="form-control"
                    value={extractedData.role}
                    onChange={(e) => setExtractedData({ ...extractedData, role: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Minimum CGPA Cutoff</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="10"
                    className="form-control"
                    value={extractedData.min_cgpa ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, min_cgpa: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Graduating Batch Year</label>
                  <input
                    type="number"
                    min="2020"
                    max="2035"
                    className="form-control"
                    value={extractedData.graduation_year ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, graduation_year: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Eligible Branches</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. CSE, IT, ECE"
                    value={extractedData.eligible_branches_str ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, eligible_branches_str: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Package / CTC</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. 5.5 LPA"
                    value={extractedData.compensation ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, compensation: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Work Location</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. Noida / Bangalore"
                    value={extractedData.location ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, location: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Employment Type</label>
                  <select
                    className="form-control"
                    value={extractedData.employment_type ?? "Full-Time"}
                    onChange={(e) => setExtractedData({ ...extractedData, employment_type: e.target.value })}
                  >
                    <option value="Full-Time">Full-Time</option>
                    <option value="Internship">Internship</option>
                    <option value="Internship + FTE">Internship + FTE</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Application Deadline</label>
                  <input
                    type="date"
                    className="form-control"
                    value={extractedData.deadline ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, deadline: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600 }}>Tier Category</label>
                  <select
                    className="form-control"
                    value={extractedData.tier ?? ""}
                    onChange={(e) => setExtractedData({ ...extractedData, tier: e.target.value })}
                  >
                    <option value="">-- Unspecified --</option>
                    <option value="Super Dream">Super Dream</option>
                    <option value="Dream">Dream</option>
                    <option value="Regular">Regular</option>
                  </select>
                </div>
              </div>

              <div className="form-group" style={{ marginTop: "1rem" }}>
                <label className="form-label" style={{ fontWeight: 600 }}>Required Skills</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Python, SQL, Data Structures"
                  value={extractedData.required_skills_str ?? ""}
                  onChange={(e) => setExtractedData({ ...extractedData, required_skills_str: e.target.value })}
                />
              </div>

              <div className="form-group" style={{ marginTop: "1rem" }}>
                <label className="form-label" style={{ fontWeight: 600 }}>Preferred Skills</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Docker, Git, Cloud"
                  value={extractedData.preferred_skills_str ?? ""}
                  onChange={(e) => setExtractedData({ ...extractedData, preferred_skills_str: e.target.value })}
                />
              </div>

              <div className="form-group" style={{ marginTop: "1rem" }}>
                <label className="form-label" style={{ fontWeight: 600 }}>Selection Rounds</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Online Assessment → Technical Interview → HR Interview"
                  value={extractedData.selection_process_str ?? ""}
                  onChange={(e) => setExtractedData({ ...extractedData, selection_process_str: e.target.value })}
                />
              </div>

              <div className="form-group" style={{ marginTop: "1rem" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={Boolean(extractedData.backlog_allowed)}
                    onChange={(e) => setExtractedData({ ...extractedData, backlog_allowed: e.target.checked })}
                  />
                  Standing Arrears / Backlogs Permitted
                </label>
              </div>

              <div className="modal-footer" style={{ marginTop: "1.5rem", display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onClose}
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSaving || !extractedData.company_name || !extractedData.role}
                >
                  {isSaving ? (
                    <>
                      <Spinner size="sm" /> Saving Drive...
                    </>
                  ) : (
                    "✓ Save to Placement Intelligence"
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

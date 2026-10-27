export default function PlacementCard({
  drive,
  priority,
  onCompare,
  onPrepare,
  onMockInterview,
  onTailorResume,
  isComparing,
  isPreparing,
}) {
  const companyName = drive.company?.name || priority?.company_name || "Unknown Company";
  const role = drive.role || priority?.role;
  const compensation = drive.compensation || priority?.compensation;
  const tier = drive.tier || priority?.tier;
  const deadline = drive.deadline || priority?.deadline;
  const daysLeft = priority?.days_until_deadline;
  const eligibilityStatus = priority?.eligibility_status || "UNKNOWN";
  const skillMatchPct = priority?.skill_match_percentage ?? 0;
  const priorityLevel = priority?.priority_level || "MEDIUM";
  const compositeScore = priority?.composite_score ?? 0;

  const getEligibilityBadgeClass = (status) => {
    switch (status) {
      case "ELIGIBLE":
        return "badge-success";
      case "NOT_ELIGIBLE":
        return "badge-danger";
      default:
        return "badge-warning";
    }
  };

  const getPriorityBadgeClass = (level) => {
    switch (level) {
      case "HIGH":
        return "badge-priority-high";
      case "MEDIUM":
        return "badge-priority-med";
      default:
        return "badge-priority-low";
    }
  };

  return (
    <div className="placement-card">
      <div className="placement-card-header">
        <div>
          <div className="placement-company-row">
            <h3 className="placement-company-name">{companyName}</h3>
            {tier && <span className="placement-tier-tag">{tier}</span>}
          </div>
          <p className="placement-role-title">{role}</p>
        </div>
        <div className="placement-badges-group">
          <span className={`badge ${getEligibilityBadgeClass(eligibilityStatus)}`}>
            {eligibilityStatus === "ELIGIBLE" && "✓ ELIGIBLE"}
            {eligibilityStatus === "NOT_ELIGIBLE" && "✕ NOT ELIGIBLE"}
            {eligibilityStatus === "UNKNOWN" && "? UNKNOWN"}
          </span>
          {priority && (
            <span className={`badge ${getPriorityBadgeClass(priorityLevel)}`}>
              {priorityLevel} PRIORITY ({compositeScore})
            </span>
          )}
        </div>
      </div>

      <div className="placement-meta-grid">
        {compensation && (
          <div className="placement-meta-item">
            <span className="placement-meta-label">Compensation:</span>
            <span className="placement-meta-val">{compensation}</span>
          </div>
        )}
        {drive.location && (
          <div className="placement-meta-item">
            <span className="placement-meta-label">Location:</span>
            <span className="placement-meta-val">{drive.location}</span>
          </div>
        )}
        {deadline && (
          <div className="placement-meta-item">
            <span className="placement-meta-label">Deadline:</span>
            <span className="placement-meta-val">
              {deadline} {daysLeft !== undefined && daysLeft !== null && `(${daysLeft}d left)`}
            </span>
          </div>
        )}
        {drive.min_cgpa && (
          <div className="placement-meta-item">
            <span className="placement-meta-label">Min CGPA:</span>
            <span className="placement-meta-val">{drive.min_cgpa}</span>
          </div>
        )}
      </div>

      {/* Skill Match Section */}
      <div className="placement-skill-match-section">
        <div className="placement-skill-match-header">
          <span className="placement-skill-match-title">Skill Match</span>
          <span className="placement-skill-match-pct">{skillMatchPct.toFixed(0)}%</span>
        </div>
        <div className="placement-progress-bar-bg">
          <div
            className="placement-progress-bar-fill"
            style={{ width: `${Math.min(100, Math.max(0, skillMatchPct))}%` }}
          />
        </div>
      </div>

      {/* Required Skills Chips */}
      {drive.required_skills && drive.required_skills.length > 0 && (
        <div className="placement-skills-chips-row">
          {drive.required_skills.slice(0, 4).map((skill, idx) => (
            <span key={idx} className="skill-chip">
              {skill}
            </span>
          ))}
          {drive.required_skills.length > 4 && (
            <span className="skill-chip skill-chip-more">
              +{drive.required_skills.length - 4} more
            </span>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div className="placement-card-actions">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onCompare(drive.id)}
          disabled={isComparing}
        >
          {isComparing ? "Comparing..." : "🔍 Compare"}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onPrepare(drive.id)}
          disabled={isPreparing}
        >
          {isPreparing ? "Preparing..." : "🎯 Prep Strategy"}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onTailorResume(drive)}
        >
          📄 Tailor Resume
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => onMockInterview(drive)}
        >
          🎙️ Mock Interview
        </button>
      </div>
    </div>
  );
}

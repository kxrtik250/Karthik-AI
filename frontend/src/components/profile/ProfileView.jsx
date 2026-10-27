import { useState } from "react";
import Spinner from "../common/Spinner";

const PROFICIENCY_OPTIONS = ["Beginner", "Intermediate", "Advanced", "Expert"];
const SKILL_CATEGORY_OPTIONS = [
  "Programming Languages",
  "Frameworks & Libraries",
  "Databases & Storage",
  "Cloud & DevOps",
  "Core CS Fundamentals",
  "Tools & Platforms",
  "Other",
];
const PROJECT_STATUS_OPTIONS = [
  { value: "completed", label: "Completed" },
  { value: "in_progress", label: "In Progress" },
  { value: "planned", label: "Planned" },
  { value: "archived", label: "Archived" },
];

export default function ProfileView({
  profile,
  skills,
  projects,
  isLoading,
  error,
  successMessage,
  onAddSkill,
  onEditSkill,
  onRemoveSkill,
  onAddProject,
  onEditProject,
  onRemoveProject,
  onClearError,
  onClearSuccess,
}) {
  // Modal states
  const [skillModalOpen, setSkillModalOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState(null);
  const [skillForm, setSkillForm] = useState({ name: "", category: "Programming Languages", proficiency: "Intermediate" });

  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [projectFormError, setProjectFormError] = useState(null);
  const [projectForm, setProjectForm] = useState({
    name: "",
    description: "",
    technologies: "",
    status: "completed",
    role: "",
    url: "",
    start_date: "",
    end_date: "",
  });

  const [deleteConfirm, setDeleteConfirm] = useState(null); // { type: 'skill' | 'project', id, name }

  // Skill Handlers
  const openAddSkillModal = () => {
    setEditingSkill(null);
    setSkillForm({ name: "", category: "Programming Languages", proficiency: "Intermediate" });
    setSkillModalOpen(true);
  };

  const openEditSkillModal = (skill) => {
    setEditingSkill(skill);
    setSkillForm({
      name: skill.name || "",
      category: skill.category || "Programming Languages",
      proficiency: skill.proficiency || "Intermediate",
    });
    setSkillModalOpen(true);
  };

  const handleSkillSubmit = async (e) => {
    e.preventDefault();
    if (!skillForm.name.trim()) return;

    try {
      if (editingSkill) {
        await onEditSkill(editingSkill.id, skillForm);
      } else {
        await onAddSkill(skillForm);
      }
      setSkillModalOpen(false);
    } catch {
      // Error handled by hook
    }
  };

  // Project Handlers
  const openAddProjectModal = () => {
    setEditingProject(null);
    setProjectFormError(null);
    setProjectForm({
      name: "",
      description: "",
      technologies: "",
      status: "completed",
      role: "",
      url: "",
      start_date: "",
      end_date: "",
    });
    setProjectModalOpen(true);
  };

  const openEditProjectModal = (proj) => {
    setEditingProject(proj);
    setProjectFormError(null);
    setProjectForm({
      name: proj.name || "",
      description: proj.description || "",
      technologies: Array.isArray(proj.technologies) ? proj.technologies.join(", ") : "",
      status: proj.status || "completed",
      role: proj.role || "",
      url: proj.url || "",
      start_date: proj.start_date || "",
      end_date: proj.end_date || "",
    });
    setProjectModalOpen(true);
  };

  const handleProjectSubmit = async (e) => {
    e.preventDefault();
    setProjectFormError(null);

    const trimmedName = projectForm.name.trim();
    if (!trimmedName) {
      setProjectFormError("Project name is required.");
      return;
    }

    // Validate URL if provided
    let normalizedUrl = null;
    if (projectForm.url && projectForm.url.trim()) {
      let candidate = projectForm.url.trim().replace(/\\/g, "/");
      if (!candidate.startsWith("http://") && !candidate.startsWith("https://")) {
        candidate = "https://" + candidate;
      }
      try {
        const parsed = new URL(candidate);
        const host = parsed.hostname.toLowerCase();
        const path = parsed.pathname.replace(/^\/+|\/+$/g, "");
        const genericHosts = [
          "github.com",
          "www.github.com",
          "gitlab.com",
          "www.gitlab.com",
          "bitbucket.org",
          "www.bitbucket.org",
        ];
        if (genericHosts.includes(host) && !path) {
          setProjectFormError(
            "Generic link is invalid. Please provide the specific repository or project URL (e.g. https://github.com/username/project)."
          );
          return;
        }
        normalizedUrl = candidate;
      } catch {
        setProjectFormError("Invalid project URL. Please enter a valid URL.");
        return;
      }
    }

    // Validate description if provided
    const trimmedDesc = projectForm.description ? projectForm.description.trim() : null;
    if (trimmedDesc && trimmedDesc.length < 10) {
      setProjectFormError("Project description must be at least 10 characters long to provide an informative summary.");
      return;
    }

    // Validate dates
    if (projectForm.start_date && projectForm.end_date && projectForm.end_date < projectForm.start_date) {
      setProjectFormError("Project end date cannot be earlier than start date.");
      return;
    }

    const techsArray = projectForm.technologies
      ? projectForm.technologies.split(",").map((t) => t.trim()).filter(Boolean)
      : [];

    const payload = {
      name: trimmedName,
      description: trimmedDesc,
      technologies: techsArray,
      status: projectForm.status,
      role: projectForm.role ? projectForm.role.trim() : null,
      url: normalizedUrl,
      start_date: projectForm.start_date || null,
      end_date: projectForm.end_date || null,
    };

    try {
      if (editingProject) {
        await onEditProject(editingProject.id, payload);
      } else {
        await onAddProject(payload);
      }
      setProjectModalOpen(false);
    } catch (err) {
      setProjectFormError(err.message || "Failed to save project.");
    }
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (!deleteConfirm) return;
    try {
      if (deleteConfirm.type === "skill") {
        await onRemoveSkill(deleteConfirm.id);
      } else if (deleteConfirm.type === "project") {
        await onRemoveProject(deleteConfirm.id);
      }
      setDeleteConfirm(null);
    } catch {
      // Error handled by hook
    }
  };

  // Group skills by category
  const skillsByCategory = skills.reduce((acc, skill) => {
    const cat = skill.category || "General";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  if (isLoading) {
    return (
      <div className="profile-view-loading">
        <Spinner size="large" />
        <p>Loading personal profile & records...</p>
      </div>
    );
  }

  return (
    <div className="profile-view-container">
      {/* Notifications */}
      {error && (
        <div className="alert-banner alert-error" role="alert">
          <span>⚠️ {error}</span>
          <button type="button" className="alert-close-btn" onClick={onClearError}>✕</button>
        </div>
      )}
      {successMessage && (
        <div className="alert-banner alert-success" role="status">
          <span>✓ {successMessage}</span>
          <button type="button" className="alert-close-btn" onClick={onClearSuccess}>✕</button>
        </div>
      )}

      {/* Page Header */}
      <div className="profile-page-header">
        <div>
          <h2 className="profile-page-title">Profile & Portfolio</h2>
          <p className="profile-page-subtitle">
            Authoritative student profile, real skills, and registered technical projects stored in PostgreSQL.
          </p>
        </div>
      </div>

      {/* Authoritative Profile Card */}
      {profile && (
        <div className="profile-summary-card">
          <div className="profile-card-header">
            <div className="profile-avatar-circle" aria-hidden="true">
              {profile.name ? profile.name[0].toUpperCase() : "K"}
            </div>
            <div>
              <h3 className="profile-name">{profile.name}</h3>
              <p className="profile-education">
                {profile.degree} in {profile.branch} • {profile.university}
              </p>
            </div>
            <span className="profile-badge-authoritative">Authoritative Profile</span>
          </div>

          <div className="profile-details-grid">
            <div className="profile-detail-item">
              <span className="detail-label">Graduation Year</span>
              <span className="detail-value">{profile.graduation_year || "2027"}</span>
            </div>
            <div className="profile-detail-item">
              <span className="detail-label">CGPA</span>
              <span className="detail-value highlight-cgpa">{profile.cgpa ? `${profile.cgpa} / 10` : "7.52 / 10"}</span>
            </div>
            <div className="profile-detail-item">
              <span className="detail-label">Email</span>
              <span className="detail-value">{profile.email || "Registered"}</span>
            </div>
            {profile.career_goals && (
              <div className="profile-detail-item full-width">
                <span className="detail-label">Career Aspirations</span>
                <span className="detail-value">{profile.career_goals}</span>
              </div>
            )}
            {profile.summary && (
              <div className="profile-detail-item full-width">
                <span className="detail-label">Summary</span>
                <span className="detail-value">{profile.summary}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Skills Section */}
      <section className="profile-section">
        <div className="section-header-row">
          <div className="section-title-group">
            <h3 className="section-title">Technical Skills</h3>
            <span className="count-pill">{skills.length}</span>
          </div>
          <button type="button" className="btn btn-primary btn-sm" onClick={openAddSkillModal}>
            ＋ Add Skill
          </button>
        </div>

        {skills.length === 0 ? (
          <div className="empty-profile-box">
            <span className="empty-icon" aria-hidden="true">💡</span>
            <h4>No skills registered yet</h4>
            <p>Add your verified programming languages, tools, and technical competencies.</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={openAddSkillModal}>
              Add First Skill
            </button>
          </div>
        ) : (
          <div className="skills-category-list">
            {Object.entries(skillsByCategory).map(([cat, catSkills]) => (
              <div key={cat} className="skill-category-block">
                <h4 className="skill-category-heading">{cat}</h4>
                <div className="skills-chips-wrapper">
                  {catSkills.map((sk) => (
                    <div key={sk.id} className="skill-chip">
                      <span className="skill-chip-name">{sk.name}</span>
                      {sk.proficiency && (
                        <span className={`skill-chip-prof prof-${sk.proficiency.toLowerCase()}`}>
                          {sk.proficiency}
                        </span>
                      )}
                      <div className="skill-chip-actions">
                        <button
                          type="button"
                          className="chip-action-btn"
                          title="Edit skill"
                          onClick={() => openEditSkillModal(sk)}
                          aria-label={`Edit ${sk.name}`}
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          className="chip-action-btn delete-btn"
                          title="Delete skill"
                          onClick={() => setDeleteConfirm({ type: "skill", id: sk.id, name: sk.name })}
                          aria-label={`Delete ${sk.name}`}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Projects Section */}
      <section className="profile-section">
        <div className="section-header-row">
          <div className="section-title-group">
            <h3 className="section-title">Projects</h3>
            <span className="count-pill">{projects.length}</span>
          </div>
          <button type="button" className="btn btn-primary btn-sm" onClick={openAddProjectModal}>
            ＋ Add Project
          </button>
        </div>

        {projects.length === 0 ? (
          <div className="empty-profile-box">
            <span className="empty-icon" aria-hidden="true">🚀</span>
            <h4>No project records registered</h4>
            <p>Register your verified academic and software projects to power grounded portfolio answers in the AI Assistant.</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={openAddProjectModal}>
              Add First Project
            </button>
          </div>
        ) : (
          <div className="projects-grid">
            {projects.map((proj) => (
              <div key={proj.id} className="project-card">
                <div className="project-card-top">
                  <div className="project-title-area">
                    <h4 className="project-name">{proj.name}</h4>
                    {proj.role && (
                      <span className="project-role">
                        <span className="role-prefix">Role:</span> {proj.role}
                      </span>
                    )}
                  </div>
                  <span className={`status-badge status-${(proj.status || "planned").toLowerCase()}`}>
                    {proj.status ? proj.status.replace("_", " ") : "Planned"}
                  </span>
                </div>

                {proj.description && (
                  <p className="project-desc">{proj.description}</p>
                )}

                {(() => {
                  const techList = Array.isArray(proj.technologies)
                    ? proj.technologies
                    : typeof proj.technologies === "string"
                    ? proj.technologies.split(",").map((t) => t.trim()).filter(Boolean)
                    : [];
                  if (techList.length === 0) return null;
                  return (
                    <div className="project-tech-tags" aria-label="Technologies used">
                      {techList.map((tech, idx) => (
                        <span key={`${tech}-${idx}`} className="tech-tag">
                          {tech}
                        </span>
                      ))}
                    </div>
                  );
                })()}

                <div className="project-card-footer">
                  <div className="project-meta-info">
                    {proj.url && (
                      <a
                        href={proj.url.replace(/\\/g, "/")}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="project-link"
                      >
                        🔗 Project Link
                      </a>
                    )}
                    {(proj.start_date || proj.end_date) && (
                      <span className="project-dates">
                        📅 {proj.start_date || "Start"} → {proj.end_date || "Present"}
                      </span>
                    )}
                  </div>
                  <div className="project-card-actions">
                    <button
                      type="button"
                      className="btn btn-outline btn-xs"
                      onClick={() => openEditProjectModal(proj)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger-outline btn-xs"
                      onClick={() => setDeleteConfirm({ type: "project", id: proj.id, name: proj.name })}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Skill Modal */}
      {skillModalOpen && (
        <div className="modal-backdrop" onClick={() => setSkillModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{editingSkill ? "Edit Skill" : "Add Skill"}</h3>
              <button type="button" className="modal-close-btn" onClick={() => setSkillModalOpen(false)}>✕</button>
            </div>
            <form onSubmit={handleSkillSubmit} className="modal-form">
              <div className="form-group">
                <label htmlFor="skill-name">Skill Name *</label>
                <input
                  id="skill-name"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Python, PostgreSQL, Docker, DSA"
                  value={skillForm.name}
                  onChange={(e) => setSkillForm({ ...skillForm, name: e.target.value })}
                  required
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label htmlFor="skill-category">Category</label>
                <select
                  id="skill-category"
                  className="form-select"
                  value={skillForm.category}
                  onChange={(e) => setSkillForm({ ...skillForm, category: e.target.value })}
                >
                  {SKILL_CATEGORY_OPTIONS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="skill-proficiency">Proficiency Level</label>
                <select
                  id="skill-proficiency"
                  className="form-select"
                  value={skillForm.proficiency}
                  onChange={(e) => setSkillForm({ ...skillForm, proficiency: e.target.value })}
                >
                  {PROFICIENCY_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setSkillModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingSkill ? "Save Changes" : "Add Skill"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Project Modal */}
      {projectModalOpen && (
        <div className="modal-backdrop" onClick={() => setProjectModalOpen(false)}>
          <div className="modal-dialog modal-dialog-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{editingProject ? "Edit Project" : "Add Project"}</h3>
              <button type="button" className="modal-close-btn" onClick={() => setProjectModalOpen(false)}>✕</button>
            </div>
            {projectFormError && (
              <div className="form-error-banner" role="alert">
                ⚠️ {projectFormError}
              </div>
            )}
            <form onSubmit={handleProjectSubmit} className="modal-form">
              <div className="form-row">
                <div className="form-group flex-2">
                  <label htmlFor="proj-name">Project Name *</label>
                  <input
                    id="proj-name"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Student Result Management System"
                    value={projectForm.name}
                    onChange={(e) => setProjectForm({ ...projectForm, name: e.target.value })}
                    required
                    autoFocus
                  />
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="proj-status">Status</label>
                  <select
                    id="proj-status"
                    className="form-select"
                    value={projectForm.status}
                    onChange={(e) => setProjectForm({ ...projectForm, status: e.target.value })}
                  >
                    {PROJECT_STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label htmlFor="proj-role">Your Role</label>
                  <input
                    id="proj-role"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Full Stack Developer, Lead"
                    value={projectForm.role}
                    onChange={(e) => setProjectForm({ ...projectForm, role: e.target.value })}
                  />
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="proj-url">Project / Repo URL</label>
                  <input
                    id="proj-url"
                    type="text"
                    className="form-input"
                    placeholder="https://github.com/username/project"
                    value={projectForm.url}
                    onChange={(e) => setProjectForm({ ...projectForm, url: e.target.value })}
                  />
                  <span className="form-hint">Specific repo or project link (e.g. https://github.com/username/repo)</span>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="proj-techs">Technologies (comma-separated)</label>
                <input
                  id="proj-techs"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Python, FastAPI, PostgreSQL, Docker, React"
                  value={projectForm.technologies}
                  onChange={(e) => setProjectForm({ ...projectForm, technologies: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label htmlFor="proj-desc">Description</label>
                <textarea
                  id="proj-desc"
                  className="form-textarea"
                  rows={3}
                  placeholder="Describe the problem solved, architecture, and accomplishments..."
                  value={projectForm.description}
                  onChange={(e) => setProjectForm({ ...projectForm, description: e.target.value })}
                />
                <span className="form-hint">Provide an informative summary (minimum 10 characters)</span>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label htmlFor="proj-start">Start Date</label>
                  <input
                    id="proj-start"
                    type="date"
                    className="form-input"
                    value={projectForm.start_date}
                    onChange={(e) => setProjectForm({ ...projectForm, start_date: e.target.value })}
                  />
                </div>
                <div className="form-group flex-1">
                  <label htmlFor="proj-end">End Date</label>
                  <input
                    id="proj-end"
                    type="date"
                    className="form-input"
                    value={projectForm.end_date}
                    onChange={(e) => setProjectForm({ ...projectForm, end_date: e.target.value })}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setProjectModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingProject ? "Save Changes" : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="modal-backdrop" onClick={() => setDeleteConfirm(null)}>
          <div className="modal-dialog modal-dialog-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Confirm Deletion</h3>
              <button type="button" className="modal-close-btn" onClick={() => setDeleteConfirm(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete the {deleteConfirm.type} <strong>"{deleteConfirm.name}"</strong>?
              </p>
              <p className="text-muted-sm">This action cannot be undone.</p>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>
                Cancel
              </button>
              <button type="button" className="btn btn-danger" onClick={handleConfirmDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

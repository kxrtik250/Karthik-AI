import { useState, useMemo } from "react";
import PlacementCard from "./PlacementCard";
import ComparisonModal from "./ComparisonModal";
import PreparationModal from "./PreparationModal";
import ImportDriveModal from "./ImportDriveModal";
import MockInterviewModal from "../interview/MockInterviewModal";
import ResumeStudioModal from "../resume/ResumeStudioModal";
import Spinner from "../common/Spinner";
import EmptyState from "../common/EmptyState";

export default function PlacementsView({
  openDrives,
  priorities,
  upcomingDrives,
  isLoading,
  error,
  onRefresh,
  selectedComparison,
  isComparing,
  onLoadComparison,
  preparationPlan,
  isGeneratingPlan,
  onGeneratePlan,
  onCloseModals,
  documents = [],
}) {
  const [activeTab, setActiveTab] = useState("priorities"); // "priorities" | "all" | "upcoming"
  const [searchQuery, setSearchQuery] = useState("");
  const [eligibilityFilter, setEligibilityFilter] = useState("all"); // "all" | "eligible" | "unknown" | "not_eligible"
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isInterviewModalOpen, setIsInterviewModalOpen] = useState(false);
  const [selectedInterviewDrive, setSelectedInterviewDrive] = useState(null);
  const [isResumeModalOpen, setIsResumeModalOpen] = useState(false);
  const [selectedResumeDrive, setSelectedResumeDrive] = useState(null);

  const handleStartInterview = (drive = null) => {
    setSelectedInterviewDrive(drive);
    setIsInterviewModalOpen(true);
  };

  const handleTailorResume = (drive = null) => {
    setSelectedResumeDrive(drive);
    setIsResumeModalOpen(true);
  };

  // Quick stats calculation
  const stats = useMemo(() => {
    const total = openDrives.length;
    const eligibleCount = priorities.filter((p) => p.eligibility_status === "ELIGIBLE").length;
    const upcomingCount = upcomingDrives.length;
    const highPriorityCount = priorities.filter((p) => p.priority_level === "HIGH").length;

    return { total, eligibleCount, upcomingCount, highPriorityCount };
  }, [openDrives, priorities, upcomingDrives]);

  // Priority lookup map by drive id
  const priorityMap = useMemo(() => {
    const map = new Map();
    priorities.forEach((p) => map.set(p.drive_id, p));
    return map;
  }, [priorities]);

  // Filtered drive list based on active tab, search, and eligibility
  const displayedDrives = useMemo(() => {
    let list = [];
    if (activeTab === "priorities") {
      // In priorities tab, sort drives in the order of ranked priorities
      const driveMap = new Map();
      openDrives.forEach((d) => driveMap.set(d.id, d));
      list = priorities
        .map((p) => driveMap.get(p.drive_id))
        .filter(Boolean);
    } else if (activeTab === "upcoming") {
      list = upcomingDrives;
    } else {
      list = openDrives;
    }

    return list.filter((drive) => {
      const p = priorityMap.get(drive.id);
      const companyName = drive.company?.name || "";
      const role = drive.role || "";

      // Search match
      const matchesSearch =
        companyName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        role.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      // Eligibility match
      if (eligibilityFilter === "eligible") {
        return p?.eligibility_status === "ELIGIBLE";
      }
      if (eligibilityFilter === "unknown") {
        return p?.eligibility_status === "UNKNOWN";
      }
      if (eligibilityFilter === "not_eligible") {
        return p?.eligibility_status === "NOT_ELIGIBLE";
      }

      return true;
    });
  }, [activeTab, openDrives, priorities, upcomingDrives, priorityMap, searchQuery, eligibilityFilter]);

  return (
    <div className="placements-view">
      {/* Top Banner / Stats Header */}
      <div className="placements-header">
        <div className="placements-title-group">
          <h2>Placement Intelligence</h2>
          <p className="placements-subtitle">
            Deterministic eligibility matching, opportunity prioritization, and targeted interview preparation.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => handleTailorResume(null)}
          >
            📄 Resume Studio
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => handleStartInterview(null)}
          >
            🎙️ Practice Mock Interview
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setIsImportModalOpen(true)}
          >
            + Import from Circular / JD
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onRefresh}
            disabled={isLoading}
          >
            {isLoading ? "Refreshing..." : "↻ Refresh Intelligence"}
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="placements-stats-grid">
        <div className="stat-card">
          <span className="stat-label">Active Drives</span>
          <span className="stat-value">{stats.total}</span>
        </div>
        <div className="stat-card stat-success">
          <span className="stat-label">Verified Eligible</span>
          <span className="stat-value">{stats.eligibleCount}</span>
        </div>
        <div className="stat-card stat-warning">
          <span className="stat-label">Deadlines Approaching</span>
          <span className="stat-value">{stats.upcomingCount}</span>
        </div>
        <div className="stat-card stat-primary">
          <span className="stat-label">High Priority</span>
          <span className="stat-value">{stats.highPriorityCount}</span>
        </div>
      </div>

      {/* Filter and Tab Controls */}
      <div className="placements-controls-bar">
        <div className="tab-pill-group">
          <button
            type="button"
            className={`tab-pill ${activeTab === "priorities" ? "active" : ""}`}
            onClick={() => setActiveTab("priorities")}
          >
            ★ Prioritized Pipeline ({priorities.length})
          </button>
          <button
            type="button"
            className={`tab-pill ${activeTab === "all" ? "active" : ""}`}
            onClick={() => setActiveTab("all")}
          >
            All Open Drives ({openDrives.length})
          </button>
          <button
            type="button"
            className={`tab-pill ${activeTab === "upcoming" ? "active" : ""}`}
            onClick={() => setActiveTab("upcoming")}
          >
            Upcoming Deadlines ({upcomingDrives.length})
          </button>
        </div>

        <div className="search-filter-group">
          <input
            type="text"
            className="input-search"
            placeholder="Search company or role..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />

          <select
            className="select-filter"
            value={eligibilityFilter}
            onChange={(e) => setEligibilityFilter(e.target.value)}
          >
            <option value="all">All Eligibility</option>
            <option value="eligible">✓ Eligible Only</option>
            <option value="unknown">? Unknown Only</option>
            <option value="not_eligible">✕ Not Eligible</option>
          </select>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="placements-scroll-container">
        {isLoading ? (
          <div className="placements-loading-state">
            <Spinner size="lg" />
            <p>Evaluating placement intelligence and ranking pipeline...</p>
          </div>
        ) : error ? (
          <div className="alert alert-danger" style={{ margin: "1.5rem" }}>
            <span>{error}</span>
          </div>
        ) : displayedDrives.length === 0 ? (
          <EmptyState
            icon="🎓"
            title="No placement drives found"
            message={
              searchQuery || eligibilityFilter !== "all"
                ? "No placement drives match your active search or filter criteria."
                : "No active placement drives recorded yet. Add placement drives to start tracking opportunities."
            }
          />
        ) : (
          <div className="placements-grid">
            {displayedDrives.map((drive) => {
              const priority = priorityMap.get(drive.id);
              return (
                <PlacementCard
                  key={drive.id}
                  drive={drive}
                  priority={priority}
                  onCompare={onLoadComparison}
                  onPrepare={onGeneratePlan}
                  onMockInterview={handleStartInterview}
                  onTailorResume={handleTailorResume}
                  isComparing={isComparing}
                  isPreparing={isGeneratingPlan}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Comparison Modal */}
      {selectedComparison && (
        <ComparisonModal
          comparison={selectedComparison}
          onClose={onCloseModals}
        />
      )}

      {/* Preparation Plan Modal */}
      {preparationPlan && (
        <PreparationModal
          plan={preparationPlan}
          onClose={onCloseModals}
        />
      )}

      {/* Import Drive from Circular / JD Modal */}
      <ImportDriveModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        documents={documents}
        onSaved={onRefresh}
      />

      {/* Interactive Mock Interview Simulator Modal */}
      <MockInterviewModal
        isOpen={isInterviewModalOpen}
        onClose={() => {
          setIsInterviewModalOpen(false);
          setSelectedInterviewDrive(null);
        }}
        drive={selectedInterviewDrive}
      />

      {/* Resume Optimizer & ATS Tailoring Studio Modal */}
      <ResumeStudioModal
        isOpen={isResumeModalOpen}
        onClose={() => {
          setIsResumeModalOpen(false);
          setSelectedResumeDrive(null);
        }}
        drive={selectedResumeDrive}
      />
    </div>
  );
}

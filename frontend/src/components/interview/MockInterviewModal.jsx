import { useState, useEffect } from "react";
import Spinner from "../common/Spinner";
import {
  startMockInterview,
  evaluateInterviewAnswer,
  completeMockInterview,
} from "../../api/interview";

export default function MockInterviewModal({ isOpen, onClose, drive = null }) {
  const [stage, setStage] = useState("config"); // "config" | "interviewing" | "feedback" | "summary"
  const [roundType, setRoundType] = useState("technical");
  const [difficulty, setDifficulty] = useState("intermediate");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Active session data
  const [session, setSession] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answerText, setAnswerText] = useState("");
  const [currentEvaluation, setCurrentEvaluation] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [summary, setSummary] = useState(null);
  const [showModelAnswer, setShowModelAnswer] = useState(false);

  // Reset or preset whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setStage("config");
      setRoundType("technical");
      setDifficulty("intermediate");
      setError(null);
      setSession(null);
      setCurrentQuestionIndex(0);
      setAnswerText("");
      setCurrentEvaluation(null);
      setEvaluations([]);
      setSummary(null);
      setShowModelAnswer(false);
    }
  }, [isOpen, drive]);

  if (!isOpen) return null;

  const currentQuestion = session?.questions?.[currentQuestionIndex] || null;
  const companyName = drive?.company?.name || session?.company_name || "General Technology";
  const roleName = drive?.role || session?.role || "Software Engineer";

  // 1. Start Session
  const handleStart = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await startMockInterview({
        drive_id: drive?.id || null,
        round_type: roundType,
        difficulty,
      });
      setSession(data);
      setCurrentQuestionIndex(0);
      setAnswerText("");
      setEvaluations([]);
      setCurrentEvaluation(null);
      setStage("interviewing");
    } catch (err) {
      setError(err.message || "Failed to start mock interview.");
    } finally {
      setIsLoading(false);
    }
  };

  // 2. Submit Answer for Evaluation
  const handleSubmitAnswer = async (e) => {
    e.preventDefault();
    if (!answerText.trim() || answerText.trim().length < 5) {
      setError("Please write a meaningful answer (at least 5 characters).");
      return;
    }

    setIsLoading(true);
    setError(null);
    setShowModelAnswer(false);

    try {
      const evalResult = await evaluateInterviewAnswer({
        session_id: session.session_id,
        question_id: currentQuestion.question_id,
        answer_text: answerText,
        question: currentQuestion,
        total_questions: session.total_questions,
      });

      setCurrentEvaluation(evalResult);
      setEvaluations((prev) => [...prev, evalResult]);
      setStage("feedback");
    } catch (err) {
      setError(err.message || "Failed to evaluate answer.");
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Move to Next Question or Finalize
  const handleNext = async () => {
    setError(null);
    setShowModelAnswer(false);

    if (currentQuestionIndex + 1 < session.total_questions) {
      setCurrentQuestionIndex((prev) => prev + 1);
      setAnswerText("");
      setCurrentEvaluation(null);
      setStage("interviewing");
    } else {
      // Completed all questions -> generate summary
      setIsLoading(true);
      try {
        const finalEvaluations = evaluations.length > 0 ? evaluations : [currentEvaluation];
        const summaryData = await completeMockInterview({
          session_id: session.session_id,
          company_name: session.company_name,
          role: session.role,
          round_type: session.round_type,
          evaluations: finalEvaluations,
        });
        setSummary(summaryData);
        setStage("summary");
      } catch (err) {
        setError(err.message || "Failed to complete interview assessment.");
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-container modal-lg interview-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h2 className="modal-title">🎙️ Mock Interview Simulator</h2>
              {session && (
                <span className="badge badge-primary" style={{ textTransform: "uppercase" }}>
                  {session.round_type.replace("_", " ")}
                </span>
              )}
            </div>
            <p className="modal-subtitle">
              {companyName} — {roleName}
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close interview modal"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="modal-body interview-modal-body">
          {error && (
            <div className="alert alert-danger" style={{ marginBottom: "1rem" }}>
              <span>{error}</span>
            </div>
          )}

          {/* STAGE 1: Configuration */}
          {stage === "config" && (
            <div className="interview-config-pane">
              <p className="interview-intro-text">
                Prepare with tailored, deterministic interview questions calibrated to your verified
                skills and projects. Choose your target round:
              </p>

              <div className="form-group" style={{ marginBottom: "1.25rem" }}>
                <label className="form-label" style={{ fontWeight: 600 }}>
                  Select Interview Round:
                </label>
                <div className="interview-round-selector">
                  <label
                    className={`round-option-card ${roundType === "technical" ? "active" : ""}`}
                  >
                    <input
                      type="radio"
                      name="roundType"
                      value="technical"
                      checked={roundType === "technical"}
                      onChange={(e) => setRoundType(e.target.value)}
                    />
                    <div className="round-option-content">
                      <span className="round-opt-title">💻 Technical & Core Concepts</span>
                      <span className="round-opt-desc">
                        PostgreSQL indexing, query optimization, Python memory, and REST APIs.
                      </span>
                    </div>
                  </label>

                  <label
                    className={`round-option-card ${
                      roundType === "project_deep_dive" ? "active" : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name="roundType"
                      value="project_deep_dive"
                      checked={roundType === "project_deep_dive"}
                      onChange={(e) => setRoundType(e.target.value)}
                    />
                    <div className="round-option-content">
                      <span className="round-opt-title">🛠️ Project Deep Dive</span>
                      <span className="round-opt-desc">
                        Architecture, schema design, and technical decisions in your Student Management project.
                      </span>
                    </div>
                  </label>

                  <label
                    className={`round-option-card ${roundType === "hr_behavioral" ? "active" : ""}`}
                  >
                    <input
                      type="radio"
                      name="roundType"
                      value="hr_behavioral"
                      checked={roundType === "hr_behavioral"}
                      onChange={(e) => setRoundType(e.target.value)}
                    />
                    <div className="round-option-content">
                      <span className="round-opt-title">🤝 Behavioral & HR (STAR Method)</span>
                      <span className="round-opt-desc">
                        Situation, Task, Action, and Result questions on pressure, collaboration, and learning agility.
                      </span>
                    </div>
                  </label>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: "1.5rem" }}>
                <label className="form-label" style={{ fontWeight: 600 }}>
                  Difficulty Level:
                </label>
                <select
                  className="input-search"
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  style={{ width: "100%", maxWidth: "300px" }}
                >
                  <option value="entry">Entry Level (Fresh Graduate)</option>
                  <option value="intermediate">Intermediate (Standard Placement Drive)</option>
                  <option value="advanced">Advanced (Deep Technical / Lead)</option>
                </select>
              </div>

              <div className="interview-grounding-notice">
                <span className="notice-icon">🛡️</span>
                <span>
                  <strong>Strict Grounding:</strong> Questions and evaluations adhere strictly to
                  your verified project descriptions and skills to ensure authentic interview practice.
                </span>
              </div>
            </div>
          )}

          {/* STAGE 2: Active Question & Answering */}
          {stage === "interviewing" && currentQuestion && (
            <div className="interview-qa-pane">
              {/* Question Progress Header */}
              <div className="interview-progress-bar-wrap">
                <div className="interview-progress-text">
                  <span>
                    Question <strong>{currentQuestionIndex + 1}</strong> of{" "}
                    <strong>{session.total_questions}</strong>
                  </span>
                  <span className="topic-badge">{currentQuestion.topic}</span>
                </div>
                <div className="placement-progress-bar-bg" style={{ height: "6px" }}>
                  <div
                    className="placement-progress-bar-fill"
                    style={{
                      width: `${((currentQuestionIndex + 1) / session.total_questions) * 100}%`,
                    }}
                  />
                </div>
              </div>

              {/* Question Box */}
              <div className="interview-question-card">
                <h3 className="interview-question-heading">
                  {currentQuestion.question_text}
                </h3>
                {currentQuestion.context_hint && (
                  <div className="interview-hint-box">
                    <span className="hint-label">💡 Strategy Tip:</span>
                    <span>{currentQuestion.context_hint}</span>
                  </div>
                )}
              </div>

              {/* Answer Input */}
              <form onSubmit={handleSubmitAnswer} className="interview-answer-form">
                <label className="form-label" style={{ fontWeight: 600 }}>
                  Your Response:
                </label>
                <textarea
                  className="interview-answer-textarea"
                  rows={6}
                  placeholder="Articulate your answer clearly. Explain your technical rationale, architecture, or STAR story..."
                  value={answerText}
                  onChange={(e) => setAnswerText(e.target.value)}
                  disabled={isLoading}
                  autoFocus
                />
                <div className="interview-form-footer">
                  <span className="char-count">{answerText.trim().split(/\s+/).filter(Boolean).length} words</span>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isLoading || answerText.trim().length < 5}
                  >
                    {isLoading ? <Spinner size="sm" /> : "Submit Answer for Assessment →"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* STAGE 3: Real-Time Evaluation & Rubric Feedback */}
          {stage === "feedback" && currentEvaluation && (
            <div className="interview-feedback-pane">
              <div className="eval-score-banner">
                <div className="eval-score-circle">
                  <span className="eval-score-num">{currentEvaluation.score}</span>
                  <span className="eval-score-den">/ 10</span>
                </div>
                <div>
                  <h3 className="eval-score-title">
                    {currentEvaluation.score >= 8
                      ? "Outstanding Response"
                      : currentEvaluation.score >= 6
                      ? "Solid Answer with Room for Polish"
                      : "Needs Additional Detail & Specifics"}
                  </h3>
                  <p className="eval-score-subtitle">
                    Evaluated for technical depth, key concept coverage, and authentic project grounding.
                  </p>
                </div>
              </div>

              {/* Grounding Warning if hallucinated features detected */}
              {currentEvaluation.grounding_warning && (
                <div className="alert alert-warning" style={{ margin: "1rem 0" }}>
                  <span>⚠️ {currentEvaluation.grounding_warning}</span>
                </div>
              )}

              {/* Strengths & Improvements Grid */}
              <div className="eval-grid">
                <div className="eval-card eval-card-strengths">
                  <h4 className="eval-card-title">✓ Key Strengths</h4>
                  <ul className="eval-bullet-list">
                    {currentEvaluation.feedback_strengths.map((s, idx) => (
                      <li key={idx}>{s}</li>
                    ))}
                  </ul>
                </div>

                <div className="eval-card eval-card-improvements">
                  <h4 className="eval-card-title">⚡ Areas for Growth</h4>
                  <ul className="eval-bullet-list">
                    {currentEvaluation.feedback_improvements.map((imp, idx) => (
                      <li key={idx}>{imp}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Model Answer Toggle */}
              <div className="eval-model-answer-section">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowModelAnswer((prev) => !prev)}
                >
                  {showModelAnswer ? "Hide Benchmark Model Answer" : "💡 View Benchmark Model Answer"}
                </button>

                {showModelAnswer && (
                  <div className="eval-model-box">
                    <pre className="prep-pre-text">{currentEvaluation.model_answer}</pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STAGE 4: Final Summary & Readiness Report */}
          {stage === "summary" && summary && (
            <div className="interview-summary-pane">
              <div className="summary-hero-card">
                <div className="summary-readiness-badge">
                  <span className="readiness-tag">{summary.readiness_level}</span>
                  <div className="summary-score-large">
                    {summary.overall_score} <span style={{ fontSize: "1.25rem", color: "#6b7280" }}>/ 10</span>
                  </div>
                </div>
                <div className="summary-hero-meta">
                  <h3>Mock Interview Assessment Report</h3>
                  <p>
                    {summary.company_name} — {summary.role} ({summary.round_type.replace("_", " ")})
                  </p>
                  <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                    Completed {summary.total_questions} evaluated questions.
                  </p>
                </div>
              </div>

              <div className="eval-grid" style={{ marginTop: "1.5rem" }}>
                <div className="eval-card eval-card-strengths">
                  <h4 className="eval-card-title">🌟 Key Strengths Identified</h4>
                  <ul className="eval-bullet-list">
                    {summary.strengths_summary.map((st, idx) => (
                      <li key={idx}>{st}</li>
                    ))}
                  </ul>
                </div>

                <div className="eval-card eval-card-improvements">
                  <h4 className="eval-card-title">🎯 Targeted Action Items Before Real Interview</h4>
                  <ul className="eval-bullet-list">
                    {summary.suggested_action_items.map((act, idx) => (
                      <li key={idx}>{act}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          {stage === "config" && (
            <>
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStart}
                disabled={isLoading}
              >
                {isLoading ? <Spinner size="sm" /> : "Begin Mock Session 🎙️"}
              </button>
            </>
          )}

          {stage === "feedback" && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleNext}
              disabled={isLoading}
            >
              {isLoading ? (
                <Spinner size="sm" />
              ) : currentQuestionIndex + 1 < session.total_questions ? (
                "Next Question →"
              ) : (
                "Complete Interview & View Report 📊"
              )}
            </button>
          )}

          {stage === "summary" && (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setStage("config")}
              >
                Practice Another Round
              </button>
              <button type="button" className="btn btn-primary" onClick={onClose}>
                Finish & Close
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

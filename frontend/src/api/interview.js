/**
 * API client methods for Interactive Mock Interview and Technical Assessment Simulator.
 */

const API_BASE = "/api/interview";

export async function startMockInterview({ drive_id = null, round_type = "technical", difficulty = "intermediate" }) {
  const resp = await fetch(`${API_BASE}/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      drive_id,
      round_type,
      difficulty,
    }),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to start mock interview session.");
  }

  return resp.json();
}

export async function evaluateInterviewAnswer({ session_id, question_id, answer_text, question, total_questions }) {
  const resp = await fetch(`${API_BASE}/evaluate-answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id,
      question_id,
      answer_text,
      question,
      total_questions,
    }),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to evaluate answer.");
  }

  return resp.json();
}

export async function completeMockInterview({ session_id, company_name, role, round_type, evaluations }) {
  const resp = await fetch(`${API_BASE}/complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id,
      company_name,
      role,
      round_type,
      evaluations,
    }),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to complete mock interview.");
  }

  return resp.json();
}

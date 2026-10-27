/**
 * API client methods for Resume Optimizer and ATS Tailoring Studio.
 */

const API_BASE = "/api/resume";

export async function optimizeResume({ drive_id = null, target_role = "Software Engineer", custom_jd_text = null }) {
  const resp = await fetch(`${API_BASE}/optimize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      drive_id,
      target_role,
      custom_jd_text,
    }),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to optimize resume.");
  }

  return resp.json();
}

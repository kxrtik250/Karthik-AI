const API_BASE = "";

/**
 * Universal JSON fetch helper with normalized error handling.
 */
export async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = { ...options.headers };

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 204) {
    return null;
  }

  let data;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    let errorMsg = "An unexpected error occurred.";
    if (data && data.detail) {
      if (typeof data.detail === "string") {
        errorMsg = data.detail;
      } else if (data.detail.message) {
        errorMsg = data.detail.message;
      } else {
        errorMsg = JSON.stringify(data.detail);
      }
    }
    const error = new Error(errorMsg);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

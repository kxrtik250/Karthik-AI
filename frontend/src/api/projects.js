import { apiFetch } from "./client";

export async function listProjects(status = null) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch(`/api/projects${query}`);
}

export async function getProject(projectId) {
  return apiFetch(`/api/projects/${projectId}`);
}

export async function createProject(projectData) {
  return apiFetch("/api/projects", {
    method: "POST",
    body: projectData,
  });
}

export async function updateProject(projectId, projectData) {
  return apiFetch(`/api/projects/${projectId}`, {
    method: "PUT",
    body: projectData,
  });
}

export async function deleteProject(projectId) {
  return apiFetch(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}

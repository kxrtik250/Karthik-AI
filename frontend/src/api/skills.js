import { apiFetch } from "./client";

export async function listSkills(category = null) {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch(`/api/skills${query}`);
}

export async function createSkill(skillData) {
  return apiFetch("/api/skills", {
    method: "POST",
    body: skillData,
  });
}

export async function updateSkill(skillId, skillData) {
  return apiFetch(`/api/skills/${skillId}`, {
    method: "PUT",
    body: skillData,
  });
}

export async function deleteSkill(skillId) {
  return apiFetch(`/api/skills/${skillId}`, {
    method: "DELETE",
  });
}

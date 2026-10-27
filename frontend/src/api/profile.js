import { apiFetch } from "./client";

export async function getProfile() {
  return apiFetch("/api/profile");
}

export async function updateProfile(profileData) {
  return apiFetch("/api/profile", {
    method: "PUT",
    body: profileData,
  });
}

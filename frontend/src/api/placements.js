import { apiFetch } from "./client";

export async function getPlacements(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch(`/api/placements${query}`);
}

export async function getOpenPlacements() {
  return apiFetch("/api/placements/open");
}

export async function getUpcomingPlacements(days = 30) {
  return apiFetch(`/api/placements/upcoming?days=${days}`);
}

export async function getEligiblePlacements() {
  return apiFetch("/api/placements/eligible");
}

export async function getPlacementPriorities() {
  return apiFetch("/api/placements/priorities");
}

export async function getPlacementEligibility(placementId) {
  return apiFetch(`/api/placements/${placementId}/eligibility`);
}

export async function getPlacementSkillMatch(placementId) {
  return apiFetch(`/api/placements/${placementId}/match`);
}

export async function getPlacementComparison(placementId) {
  return apiFetch(`/api/placements/${placementId}/comparison`);
}

export async function prepareForPlacement(placementId) {
  return apiFetch(`/api/placements/${placementId}/prepare`, {
    method: "POST",
  });
}

export async function extractPlacementFromText(text, sourceFilename = null) {
  return apiFetch("/api/placements/extract-from-text", {
    method: "POST",
    body: JSON.stringify({ text, source_filename: sourceFilename }),
  });
}

export async function extractPlacementFromDocument(documentId) {
  return apiFetch(`/api/placements/extract-from-document/${documentId}`, {
    method: "POST",
  });
}

export async function extractAndCreatePlacement(driveData, createCompanyIfMissing = true) {
  return apiFetch("/api/placements/extract-and-create", {
    method: "POST",
    body: JSON.stringify({
      drive_data: driveData,
      create_company_if_missing: createCompanyIfMissing,
    }),
  });
}


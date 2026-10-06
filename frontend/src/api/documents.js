import { apiFetch } from "./client";

export async function listDocuments(status = null) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch(`/api/documents${query}`);
}

export async function getDocument(documentId) {
  return apiFetch(`/api/documents/${documentId}`);
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch("/api/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function deleteDocument(documentId) {
  return apiFetch(`/api/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function getDocumentChunks(documentId) {
  return apiFetch(`/api/documents/${documentId}/chunks`);
}

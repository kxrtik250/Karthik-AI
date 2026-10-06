import { apiFetch } from "./client";

export async function getProviderStatus() {
  return apiFetch("/api/rag/provider");
}

export async function queryRag(payload) {
  return apiFetch("/api/rag/query", {
    method: "POST",
    body: payload,
  });
}

export async function chatRag(payload) {
  return apiFetch("/api/rag/chat", {
    method: "POST",
    body: payload,
  });
}

export async function listConversations() {
  return apiFetch("/api/rag/conversations");
}

export async function getConversation(conversationId) {
  return apiFetch(`/api/rag/conversations/${conversationId}`);
}

export async function deleteConversation(conversationId) {
  return apiFetch(`/api/rag/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

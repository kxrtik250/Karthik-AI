import { useState, useEffect, useCallback } from "react";
import { listConversations, deleteConversation as apiDeleteConversation } from "../api/rag";

export function useConversations() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadConversations = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await listConversations();
      setConversations(data || []);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load conversations");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const startNewChat = useCallback(() => {
    setActiveConversationId(null);
    setError(null);
  }, []);

  const selectConversation = useCallback((id) => {
    setActiveConversationId(id);
    setError(null);
  }, []);

  const deleteConversation = useCallback(
    async (id) => {
      try {
        await apiDeleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeConversationId === id) {
          setActiveConversationId(null);
        }
      } catch (err) {
        setError(err.message || "Failed to delete conversation");
      }
    },
    [activeConversationId]
  );

  return {
    conversations,
    activeConversationId,
    setActiveConversationId,
    isLoading,
    error,
    loadConversations,
    startNewChat,
    selectConversation,
    deleteConversation,
    clearError: () => setError(null),
  };
}

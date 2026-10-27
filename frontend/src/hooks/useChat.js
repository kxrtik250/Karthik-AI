import { useState, useEffect, useCallback } from "react";
import { getConversation, chatRag } from "../api/rag";

export function useChat(activeConversationId, onConversationCreated) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load messages when active conversation changes
  useEffect(() => {
    let isCancelled = false;

    if (!activeConversationId) {
      setMessages([]);
      setError(null);
      return;
    }

    async function loadMessages() {
      try {
        setIsLoading(true);
        const data = await getConversation(activeConversationId);
        if (!isCancelled && data) {
          setMessages(data.messages || []);
          setError(null);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || "Failed to load chat messages");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    loadMessages();

    return () => {
      isCancelled = true;
    };
  }, [activeConversationId]);

  const sendMessage = useCallback(
    async (text) => {
      if (!text || !text.trim()) return;

      const optimisticUserMsg = {
        id: "temp-" + Date.now(),
        role: "user",
        content: text.trim(),
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, optimisticUserMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const payload = {
          message: text.trim(),
          conversation_id: activeConversationId || null,
        };

        const response = await chatRag(payload);

        // Replace or append assistant message
        const assistantMsg = {
          ...response.message,
          intent: response.intent,
          sources_used: response.sources_used || [],
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // If this was a new conversation, notify parent
        if (!activeConversationId && response.conversation_id) {
          if (onConversationCreated) {
            onConversationCreated(response.conversation_id);
          }
        }
      } catch (err) {
        setError(err.message || "Failed to get a response from Karthik AI");
      } finally {
        setIsLoading(false);
      }
    },
    [activeConversationId, onConversationCreated]
  );

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearError: () => setError(null),
  };
}

import { useEffect, useRef } from "react";
import MessageItem from "./MessageItem";
import Spinner from "../common/Spinner";
import EmptyState from "../common/EmptyState";

export default function MessageList({
  messages,
  isLoading,
  onSelectCitation,
  onPromptClick,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (!messages || messages.length === 0) {
    const suggestions = [
      "What skills and projects are highlighted in my profile?",
      "Summarize my placement preparation strategy.",
      "What core technologies and databases do I have experience with?",
    ];

    return (
      <div className="message-list-empty">
        <EmptyState
          icon="✨"
          title="Ask Karthik AI anything"
          description="Ask questions grounded in your uploaded resumes, academic records, and placement documents."
        />
        <div className="prompt-suggestions">
          <span className="suggestions-label">Try asking:</span>
          <div className="suggestion-chips">
            {suggestions.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                className="suggestion-chip"
                onClick={() => onPromptClick && onPromptClick(prompt)}
              >
                "{prompt}"
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg, idx) => (
        <MessageItem
          key={msg.id || idx}
          message={msg}
          onSelectCitation={onSelectCitation}
        />
      ))}

      {isLoading && (
        <div className="message-row assistant-row">
          <div className="message-bubble assistant-bubble thinking-bubble">
            <div className="thinking-indicator">
              <Spinner size="sm" label="Searching documents and generating response..." />
              <span>Thinking & searching documents...</span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

import { useState } from "react";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import CitationModal from "./CitationModal";

export default function ChatView({
  messages,
  isLoading,
  error,
  onSendMessage,
  activeConversation,
  onClearError,
}) {
  const [selectedCitation, setSelectedCitation] = useState(null);

  return (
    <div className="chat-view">
      <div className="chat-header">
        <div className="chat-header-info">
          <h2 className="chat-title">
            {activeConversation ? activeConversation.title : "AI Assistant"}
          </h2>
          <span className="chat-subtitle">
            Document-grounded RAG assistance
          </span>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <span className="error-text">{error}</span>
          {onClearError && (
            <button
              type="button"
              className="error-dismiss-btn"
              onClick={onClearError}
              aria-label="Dismiss error"
            >
              ✕
            </button>
          )}
        </div>
      )}

      <div className="chat-body">
        <MessageList
          messages={messages}
          isLoading={isLoading}
          onSelectCitation={(citation) => setSelectedCitation(citation)}
          onPromptClick={(prompt) => onSendMessage(prompt)}
        />
      </div>

      <div className="chat-footer">
        <ChatInput
          onSendMessage={onSendMessage}
          disabled={isLoading}
          placeholder="Ask a question about your uploaded documents..."
        />
      </div>

      {selectedCitation && (
        <CitationModal
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
}

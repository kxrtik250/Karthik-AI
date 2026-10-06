import { useState, useRef, useEffect } from "react";
import Spinner from "../common/Spinner";

export default function ChatInput({ onSendMessage, disabled = false, placeholder = "Ask a question about your documents..." }) {
  const [text, setText] = useState("");
  const textareaRef = useRef(null);

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [text]);

  function handleSubmit(e) {
    if (e) e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;

    onSendMessage(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      <div className="chat-input-container">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          disabled={disabled}
          aria-label="Your question or message"
        />

        <button
          type="submit"
          className="chat-send-btn"
          disabled={!text.trim() || disabled}
          aria-label="Send message"
        >
          {disabled ? (
            <Spinner size="sm" label="Sending..." />
          ) : (
            <svg
              className="send-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
      <div className="chat-input-footer">
        <span className="footer-hint">Press <strong>Enter</strong> to send, <strong>Shift + Enter</strong> for a new line</span>
      </div>
    </form>
  );
}

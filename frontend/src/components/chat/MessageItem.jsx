import CitationTray from "./CitationTray";

export default function MessageItem({ message, onSelectCitation }) {
  const isUser = message.role === "user";
  const citations = message.citations || [];
  const hasNoDocsInfo =
    !isUser &&
    citations.length === 0 &&
    message.content.toLowerCase().includes("not enough information");

  return (
    <div className={`message-row ${isUser ? "user-row" : "assistant-row"}`}>
      <div className={`message-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}>
        <div className="message-header">
          <span className="message-author">{isUser ? "You" : "Karthik AI"}</span>
          {message.created_at && (
            <span className="message-time">
              {new Date(message.created_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>

        <div className="message-content">
          <p>{message.content}</p>
        </div>

        {hasNoDocsInfo && (
          <div className="ungrounded-notice">
            <span aria-hidden="true">ℹ️</span> No relevant information was found in your uploaded documents.
          </div>
        )}

        {citations.length > 0 && (
          <CitationTray citations={citations} onSelectCitation={onSelectCitation} />
        )}
      </div>
    </div>
  );
}

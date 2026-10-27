import CitationTray from "./CitationTray";

export default function MessageItem({ message, onSelectCitation }) {
  const isUser = message.role === "user";
  const citations = message.citations || [];
  const intent = message.intent;

  const hasNoDocsInfo =
    !isUser &&
    citations.length === 0 &&
    intent !== "CASUAL" &&
    intent !== "GENERAL_KNOWLEDGE" &&
    intent !== "PERSONAL_PROFILE" &&
    intent !== "PLACEMENT" &&
    !message.content.includes("• Recommended Next Steps") &&
    !message.content.includes("General Company Information") &&
    (message.content.toLowerCase().includes("not enough information") ||
      message.content.toLowerCase().includes("couldn't find relevant information in your uploaded documents"));

  const renderIntentBadge = () => {
    if (isUser || !intent || intent === "CASUAL" || intent === "UNKNOWN") return null;
    const badgeMap = {
      PERSONAL_PROFILE: { label: "Profile", icon: "👤" },
      DOCUMENT_RAG: { label: "Knowledge", icon: "📄" },
      PLACEMENT: { label: "Placement", icon: "💼" },
      GENERAL_KNOWLEDGE: { label: "Concept", icon: "💡" },
    };
    const b = badgeMap[intent];
    if (!b) return null;
    return (
      <span className="message-intent-badge" title={`Routed via ${intent}`}>
        <span aria-hidden="true">{b.icon}</span> {b.label}
      </span>
    );
  };

  return (
    <div className={`message-row ${isUser ? "user-row" : "assistant-row"}`}>
      <div className={`message-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}>
        <div className="message-header">
          <span className="message-author">
            {isUser ? "You" : "Karthik AI"}
            {renderIntentBadge()}
          </span>
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

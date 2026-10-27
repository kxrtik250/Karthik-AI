import { useState, useEffect } from "react";
import { getProviderStatus } from "../../api/rag";
import Spinner from "../common/Spinner";

export default function Sidebar({
  activeView,
  onSelectView,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  isOpen,
  onCloseMobile,
}) {
  const [providerInfo, setProviderInfo] = useState(null);

  useEffect(() => {
    getProviderStatus()
      .then((data) => setProviderInfo(data))
      .catch(() => setProviderInfo({ healthy: false, provider: "unknown" }));
  }, []);

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="sidebar-backdrop"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside className={`app-sidebar ${isOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand-group">
            <span className="brand-logo" aria-hidden="true">🤖</span>
            <div>
              <h1 className="brand-title">Karthik AI</h1>
              <p className="brand-subtitle">Personal AI Assistant</p>
            </div>
          </div>
        </div>

        <div className="sidebar-actions">
          <button
            type="button"
            className="btn btn-primary btn-new-chat"
            onClick={() => {
              onNewChat();
              onSelectView("chat");
              onCloseMobile && onCloseMobile();
            }}
          >
            <span aria-hidden="true">＋</span> New Chat
          </button>
        </div>

        <nav className="sidebar-nav">
          <button
            type="button"
            className={`nav-tab-btn ${activeView === "chat" ? "active" : ""}`}
            onClick={() => {
              onSelectView("chat");
              onCloseMobile && onCloseMobile();
            }}
          >
            <span className="nav-icon" aria-hidden="true">💬</span>
            <span>AI Assistant</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === "documents" ? "active" : ""}`}
            onClick={() => {
              onSelectView("documents");
              onCloseMobile && onCloseMobile();
            }}
          >
            <span className="nav-icon" aria-hidden="true">📁</span>
            <span>Knowledge Documents</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === "placements" ? "active" : ""}`}
            onClick={() => {
              onSelectView("placements");
              onCloseMobile && onCloseMobile();
            }}
          >
            <span className="nav-icon" aria-hidden="true">🎓</span>
            <span>Placement Intelligence</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === "profile" ? "active" : ""}`}
            onClick={() => {
              onSelectView("profile");
              onCloseMobile && onCloseMobile();
            }}
          >
            <span className="nav-icon" aria-hidden="true">👤</span>
            <span>Profile & Portfolio</span>
          </button>
        </nav>

        <div className="sidebar-conversations-section">
          <div className="conversations-header">
            <span className="conversations-label">Recent Conversations</span>
          </div>

          <div className="conversations-scroll">
            {conversations.length === 0 ? (
              <p className="no-conversations-hint">No past chats yet</p>
            ) : (
              conversations.map((conv) => {
                const isActive = activeConversationId === conv.id;
                return (
                  <div
                    key={conv.id}
                    className={`conversation-item ${isActive ? "active" : ""}`}
                  >
                    <button
                      type="button"
                      className="conversation-title-btn"
                      onClick={() => {
                        onSelectConversation(conv.id);
                        onSelectView("chat");
                        onCloseMobile && onCloseMobile();
                      }}
                      title={conv.title}
                    >
                      <span className="conv-icon" aria-hidden="true">💭</span>
                      <span className="conv-title-text">{conv.title}</span>
                    </button>

                    <button
                      type="button"
                      className="conv-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      title="Delete conversation"
                      aria-label={`Delete ${conv.title}`}
                    >
                      ✕
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="provider-status-badge">
            <span
              className={`status-dot ${providerInfo?.healthy ? "green" : "orange"}`}
              aria-hidden="true"
            />
            <span className="provider-name">
              LLM: {providerInfo?.provider || "Connecting..."}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}

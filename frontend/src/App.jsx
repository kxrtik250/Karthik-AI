import { useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import ChatView from "./components/chat/ChatView";
import DocumentsView from "./components/documents/DocumentsView";
import PlacementsView from "./components/placements/PlacementsView";
import ProfileView from "./components/profile/ProfileView";
import { useConversations } from "./hooks/useConversations";
import { useChat } from "./hooks/useChat";
import { useDocuments } from "./hooks/useDocuments";
import { usePlacements } from "./hooks/usePlacements";
import { useProfile } from "./hooks/useProfile";
import "./App.css";

export default function App() {
  const [activeView, setActiveView] = useState("chat");
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Conversations state
  const {
    conversations,
    activeConversationId,
    setActiveConversationId,
    startNewChat,
    selectConversation,
    deleteConversation,
    loadConversations,
  } = useConversations();

  // Chat state
  const {
    messages,
    isLoading: isChatLoading,
    error: chatError,
    sendMessage,
    clearError: clearChatError,
  } = useChat(activeConversationId, (newConversationId) => {
    setActiveConversationId(newConversationId);
    loadConversations();
  });

  // Documents state
  const {
    documents,
    isLoading: isDocsLoading,
    isUploading: isDocsUploading,
    isDeletingId: isDocDeletingId,
    error: docsError,
    uploadFile,
    deleteDocument,
    clearError: clearDocsError,
  } = useDocuments();

  // Placements state
  const {
    openDrives,
    priorities,
    upcomingDrives,
    isLoading: isPlacementsLoading,
    error: placementsError,
    refresh: refreshPlacements,
    selectedComparison,
    isComparing,
    loadComparison,
    preparationPlan,
    isGeneratingPlan,
    generatePlan,
    closeModals: closePlacementModals,
  } = usePlacements();

  // Profile, Skills & Projects state
  const {
    profile,
    skills,
    projects,
    isLoading: isProfileLoading,
    error: profileError,
    successMessage: profileSuccess,
    addSkill,
    editSkill,
    removeSkill,
    addProject,
    editProject,
    removeProject,
    clearError: clearProfileError,
    clearSuccess: clearProfileSuccess,
  } = useProfile();

  const activeConversation = conversations.find((c) => c.id === activeConversationId);

  return (
    <div className="app-layout">
      {/* Mobile Top Bar */}
      <header className="mobile-header">
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={() => setIsMobileSidebarOpen(true)}
          aria-label="Open navigation menu"
        >
          ☰
        </button>
        <span className="mobile-brand">Karthik AI</span>
      </header>

      {/* Sidebar */}
      <Sidebar
        activeView={activeView}
        onSelectView={(view) => setActiveView(view)}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={(id) => selectConversation(id)}
        onNewChat={() => startNewChat()}
        onDeleteConversation={(id) => deleteConversation(id)}
        isOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <main className="app-main-content">
        {activeView === "chat" ? (
          <ChatView
            messages={messages}
            isLoading={isChatLoading}
            error={chatError}
            onSendMessage={sendMessage}
            activeConversation={activeConversation}
            onClearError={clearChatError}
          />
        ) : activeView === "documents" ? (
          <DocumentsView
            documents={documents}
            isLoading={isDocsLoading}
            isUploading={isDocsUploading}
            uploadError={docsError}
            onUpload={uploadFile}
            onDelete={deleteDocument}
            isDeletingId={isDocDeletingId}
            onClearError={clearDocsError}
          />
        ) : activeView === "placements" ? (
          <PlacementsView
            openDrives={openDrives}
            priorities={priorities}
            upcomingDrives={upcomingDrives}
            isLoading={isPlacementsLoading}
            error={placementsError}
            onRefresh={refreshPlacements}
            selectedComparison={selectedComparison}
            isComparing={isComparing}
            onLoadComparison={loadComparison}
            preparationPlan={preparationPlan}
            isGeneratingPlan={isGeneratingPlan}
            onGeneratePlan={generatePlan}
            onCloseModals={closePlacementModals}
            documents={documents}
          />
        ) : (
          <ProfileView
            profile={profile}
            skills={skills}
            projects={projects}
            isLoading={isProfileLoading}
            error={profileError}
            successMessage={profileSuccess}
            onAddSkill={addSkill}
            onEditSkill={editSkill}
            onRemoveSkill={removeSkill}
            onAddProject={addProject}
            onEditProject={editProject}
            onRemoveProject={removeProject}
            onClearError={clearProfileError}
            onClearSuccess={clearProfileSuccess}
          />
        )}
      </main>
    </div>
  );
}

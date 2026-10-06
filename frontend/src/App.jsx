import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [backendStatus, setBackendStatus] = useState("checking...");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data) => setBackendStatus(data.status))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Karthik AI</h1>
        <p className="subtitle">Personal AI Assistant</p>
      </header>
      <main className="app-main">
        <div className="status-card">
          <h2>System Status</h2>
          <p>
            Backend:{" "}
            <span className={`status-badge ${backendStatus === "healthy" ? "green" : "red"}`}>
              {backendStatus}
            </span>
          </p>
        </div>
        <p className="phase-note">Phase 1 — Foundation scaffold is running.</p>
      </main>
    </div>
  );
}

export default App;

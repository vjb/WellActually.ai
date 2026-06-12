import React, { useState, useEffect, useRef } from "react";

function App() {
  const [status, setStatus] = useState("IDLE");
  const [prId, setPrId] = useState("PR-104");
  const [diffFiles, setDiffFiles] = useState([]);
  const [triageResult, setTriageResult] = useState(null);
  const [consensusRound, setConsensusRound] = useState(0);
  const [roomId, setRoomId] = useState(null);
  const [currentCode, setCurrentCode] = useState(null);
  const [schemaCheck, setSchemaCheck] = useState(null);
  const [openapiCheck, setOpenapiCheck] = useState(null);
  
  const [events, setEvents] = useState([]);
  const [watchdogLogs, setWatchdogLogs] = useState([]);
  const [activeTab, setActiveTab] = useState("debate"); // "debate" or "code" or "logs"
  const [isStarting, setIsStarting] = useState(false);
  
  const debateEndRef = useRef(null);

  // Poll server state
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const resStatus = await fetch("http://localhost:8000/api/status");
        if (resStatus.ok) {
          const data = await resStatus.json();
          setStatus(data.status);
          setPrId(data.pr_id);
          setDiffFiles(data.diff_files || []);
          setTriageResult(data.triage_result);
          setConsensusRound(data.consensus_round);
          setRoomId(data.room_id);
          setCurrentCode(data.current_code);
          setSchemaCheck(data.schema_check);
          setOpenapiCheck(data.openapi_check);
        }

        const resEvents = await fetch("http://localhost:8000/api/events");
        if (resEvents.ok) {
          const data = await resEvents.json();
          setEvents(data);
        }
      } catch (err) {
        console.error("Failed to connect to backend api:", err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Fetch telemetry anomalies on mount
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/telemetry");
        if (res.ok) {
          const data = await res.json();
          setWatchdogLogs(data);
        }
      } catch (err) {
        console.error("Failed to fetch telemetry:", err);
      }
    };
    fetchTelemetry();
  }, [status]);

  // Scroll to bottom of debate chat
  useEffect(() => {
    if (debateEndRef.current) {
      debateEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [events]);

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await fetch("http://localhost:8000/api/start", { method: "POST" });
    } catch (err) {
      console.error("Error starting simulation:", err);
    }
    setIsStarting(false);
  };

  const handleConsent = async (approve) => {
    try {
      await fetch("http://localhost:8000/api/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approve })
      });
    } catch (err) {
      console.error("Error submitting consent:", err);
    }
  };

  const getStatusColor = (s) => {
    switch (s) {
      case "IDLE": return "rgba(156, 163, 175, 0.2)";
      case "TRIAGE": return "rgba(234, 179, 8, 0.2)";
      case "PENDING_HUMAN_APPROVAL": return "rgba(239, 68, 68, 0.3)";
      case "RUNNING": return "rgba(34, 197, 94, 0.2)";
      case "HALTED": return "rgba(239, 68, 68, 0.2)";
      case "COMPLETED": return "rgba(59, 130, 246, 0.2)";
      case "CRASHED": return "rgba(220, 38, 38, 0.4)";
      default: return "rgba(156, 163, 175, 0.2)";
    }
  };

  const getStatusBorder = (s) => {
    switch (s) {
      case "IDLE": return "rgba(156, 163, 175, 0.4)";
      case "TRIAGE": return "rgba(234, 179, 8, 0.6)";
      case "PENDING_HUMAN_APPROVAL": return "rgba(239, 68, 68, 0.8)";
      case "RUNNING": return "rgba(34, 197, 94, 0.6)";
      case "HALTED": return "rgba(239, 68, 68, 0.6)";
      case "COMPLETED": return "rgba(59, 130, 246, 0.6)";
      case "CRASHED": return "rgba(220, 38, 38, 0.8)";
      default: return "rgba(156, 163, 175, 0.4)";
    }
  };

  const getSenderColor = (sender) => {
    if (!sender) return "rgba(255,255,255,0.7)";
    if (sender.includes("conductor")) return "#3b82f6"; // Orchestrator blue
    if (sender.includes("coder")) return "#22c55e"; // Coder green
    if (sender.includes("reviewer-auth") || sender.includes("coder-b2a5")) return "#a855f7"; // Auth SME purple
    if (sender.includes("reviewer-cart") || sender.includes("conductor-b2a5")) return "#eab308"; // Cart SME yellow
    return "rgba(255,255,255,0.8)";
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", padding: "2rem" }}>
      {/* Header Panel */}
      <header className="glass-panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "1.8rem", fontWeight: "bold", background: "linear-gradient(to right, #06b6d4, #a855f7)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            WellActually.ai
          </h1>
          <p style={{ margin: "0.25rem 0 0 0", color: "#9ca3af", fontSize: "0.9rem" }}>
            Domain-Driven Adversarial Code Review Swarm Center
          </p>
        </div>
        
        <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
          {status === "RUNNING" && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="pulse" style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#22c55e" }}></span>
              <span style={{ fontSize: "0.85rem", color: "#10b981" }}>Live Debate Active</span>
            </div>
          )}
          
          <div style={{
            padding: "0.5rem 1rem",
            borderRadius: "6px",
            backgroundColor: getStatusColor(status),
            border: `1px solid ${getStatusBorder(status)}`,
            fontSize: "0.9rem",
            fontWeight: "bold",
            letterSpacing: "0.05em"
          }}>
            {status}
          </div>
          
          <button
            onClick={handleStart}
            disabled={status === "RUNNING" || status === "TRIAGE" || isStarting}
            className="glass-panel"
            style={{
              padding: "0.5rem 1.5rem",
              borderRadius: "6px",
              cursor: (status === "RUNNING" || status === "TRIAGE" || isStarting) ? "not-allowed" : "pointer",
              fontWeight: "bold",
              background: "linear-gradient(135deg, #0891b2, #7c3aed)",
              border: "none",
              color: "white",
              transition: "transform 0.1s"
            }}
            onMouseDown={(e) => e.target.style.transform = "scale(0.98)"}
            onMouseUp={(e) => e.target.style.transform = "scale(1)"}
          >
            {isStarting ? "Dispatching..." : "Start Swarm Review"}
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "2rem", flex: 1 }}>
        {/* Left Column: Triage, MCP and Watchdog Metrics */}
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          
          {/* PR Information & Triage card */}
          <section className={`glass-panel ${status === "PENDING_HUMAN_APPROVAL" ? "glow-red" : ""}`}>
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              Pull Request compliance details
            </h2>
            
            <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "0.75rem", fontSize: "0.9rem", color: "#d1d5db" }}>
              <span style={{ color: "#9ca3af" }}>Target PR:</span>
              <span style={{ fontWeight: "bold" }}>{prId}</span>
              
              <span style={{ color: "#9ca3af" }}>Branch:</span>
              <code>codeband/branch-pr-104</code>
              
              <span style={{ color: "#9ca3af" }}>Modified:</span>
              <span style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                {diffFiles.map((f, i) => (
                  <code key={i} style={{ color: "#f472b6" }}>{f}</code>
                ))}
              </span>
            </div>

            {triageResult && (
              <div style={{ marginTop: "1rem", padding: "0.75rem", borderRadius: "6px", backgroundColor: "rgba(0,0,0,0.2)", fontSize: "0.85rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <span style={{ color: "#9ca3af" }}>Compliance Triage:</span>
                  <span style={{ fontWeight: "bold", color: triageResult.is_high_stakes ? "#ef4444" : "#10b981" }}>
                    {triageResult.is_high_stakes ? "High Stakes Match" : "Compliant Path"}
                  </span>
                </div>
                <div style={{ color: "#9ca3af" }}>Required Approvals:</div>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem" }}>
                  {triageResult.required_approvals.map((appr, idx) => (
                    <span key={idx} style={{ padding: "0.2rem 0.5rem", borderRadius: "4px", backgroundColor: "rgba(244,114,182,0.15)", border: "1px solid rgba(244,114,182,0.3)", color: "#f472b6", fontSize: "0.8rem" }}>
                      {appr}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Manual Human Consent Action Bar */}
            {status === "PENDING_HUMAN_APPROVAL" && (
              <div style={{ marginTop: "1.5rem", padding: "1rem", borderRadius: "8px", border: "1px solid rgba(239, 68, 68, 0.4)", backgroundColor: "rgba(239, 68, 68, 0.05)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#ef4444", fontWeight: "bold", fontSize: "0.95rem", marginBottom: "0.5rem" }}>
                  <span className="pulse" style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#ef4444" }}></span>
                  Attention: Human approval required to bypass Zero-Trust check
                </div>
                <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#d1d5db" }}>
                  Modifications are touching security/billing directories. Bypassing automatic auto-merge pipeline requires manual consent.
                </p>
                <div style={{ display: "flex", gap: "1rem" }}>
                  <button
                    onClick={() => handleConsent(true)}
                    style={{ flex: 1, padding: "0.5rem 1rem", borderRadius: "6px", backgroundColor: "#dc2626", border: "none", color: "white", fontWeight: "bold", cursor: "pointer" }}
                  >
                    Approve Exception
                  </button>
                  <button
                    onClick={() => handleConsent(false)}
                    style={{ flex: 1, padding: "0.5rem 1rem", borderRadius: "6px", backgroundColor: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "white", fontWeight: "bold", cursor: "pointer" }}
                  >
                    Reject PR
                  </button>
                </div>
              </div>
            )}

            {/* Deadlock Human Consent Action Bar */}
            {status === "HALTED" && (
              <div style={{ marginTop: "1.5rem", padding: "1rem", borderRadius: "8px", border: "1px solid rgba(239, 68, 68, 0.4)", backgroundColor: "rgba(239, 68, 68, 0.05)" }}>
                <div style={{ color: "#ef4444", fontWeight: "bold", fontSize: "0.95rem", marginBottom: "0.5rem" }}>
                  ⚠️ Consensus Deadlock Intervention
                </div>
                <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#d1d5db" }}>
                  Coder agent is stubborn and continues schema violations. Please intervene.
                </p>
                <div style={{ display: "flex", gap: "1rem" }}>
                  <button
                    onClick={() => handleConsent(true)}
                    style={{ flex: 1, padding: "0.5rem 1rem", borderRadius: "6px", backgroundColor: "#2563eb", border: "none", color: "white", fontWeight: "bold", cursor: "pointer" }}
                  >
                    Override & Approve PR
                  </button>
                  <button
                    onClick={() => handleConsent(false)}
                    style={{ flex: 1, padding: "0.5rem 1rem", borderRadius: "6px", backgroundColor: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "white", fontWeight: "bold", cursor: "pointer" }}
                  >
                    Reject PR
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Static Context Checker Panel */}
          <section className="glass-panel">
            <h2 style={{ margin: "0 0 1.25rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              Static Bounded Context (MCP) checkers
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {/* Postgres check */}
              <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                <div style={{ fontSize: "1.5rem" }}>
                  {schemaCheck === null ? "⏳" : schemaCheck.compliant ? "✅" : "❌"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: schemaCheck && !schemaCheck.compliant ? "#ef4444" : "#f3f4f6" }}>
                    PostgreSQL Bounded Context Check
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                    Target: Postgres Table <code>cart_items</code>
                  </div>
                  {schemaCheck && !schemaCheck.compliant && (
                    <div style={{ fontSize: "0.75rem", color: "#ef4444", marginTop: "0.5rem", fontFamily: "monospace", backgroundColor: "rgba(239,68,68,0.1)", padding: "0.5rem", borderRadius: "4px" }}>
                      {schemaCheck.violations.join("\n")}
                    </div>
                  )}
                </div>
              </div>

              {/* OpenAPI check */}
              <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                <div style={{ fontSize: "1.5rem" }}>
                  {openapiCheck === null ? "⏳" : openapiCheck.compliant ? "✅" : "❌"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: openapiCheck && !openapiCheck.compliant ? "#ef4444" : "#f3f4f6" }}>
                    OpenAPI contract check
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                    Target: Checkout REST Endpoint <code>/api/v1/checkout</code>
                  </div>
                  {openapiCheck && !openapiCheck.compliant && (
                    <div style={{ fontSize: "0.75rem", color: "#ef4444", marginTop: "0.5rem", fontFamily: "monospace", backgroundColor: "rgba(239,68,68,0.1)", padding: "0.5rem", borderRadius: "4px" }}>
                      {openapiCheck.violations.join("\n")}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Telemetry watchdog Alerts */}
          <section className="glass-panel">
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              Context-Aware Telemetry watchdog
            </h2>

            {watchdogLogs.length === 0 ? (
              <p style={{ margin: 0, fontSize: "0.85rem", color: "#9ca3af", fontStyle: "italic" }}>
                No active anomalies scanned in telemetry stream.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {watchdogLogs.map((log, idx) => (
                  <div key={idx} style={{ padding: "0.75rem", borderRadius: "6px", backgroundColor: "rgba(239, 68, 68, 0.08)", borderLeft: "4px solid #ef4444" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", fontWeight: "bold", color: "#f3f4f6" }}>
                      <span>🚨 {log.service}</span>
                      <span style={{ color: "#ef4444" }}>{log.level}</span>
                    </div>
                    <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem", color: "#d1d5db" }}>
                      {log.message}
                    </p>
                    <div style={{ fontSize: "0.7rem", color: "#9ca3af", marginTop: "0.25rem", textAlign: "right" }}>
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

        </div>

        {/* Right Column: Live feed panel */}
        <section className="glass-panel" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 10rem)", minHeight: "500px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
            <div style={{ display: "flex", gap: "1rem" }}>
              <button
                onClick={() => setActiveTab("debate")}
                style={{
                  background: "none",
                  border: "none",
                  color: activeTab === "debate" ? "#06b6d4" : "#9ca3af",
                  fontWeight: "bold",
                  cursor: "pointer",
                  fontSize: "1rem",
                  borderBottom: activeTab === "debate" ? "2px solid #06b6d4" : "none",
                  paddingBottom: "0.5rem"
                }}
              >
                Swarm Debate Room Feed
              </button>
              <button
                onClick={() => setActiveTab("code")}
                style={{
                  background: "none",
                  border: "none",
                  color: activeTab === "code" ? "#06b6d4" : "#9ca3af",
                  fontWeight: "bold",
                  cursor: "pointer",
                  fontSize: "1rem",
                  borderBottom: activeTab === "code" ? "2px solid #06b6d4" : "none",
                  paddingBottom: "0.5rem"
                }}
              >
                Proposed Implementation
              </button>
            </div>
            
            {roomId && (
              <span style={{ fontSize: "0.8rem", color: "#9ca3af" }}>
                Room ID: <code>{roomId.substring(0, 8)}...</code>
              </span>
            )}
          </div>

          {activeTab === "debate" ? (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "1rem", paddingRight: "0.5rem" }}>
              {events.length === 0 ? (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontStyle: "italic", fontSize: "0.95rem" }}>
                  Swarm Room inactive. Press Start to initiate.
                </div>
              ) : (
                events.map((evt, idx) => {
                  const isAgent = evt.sender !== "SYSTEM" && evt.sender !== "TriageScanner" && evt.sender !== "TelemetryScanner" && evt.sender !== "WatchdogDaemon";
                  return (
                    <div
                      key={idx}
                      style={{
                        padding: "0.75rem",
                        borderRadius: "8px",
                        backgroundColor: isAgent ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.15)",
                        border: isAgent ? `1px solid rgba(255,255,255,0.05)` : "1px dashed rgba(255,255,255,0.02)",
                        borderLeft: isAgent ? `4px solid ${getSenderColor(evt.sender)}` : "none"
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                        <span style={{ fontWeight: "bold", color: getSenderColor(evt.sender), fontSize: "0.85rem" }}>
                          {evt.sender} {evt.role !== "SYSTEM" && `(${evt.role})`}
                        </span>
                        {evt.sender.includes("reviewer-auth") && (
                          <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(168,85,247,0.15)", color: "#a855f7", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                            Featherless: Llama-3-70B
                          </span>
                        )}
                      </div>
                      
                      {evt.message.includes("def ") ? (
                        <pre style={{ margin: "0.5rem 0 0 0", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#04060a", overflowX: "auto", fontFamily: "monospace", fontSize: "0.8rem", color: "#a78bfa" }}>
                          {evt.message}
                        </pre>
                      ) : (
                        <p style={{ margin: 0, fontSize: "0.85rem", color: "#e5e7eb", whiteSpace: "pre-wrap" }}>
                          {evt.message}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
              <div ref={debateEndRef} />
            </div>
          ) : (
            <div style={{ flex: 1, overflow: "auto", backgroundColor: "#04060a", borderRadius: "8px", padding: "1rem" }}>
              {currentCode ? (
                <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.85rem", color: "#a78bfa", whiteSpace: "pre-wrap" }}>
                  {currentCode}
                </pre>
              ) : (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontStyle: "italic", fontSize: "0.95rem" }}>
                  No code proposed in current session.
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;

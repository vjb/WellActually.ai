import React, { useState, useEffect, useRef, useMemo } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 1000;

// Lightweight Python syntax highlighter
function highlightPython(code) {
  if (!code) return null;
  const keywords = new Set(['def', 'class', 'import', 'from', 'return', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'raise', 'pass', 'break', 'continue', 'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False', 'lambda', 'yield', 'async', 'await', 'global', 'nonlocal', 'del', 'assert']);
  const builtins = new Set(['print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'type', 'isinstance', 'getattr', 'setattr', 'hasattr', 'super', 'open', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'any', 'all', 'min', 'max', 'sum', 'abs', 'round', 'format', 'input', 'id', 'hex', 'oct', 'bin', 'chr', 'ord', 'repr', 'hash', 'next', 'iter', 'object', 'property', 'staticmethod', 'classmethod', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError', 'Exception', 'RuntimeError', 'StopIteration', 'NotImplementedError']);
  
  // Tokenize with regex
  const tokenPattern = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"])*"|'(?:\\.|[^'])*')|(#[^\n]*)|(\b\d+\.?\d*\b)|(@\w+)|(\b(?:def|class)\s+)(\w+)|(\b\w+(?=\s*\())|([\w]+)/g;
  
  const spans = [];
  let lastIndex = 0;
  let match;
  
  while ((match = tokenPattern.exec(code)) !== null) {
    // Add any text between matches as plain
    if (match.index > lastIndex) {
      spans.push({ text: code.slice(lastIndex, match.index), color: '#e5e7eb' });
    }
    
    if (match[1]) { // Strings
      spans.push({ text: match[0], color: '#a3e635' });
    } else if (match[2]) { // Comments
      spans.push({ text: match[0], color: '#6b7280', italic: true });
    } else if (match[3]) { // Numbers
      spans.push({ text: match[0], color: '#fb923c' });
    } else if (match[4]) { // Decorators
      spans.push({ text: match[0], color: '#fbbf24' });
    } else if (match[5]) { // def/class keyword followed by name
      spans.push({ text: match[5], color: '#c084fc' });
      spans.push({ text: match[6], color: '#67e8f9' });
    } else if (match[7]) { // Function calls
      if (builtins.has(match[7])) {
        spans.push({ text: match[0], color: '#67e8f9' });
      } else {
        spans.push({ text: match[0], color: '#93c5fd' });
      }
    } else if (match[8]) { // Words
      if (keywords.has(match[8])) {
        spans.push({ text: match[0], color: '#c084fc', bold: true });
      } else if (builtins.has(match[8])) {
        spans.push({ text: match[0], color: '#67e8f9' });
      } else {
        spans.push({ text: match[0], color: '#e5e7eb' });
      }
    } else {
      spans.push({ text: match[0], color: '#e5e7eb' });
    }
    lastIndex = match.index + match[0].length;
  }
  
  // Trailing text
  if (lastIndex < code.length) {
    spans.push({ text: code.slice(lastIndex), color: '#e5e7eb' });
  }
  
  return spans.map((s, i) => (
    React.createElement('span', {
      key: i,
      style: {
        color: s.color,
        fontWeight: s.bold ? 'bold' : 'normal',
        fontStyle: s.italic ? 'italic' : 'normal'
      }
    }, s.text)
  ));
}

function HighlightedCode({ code }) {
  const highlighted = useMemo(() => highlightPython(code), [code]);
  return React.createElement('pre', {
    style: {
      margin: '0.5rem 0 0 0',
      padding: '0.75rem',
      borderRadius: '6px',
      backgroundColor: '#0a0c12',
      overflowX: 'auto',
      fontFamily: "'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace",
      fontSize: '0.82rem',
      lineHeight: '1.6',
      border: '1px solid rgba(255,255,255,0.06)'
    }
  }, highlighted);
}

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
  const [mcpTargetsFromServer, setMcpTargetsFromServer] = useState(null);
  const [rbacCheck, setRbacCheck] = useState(null);
  const [initialSchemaCheck, setInitialSchemaCheck] = useState(null);
  const [initialOpenapiCheck, setInitialOpenapiCheck] = useState(null);
  const [initialRbacCheck, setInitialRbacCheck] = useState(null);
  const [resolutionType, setResolutionType] = useState(null);
  
  const [events, setEvents] = useState([]);
  const [watchdogLogs, setWatchdogLogs] = useState([]);
  const [activeTab, setActiveTab] = useState("debate"); // "debate" or "code"
  const [isStarting, setIsStarting] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const [debateSummary, setDebateSummary] = useState(null);
  const [selectedScenario, setSelectedScenario] = useState("rbac_bypass");
  const [scenarioFromServer, setScenarioFromServer] = useState("rbac_bypass");

  const cleanSenderName = (sender, role) => {
    if (!sender) return sender;
    // For agent messages, prefer the role as the display name
    if (role && role !== "SYSTEM") return role;
    // Strip hash suffixes like '-7c6144ef' from agent names
    let clean = sender.replace(/-[a-f0-9]{6,}$/i, '');
    // Clean reviewer internal names: "reviewer-auth_and_fraud_sme" -> readable form
    if (clean.startsWith('reviewer-')) {
      clean = clean.replace('reviewer-', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()).replace(' And ', ' & ');
    }
    return clean;
  };

  // Strip identity leaks from LLM responses (e.g. "[reviewer-cart_sme-ab8ff0d4 (Cart SME)]: ")
  const cleanMessageText = (text) => {
    if (!text) return text;
    return text.replace(/^\[.*?\]:\s*/i, '');
  };

  // MCP targets: prefer server data, fallback to scenario-based defaults
  const mcpTargets = mcpTargetsFromServer 
    ? { table: mcpTargetsFromServer.schema_table, endpoint: mcpTargetsFromServer.api_endpoint }
    : scenarioFromServer === "rbac_bypass" 
      ? { table: "billing_profiles", endpoint: "/api/v1/billing/spending" }
      : { table: "cart_items", endpoint: "/api/v1/checkout" };

  // MCP display: show latest check results to tell the self-healing story
  const displaySchemaCheck = schemaCheck || initialSchemaCheck;
  const displayOpenapiCheck = openapiCheck || initialOpenapiCheck;
  const displayRbacCheck = rbacCheck || initialRbacCheck;

  
  const chatContainerRef = useRef(null);
  const leftColumnRef = useRef(null);
  const [showBackToTop, setShowBackToTop] = useState(false);

  // Poll server state
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const resStatus = await fetch(`${API_BASE}/api/status`);
        if (resStatus.ok) {
          setBackendOnline(true);
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
          setRbacCheck(data.rbac_check);
          setDebateSummary(data.debate_summary);
          setScenarioFromServer(data.scenario);
          setMcpTargetsFromServer(data.mcp_targets);
          setInitialSchemaCheck(data.initial_schema_check);
          setInitialOpenapiCheck(data.initial_openapi_check);
          setInitialRbacCheck(data.initial_rbac_check);
          setResolutionType(data.resolution_type);
        }

        const resEvents = await fetch(`${API_BASE}/api/events`);
        if (resEvents.ok) {
          const data = await resEvents.json();
          setEvents(data);
        }
      } catch (err) {
        setBackendOnline(false);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  // Fetch telemetry anomalies on mount
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/telemetry`);
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

  // Scroll to bottom of debate chat only when a new message arrives
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [events.length]);

  // Show back-to-top button when page is scrolled down
  useEffect(() => {
    const handleScroll = () => setShowBackToTop(window.scrollY > 300);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Clear isStarting when status changes away from IDLE
  useEffect(() => {
    if (status !== 'IDLE') setIsStarting(false);
  }, [status]);

  const handleStart = async () => {
    setIsStarting(true);
    try {
      const res = await fetch(`${API_BASE}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: selectedScenario })
      });
      if (!res.ok) {
        const errText = await res.text();
        console.error("Failed to start:", errText);
      }
    } catch (err) {
      console.error("Error starting simulation:", err);
    }
  };

  const handleConsent = async (approve) => {
    try {
      await fetch(`${API_BASE}/api/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approve })
      });
    } catch (err) {
      console.error("Error submitting consent:", err);
    }
  };

  const handleReset = async () => {
    try {
      await fetch(`${API_BASE}/api/reset`, { method: "POST" });
    } catch (err) {
      console.error("Error resetting state:", err);
    }
  };

  const canReset = !["IDLE", "RUNNING", "TRIAGE", "PENDING_HUMAN_APPROVAL"].includes(status);
  const canStart = ["IDLE", "COMPLETED", "HALTED", "CRASHED"].includes(status) && !isStarting;

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
    if (sender.includes("reviewer-auth")) return "#a855f7"; // Auth SME purple (Featherless)
    if (sender.includes("reviewer-cart")) return "#eab308"; // Cart SME yellow (AIML)
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
          {!backendOnline && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#ef4444" }}></span>
              <span style={{ fontSize: "0.85rem", color: "#ef4444", fontWeight: "bold" }}>Backend Offline</span>
            </div>
          )}
          {status === "RUNNING" && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="pulse" style={{ width: "10px", height: "10px", borderRadius: "50%", backgroundColor: "#22c55e" }}></span>
              <span style={{ fontSize: "0.85rem", color: "#10b981" }}>Live Debate Active</span>
              {consensusRound > 0 && (
                <span style={{ fontSize: "0.8rem", color: "#9ca3af", marginLeft: "0.25rem" }}>
                  — Round {consensusRound} of 2
                </span>
              )}
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
          
          <div
            style={{
              padding: "0.5rem 0.75rem",
              borderRadius: "6px",
              backgroundColor: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: "#e5e7eb",
              fontSize: "0.85rem",
              fontWeight: "500",
              letterSpacing: "0.02em",
            }}
          >
            Spending Report RBAC Bypass
          </div>
          
          <button
            onClick={handleStart}
            disabled={!canStart}
            className="glass-panel"
            style={{
              padding: "0.5rem 1.5rem",
              borderRadius: "6px",
              cursor: canStart ? "pointer" : "not-allowed",
              fontWeight: "bold",
              background: canStart ? "linear-gradient(135deg, #0891b2, #7c3aed)" : "rgba(55, 65, 81, 0.5)",
              border: "none",
              color: "white",
              transition: "transform 0.1s, opacity 0.2s",
              opacity: canStart ? 1 : 0.5
            }}

          >
            {isStarting ? "Dispatching..." : "Start Swarm Review"}
          </button>
          
          <button
            onClick={handleReset}
            disabled={!canReset}
            style={{
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              cursor: canReset ? "pointer" : "not-allowed",
              fontWeight: "bold",
              background: "none",
              border: canReset ? "1px solid rgba(239, 68, 68, 0.5)" : "1px solid rgba(255,255,255,0.1)",
              color: canReset ? "#f87171" : "rgba(255,255,255,0.25)",
              fontSize: "0.85rem",
              transition: "all 0.2s"
            }}
          >
            ↺ Reset
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <div className="main-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "2rem", flex: 1, minHeight: 0 }}>
        {/* Left Column: Triage, MCP and Watchdog Metrics */}
        <div
          ref={leftColumnRef}
          style={{ display: "flex", flexDirection: "column", gap: "2rem", overflowY: "auto", minHeight: 0, position: "relative" }}
        >
          
          {/* PR Information & Triage card */}
          <section className={`glass-panel ${status === "PENDING_HUMAN_APPROVAL" ? "glow-red" : ""}`}>
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              Pull Request compliance details
            </h2>
            
            <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "0.75rem", fontSize: "0.9rem", color: "#d1d5db" }}>
              <span style={{ color: "#9ca3af" }}>Target PR:</span>
              <span style={{ fontWeight: "bold" }}>{prId}</span>
              
              <span style={{ color: "#9ca3af" }}>Branch:</span>
              <code>codeband/branch-{prId?.toLowerCase()}</code>
              
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
            {status === "HALTED" && !resolutionType && (
              <div style={{ marginTop: "1.5rem", padding: "1rem", borderRadius: "8px", border: "1px solid rgba(239, 68, 68, 0.4)", backgroundColor: "rgba(239, 68, 68, 0.05)" }}>
                <div style={{ color: "#ef4444", fontWeight: "bold", fontSize: "0.95rem", marginBottom: "0.5rem" }}>
                  ⚠️ Consensus Deadlock Intervention
                </div>
                <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#d1d5db" }}>
                  Coder agent continues proposing changes that violate schema constraints despite reviewer feedback. Please intervene.
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
                  {displaySchemaCheck === null ? "⏳" : displaySchemaCheck.compliant ? "✅" : "❌"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: displaySchemaCheck && !displaySchemaCheck.compliant ? "#ef4444" : "#f3f4f6" }}>
                    PostgreSQL Bounded Context Check
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                    Target: Postgres Table <code>{mcpTargets.table}</code>
                  </div>
                  {displaySchemaCheck && !displaySchemaCheck.compliant && (
                    <div style={{ fontSize: "0.75rem", color: "#ef4444", marginTop: "0.5rem", fontFamily: "monospace", backgroundColor: "rgba(239,68,68,0.1)", padding: "0.5rem", borderRadius: "4px" }}>
                      {displaySchemaCheck.violations.join("\n")}
                    </div>
                  )}
                </div>
              </div>

              {/* OpenAPI check */}
              <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                <div style={{ fontSize: "1.5rem" }}>
                  {displayOpenapiCheck === null ? "⏳" : displayOpenapiCheck.compliant ? "✅" : "❌"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: displayOpenapiCheck && !displayOpenapiCheck.compliant ? "#ef4444" : "#f3f4f6" }}>
                    OpenAPI contract check
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                    Target: REST Endpoint <code>{mcpTargets.endpoint}</code>
                  </div>
                  {displayOpenapiCheck && !displayOpenapiCheck.compliant && (
                    <div style={{ fontSize: "0.75rem", color: "#ef4444", marginTop: "0.5rem", fontFamily: "monospace", backgroundColor: "rgba(239,68,68,0.1)", padding: "0.5rem", borderRadius: "4px" }}>
                      {displayOpenapiCheck.violations.join("\n")}
                    </div>
                  )}
                </div>
              </div>

              {/* RBAC Policy check */}
              <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                <div style={{ fontSize: "1.5rem" }}>
                  {displayRbacCheck === null ? "⏳" : displayRbacCheck.compliant ? "✅" : "❌"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: displayRbacCheck && !displayRbacCheck.compliant ? "#ef4444" : "#f3f4f6" }}>
                    RBAC Access Policy Check
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                    Target: {mcpTargetsFromServer?.rbac_target 
                      ? <><span>Sensitive Financial Column </span><code>{mcpTargetsFromServer.rbac_target}</code></>
                      : <><span>Access Policy Boundaries — </span><code>{mcpTargets.table}</code></>
                    }
                  </div>
                  {displayRbacCheck && !displayRbacCheck.compliant && (
                    <div style={{ fontSize: "0.75rem", color: "#ef4444", marginTop: "0.5rem", fontFamily: "monospace", backgroundColor: "rgba(239,68,68,0.1)", padding: "0.5rem", borderRadius: "4px" }}>
                      {displayRbacCheck.violations.join("\n")}
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

          {/* Post-Debate Summary Card (Fix #5) */}
          {debateSummary && (status === "HALTED" || status === "COMPLETED") && (
            <section className="glass-panel" style={{ borderLeft: "4px solid #22c55e" }}>
              <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#22c55e" }}>
                📊 Debate Summary
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
                <div style={{ backgroundColor: "rgba(255,255,255,0.03)", borderRadius: "8px", padding: "0.75rem", textAlign: "center" }}>
                  <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#f59e0b" }}>{debateSummary.total_rounds}</div>
                  <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Rounds</div>
                </div>
                <div style={{ backgroundColor: "rgba(255,255,255,0.03)", borderRadius: "8px", padding: "0.75rem", textAlign: "center" }}>
                  <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: debateSummary.is_deadlocked ? "#ef4444" : "#22c55e" }}>
                    {debateSummary.is_deadlocked ? "Deadlocked" : "Consensus"}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Outcome</div>
                </div>
                <div style={{ backgroundColor: "rgba(255,255,255,0.03)", borderRadius: "8px", padding: "0.75rem", textAlign: "center" }}>
                  <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#ef4444" }}>{debateSummary.rejections}</div>
                  <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Rejections</div>
                </div>
                <div style={{ backgroundColor: "rgba(255,255,255,0.03)", borderRadius: "8px", padding: "0.75rem", textAlign: "center" }}>
                  <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#22c55e" }}>{debateSummary.approvals}</div>
                  <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Approvals</div>
                </div>
              </div>

              {/* Per-Reviewer Breakdown */}
              {debateSummary.rejections_by_reviewer && Object.entries(debateSummary.rejections_by_reviewer).map(([name, info]) => (
                <div key={name} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "0.5rem 0.75rem", marginBottom: "0.4rem",
                  backgroundColor: "rgba(239, 68, 68, 0.05)", borderRadius: "6px",
                  border: "1px solid rgba(239, 68, 68, 0.15)"
                }}>
                  <div>
                    <span style={{ fontWeight: "bold", fontSize: "0.85rem", color: "#e5e7eb" }}>{info.role}</span>
                    <span style={{
                      fontSize: "0.65rem", marginLeft: "0.5rem",
                      backgroundColor: info.domain === "auth" ? "rgba(168,85,247,0.15)" : "rgba(6,182,212,0.15)",
                      color: info.domain === "auth" ? "#a855f7" : "#06b6d4",
                      padding: "0.1rem 0.4rem", borderRadius: "4px"
                    }}>
                      {info.domain === "auth" ? "Domain: Auth & Schema" : info.domain === "cart" ? "Domain: API Contract" : `Domain: ${info.domain}`}
                    </span>
                  </div>
                  <span style={{ color: "#ef4444", fontWeight: "bold", fontSize: "0.85rem" }}>
                    {info.count}× rejected
                  </span>
                </div>
              ))}

              {/* Resolution */}
              <div style={{
                marginTop: "0.75rem", padding: "0.5rem 0.75rem", borderRadius: "6px",
                backgroundColor: status === "COMPLETED" ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                border: `1px solid ${status === "COMPLETED" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`
              }}>
                <span style={{ fontSize: "0.8rem", color: status === "COMPLETED" ? "#22c55e" : "#ef4444" }}>
                  Resolution: {resolutionType === "consensus" 
                    ? "✓ Approved by Swarm Consensus" 
                    : resolutionType === "human_override" 
                      ? "✓ Approved (Human Override)" 
                      : resolutionType === "halted" 
                        ? "⚠️ Halted — PR Rejected"
                        : status === "COMPLETED"
                          ? (debateSummary?.is_deadlocked ? "✓ Approved (Human Override)" : "✓ Approved by Swarm Consensus")
                          : "⚠️ Halted — Awaiting HITL"}
                </span>
              </div>
            </section>
          )}

        </div>

        {/* Right Column: Live feed panel */}
        <section className="glass-panel" style={{ display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
            <div role="tablist" style={{ display: "flex", gap: "1rem" }}>
              <button
                onClick={() => setActiveTab("debate")}
                role="tab"
                aria-selected={activeTab === "debate"}
                style={{
                  background: "none",
                  border: "none",
                  color: activeTab === "debate" ? "#06b6d4" : "#9ca3af",
                  fontWeight: "bold",
                  cursor: "pointer",
                  fontSize: "1rem",
                  borderBottom: activeTab === "debate" ? "2px solid #06b6d4" : "2px solid transparent",
                  paddingBottom: "0.5rem"
                }}
              >
                Swarm Debate Room Feed
              </button>
              <button
                onClick={() => setActiveTab("code")}
                role="tab"
                aria-selected={activeTab === "code"}
                style={{
                  background: "none",
                  border: "none",
                  color: activeTab === "code" ? "#06b6d4" : "#9ca3af",
                  fontWeight: "bold",
                  cursor: "pointer",
                  fontSize: "1rem",
                  borderBottom: activeTab === "code" ? "2px solid #06b6d4" : "2px solid transparent",
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
            <div ref={chatContainerRef} style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "1rem", paddingRight: "0.5rem" }}>
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
                          {cleanSenderName(evt.sender, evt.role)} {evt.role !== "SYSTEM" && evt.role !== cleanSenderName(evt.sender, evt.role) && `(${evt.role})`}
                        </span>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                          {evt.sender.includes("reviewer-auth") && (
                            <>
                              <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(168,85,247,0.15)", color: "#a855f7", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                Featherless: Llama-3.1-70B
                              </span>
                              <span style={{ fontSize: "0.65rem", backgroundColor: "rgba(168,85,247,0.08)", color: "#c084fc", padding: "0.1rem 0.4rem", borderRadius: "4px", border: "1px solid rgba(168,85,247,0.2)" }}>
                                Domain: Auth & Schema
                              </span>
                            </>
                          )}
                          {evt.sender.includes("reviewer-cart") && (
                            <>
                              <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(6,182,212,0.15)", color: "#06b6d4", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                AIML: GPT-4o-mini
                              </span>
                              <span style={{ fontSize: "0.65rem", backgroundColor: "rgba(6,182,212,0.08)", color: "#67e8f9", padding: "0.1rem 0.4rem", borderRadius: "4px", border: "1px solid rgba(6,182,212,0.2)" }}>
                                Domain: API Contract
                              </span>
                            </>
                          )}
                          {(evt.sender.includes("coder") || evt.sender.includes("conductor")) && evt.role !== "SYSTEM" && (
                            <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(6,182,212,0.15)", color: "#06b6d4", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                              AIML: GPT-4o-mini
                            </span>
                          )}
                        </div>
                      </div>
                      
                      {(() => {
                        const msg = cleanMessageText(evt.message);
                        return (msg.includes("```") || (msg.includes("def ") && msg.includes(":"))) ? (
                          <HighlightedCode code={msg} />
                        ) : (
                          <p style={{ margin: 0, fontSize: "0.85rem", color: "#e5e7eb", whiteSpace: "pre-wrap" }}>
                            {msg}
                          </p>
                        );
                      })()}
                    </div>
                  );
                })
              )}
              {status === "RUNNING" && (
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.6rem",
                  padding: "0.75rem 1rem",
                  marginTop: "0.5rem",
                  borderRadius: "8px",
                  backgroundColor: "rgba(34, 197, 94, 0.05)",
                  border: "1px solid rgba(34, 197, 94, 0.15)"
                }}>
                  <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                    {[0, 1, 2].map(i => (
                      <span key={i} style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        backgroundColor: "#22c55e",
                        animation: `thinkingDot 1.4s ease-in-out ${i * 0.2}s infinite`
                      }} />
                    ))}
                  </div>
                  <span style={{ fontSize: "0.8rem", color: "#22c55e", fontStyle: "italic" }}>
                    Auth & Fraud SME + Cart SME reasoning via Band.ai room...
                  </span>
                </div>
              )}

            </div>
          ) : (
            <div style={{ flex: 1, overflow: "auto", backgroundColor: "#04060a", borderRadius: "8px", padding: "1rem" }}>
              {currentCode ? (
                <HighlightedCode code={currentCode} />
              ) : (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontStyle: "italic", fontSize: "0.95rem" }}>
                  No code proposed in current session.
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {/* Back to top button — fixed to viewport */}
      {showBackToTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="Back to top"
          style={{
            position: "fixed",
            bottom: "2rem",
            left: "2rem",
            width: "42px",
            height: "42px",
            borderRadius: "50%",
            border: "1px solid rgba(6, 182, 212, 0.5)",
            background: "rgba(6, 182, 212, 0.15)",
            backdropFilter: "blur(12px)",
            color: "#06b6d4",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "1.2rem",
            transition: "all 0.2s",
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            zIndex: 1000
          }}
          onMouseEnter={(e) => { e.target.style.background = "rgba(6, 182, 212, 0.3)"; e.target.style.transform = "scale(1.1)"; }}
          onMouseLeave={(e) => { e.target.style.background = "rgba(6, 182, 212, 0.15)"; e.target.style.transform = "scale(1)"; }}
        >
          ↑
        </button>
      )}
    </div>
  );
}

export default App;

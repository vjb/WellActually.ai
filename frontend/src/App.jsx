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


const getDomainIcon = (domain) => {
  switch (domain?.toLowerCase()) {
    case "security": return "🛡️";
    case "database": return "🗄️";
    case "documentation": return "📝";
    case "cart": return "🛒";
    case "billing": return "💳";
    case "api": return "🔌";
    case "qa": return "🧪";
    case "workflow": return "🔄";
    case "architecture": return "🏗️";
    default: return "🔍";
  }
};

function AgentTopology({ status, activeSender, reviewerAuthRole = "Auth & Fraud SME", reviewerCartRole = "Cart SME", reviewerAuthDomain = "auth", reviewerCartDomain = "cart", activeAgents = [], selectedPrDetails = null }) {
  const normalizeName = (name) => {
    if (!name) return "";
    return name
      .replace(/-[a-f0-9]{6,}$/i, '') // Strip suffix hash if any
      .replace(/[^a-zA-Z0-9]/g, '')    // Remove special characters
      .toLowerCase();
  };

  const getNodeColor = (agent) => {
    if (agent.id === "conductor") return "#3b82f6"; // Orchestrator blue
    if (agent.id === "coder") return "#22c55e"; // Coder green
    
    switch (agent.domain?.toLowerCase()) {
      case "auth": return "#a855f7"; // purple
      case "billing": return "#f97316"; // orange
      case "database": return "#6366f1"; // indigo
      case "security": return "#ef4444"; // red
      case "cart": return "#eab308"; // yellow
      case "api": return "#06b6d4"; // cyan
      case "qa": return "#ec4899"; // pink
      case "documentation": return "#10b981"; // emerald
      default: return "#8b5cf6"; // violet
    }
  };

  const agents = useMemo(() => {
    if (status !== "IDLE" && activeAgents && activeAgents.length > 0) {
      return activeAgents;
    }
    
    // Construct dynamic list during IDLE based on predicted reviewers
    const base = [
      { id: "conductor", name: "conductor", role: "Orchestrator", domain: "system", icon: "👑" },
      { id: "coder", name: "coder", role: "Coder", domain: "system", icon: "💻" }
    ];
    
    if (selectedPrDetails && selectedPrDetails.predicted_reviewers) {
      const reviewers = selectedPrDetails.predicted_reviewers.map((r, i) => ({
        id: `reviewer-${i}`,
        name: `reviewer-${r.domain}`,
        role: r.role,
        domain: r.domain,
        icon: getDomainIcon(r.domain)
      }));
      return [...base, ...reviewers];
    }
    
    // Default fallback (legacy 4-node setup)
    return [
      ...base,
      { id: "reviewer-0", name: "reviewer-auth", role: reviewerAuthRole, domain: reviewerAuthDomain, icon: getDomainIcon(reviewerAuthDomain) },
      { id: "reviewer-1", name: "reviewer-cart", role: reviewerCartRole, domain: reviewerCartDomain, icon: getDomainIcon(reviewerCartDomain) }
    ];
  }, [status, activeAgents, selectedPrDetails, reviewerAuthRole, reviewerCartRole, reviewerAuthDomain, reviewerCartDomain]);

  const nodes = useMemo(() => {
    const reviewers = agents.filter(a => a.id.startsWith("reviewer"));
    const N = reviewers.length;
    
    return agents.map(agent => {
      if (agent.id === "conductor") {
        return { ...agent, label: "Conductor", sub: agent.role || "Orchestrator", x: 200, y: 50 };
      }
      if (agent.id === "coder") {
        return { ...agent, label: "Coder", sub: agent.role || "Implementation", x: 80, y: 160 };
      }
      
      const i = reviewers.findIndex(r => r.id === agent.id);
      let x, y;
      if (N === 1) {
        x = 320;
        y = 160;
      } else {
        const angle = (-15 + i * (120 / (N - 1))) * Math.PI / 180;
        x = Math.round(200 + 115 * Math.cos(angle));
        y = Math.round(150 + 80 * Math.sin(angle));
      }
      
      const label = agent.role?.includes("SME") ? agent.role.split("SME")[0].trim() : (agent.role || `Reviewer ${i + 1}`);
      return { ...agent, label, sub: "SME", x, y };
    });
  }, [agents]);

  const getHighlightClass = (nodeId) => {
    if (!activeSender) return false;
    const normActive = normalizeName(activeSender);
    
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return false;
    
    if (node.id === "conductor") {
      return normActive.startsWith("conductor");
    }
    if (node.id === "coder") {
      return normActive.startsWith("coder");
    }
    
    const normNodeName = normalizeName(node.name);
    const normNodeRole = normalizeName(node.role);
    
    return normActive === normNodeName || 
           normActive === `reviewer${normNodeRole}` ||
           normActive.includes(normNodeName) ||
           (node.domain && normActive.includes(node.domain.toLowerCase()));
  };

  const lines = useMemo(() => {
    const conductorNode = nodes.find(n => n.id === "conductor");
    if (!conductorNode) return [];
    
    return nodes
      .filter(n => n.id !== "conductor")
      .map(n => {
        const isTargetActive = getHighlightClass(n.id);
        const isConductorActive = getHighlightClass("conductor");
        
        let stroke = "rgba(255,255,255,0.15)";
        let strokeWidth = 2;
        let strokeDasharray = "4 4";
        let className = "";
        
        if (isTargetActive) {
          strokeWidth = 2.5;
          className = "flow-line-active";
          stroke = getNodeColor(n);
          strokeDasharray = undefined;
        } else if (isConductorActive) {
          stroke = "#3b82f6";
          strokeWidth = 2.5;
          className = "flow-line-active";
          strokeDasharray = undefined;
        }
        
        return {
          id: `line-${n.id}`,
          x1: conductorNode.x,
          y1: conductorNode.y,
          x2: n.x,
          y2: n.y,
          stroke,
          strokeWidth,
          strokeDasharray,
          className
        };
      });
  }, [nodes, activeSender]);

  return (
    <section className="glass-panel" style={{ padding: "1.25rem", position: "relative" }}>
      <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
        🌐 Agent Swarm Topology Graph
      </h2>
      <svg width="100%" height="280" viewBox="0 0 400 280" style={{ overflow: "visible" }}>
        <defs>
          <filter id="glow-active" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        
        {/* Connections */}
        {lines.map(line => (
          <line
            key={line.id}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke={line.stroke}
            strokeWidth={line.strokeWidth}
            strokeDasharray={line.strokeDasharray}
            className={line.className}
          />
        ))}

        {nodes.map(n => {
          const active = getHighlightClass(n.id);
          return (
            <g key={n.id} style={{ cursor: "pointer" }}>
              {active && (
                <circle
                  cx={n.x}
                  cy={n.y}
                  r="32"
                  fill="none"
                  stroke={getNodeColor(n)}
                  strokeWidth="3"
                  filter="url(#glow-active)"
                  style={{
                    transformOrigin: `${n.x}px ${n.y}px`,
                    animation: "pulse-ring 1.8s cubic-bezier(0.215, 0.610, 0.355, 1) infinite"
                  }}
                />
              )}
              <circle
                cx={n.x}
                cy={n.y}
                r="26"
                fill="#0f172a"
                stroke={active ? getNodeColor(n) : "rgba(255, 255, 255, 0.2)"}
                strokeWidth={active ? "3" : "1.5"}
                style={{ transition: "all 0.3s" }}
              />
              <text x={n.x} y={n.y + 6} textAnchor="middle" fontSize="1.3rem">
                {n.icon}
              </text>
              <text x={n.x} y={n.y + 42} textAnchor="middle" fontSize="0.75rem" fontWeight="bold" fill={active ? "#f3f4f6" : "#9ca3af"}>
                {n.label}
              </text>
              <text x={n.x} y={n.y + 54} textAnchor="middle" fontSize="0.65rem" fill="#6b7280">
                {n.sub}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Live Status text below the SVG */}
      <div style={{ marginTop: "1rem", textAlign: "center", fontSize: "0.85rem", color: "#9ca3af", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "0.75rem" }}>
        {getHighlightClass("conductor") && <span>📢 <strong>Conductor Orchestrator</strong> is orchestrating the Task Room...</span>}
        {getHighlightClass("coder") && <span>💻 <strong>Lead Coder</strong> is proposing code adjustments...</span>}
        {nodes.filter(n => n.id.startsWith("reviewer")).map(n => 
          getHighlightClass(n.id) && (
            <span key={n.id}>
              {getDomainIcon(n.domain)} <strong>{n.label} ({n.role})</strong> is auditing compliance...
            </span>
          )
        )}
        {!getHighlightClass("conductor") && !getHighlightClass("coder") && !nodes.some(n => getHighlightClass(n.id)) && (() => {
          if (status === "TRIAGE") {
            return <span>🔍 Compliance Triage Gate in progress. Running codeowners checks...</span>;
          }
          if (status === "RUNNING") {
            return <span>⚡ Swarm Debate Active. Conductor, Coder, and Reviewers are communicating...</span>;
          }
          if (status === "COMPLETED") {
            return <span>✅ Swarm Review Completed successfully.</span>;
          }
          if (status === "HALTED") {
            return <span>⚠️ Swarm Halted. Pending administrator consensus intervention.</span>;
          }
          if (status === "CRASHED") {
            return <span>💥 Swarm Review CRASHED. Halted on system failure.</span>;
          }
          if (status === "PENDING_HUMAN_APPROVAL") {
            return <span>⏳ Compliance exception pending human operator approval.</span>;
          }
          return <span>💤 Swarm topology idle. Waiting for active debate rounds...</span>;
        })()}
      </div>
    </section>
  );
}

function SqlAstVisualizer({ checkedColumns }) {
  return (
    <section className="glass-panel">
      <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
        📊 SQL AST Column Mapping Visualizer
      </h2>
      {checkedColumns.length === 0 ? (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#9ca3af", fontStyle: "italic" }}>
          No columns checked yet. Start a scenario to view AST schema mapping.
        </p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", color: "#9ca3af" }}>
                <th style={{ padding: "0.5rem" }}>Table</th>
                <th style={{ padding: "0.5rem" }}>Column</th>
                <th style={{ padding: "0.5rem" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {checkedColumns.map((col, idx) => (
                <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", backgroundColor: idx % 2 === 0 ? "rgba(255,255,255,0.01)" : "transparent" }}>
                  <td style={{ padding: "0.5rem", fontFamily: "monospace", color: "#c084fc" }}>{col.table}</td>
                  <td style={{ padding: "0.5rem", fontFamily: "monospace", color: "#67e8f9" }}>{col.column}</td>
                  <td style={{ padding: "0.5rem" }}>
                    <span style={{
                      padding: "0.15rem 0.5rem",
                      borderRadius: "4px",
                      backgroundColor: col.compliant ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                      border: `1px solid ${col.compliant ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                      color: col.compliant ? "#22c55e" : "#ef4444",
                      fontWeight: "bold",
                      fontSize: "0.75rem"
                    }}>
                      {col.compliant ? "COMPLIANT" : "VIOLATED"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function TelemetryWatchdogChart({ logs }) {
  const warningCounts = [1, 2, 0, 1, 3, 2];
  const errorCounts = [0, 1, 0, 0, 1, 1];

  let actualWarnings = 0;
  let actualErrors = 0;
  if (logs && Array.isArray(logs)) {
    logs.forEach(l => {
      if (l.level === "WARNING") actualWarnings++;
      if (l.level === "ERROR") actualErrors++;
    });
  }

  warningCounts[5] = actualWarnings;
  errorCounts[5] = actualErrors;

  const width = 300;
  const height = 100;
  const maxVal = Math.max(...warningCounts, ...errorCounts, 4);

  const getPoints = (counts) => {
    return counts.map((c, i) => {
      const x = 10 + i * 56;
      const y = height - 10 - (c / maxVal) * 80;
      return `${x},${y}`;
    }).join(" ");
  };

  const warningPoints = getPoints(warningCounts);
  const errorPoints = getPoints(errorCounts);

  return (
    <div style={{ marginTop: "1rem", backgroundColor: "rgba(0,0,0,0.2)", borderRadius: "8px", padding: "0.75rem", border: "1px solid rgba(255,255,255,0.05)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <span style={{ fontSize: "0.8rem", color: "#e5e7eb", fontWeight: "bold" }}>📈 Telemetry Stream Rate</span>
        <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.7rem" }}>
          <span style={{ color: "#fb923c" }}>● Warnings ({actualWarnings})</span>
          <span style={{ color: "#ef4444" }}>● Errors ({actualErrors})</span>
        </div>
      </div>
      <svg width="100%" height="100" viewBox="0 0 320 100" style={{ overflow: "visible" }}>
        <line x1="10" y1="10" x2="300" y2="10" stroke="rgba(255,255,255,0.05)" />
        <line x1="10" y1="50" x2="300" y2="50" stroke="rgba(255,255,255,0.05)" />
        <line x1="10" y1="90" x2="300" y2="90" stroke="rgba(255,255,255,0.1)" />

        <polyline
          fill="none"
          stroke="#fb923c"
          strokeWidth="2.5"
          points={warningPoints}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <polyline
          fill="none"
          stroke="#ef4444"
          strokeWidth="2.5"
          points={errorPoints}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {warningCounts.map((c, i) => {
          const x = 10 + i * 56;
          const y = height - 10 - (c / maxVal) * 80;
          return <circle key={`w-${i}`} cx={x} cy={y} r="3.5" fill="#0f172a" stroke="#fb923c" strokeWidth="1.5" />;
        })}

        {errorCounts.map((c, i) => {
          const x = 10 + i * 56;
          const y = height - 10 - (c / maxVal) * 80;
          return <circle key={`e-${i}`} cx={x} cy={y} r="3.5" fill="#0f172a" stroke="#ef4444" strokeWidth="1.5" />;
        })}
      </svg>
    </div>
  );
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
  const [prDiff, setPrDiff] = useState(null);
  const [prTitle, setPrTitle] = useState("");
  const [prBranch, setPrBranch] = useState("");
  const [reviewerAuthRole, setReviewerAuthRole] = useState("Auth & Fraud SME");
  const [reviewerAuthDomain, setReviewerAuthDomain] = useState("auth");
  const [reviewerCartRole, setReviewerCartRole] = useState("Cart SME");
  const [reviewerCartDomain, setReviewerCartDomain] = useState("cart");
  const [activeAgents, setActiveAgents] = useState([]);
  
  const [events, setEvents] = useState([]);
  const [watchdogLogs, setWatchdogLogs] = useState([]);
  const [activeTab, setActiveTab] = useState("debate"); // "debate" or "code"
  const [isStarting, setIsStarting] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const [debateSummary, setDebateSummary] = useState(null);
  const [selectedScenario, setSelectedScenario] = useState("dynamic");
  const [scenarioFromServer, setScenarioFromServer] = useState("rbac_bypass");

  const [selectedRepo, setSelectedRepo] = useState("vjb/WellActually.ai");
  const [prsList, setPrsList] = useState([]);
  const [selectedPrNumber, setSelectedPrNumber] = useState("");
  const [selectedPrDetails, setSelectedPrDetails] = useState(null);
  const [isFetchingPrs, setIsFetchingPrs] = useState(false);
  const [isFetchingPrDetails, setIsFetchingPrDetails] = useState(false);
  const [githubFallback, setGithubFallback] = useState(false);
  const [githubErrorMsg, setGithubErrorMsg] = useState("");


  const fetchPRs = async (repoName) => {
    setIsFetchingPrs(true);
    setGithubFallback(false);
    setGithubErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/github/prs?repo=${encodeURIComponent(repoName)}`);
      if (res.ok) {
        const isFallback = res.headers.get("X-GitHub-Fallback") === "true";
        if (isFallback) {
          setGithubFallback(true);
          setGithubErrorMsg(`Could not connect to GitHub API for repo "${repoName}". Loaded offline mock data instead. Please check your credentials/network.`);
        }
        const data = await res.json();
        setPrsList(data || []);
        if (data && data.length > 0) {
          setSelectedPrNumber(data[0].number.toString());
          fetchPRDetails(repoName, data[0].number);
        } else {
          setSelectedPrNumber("");
          setSelectedPrDetails(null);
        }
      } else {
        console.error("Failed to fetch PRs");
        setGithubErrorMsg(`Server error: Failed to fetch PRs for "${repoName}".`);
      }
    } catch (err) {
      console.error("Error fetching PRs:", err);
      setGithubErrorMsg("Network error: Could not connect to WellActually.ai backend server.");
    } finally {
      setIsFetchingPrs(false);
    }
  };

  const fetchPRDetails = async (repoName, prNum) => {
    setIsFetchingPrDetails(true);
    try {
      const res = await fetch(`${API_BASE}/api/github/pr-details?repo=${encodeURIComponent(repoName)}&number=${prNum}`);
      if (res.ok) {
        const isFallback = res.headers.get("X-GitHub-Fallback") === "true";
        if (isFallback) {
          setGithubFallback(true);
          setGithubErrorMsg(`Could not connect to GitHub API for repo "${repoName}" PR #${prNum}. Loaded offline mock details instead.`);
        }
        const data = await res.json();
        setSelectedPrDetails(data);
      } else {
        console.error("Failed to fetch PR details");
      }
    } catch (err) {
      console.error("Error fetching PR details:", err);
    } finally {
      setIsFetchingPrDetails(false);
    }
  };

  useEffect(() => {
    if (selectedScenario === "dynamic" && prsList.length === 0) {
      fetchPRs(selectedRepo);
    }
  }, [selectedScenario]);

  const handleSimulateWebhook = async () => {
    try {
      const prNum = parseInt(selectedPrNumber, 10);
      if (!prNum || isNaN(prNum)) {
        alert("Please load and select a valid Pull Request first.");
        return;
      }
      const payload = {
        action: "opened",
        pull_request: {
          number: prNum,
          base: {
            repo: {
              full_name: selectedRepo
            }
          }
        }
      };
      const res = await fetch(`${API_BASE}/api/webhooks/github`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Webhook successfully triggered! State: ${JSON.stringify(data)}`);
      } else {
        const errText = await res.text();
        alert(`Webhook simulation failed: ${errText}`);
      }
    } catch (err) {
      alert(`Error triggering webhook: ${err.message}`);
    }
  };


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

  const renderMessageWithMentions = (msg) => {
    if (!msg) return msg;
    const parts = msg.split(/(@[a-zA-Z0-9_-]+)/g);
    return parts.map((part, index) => {
      if (part.startsWith("@")) {
        const handle = part.substring(1).toLowerCase();
        let color = "#3b82f6"; // Orchestrator blue
        if (handle.includes("coder")) color = "#22c55e"; // Coder green
        if (handle.includes("reviewer") || handle.includes("sme")) {
          const authKey = reviewerAuthRole?.replace(/\s+/g, '_').replace(/&/g, 'and').toLowerCase();
          const cartKey = reviewerCartRole?.replace(/\s+/g, '_').replace(/&/g, 'and').toLowerCase();
          if (handle.includes("auth") || (authKey && handle.includes(authKey))) {
            color = "#a855f7"; // Auth purple
          } else if (handle.includes("cart") || (cartKey && handle.includes(cartKey))) {
            color = "#eab308"; // Cart yellow
          } else {
            color = "#a855f7";
          }
        }
        return (
          <span
            key={index}
            style={{
              display: "inline-block",
              padding: "0.05rem 0.35rem",
              borderRadius: "4px",
              backgroundColor: `${color}20`,
              color: color,
              border: `1px solid ${color}40`,
              fontWeight: "bold",
              fontSize: "0.82rem",
              margin: "0 2px",
              verticalAlign: "middle"
            }}
          >
            {part}
          </span>
        );
      }
      return part;
    });
  };

  // MCP targets: prefer server data, fallback to scenario-based defaults
  // Dynamic reviewer roles and domains during idle state under dynamic scenario
  const displayAuthRole = (selectedScenario === "dynamic" && status === "IDLE")
    ? (selectedPrDetails?.predicted_reviewer_auth?.role || "Reviewer A (Dynamic)")
    : reviewerAuthRole;

  const displayCartRole = (selectedScenario === "dynamic" && status === "IDLE")
    ? (selectedPrDetails?.predicted_reviewer_cart?.role || "Reviewer B (Dynamic)")
    : reviewerCartRole;

  const displayAuthDomain = (selectedScenario === "dynamic" && status === "IDLE")
    ? (selectedPrDetails?.predicted_reviewer_auth?.domain || "dynamic_a")
    : reviewerAuthDomain;

  const displayCartDomain = (selectedScenario === "dynamic" && status === "IDLE")
    ? (selectedPrDetails?.predicted_reviewer_cart?.domain || "dynamic_b")
    : reviewerCartDomain;

  // MCP targets: prefer server data, override on dynamic/idle, fallback to scenario-based defaults
  const mcpTargets = (status === "IDLE" && selectedScenario === "dynamic")
    ? { table: "Pending PR analysis", endpoint: "Pending PR analysis" }
    : mcpTargetsFromServer 
      ? { table: mcpTargetsFromServer.schema_table, endpoint: mcpTargetsFromServer.api_endpoint }
      : selectedScenario === "dynamic"
        ? { table: "Pending PR analysis", endpoint: "Pending PR analysis" }
        : { table: "billing_profiles", endpoint: "/api/v1/billing/spending" };

  // MCP display: show latest check results to tell the self-healing story
  const displaySchemaCheck = schemaCheck || initialSchemaCheck;
  const displayOpenapiCheck = openapiCheck || initialOpenapiCheck;
  const displayRbacCheck = rbacCheck || initialRbacCheck;

  // Display filters for MCP verification checkers
  const showSchemaCheck = status === "IDLE" || (mcpTargets.table && mcpTargets.table !== "None" && mcpTargets.table !== "null" && mcpTargets.table !== null);
  const showOpenapiCheck = status === "IDLE" || (mcpTargets.endpoint && mcpTargets.endpoint !== "None" && mcpTargets.endpoint !== "null" && mcpTargets.endpoint !== null);
  const showRbacCheck = status === "IDLE" || (mcpTargetsFromServer?.rbac_target && mcpTargetsFromServer.rbac_target !== "None" && mcpTargetsFromServer.rbac_target !== "null" && mcpTargetsFromServer.rbac_target !== null);

  // Clear stale watchdog anomalies during idle state under dynamic scenario
  const displayWatchdogLogs = (status === "IDLE" && selectedScenario === "dynamic")
    ? []
    : watchdogLogs;

  
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
          setPrDiff(data.pr_diff);
          setPrTitle(data.pr_title || "");
          setPrBranch(data.pr_branch || "");
          setReviewerAuthRole(data.reviewer_auth_role || "Auth & Fraud SME");
          setReviewerAuthDomain(data.reviewer_auth_domain || "auth");
          setReviewerCartRole(data.reviewer_cart_role || "Cart SME");
          setReviewerCartDomain(data.reviewer_cart_domain || "cart");
          setActiveAgents(data.active_agents || []);
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
      const payload = { scenario: selectedScenario };
      if (selectedScenario === "dynamic") {
        payload.repo = selectedRepo;
        payload.pr_number = selectedPrNumber ? parseInt(selectedPrNumber, 10) : null;
      }
      const res = await fetch(`${API_BASE}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
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
    const norm = sender.replace(/-[a-f0-9]{6,}$/i, '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
    if (norm.includes("conductor")) return "#3b82f6";
    if (norm.includes("coder")) return "#22c55e";
    
    // Find matching active agent dynamically
    const agent = activeAgents.find(a => {
      const aNorm = a.name.replace(/-[a-f0-9]{6,}$/i, '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
      return aNorm === norm;
    });
    if (agent) {
      if (agent.id === "reviewer-0") return "#a855f7";
      if (agent.id === "reviewer-1") return "#06b6d4";
      // Fallback based on domain color
      switch (agent.domain?.toLowerCase()) {
        case "auth": return "#a855f7";
        case "billing": return "#f97316";
        case "database": return "#6366f1";
        case "security": return "#ef4444";
        case "cart": return "#eab308";
        case "api": return "#06b6d4";
        case "qa": return "#ec4899";
        case "documentation": return "#10b981";
      }
    }
    
    if (sender.includes("reviewer-auth")) return "#a855f7";
    if (sender.includes("reviewer-cart")) return "#eab308";
    return "rgba(255,255,255,0.8)";
  };

  const lastEvent = events[events.length - 1];
  const activeSender = lastEvent ? lastEvent.sender.toLowerCase() : "";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", padding: "2rem" }}>
      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(0.95); opacity: 1; }
          50% { transform: scale(1.15); opacity: 0.4; }
          100% { transform: scale(0.95); opacity: 1; }
        }
        @keyframes thinkingDot {
          0%, 100% { transform: scale(0.6); opacity: 0.4; }
          50% { transform: scale(1.2); opacity: 1; }
        }
        @keyframes flow-active {
          to {
            stroke-dashoffset: -20;
          }
        }
        .flow-line-active {
          stroke-dasharray: 6 4;
          animation: flow-active 1.2s linear infinite;
        }
      `}</style>
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
            Scenario: {scenarioFromServer === "rbac_bypass" ? "Spending Report RBAC Bypass" : "Dynamic GitHub PR"}
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
          
          {/* Repository Input & PR Loader */}
          <section className="glass-panel">
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              📦 GitHub PR Loader
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "#9ca3af", marginBottom: "0.25rem" }}>GitHub Repository</label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input
                    type="text"
                    value={selectedRepo}
                    onChange={(e) => setSelectedRepo(e.target.value)}
                    placeholder="owner/repo"
                    style={{
                      flex: 1,
                      padding: "0.4rem 0.6rem",
                      borderRadius: "4px",
                      border: "1px solid rgba(255,255,255,0.15)",
                      backgroundColor: "rgba(0,0,0,0.3)",
                      color: "white",
                      fontSize: "0.85rem"
                    }}
                  />
                  <button
                    onClick={() => fetchPRs(selectedRepo)}
                    disabled={isFetchingPrs}
                    style={{
                      padding: "0.4rem 1rem",
                      borderRadius: "4px",
                      backgroundColor: "rgba(6, 182, 212, 0.2)",
                      border: "1px solid rgba(6, 182, 212, 0.4)",
                      color: "#67e8f9",
                      fontSize: "0.8rem",
                      cursor: "pointer"
                    }}
                  >
                    {isFetchingPrs ? "Loading..." : "Load PRs"}
                  </button>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "#9ca3af", marginBottom: "0.25rem" }}>Select open PR</label>
                <select
                  value={selectedPrNumber}
                  onChange={(e) => {
                    setSelectedPrNumber(e.target.value);
                    if (e.target.value) {
                      fetchPRDetails(selectedRepo, parseInt(e.target.value, 10));
                    }
                  }}
                  style={{
                    width: "100%",
                    padding: "0.4rem 0.6rem",
                    borderRadius: "4px",
                    border: "1px solid rgba(255,255,255,0.15)",
                    backgroundColor: "rgba(0,0,0,0.3)",
                    color: "white",
                    fontSize: "0.85rem"
                  }}
                >
                  {prsList.length === 0 ? (
                    <option value="">-- No open PRs found --</option>
                  ) : (
                    prsList.map(pr => (
                      <option key={pr.number} value={pr.number}>
                        #{pr.number} - {pr.title}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div style={{ marginTop: "0.25rem", display: "flex" }}>
                <button
                  onClick={handleSimulateWebhook}
                  style={{
                    flex: 1,
                    padding: "0.5rem 1rem",
                    borderRadius: "6px",
                    backgroundColor: "rgba(59, 130, 246, 0.15)",
                    border: "1px solid rgba(59, 130, 246, 0.4)",
                    color: "#60a5fa",
                    fontWeight: "bold",
                    fontSize: "0.8rem",
                    cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                >
                  🔌 Simulate Webhook Trigger
                </button>
              </div>

              {githubErrorMsg && (
                <div style={{
                  padding: "0.6rem 0.8rem",
                  borderRadius: "4px",
                  backgroundColor: "rgba(245, 158, 11, 0.15)",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                  color: "#fde047",
                  fontSize: "0.75rem",
                  lineHeight: "1.3",
                  marginTop: "0.25rem"
                }}>
                  ⚠️ {githubErrorMsg}
                </div>
              )}
            </div>
          </section>

          {/* Agent Swarm Topology Graph */}
          <AgentTopology status={status} activeSender={activeSender} reviewerAuthRole={displayAuthRole} reviewerCartRole={displayCartRole} reviewerAuthDomain={displayAuthDomain} reviewerCartDomain={displayCartDomain} activeAgents={activeAgents} selectedPrDetails={selectedPrDetails} />

          {/* JIT Synthesized Swarm Agents Panel */}
          {activeAgents && activeAgents.filter(a => a.id.startsWith("reviewer")).length > 0 && (
            <section className="glass-panel">
              <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
                🤖 JIT Synthesized Swarm Agents
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {activeAgents.filter(a => a.id.startsWith("reviewer")).map((agent) => {
                  const isLlama = agent.model && agent.model.includes("Llama");
                  const modelLabel = isLlama ? "Llama-3.1-70B via Featherless AI" : `${agent.model || "GPT-4o-mini"} via AIML API`;
                  const borderCol = isLlama ? "rgba(168,85,247,0.3)" : "rgba(6,182,212,0.3)";
                  const bgCol = isLlama ? "rgba(168,85,247,0.05)" : "rgba(6,182,212,0.05)";
                  const titleColor = isLlama ? "#c084fc" : "#67e8f9";
                  return (
                    <div key={agent.id} style={{
                      padding: "0.85rem",
                      borderRadius: "6px",
                      backgroundColor: bgCol,
                      border: `1px solid ${borderCol}`,
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                        <span style={{ fontWeight: "bold", color: titleColor, fontSize: "0.9rem" }}>
                          {agent.icon} {agent.role}
                        </span>
                        <span style={{
                          fontSize: "0.7rem",
                          backgroundColor: isLlama ? "rgba(168,85,247,0.15)" : "rgba(6,182,212,0.15)",
                          color: isLlama ? "#a855f7" : "#06b6d4",
                          padding: "0.15rem 0.45rem",
                          borderRadius: "4px",
                          fontWeight: "500"
                        }}>
                          {modelLabel}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "#9ca3af", marginBottom: "0.25rem" }}>
                        <strong>Domain:</strong> <code style={{ color: "#f472b6" }}>{agent.domain}</code>
                      </div>
                      {agent.prompt && (
                        <div style={{
                          fontSize: "0.75rem",
                          color: "#d1d5db",
                          backgroundColor: "rgba(0,0,0,0.2)",
                          padding: "0.5rem",
                          borderRadius: "4px",
                          fontFamily: "monospace",
                          whiteSpace: "pre-wrap",
                          marginTop: "0.4rem",
                          border: "1px solid rgba(255,255,255,0.05)"
                        }}>
                          {agent.prompt}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* PR Information & Triage card */}
          <section className={`glass-panel ${status === "PENDING_HUMAN_APPROVAL" ? "glow-red" : ""}`}>
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              Pull Request compliance details
            </h2>
            
            <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "0.75rem", fontSize: "0.9rem", color: "#d1d5db" }}>
              <span style={{ color: "#9ca3af" }}>Target PR:</span>
              <span style={{ fontWeight: "bold" }}>
                {scenarioFromServer === "dynamic" || selectedScenario === "dynamic"
                  ? (status === "IDLE" ? (selectedPrDetails ? "#" + selectedPrDetails.number : "Pending load") : prId)
                  : (status === "IDLE" && selectedPrDetails ? "#" + selectedPrDetails.number : prId)
                }
              </span>
              
              <span style={{ color: "#9ca3af" }}>Title:</span>
              <span>
                {scenarioFromServer === "dynamic" || selectedScenario === "dynamic"
                  ? (status === "IDLE" ? (selectedPrDetails?.title || "Pending PR load") : (prTitle || selectedPrDetails?.title || "Loading PR details..."))
                  : (status === "IDLE" && selectedPrDetails ? selectedPrDetails.title : (scenarioFromServer === "rbac_bypass" ? "RBAC Bypass: Stale docs hide a removed column" : "Refactor checkout flow database queries"))
                }
              </span>

              <span style={{ color: "#9ca3af" }}>Branch:</span>
              <code>
                {scenarioFromServer === "dynamic" || selectedScenario === "dynamic"
                  ? (status === "IDLE" ? (selectedPrDetails?.branch || (selectedPrDetails ? `github/pr-${selectedPrDetails.number}` : "Pending")) : (prBranch || selectedPrDetails?.branch || `github/pr-${prId?.replace("PR-", "")}`))
                  : (status === "IDLE" && selectedPrDetails ? `github/pr-${selectedPrDetails.number}` : `codeband/branch-${prId?.toLowerCase()}`)
                }
              </code>
              
              <span style={{ color: "#9ca3af" }}>Modified:</span>
              <span style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                {(status === "IDLE" && (selectedScenario === "dynamic" || scenarioFromServer === "dynamic") && selectedPrDetails
                  ? selectedPrDetails.diff_files
                  : diffFiles
                ).map((f, i) => (
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
          {(showSchemaCheck || showOpenapiCheck || showRbacCheck) && (
            <section className="glass-panel">
              <h2 style={{ margin: "0 0 1.25rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
                Static Bounded Context (MCP) checkers
              </h2>

              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {/* Postgres check */}
                {showSchemaCheck && (
                  <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                    <div style={{ fontSize: "1.5rem" }}>
                      {status === "IDLE" ? "⚪" : displaySchemaCheck === null ? "⏳" : displaySchemaCheck.compliant ? "✅" : "❌"}
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
                )}

                {/* OpenAPI check */}
                {showOpenapiCheck && (
                  <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                    <div style={{ fontSize: "1.5rem" }}>
                      {status === "IDLE" ? "⚪" : displayOpenapiCheck === null ? "⏳" : displayOpenapiCheck.compliant ? "✅" : "❌"}
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
                )}

                {/* RBAC Policy check */}
                {showRbacCheck && (
                  <div style={{ display: "flex", gap: "1rem", padding: "0.75rem", borderRadius: "8px", backgroundColor: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)" }}>
                    <div style={{ fontSize: "1.5rem" }}>
                      {status === "IDLE" ? "⚪" : displayRbacCheck === null ? "⏳" : displayRbacCheck.compliant ? "✅" : "❌"}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: "bold", fontSize: "0.9rem", color: displayRbacCheck && !displayRbacCheck.compliant ? "#ef4444" : "#f3f4f6" }}>
                        RBAC Access Policy Check
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "#9ca3af", marginTop: "0.25rem" }}>
                        Target: {status === "IDLE" && selectedScenario === "dynamic"
                          ? <code>Pending PR analysis</code>
                          : mcpTargetsFromServer?.rbac_target 
                            ? <><span>Sensitive Column </span><code>{mcpTargetsFromServer.rbac_target}</code></>
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
                )}
              </div>
            </section>
          )}

          {/* SQL AST Visualizer */}
          <SqlAstVisualizer checkedColumns={displaySchemaCheck?.checked_columns || []} />

          {/* Telemetry watchdog Alerts */}
          <section className="glass-panel">
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.1rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", color: "#06b6d4" }}>
              Context-Aware Telemetry watchdog
            </h2>

            <TelemetryWatchdogChart logs={displayWatchdogLogs} />

            {displayWatchdogLogs.length === 0 ? (
              <p style={{ margin: 0, fontSize: "0.85rem", color: "#9ca3af", fontStyle: "italic" }}>
                No active anomalies scanned in telemetry stream.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {displayWatchdogLogs.map((log, idx) => (
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
                  const rawMsg = cleanMessageText(evt.message);
                  
                  // Check message sub-types
                  const isToolCall = rawMsg.startsWith("🔌");
                  const isTriage = evt.sender === "TriageScanner" || rawMsg.includes("Zero-Trust");
                  const isWatchdog = evt.sender === "WatchdogDaemon" || evt.sender === "TelemetryScanner" || rawMsg.includes("Anomaly detected");
                  const isJira = rawMsg.includes("[JIRA INTEGRATION]");
                  const isBandRoom = rawMsg.includes("Band.ai Task Room");

                  // Determine card layout parameters based on message sub-types
                  let cardStyle = {
                    padding: "0.75rem",
                    borderRadius: "8px",
                    backgroundColor: isAgent ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.15)",
                    border: isAgent ? `1px solid rgba(255,255,255,0.05)` : "1px dashed rgba(255,255,255,0.02)",
                    borderLeft: isAgent ? `4px solid ${getSenderColor(evt.sender)}` : "none"
                  };
                  let headerText = cleanSenderName(evt.sender, evt.role);
                  if (evt.role !== "SYSTEM" && evt.role !== headerText) {
                    headerText = `${headerText} (${evt.role})`;
                  }
                  let headerColor = getSenderColor(evt.sender);
                  let customContent = null;

                  if (isToolCall) {
                    const cleanToolMsg = rawMsg.replace(/^🔌\s*/, "");
                    const isCalling = cleanToolMsg.includes("Calling") || cleanToolMsg.includes("dispatch");
                    const isSuccess = cleanToolMsg.includes("COMPLIANT") || cleanToolMsg.includes("Result: passed") || cleanToolMsg.includes("Result: COMPLIANT");
                    const isFailure = cleanToolMsg.includes("FAILED") || cleanToolMsg.includes("Result: failed") || cleanToolMsg.includes("Result: FAILED");
                    
                    let statusBadge = "RUNNING";
                    let badgeBg = "rgba(6, 182, 212, 0.15)";
                    let badgeColor = "#06b6d4";
                    let leftBorderColor = "#06b6d4";
                    let bg = "rgba(15, 23, 42, 0.45)";
                    let titleText = "MCP Tool Invocation";

                    if (isSuccess) {
                      statusBadge = "SUCCESS";
                      badgeBg = "rgba(16, 185, 129, 0.15)";
                      badgeColor = "#10b981";
                      leftBorderColor = "#10b981";
                      bg = "rgba(6, 78, 59, 0.15)";
                      titleText = "MCP Tool Response";
                    } else if (isFailure) {
                      statusBadge = "FAILED";
                      badgeBg = "rgba(239, 68, 68, 0.15)";
                      badgeColor = "#ef4444";
                      leftBorderColor = "#ef4444";
                      bg = "rgba(127, 29, 29, 0.15)";
                      titleText = "MCP Tool Response";
                    } else if (isCalling) {
                      statusBadge = "DISPATCH";
                      badgeBg = "rgba(59, 130, 246, 0.15)";
                      badgeColor = "#3b82f6";
                      leftBorderColor = "#3b82f6";
                      bg = "rgba(30, 41, 59, 0.45)";
                      titleText = "MCP Tool Dispatch";
                    }

                    cardStyle = {
                      padding: "0.75rem",
                      borderRadius: "8px",
                      backgroundColor: bg,
                      border: `1px solid ${badgeColor}25`,
                      borderLeft: `4px solid ${leftBorderColor}`,
                      fontFamily: "'Fira Code', 'Cascadia Code', monospace"
                    };

                    customContent = (
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                          <span style={{ fontWeight: "bold", color: badgeColor, fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                            🔌 {titleText}
                          </span>
                          <span style={{ fontSize: "0.65rem", backgroundColor: badgeBg, color: badgeColor, padding: "0.05rem 0.35rem", borderRadius: "4px", fontWeight: "bold" }}>
                            {statusBadge}
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: isFailure ? "#f87171" : isSuccess ? "#34d399" : "#e2e8f0", whiteSpace: "pre-wrap" }}>
                          {cleanToolMsg}
                        </p>
                      </div>
                    );
                  } else if (isJira) {
                    cardStyle = {
                      padding: "0.75rem",
                      borderRadius: "8px",
                      backgroundColor: "rgba(37, 99, 235, 0.08)",
                      border: "1px solid rgba(37, 99, 235, 0.18)",
                      borderLeft: "4px solid #2563eb"
                    };
                    customContent = (
                      <div>
                        <div style={{ fontWeight: "bold", color: "#60a5fa", fontSize: "0.8rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          📘 JIRA Integration Agent Reference
                        </div>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: "#d1d5db", whiteSpace: "pre-wrap", fontStyle: "italic" }}>
                          {rawMsg}
                        </p>
                      </div>
                    );
                  } else if (isBandRoom) {
                    cardStyle = {
                      padding: "0.75rem",
                      borderRadius: "8px",
                      backgroundColor: "rgba(168, 85, 247, 0.08)",
                      border: "1px solid rgba(168, 85, 247, 0.18)",
                      borderLeft: "4px solid #a855f7"
                    };
                    customContent = (
                      <div>
                        <div style={{ fontWeight: "bold", color: "#c084fc", fontSize: "0.8rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          🔮 Band.ai Orchestration Engine
                        </div>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: "#e9d5ff", whiteSpace: "pre-wrap", fontWeight: "bold" }}>
                          {rawMsg}
                        </p>
                      </div>
                    );
                  } else if (isTriage) {
                    const isTriageFail = rawMsg.includes("FAILED") || rawMsg.includes("triage check failed") || rawMsg.includes("Zero-Trust Check FAILED");
                    cardStyle = {
                      padding: "0.75rem",
                      borderRadius: "8px",
                      backgroundColor: isTriageFail ? "rgba(220, 38, 38, 0.08)" : "rgba(16, 185, 129, 0.08)",
                      border: isTriageFail ? "1px solid rgba(220, 38, 38, 0.18)" : "1px solid rgba(16, 185, 129, 0.18)",
                      borderLeft: isTriageFail ? "4px solid #ef4444" : "4px solid #10b981"
                    };
                    customContent = (
                      <div>
                        <div style={{ fontWeight: "bold", color: isTriageFail ? "#f87171" : "#34d399", fontSize: "0.8rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          🛡️ Zero-Trust Compliance Gate
                        </div>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: "#f3f4f6", whiteSpace: "pre-wrap" }}>
                          {rawMsg}
                        </p>
                      </div>
                    );
                  } else if (isWatchdog) {
                    cardStyle = {
                      padding: "0.75rem",
                      borderRadius: "8px",
                      backgroundColor: "rgba(245, 158, 11, 0.08)",
                      border: "1px solid rgba(245, 158, 11, 0.18)",
                      borderLeft: "4px solid #f59e0b"
                    };
                    customContent = (
                      <div>
                        <div style={{ fontWeight: "bold", color: "#fbbf24", fontSize: "0.8rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          🚨 Watchdog Daemon Anomaly Scanner
                        </div>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: "#fef3c7", whiteSpace: "pre-wrap" }}>
                          {rawMsg}
                        </p>
                      </div>
                    );
                  }

                  return (
                    <div key={idx} style={cardStyle}>
                      {customContent ? customContent : (
                        <>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                            <span style={{ fontWeight: "bold", color: headerColor, fontSize: "0.85rem" }}>
                              {headerText}
                            </span>
                            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                              {(() => {
                                const norm = normalizeName(evt.sender);
                                const agent = activeAgents.find(a => normalizeName(a.name) === norm);
                                if (agent && agent.id.startsWith("reviewer")) {
                                  const isLlama = agent.model && agent.model.includes("Llama");
                                  const modelLabel = isLlama ? "Featherless: Llama-3.1-70B" : `AIML: ${agent.model || "GPT-4o-mini"}`;
                                  const badgeColor = isLlama ? "#a855f7" : "#06b6d4";
                                  const bgAlpha = isLlama ? "rgba(168,85,247,0.15)" : "rgba(6,182,212,0.15)";
                                  const borderBg = isLlama ? "rgba(168,85,247,0.08)" : "rgba(6,182,212,0.08)";
                                  const textSubColor = isLlama ? "#c084fc" : "#67e8f9";
                                  const borderCol = isLlama ? "rgba(168,85,247,0.2)" : "rgba(6,182,212,0.2)";
                                  
                                  return (
                                    <>
                                      <span style={{ fontSize: "0.7rem", backgroundColor: bgAlpha, color: badgeColor, padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                        {modelLabel}
                                      </span>
                                      <span style={{ fontSize: "0.65rem", backgroundColor: borderBg, color: textSubColor, padding: "0.1rem 0.4rem", borderRadius: "4px", border: `1px solid ${borderCol}` }}>
                                        Domain: {agent.domain ? agent.domain.charAt(0).toUpperCase() + agent.domain.slice(1) : "Unknown"}
                                      </span>
                                    </>
                                  );
                                } else if (agent && (agent.id === "conductor" || agent.id === "coder") && evt.role !== "SYSTEM") {
                                  return (
                                    <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(6,182,212,0.15)", color: "#06b6d4", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                      AIML: {agent.model || "GPT-4o-mini"}
                                    </span>
                                  );
                                } else {
                                  // Fallback for static scenario values when activeAgents is empty or matching fails
                                  if (evt.sender.includes("reviewer-auth")) {
                                    return (
                                      <>
                                        <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(168,85,247,0.15)", color: "#a855f7", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                          Featherless: Llama-3.1-70B
                                        </span>
                                        <span style={{ fontSize: "0.65rem", backgroundColor: "rgba(168,85,247,0.08)", color: "#c084fc", padding: "0.1rem 0.4rem", borderRadius: "4px", border: "1px solid rgba(168,85,247,0.2)" }}>
                                          Domain: {reviewerAuthDomain === "auth" ? "Auth & Schema" : reviewerAuthDomain.charAt(0).toUpperCase() + reviewerAuthDomain.slice(1)}
                                        </span>
                                      </>
                                    );
                                  }
                                  if (evt.sender.includes("reviewer-cart")) {
                                    return (
                                      <>
                                        <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(6,182,212,0.15)", color: "#06b6d4", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                          AIML: GPT-4o-mini
                                        </span>
                                        <span style={{ fontSize: "0.65rem", backgroundColor: "rgba(6,182,212,0.08)", color: "#67e8f9", padding: "0.1rem 0.4rem", borderRadius: "4px", border: "1px solid rgba(6,182,212,0.2)" }}>
                                          Domain: {reviewerCartDomain === "cart" ? "API Contract" : reviewerCartDomain.charAt(0).toUpperCase() + reviewerCartDomain.slice(1)}
                                        </span>
                                      </>
                                    );
                                  }
                                  if ((evt.sender.includes("coder") || evt.sender.includes("conductor")) && evt.role !== "SYSTEM") {
                                    return (
                                      <span style={{ fontSize: "0.7rem", backgroundColor: "rgba(6,182,212,0.15)", color: "#06b6d4", padding: "0.1rem 0.4rem", borderRadius: "4px" }}>
                                        AIML: GPT-4o-mini
                                      </span>
                                    );
                                  }
                                }
                                return null;
                              })()}
                            </div>
                          </div>
                          
                          {(() => {
                            return (rawMsg.includes("```") || (rawMsg.includes("def ") && rawMsg.includes(":"))) ? (
                              <HighlightedCode code={rawMsg} />
                            ) : (
                              <p style={{ margin: 0, fontSize: "0.85rem", color: "#e5e7eb", whiteSpace: "pre-wrap" }}>
                                {renderMessageWithMentions(rawMsg)}
                              </p>
                            );
                          })()}
                        </>
                      )}
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
                    {reviewerAuthRole} + {reviewerCartRole} reasoning via Band.ai room...
                  </span>
                </div>
              )}

            </div>
          ) : (
            <div style={{ flex: 1, overflow: "auto", backgroundColor: "#04060a", borderRadius: "8px", padding: "1rem" }}>
              {currentCode ? (
                <div>
                  <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#22c55e" }}>🛠️ Swarm Proposed Code Fix (Adversarial Round {consensusRound}):</h3>
                  <HighlightedCode code={currentCode} />
                </div>
              ) : (prDiff || (selectedPrDetails && selectedPrDetails.diff)) ? (
                <div>
                  <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#06b6d4" }}>📄 Original Pull Request Diff (Under Review):</h3>
                  <pre style={{
                    margin: 0,
                    padding: "0.5rem",
                    color: "#e5e7eb",
                    fontFamily: "'Fira Code', 'Cascadia Code', monospace",
                    fontSize: "0.82rem",
                    whiteSpace: "pre-wrap",
                    backgroundColor: "rgba(0,0,0,0.3)",
                    borderRadius: "4px",
                    border: "1px solid rgba(255,255,255,0.05)"
                  }}>{prDiff || (selectedPrDetails && selectedPrDetails.diff)}</pre>
                </div>
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

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 1000;

// ─── Utility: Python Syntax Highlighter ────────────────────────────────
function highlightPython(code) {
  if (!code) return null;
  const keywords = new Set(['def', 'class', 'import', 'from', 'return', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'raise', 'pass', 'break', 'continue', 'and', 'or', 'not', 'in', 'is', 'None', 'True', 'False', 'lambda', 'yield', 'async', 'await', 'global', 'nonlocal', 'del', 'assert']);
  const builtins = new Set(['print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'type', 'isinstance', 'getattr', 'setattr', 'hasattr', 'super', 'open', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'any', 'all', 'min', 'max', 'sum', 'abs', 'round', 'format', 'input', 'id', 'hex', 'oct', 'bin', 'chr', 'ord', 'repr', 'hash', 'next', 'iter', 'object', 'property', 'staticmethod', 'classmethod', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError', 'Exception', 'RuntimeError', 'StopIteration', 'NotImplementedError']);
  const tokenPattern = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"])*"|'(?:\\.|[^'])*')|(#[^\n]*)|(\b\d+\.?\d*\b)|(@\w+)|(\b(?:def|class)\s+)(\w+)|(\b\w+(?=\s*\())|([.\w]+)/g;
  const spans = [];
  let lastIndex = 0;
  let match;
  while ((match = tokenPattern.exec(code)) !== null) {
    if (match.index > lastIndex) spans.push({ text: code.slice(lastIndex, match.index), color: '#e5e7eb' });
    if (match[1]) spans.push({ text: match[0], color: '#a3e635' });
    else if (match[2]) spans.push({ text: match[0], color: '#6b7280', italic: true });
    else if (match[3]) spans.push({ text: match[0], color: '#fb923c' });
    else if (match[4]) spans.push({ text: match[0], color: '#fbbf24' });
    else if (match[5]) { spans.push({ text: match[5], color: '#c084fc' }); spans.push({ text: match[6], color: '#67e8f9' }); }
    else if (match[7]) spans.push({ text: match[0], color: builtins.has(match[7]) ? '#67e8f9' : '#93c5fd' });
    else if (match[8]) {
      if (keywords.has(match[8])) spans.push({ text: match[0], color: '#c084fc', bold: true });
      else if (builtins.has(match[8])) spans.push({ text: match[0], color: '#67e8f9' });
      else spans.push({ text: match[0], color: '#e5e7eb' });
    } else spans.push({ text: match[0], color: '#e5e7eb' });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < code.length) spans.push({ text: code.slice(lastIndex), color: '#e5e7eb' });
  return spans.map((s, i) => (
    <span key={i} style={{ color: s.color, fontWeight: s.bold ? 'bold' : 'normal', fontStyle: s.italic ? 'italic' : 'normal' }}>{s.text}</span>
  ));
}

function HighlightedCode({ code }) {
  const highlighted = useMemo(() => highlightPython(code), [code]);
  return (
    <pre style={{ margin: '0.5rem 0 0 0', padding: '0.75rem', borderRadius: '8px', backgroundColor: '#080a10', overflowX: 'auto', fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: '0.8rem', lineHeight: '1.6', border: '1px solid rgba(255,255,255,0.04)' }}>
      {highlighted}
    </pre>
  );
}

// ─── Utility: Name / Message Helpers ───────────────────────────────────
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
    case "auth": return "🔐";
    case "compliance": return "📋";
    case "performance": return "⚡";
    default: return "🤖";
  }
};

const getDomainColor = (domain) => {
  switch (domain?.toLowerCase()) {
    case "auth": return "#a855f7";
    case "billing": return "#f97316";
    case "database": return "#6366f1";
    case "security": return "#ef4444";
    case "cart": return "#eab308";
    case "api": return "#06b6d4";
    case "qa": return "#ec4899";
    case "documentation": return "#10b981";
    case "architecture": return "#8b5cf6";
    case "compliance": return "#f472b6";
    case "performance": return "#f59e0b";
    default: return "#8b5cf6";
  }
};

const normalizeName = (name) => {
  if (!name) return "";
  return name.replace(/-[a-f0-9]{6,}$/i, '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
};

const cleanSenderName = (sender, role) => {
  if (!sender) return sender;
  if (role && role !== "SYSTEM") return role;
  let clean = sender.replace(/-[a-f0-9]{6,}$/i, '');
  if (clean.startsWith('reviewer-')) {
    clean = clean.replace('reviewer-', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()).replace(' And ', ' & ');
  }
  return clean;
};

const cleanMessageText = (text) => {
  if (!text) return text;
  return text.replace(/^\[.*?\]:\s*/i, '');
};

// ─── Pipeline Progress Indicator ───────────────────────────────────────
const PHASES = [
  { key: "ingest", icon: "🎯", label: "Ingest PR", color: "#06b6d4" },
  { key: "analyze", icon: "🧠", label: "JIT Synthesis", color: "#a855f7" },
  { key: "deploy", icon: "🔗", label: "Deploy Swarm", color: "#3b82f6" },
  { key: "debate", icon: "⚔️", label: "Adversarial Debate", color: "#22c55e" },
  { key: "verdict", icon: "📊", label: "Verdict", color: "#f59e0b" },
];

function getActivePhase(status, hasAgents, hasPrDetails) {
  if (status === "IDLE") return hasPrDetails ? 0 : -1;
  if (status === "TRIAGE") return 1;
  if (status === "PENDING_HUMAN_APPROVAL") return 2;
  if (status === "RUNNING") return hasAgents ? 3 : 2;
  if (status === "COMPLETED" || status === "HALTED" || status === "CRASHED") return 4;
  return -1;
}

function PipelineProgress({ activePhase }) {
  return (
    <div className="pipeline-bar" style={{ margin: "1.5rem 0" }}>
      {PHASES.map((phase, i) => {
        const isActive = i === activePhase;
        const isCompleted = i < activePhase;
        const dotClass = isActive ? "active" : isCompleted ? "completed" : "";
        const labelClass = isActive ? "active" : isCompleted ? "completed" : "";

        return (
          <React.Fragment key={phase.key}>
            {i > 0 && (
              <div
                className={`pipeline-connector ${isCompleted ? "completed" : isActive ? "active" : ""}`}
                style={{
                  "--connector-color": isCompleted ? phase.color : isActive ? phase.color : undefined
                }}
              />
            )}
            <div className="pipeline-phase">
              <div
                className={`pipeline-dot ${dotClass}`}
                style={{ "--dot-color": phase.color }}
              >
                {isCompleted ? "✓" : phase.icon}
              </div>
              <span
                className={`pipeline-label ${labelClass}`}
                style={{ "--label-color": phase.color }}
              >
                {phase.label}
              </span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─── JIT Synthesis Hero Panel ──────────────────────────────────────────
function JITSynthesisPanel({ agents, status, isAnalyzing }) {
  const reviewerAgents = agents.filter(a => a.id?.startsWith("reviewer"));

  if (status === "IDLE" && !isAnalyzing && reviewerAgents.length === 0) {
    return (
      <section className="glass-panel jit-hero" style={{ textAlign: "center", padding: "3rem 2rem" }}>
        <div style={{ fontSize: "3rem", marginBottom: "1rem", opacity: 0.6 }}>🧠</div>
        <h2 style={{ margin: "0 0 0.75rem 0", fontSize: "1.4rem", background: "linear-gradient(135deg, #a855f7, #ec4899)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", fontWeight: 800 }}>
          Just-in-Time Agent Synthesis
        </h2>
        <p style={{ margin: 0, color: "#9ca3af", fontSize: "0.9rem", maxWidth: "500px", marginLeft: "auto", marginRight: "auto", lineHeight: 1.6 }}>
          When a PR arrives, the Conductor AI reads the diff, identifies domains & compliance regimes,
          and <strong style={{ color: "#c084fc" }}>invents bespoke reviewer agents</strong> with custom prompts — in real time.
          No pre-configured agents. Pure JIT governance compute.
        </p>
      </section>
    );
  }

  if (isAnalyzing) {
    return (
      <section className="glass-panel jit-hero" style={{ padding: "2rem", position: "relative" }}>
        {/* Scanning overlay effect */}
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, bottom: 0, overflow: "hidden",
          borderRadius: "16px", pointerEvents: "none"
        }}>
          <div style={{
            position: "absolute", left: 0, right: 0, height: "2px",
            background: "linear-gradient(90deg, transparent, #a855f7, #ec4899, transparent)",
            animation: "scan-line 2s ease-in-out infinite"
          }} />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
          <div style={{
            width: "48px", height: "48px", borderRadius: "12px",
            background: "linear-gradient(135deg, rgba(168,85,247,0.2), rgba(236,72,153,0.2))",
            border: "1px solid rgba(168,85,247,0.3)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.5rem"
          }}>🧠</div>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "#e5e7eb" }}>
              Conductor is Analyzing the PR Diff...
            </h2>
            <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem", color: "#a855f7" }}>
              Reading code changes, identifying domains, synthesizing custom agents
            </p>
          </div>
        </div>

        {/* Shimmer skeleton cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {[1, 2].map(i => (
            <div key={i} className="shimmer" style={{
              height: "70px", borderRadius: "12px",
              border: "1px solid rgba(168,85,247,0.1)"
            }} />
          ))}
        </div>
      </section>
    );
  }

  // Agents have materialized — show them with entrance animation
  return (
    <section className="glass-panel jit-hero" style={{ padding: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{
            width: "36px", height: "36px", borderRadius: "10px",
            background: "linear-gradient(135deg, rgba(168,85,247,0.25), rgba(236,72,153,0.25))",
            border: "1px solid rgba(168,85,247,0.3)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.1rem"
          }}>🧠</div>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#e5e7eb" }}>
              JIT Synthesized Agents
            </h2>
            <span style={{ fontSize: "0.72rem", color: "#a855f7" }}>
              {reviewerAgents.length} custom agent{reviewerAgents.length !== 1 ? 's' : ''} materialized from PR diff analysis
            </span>
          </div>
        </div>
        <span style={{
          fontSize: "0.65rem", fontWeight: 700, padding: "0.2rem 0.6rem", borderRadius: "6px",
          background: "linear-gradient(135deg, rgba(168,85,247,0.2), rgba(236,72,153,0.2))",
          border: "1px solid rgba(168,85,247,0.3)", color: "#c084fc",
          textTransform: "uppercase", letterSpacing: "0.1em"
        }}>
          ⚡ JIT Created
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {reviewerAgents.map((agent) => {
          const isLlama = agent.model?.includes("Llama");
          const modelName = agent.model || "";
          let modelLabel = "";
          if (isLlama) {
            modelLabel = modelName.includes("70B") ? "Llama-3.1-70B via Featherless AI" : "Llama-3.1-8B via Featherless AI";
          } else {
            modelLabel = modelName.includes("mini") ? "GPT-4o Mini via AIML API" : "GPT-4o via AIML API";
          }
          const domainColor = getDomainColor(agent.domain);

          return (
            <div key={agent.id} className="agent-card-materialize" style={{
              padding: "1rem",
              borderRadius: "12px",
              background: `linear-gradient(135deg, ${domainColor}08, ${domainColor}03, rgba(13,19,33,0.6))`,
              border: `1px solid ${domainColor}30`,
              position: "relative",
              overflow: "hidden"
            }}>
              {/* Accent stripe */}
              <div style={{
                position: "absolute", top: 0, left: 0, bottom: 0, width: "3px",
                background: domainColor, borderRadius: "3px 0 0 3px"
              }} />

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem", paddingLeft: "0.75rem" }}>
                <div>
                  <span style={{ fontWeight: 700, color: "#f3f4f6", fontSize: "0.95rem" }}>
                    {getDomainIcon(agent.domain)} {agent.role}
                  </span>
                  <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.35rem", flexWrap: "wrap" }}>
                    <span style={{
                      fontSize: "0.65rem", padding: "0.1rem 0.4rem", borderRadius: "4px",
                      background: `${domainColor}18`, color: domainColor, border: `1px solid ${domainColor}30`,
                      fontWeight: 600
                    }}>
                      {agent.domain?.toUpperCase()}
                    </span>
                    <span style={{
                      fontSize: "0.65rem", padding: "0.1rem 0.4rem", borderRadius: "4px",
                      background: isLlama ? "rgba(168,85,247,0.12)" : "rgba(6,182,212,0.12)",
                      color: isLlama ? "#c084fc" : "#67e8f9",
                      border: `1px solid ${isLlama ? "rgba(168,85,247,0.25)" : "rgba(6,182,212,0.25)"}`,
                      fontWeight: 500
                    }}>
                      {modelLabel}
                    </span>
                  </div>
                </div>
              </div>

              {agent.prompt && (
                <div style={{
                  marginTop: "0.5rem", marginLeft: "0.75rem",
                  fontSize: "0.73rem", color: "#9ca3af",
                  backgroundColor: "rgba(0,0,0,0.25)", padding: "0.6rem 0.75rem",
                  borderRadius: "8px", fontFamily: "'JetBrains Mono', monospace",
                  whiteSpace: "pre-wrap", lineHeight: 1.5,
                  border: "1px solid rgba(255,255,255,0.04)"
                }}>
                  {agent.prompt}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ─── Topology Graph (SVG) ──────────────────────────────────────────────
function AgentTopology({ status, activeSender, activeAgents, lastActiveSenders = [] }) {
  const isDeployed = status === "RUNNING" || status === "COMPLETED" || status === "HALTED" || status === "CRASHED";
  const agents = useMemo(() => {
    if (status !== "IDLE" && activeAgents?.length > 0) return activeAgents;
    return [
      { id: "conductor", name: "conductor", role: "Orchestrator", domain: "system", icon: "👑" },
      { id: "coder", name: "coder", role: "Coder", domain: "system", icon: "💻" }
    ];
  }, [status, activeAgents]);

  const getNodeColor = (agent) => {
    if (agent.id === "conductor") return "#3b82f6";
    if (agent.id === "coder") return "#22c55e";
    return getDomainColor(agent.domain);
  };

  const nodes = useMemo(() => {
    const reviewers = agents.filter(a => a.id.startsWith("reviewer"));
    const N = reviewers.length;
    return agents.map(agent => {
      if (agent.id === "conductor") return { ...agent, label: "Conductor", sub: "Orchestrator", x: 200, y: 45 };
      if (agent.id === "coder") return { ...agent, label: "Coder", sub: "Implementation", x: 70, y: 145 };
      const i = reviewers.findIndex(r => r.id === agent.id);
      let x, y;
      if (N === 1) { x = 330; y = 145; }
      else if (N === 2) { x = 230 + i * 100; y = 145; }
      else {
        const angle = (-20 + i * (130 / (N - 1))) * Math.PI / 180;
        x = Math.round(200 + 130 * Math.cos(angle));
        y = Math.round(140 + 70 * Math.sin(angle));
      }
      const label = agent.role?.includes("SME") ? agent.role.split("SME")[0].trim() : (agent.role || `R${i + 1}`);
      return { ...agent, label, sub: "JIT Agent", x, y };
    });
  }, [agents]);

  const matchesSender = useCallback((senderName, nodeId) => {
    if (!senderName) return false;
    const normActive = normalizeName(senderName);
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return false;
    if (node.id === "conductor") return normActive.startsWith("conductor");
    if (node.id === "coder") return normActive.startsWith("coder");
    const normNodeName = normalizeName(node.name);
    return normActive === normNodeName || normActive.includes(normNodeName) || (node.domain && normActive.includes(node.domain.toLowerCase()));
  }, [nodes]);

  const isNodeActive = useCallback((nodeId) => matchesSender(activeSender, nodeId), [activeSender, matchesSender]);

  const isNodeRecentlyActive = useCallback((nodeId) => {
    if (isNodeActive(nodeId)) return false; // currently active nodes use the brighter glow
    return lastActiveSenders.some(s => matchesSender(s.sender, nodeId));
  }, [lastActiveSenders, isNodeActive, matchesSender]);

  const getRecentGlowOpacity = useCallback((nodeId) => {
    const match = lastActiveSenders.find(s => matchesSender(s.sender, nodeId));
    if (!match) return 0;
    const age = Date.now() - match.ts;
    return Math.max(0.2, 1 - age / 4000); // fade from 1 to 0.2 over 4s
  }, [lastActiveSenders, matchesSender]);

  const conductorNode = nodes.find(n => n.id === "conductor");

  return (
    <div style={{ padding: "0.5rem 0" }}>
      <svg width="100%" height="230" viewBox="0 0 400 230" style={{ overflow: "visible" }}>
        <defs>
          <filter id="glow-active" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="glow-deployed" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          {/* Animated flow particle */}
          {isDeployed && nodes.filter(n => n.id !== "conductor").map(n => (
            <React.Fragment key={`flow-anim-${n.id}`}>
              <circle id={`dot-${n.id}`} r="3" fill={getNodeColor(n)} opacity="0.9">
                <animateMotion dur="2s" repeatCount="indefinite" begin={`${nodes.indexOf(n) * 0.4}s`}>
                  <mpath href={`#path-${n.id}`} />
                </animateMotion>
              </circle>
            </React.Fragment>
          ))}
        </defs>

        {/* Connection lines + animated flow paths */}
        {conductorNode && nodes.filter(n => n.id !== "conductor").map(n => {
          const active = isNodeActive(n.id) || isNodeActive("conductor");
          const color = getNodeColor(n);
          return (
            <React.Fragment key={`line-${n.id}`}>
              {/* Invisible path for flow animation */}
              <path
                id={`path-${n.id}`}
                d={`M${conductorNode.x},${conductorNode.y} L${n.x},${n.y}`}
                fill="none" stroke="none"
              />
              {/* Visible line */}
              <line
                x1={conductorNode.x} y1={conductorNode.y} x2={n.x} y2={n.y}
                stroke={active ? color : isDeployed ? `${color}40` : "rgba(255,255,255,0.1)"}
                strokeWidth={active ? 2.5 : isDeployed ? 1.5 : 1.5}
                strokeDasharray={isDeployed ? undefined : "4 4"}
                style={{ transition: "all 0.5s" }}
              />
              {/* Flow particle dot */}
              {isDeployed && (
                <circle r="3" fill={color} opacity="0.85">
                  <animateMotion dur={`${1.5 + Math.random()}s`} repeatCount="indefinite" begin={`${nodes.indexOf(n) * 0.3}s`}>
                    <mpath href={`#path-${n.id}`} />
                  </animateMotion>
                </circle>
              )}
            </React.Fragment>
          );
        })}

        {/* Nodes */}
        {nodes.map(n => {
          const active = isNodeActive(n.id);
          const recentlyActive = isNodeRecentlyActive(n.id);
          const recentOpacity = getRecentGlowOpacity(n.id);
          const deployed = isDeployed;
          const color = getNodeColor(n);
          return (
            <g key={n.id}>
              {/* Active speaking glow (bright, pulsing) */}
              {active && (
                <circle cx={n.x} cy={n.y} r="28" fill="none" stroke={color} strokeWidth="2.5"
                  filter="url(#glow-active)"
                  style={{ transformOrigin: `${n.x}px ${n.y}px`, animation: "pulse-ring 1.8s cubic-bezier(0.215, 0.610, 0.355, 1) infinite" }}
                />
              )}
              {/* Recently-spoken glow (dimmer, fading) */}
              {recentlyActive && (
                <circle cx={n.x} cy={n.y} r="27" fill="none" stroke={color} strokeWidth="1.8"
                  filter="url(#glow-active)"
                  opacity={recentOpacity * 0.6}
                  style={{ transformOrigin: `${n.x}px ${n.y}px`, animation: "pulse-ring 2.5s ease-in-out infinite", transition: "opacity 0.5s" }}
                />
              )}
              {/* Deployed but not speaking glow (subtle ambient) */}
              {deployed && !active && !recentlyActive && (
                <circle cx={n.x} cy={n.y} r="26" fill="none" stroke={color} strokeWidth="1.5"
                  filter="url(#glow-deployed)"
                  opacity="0.5"
                  style={{ transformOrigin: `${n.x}px ${n.y}px`, animation: "pulse-ring 3s ease-in-out infinite" }}
                />
              )}
              <circle cx={n.x} cy={n.y} r="22" fill={deployed ? `${color}08` : "#0a0e1a"}
                stroke={active ? color : recentlyActive ? `${color}B0` : deployed ? `${color}80` : "rgba(255,255,255,0.15)"}
                strokeWidth={active ? 2.5 : recentlyActive ? 2.2 : deployed ? 2 : 1.5}
                style={{ transition: "all 0.4s" }}
              />
              <text x={n.x} y={n.y + 5} textAnchor="middle" fontSize="1.1rem">{n.icon || getDomainIcon(n.domain)}</text>
              <text x={n.x} y={n.y + 38} textAnchor="middle" fontSize="0.65rem" fontWeight="bold" fill={active ? "#f3f4f6" : recentlyActive ? "#e5e7eb" : deployed ? "#d1d5db" : "#6b7280"}>
                {n.label?.length > 14 ? n.label.substring(0, 12) + "…" : n.label}
              </text>
              <text x={n.x} y={n.y + 49} textAnchor="middle" fontSize="0.55rem" fill={deployed ? "#9ca3af" : "#4b5563"}>{n.sub}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Debate Message Renderer ───────────────────────────────────────────
function DebateMessage({ evt, activeAgents }) {
  const rawMsg = cleanMessageText(evt.message);
  const headerText = cleanSenderName(evt.sender, evt.role);

  const getSenderColor = (sender) => {
    if (!sender) return "rgba(255,255,255,0.7)";
    const norm = sender.replace(/-[a-f0-9]{6,}$/i, '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
    if (norm.includes("conductor")) return "#3b82f6";
    if (norm.includes("coder")) return "#22c55e";
    const agent = activeAgents.find(a => normalizeName(a.name) === norm);
    if (agent) return getDomainColor(agent.domain);
    if (sender.includes("reviewer")) return "#a855f7";
    return "rgba(255,255,255,0.7)";
  };

  const isAgent = evt.sender !== "SYSTEM" && evt.sender !== "TriageScanner" && evt.sender !== "TelemetryScanner" && evt.sender !== "WatchdogDaemon";
  const isToolCall = rawMsg.startsWith("🔌");
  const isTriage = evt.sender === "TriageScanner" || rawMsg.includes("Zero-Trust");
  const isBandRoom = rawMsg.includes("Band.ai Task Room");
  const isPrSummary = rawMsg.startsWith("📝 [PR SUMMARY]");
  const isWatchdog = evt.sender === "WatchdogDaemon" || evt.sender === "TelemetryScanner" || rawMsg.includes("Anomaly detected");

  const senderColor = getSenderColor(evt.sender);

  // Determine model badge for the sender
  const norm = normalizeName(evt.sender);
  const matchedAgent = activeAgents.find(a => normalizeName(a.name) === norm);
  const isLlama = matchedAgent?.model?.includes("Llama");
  const modelName = matchedAgent?.model || "";
  const modelLabel = isLlama 
    ? (modelName.includes("70B") ? "Llama-3.1-70B" : "Llama-3.1-8B") 
    : (modelName.includes("mini") ? "GPT-4o Mini" : "GPT-4o");
  const modelBadge = matchedAgent && evt.role !== "SYSTEM"
    ? (isLlama ? `Featherless: ${modelLabel}` : `AIML: ${modelLabel}`)
    : null;

  // Special card styles
  if (isToolCall) {
    const cleanToolMsg = rawMsg.replace(/^🔌\s*/, "");
    const isSuccess = cleanToolMsg.includes("COMPLIANT") || cleanToolMsg.includes("Result: passed");
    const isFailure = cleanToolMsg.includes("FAILED") || cleanToolMsg.includes("Result: failed");
    const isCalling = cleanToolMsg.includes("Calling") || cleanToolMsg.includes("dispatch");
    const statusBadge = isSuccess ? "SUCCESS" : isFailure ? "FAILED" : isCalling ? "DISPATCH" : "RUNNING";
    const badgeColor = isSuccess ? "#10b981" : isFailure ? "#ef4444" : isCalling ? "#3b82f6" : "#06b6d4";

    return (
      <div style={{
        padding: "0.65rem 0.75rem", borderRadius: "10px",
        background: `${badgeColor}08`, border: `1px solid ${badgeColor}20`,
        borderLeft: `3px solid ${badgeColor}`,
        fontFamily: "'JetBrains Mono', monospace"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
          <span style={{ fontWeight: 700, color: badgeColor, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            🔌 MCP Tool {isCalling ? "Dispatch" : "Response"}
          </span>
          <span style={{ fontSize: "0.6rem", background: `${badgeColor}18`, color: badgeColor, padding: "0.1rem 0.35rem", borderRadius: "4px", fontWeight: 700 }}>
            {statusBadge}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.78rem", color: isFailure ? "#f87171" : isSuccess ? "#34d399" : "#d1d5db", whiteSpace: "pre-wrap" }}>
          {cleanToolMsg}
        </p>
      </div>
    );
  }

  if (isPrSummary) {
    const cleanMsg = rawMsg.replace(/^📝\s*\[PR SUMMARY\]\s*/i, "");
    return (
      <div style={{
        padding: "0.8rem 1rem", borderRadius: "10px",
        background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.15)",
        borderLeft: "3px solid #8b5cf6"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontWeight: 700, color: "#a78bfa", fontSize: "0.72rem", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>📝</span> PR Diff Executive Summary
        </div>
        <p style={{ margin: 0, fontSize: "0.82rem", color: "#e9d5ff", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{cleanMsg}</p>
      </div>
    );
  }

  if (isTriage) {
    const isTriageFail = rawMsg.includes("FAILED") || rawMsg.includes("Zero-Trust Check FAILED");
    return (
      <div style={{
        padding: "0.65rem 0.75rem", borderRadius: "10px",
        background: isTriageFail ? "rgba(220,38,38,0.06)" : "rgba(16,185,129,0.06)",
        border: isTriageFail ? "1px solid rgba(220,38,38,0.15)" : "1px solid rgba(16,185,129,0.15)",
        borderLeft: isTriageFail ? "3px solid #ef4444" : "3px solid #10b981"
      }}>
        <div style={{ fontWeight: 700, color: isTriageFail ? "#f87171" : "#34d399", fontSize: "0.72rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          🛡️ Zero-Trust Compliance Gate
        </div>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "#e5e7eb", whiteSpace: "pre-wrap" }}>{rawMsg}</p>
      </div>
    );
  }

  if (isBandRoom) {
    return (
      <div style={{
        padding: "0.65rem 0.75rem", borderRadius: "10px",
        background: "rgba(168,85,247,0.06)", border: "1px solid rgba(168,85,247,0.15)",
        borderLeft: "3px solid #a855f7"
      }}>
        <div style={{ fontWeight: 700, color: "#c084fc", fontSize: "0.72rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          🔮 Band.ai Orchestration Engine
        </div>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "#e9d5ff", whiteSpace: "pre-wrap", fontWeight: 600 }}>{rawMsg}</p>
      </div>
    );
  }

  if (isWatchdog) {
    return (
      <div style={{
        padding: "0.65rem 0.75rem", borderRadius: "10px",
        background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)",
        borderLeft: "3px solid #f59e0b"
      }}>
        <div style={{ fontWeight: 700, color: "#fbbf24", fontSize: "0.72rem", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          🚨 Watchdog Daemon
        </div>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "#fef3c7", whiteSpace: "pre-wrap" }}>{rawMsg}</p>
      </div>
    );
  }

  // Standard agent or system message
  const hasCode = rawMsg.includes("```") || (rawMsg.includes("def ") && rawMsg.includes(":"));

  return (
    <div style={{
      padding: "0.65rem 0.75rem", borderRadius: "10px",
      background: isAgent ? "rgba(255,255,255,0.015)" : "rgba(0,0,0,0.12)",
      border: isAgent ? "1px solid rgba(255,255,255,0.04)" : "1px dashed rgba(255,255,255,0.03)",
      borderLeft: isAgent ? `3px solid ${senderColor}` : "none"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.2rem" }}>
        <span style={{ fontWeight: 700, color: senderColor, fontSize: "0.82rem" }}>{headerText}</span>
        <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
          {modelBadge && (
            <span style={{
              fontSize: "0.6rem", padding: "0.08rem 0.35rem", borderRadius: "4px",
              background: isLlama ? "rgba(168,85,247,0.12)" : "rgba(6,182,212,0.12)",
              color: isLlama ? "#a855f7" : "#06b6d4"
            }}>{modelBadge}</span>
          )}
          {matchedAgent?.domain && matchedAgent.id?.startsWith("reviewer") && (
            <span style={{
              fontSize: "0.6rem", padding: "0.08rem 0.35rem", borderRadius: "4px",
              background: `${getDomainColor(matchedAgent.domain)}10`,
              color: getDomainColor(matchedAgent.domain),
              border: `1px solid ${getDomainColor(matchedAgent.domain)}20`
            }}>
              {matchedAgent.domain?.toUpperCase()}
            </span>
          )}
        </div>
      </div>
      {hasCode ? <HighlightedCode code={rawMsg} /> : (
        <p style={{ margin: 0, fontSize: "0.82rem", color: "#d1d5db", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{rawMsg}</p>
      )}
    </div>
  );
}

const getModelBadge = (modelName) => {
  if (!modelName) return null;
  const isLlama = modelName.includes("Llama");
  return (
    <span style={{
      fontSize: "0.65rem", padding: "0.15rem 0.4rem", borderRadius: "4px",
      background: isLlama ? "rgba(167, 139, 250, 0.15)" : "rgba(6, 182, 212, 0.15)",
      border: isLlama ? "1px solid rgba(167, 139, 250, 0.3)" : "1px solid rgba(6, 182, 212, 0.3)",
      color: isLlama ? "#a78bfa" : "#67e8f9",
      fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "0.2rem",
      whiteSpace: "nowrap"
    }}>
      {isLlama ? "🦙 Featherless" : "☁️ AIML API"}
    </span>
  );
};

function getEffectiveAssignments(preset, customAssignments) {
  if (preset === "hybrid") {
    return {
      conductor: "gpt-4o-mini",
      coder: "gpt-4o-mini",
      high_stakes: "unsloth/Meta-Llama-3.1-8B-Instruct",
      general: "gpt-4o-mini"
    };
  }
  if (preset === "featherless") {
    return {
      conductor: "unsloth/Meta-Llama-3.1-8B-Instruct",
      coder: "unsloth/Meta-Llama-3.1-8B-Instruct",
      high_stakes: "unsloth/Meta-Llama-3.1-70B-Instruct",
      general: "unsloth/Meta-Llama-3.1-8B-Instruct"
    };
  }
  if (preset === "aiml") {
    return {
      conductor: "gpt-4o-mini",
      coder: "gpt-4o",
      high_stakes: "gpt-4o",
      general: "gpt-4o-mini"
    };
  }
  const assigns = customAssignments || {};
  return {
    conductor: assigns.conductor || "gpt-4o-mini",
    coder: assigns.coder || "gpt-4o-mini",
    high_stakes: assigns.high_stakes || "unsloth/Meta-Llama-3.1-8B-Instruct",
    general: assigns.general || "gpt-4o-mini"
  };
}

// ─── Main App ──────────────────────────────────────────────────────────
function App() {
  // ── State ──
  const [status, setStatus] = useState("IDLE");
  const [prId, setPrId] = useState("PR-104");
  const [diffFiles, setDiffFiles] = useState([]);
  const [triageResult, setTriageResult] = useState(null);
  const [consensusRound, setConsensusRound] = useState(0);
  const [roomId, setRoomId] = useState(null);
  const [currentCode, setCurrentCode] = useState(null);
  const [schemaCheck, setSchemaCheck] = useState(null);
  const [openapiCheck, setOpenapiCheck] = useState(null);
  const [rbacCheck, setRbacCheck] = useState(null);
  const [mcpTargetsFromServer, setMcpTargetsFromServer] = useState(null);
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
  const [isStarting, setIsStarting] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const [debateSummary, setDebateSummary] = useState(null);
  const [scenarioFromServer, setScenarioFromServer] = useState("dynamic");
  const [modelPreset, setModelPreset] = useState("hybrid");
  const [modelAssignments, setModelAssignments] = useState({
    conductor: "gpt-4o-mini",
    coder: "gpt-4o-mini",
    high_stakes: "unsloth/Meta-Llama-3.1-8B-Instruct",
    general: "gpt-4o-mini"
  });
  const [showMappings, setShowMappings] = useState(false);
  const [showSwarmConfig, setShowSwarmConfig] = useState(false);

  const [selectedRepo, setSelectedRepo] = useState("vjb/WellActually.ai");
  const [prsList, setPrsList] = useState([]);
  const [selectedPrNumber, setSelectedPrNumber] = useState("");
  const [selectedPrDetails, setSelectedPrDetails] = useState(null);
  const [isFetchingPrs, setIsFetchingPrs] = useState(false);
  const [isFetchingPrDetails, setIsFetchingPrDetails] = useState(false);
  const [githubErrorMsg, setGithubErrorMsg] = useState("");

  const [activeTab, setActiveTab] = useState("debate");
  const chatContainerRef = useRef(null);
  const [showBackToTop, setShowBackToTop] = useState(false);

  // ── Derived state ──
  const reviewerAgents = activeAgents.filter(a => a.id?.startsWith("reviewer"));
  const hasAgents = reviewerAgents.length > 0;
  const activePhase = getActivePhase(status, hasAgents, !!selectedPrDetails);
  const isAnalyzing = (status === "TRIAGE" || (status === "RUNNING" && !hasAgents));
  const effectiveAssignments = getEffectiveAssignments(modelPreset, modelAssignments);

  const handlePresetChange = (preset) => {
    setModelPreset(preset);
    if (preset === "hybrid") {
      setModelAssignments({
        conductor: "gpt-4o-mini",
        coder: "gpt-4o-mini",
        high_stakes: "unsloth/Meta-Llama-3.1-8B-Instruct",
        general: "gpt-4o-mini"
      });
    } else if (preset === "featherless") {
      setModelAssignments({
        conductor: "unsloth/Meta-Llama-3.1-8B-Instruct",
        coder: "unsloth/Meta-Llama-3.1-8B-Instruct",
        high_stakes: "unsloth/Meta-Llama-3.1-70B-Instruct",
        general: "unsloth/Meta-Llama-3.1-8B-Instruct"
      });
    } else if (preset === "aiml") {
      setModelAssignments({
        conductor: "gpt-4o-mini",
        coder: "gpt-4o",
        high_stakes: "gpt-4o",
        general: "gpt-4o-mini"
      });
    } else if (preset === "custom") {
      setShowMappings(true);
    }
  };


  // ── API Calls ──
  const fetchPRs = async (repoName) => {
    setIsFetchingPrs(true);
    setGithubErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/github/prs?repo=${encodeURIComponent(repoName)}`);
      if (res.ok) {
        const isFallback = res.headers.get("X-GitHub-Fallback") === "true";
        if (isFallback) setGithubErrorMsg(`Offline mode: Loaded mock data for "${repoName}".`);
        const data = await res.json();
        setPrsList(data || []);
        if (data?.length > 0) {
          setSelectedPrNumber(data[0].number.toString());
          fetchPRDetails(repoName, data[0].number);
        } else {
          setSelectedPrNumber("");
          setSelectedPrDetails(null);
        }
      } else {
        setGithubErrorMsg(`Failed to fetch PRs for "${repoName}".`);
      }
    } catch (err) {
      setGithubErrorMsg("Network error: Backend server unreachable.");
    } finally {
      setIsFetchingPrs(false);
    }
  };

  const fetchPRDetails = async (repoName, prNum) => {
    setIsFetchingPrDetails(true);
    try {
      const res = await fetch(`${API_BASE}/api/github/pr-details?repo=${encodeURIComponent(repoName)}&number=${prNum}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedPrDetails(data);
      }
    } catch (err) {
      console.error("Error fetching PR details:", err);
    } finally {
      setIsFetchingPrDetails(false);
    }
  };

  useEffect(() => {
    if (prsList.length === 0) fetchPRs(selectedRepo);
  }, []);

  const handleStart = async () => {
    setIsStarting(true);
    try {
      const payload = {
        scenario: "dynamic",
        repo: selectedRepo,
        pr_number: selectedPrNumber ? parseInt(selectedPrNumber, 10) : null,
        model_preset: modelPreset,
        model_assignments: effectiveAssignments
      };
      await fetch(`${API_BASE}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
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

  // ── Polling ──
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const resStatus = await fetch(`${API_BASE}/api/status`);
        if (resStatus.ok) {
          setBackendOnline(true);
          const d = await resStatus.json();
          setStatus(d.status);
          setPrId(d.pr_id);
          setDiffFiles(d.diff_files || []);
          setTriageResult(d.triage_result);
          setConsensusRound(d.consensus_round);
          setRoomId(d.room_id);
          setCurrentCode(d.current_code);
          setSchemaCheck(d.schema_check);
          setOpenapiCheck(d.openapi_check);
          setRbacCheck(d.rbac_check);
          setDebateSummary(d.debate_summary);
          setScenarioFromServer(d.scenario);
          setMcpTargetsFromServer(d.mcp_targets);
          setInitialSchemaCheck(d.initial_schema_check);
          setInitialOpenapiCheck(d.initial_openapi_check);
          setInitialRbacCheck(d.initial_rbac_check);
          setResolutionType(d.resolution_type);
          setPrDiff(d.pr_diff);
          setPrTitle(d.pr_title || "");
          setPrBranch(d.pr_branch || "");
          setReviewerAuthRole(d.reviewer_auth_role || "Auth & Fraud SME");
          setReviewerAuthDomain(d.reviewer_auth_domain || "auth");
          setReviewerCartRole(d.reviewer_cart_role || "Cart SME");
          setReviewerCartDomain(d.reviewer_cart_domain || "cart");
          setActiveAgents(d.active_agents || []);
          if (d.status !== "IDLE") {
            if (d.model_preset) setModelPreset(d.model_preset);
            if (d.model_assignments) setModelAssignments(d.model_assignments);
          }
        }
        const resEvents = await fetch(`${API_BASE}/api/events`);
        if (resEvents.ok) setEvents(await resEvents.json());
      } catch {
        setBackendOnline(false);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { if (status !== 'IDLE') setIsStarting(false); }, [status]);
  useEffect(() => { if (chatContainerRef.current) chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight; }, [events.length]);
  useEffect(() => {
    const h = () => setShowBackToTop(window.scrollY > 300);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  // Fetch telemetry on status change
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/telemetry`);
        if (res.ok) setWatchdogLogs(await res.json());
      } catch {}
    };
    fetchTelemetry();
  }, [status]);

  const canReset = !["IDLE", "RUNNING", "TRIAGE", "PENDING_HUMAN_APPROVAL"].includes(status);
  const canStart = ["IDLE", "COMPLETED", "HALTED", "CRASHED"].includes(status) && !isStarting;

  const lastEvent = events[events.length - 1];
  const activeSender = lastEvent ? lastEvent.sender.toLowerCase() : "";

  // ── Task 3: Glow persistence — track last 3 speakers with fade-out ──
  const [lastActiveSenders, setLastActiveSenders] = useState([]);
  const lastActiveSendersRef = useRef([]);

  useEffect(() => {
    if (!activeSender) return;
    const now = Date.now();
    setLastActiveSenders(prev => {
      // Remove the current sender if already in the list, then prepend
      const filtered = prev.filter(s => s.sender !== activeSender);
      const updated = [{ sender: activeSender, ts: now }, ...filtered].slice(0, 3);
      lastActiveSendersRef.current = updated;
      return updated;
    });
    // Set up a cleanup timer to remove stale entries after 4s
    const timer = setTimeout(() => {
      setLastActiveSenders(prev => prev.filter(s => Date.now() - s.ts < 4000));
    }, 4100);
    return () => clearTimeout(timer);
  }, [activeSender]);

  // Refresh opacity values periodically during active debate
  useEffect(() => {
    if (status !== "RUNNING" || lastActiveSendersRef.current.length === 0) return;
    const interval = setInterval(() => {
      setLastActiveSenders(prev => {
        const filtered = prev.filter(s => Date.now() - s.ts < 4000);
        if (filtered.length !== prev.length) return filtered;
        return [...prev]; // force re-render for opacity recalc
      });
    }, 500);
    return () => clearInterval(interval);
  }, [status]);

  // ── MCP Display Helpers ──
  const displaySchemaCheck = schemaCheck || initialSchemaCheck;
  const displayOpenapiCheck = openapiCheck || initialOpenapiCheck;
  const displayRbacCheck = rbacCheck || initialRbacCheck;

  const mcpTargets = mcpTargetsFromServer
    ? { table: mcpTargetsFromServer.schema_table, endpoint: mcpTargetsFromServer.api_endpoint, rbac: mcpTargetsFromServer.rbac_target }
    : { table: null, endpoint: null, rbac: null };

  const showSchemaCheck = displaySchemaCheck || (mcpTargets.table && mcpTargets.table !== "None" && mcpTargets.table !== "null");
  const showOpenapiCheck = displayOpenapiCheck || (mcpTargets.endpoint && mcpTargets.endpoint !== "None" && mcpTargets.endpoint !== "null");
  const showRbacCheck = displayRbacCheck || (mcpTargets.rbac && mcpTargets.rbac !== "None" && mcpTargets.rbac !== "null");
  const hasAnyMcp = status !== "IDLE" && (showSchemaCheck || showOpenapiCheck || showRbacCheck);

  // PR display fields
  const displayDiffFiles = (status === "IDLE" && selectedPrDetails) ? selectedPrDetails.diff_files : diffFiles;
  const displayPrTitle = status === "IDLE" ? (selectedPrDetails?.title || "Pending load") : (prTitle || selectedPrDetails?.title || "");
  const displayPrNumber = status === "IDLE" ? (selectedPrDetails ? `#${selectedPrDetails.number}` : "—") : prId;
  const displayBranch = status === "IDLE" ? (selectedPrDetails?.branch || "—") : (prBranch || "—");

  // Status badge styling
  const getStatusColor = (s) => {
    switch (s) {
      case "IDLE": return { bg: "rgba(156,163,175,0.12)", border: "rgba(156,163,175,0.3)", text: "#9ca3af" };
      case "TRIAGE": return { bg: "rgba(234,179,8,0.12)", border: "rgba(234,179,8,0.4)", text: "#eab308" };
      case "PENDING_HUMAN_APPROVAL": return { bg: "rgba(239,68,68,0.15)", border: "rgba(239,68,68,0.5)", text: "#ef4444" };
      case "RUNNING": return { bg: "rgba(34,197,94,0.12)", border: "rgba(34,197,94,0.4)", text: "#22c55e" };
      case "HALTED": return { bg: "rgba(239,68,68,0.12)", border: "rgba(239,68,68,0.4)", text: "#ef4444" };
      case "COMPLETED": return { bg: "rgba(59,130,246,0.12)", border: "rgba(59,130,246,0.4)", text: "#3b82f6" };
      case "CRASHED": return { bg: "rgba(220,38,38,0.2)", border: "rgba(220,38,38,0.6)", text: "#dc2626" };
      default: return { bg: "rgba(156,163,175,0.12)", border: "rgba(156,163,175,0.3)", text: "#9ca3af" };
    }
  };

  const statusStyle = getStatusColor(status);

  // ── RENDER ──
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", padding: "1.5rem 2rem", maxWidth: "1600px", margin: "0 auto" }}>

      {/* ═══ HEADER ═══ */}
      <header style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: "0.75rem", padding: "0 0.25rem"
      }}>
        <div>
          <h1 style={{
            margin: 0, fontSize: "2rem", fontWeight: 900, letterSpacing: "-0.02em",
            background: "linear-gradient(135deg, #06b6d4 0%, #a855f7 50%, #ec4899 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>
            WellActually.ai
          </h1>
          <p style={{ margin: "0.15rem 0 0 0", color: "#6b7280", fontSize: "0.78rem", fontWeight: 500, letterSpacing: "0.03em" }}>
            Just-in-Time Swarm Intelligence · Powered by Band.ai
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          {!backendOnline && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#ef4444" }} />
              <span style={{ fontSize: "0.78rem", color: "#ef4444", fontWeight: 600 }}>Offline</span>
            </div>
          )}

          {status === "RUNNING" && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span className="pulse" style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#22c55e" }} />
              <span style={{ fontSize: "0.78rem", color: "#22c55e", fontWeight: 500 }}>
                Live · Round {consensusRound}/2
              </span>
            </div>
          )}

          <div style={{
            padding: "0.35rem 0.75rem", borderRadius: "8px",
            background: statusStyle.bg, border: `1px solid ${statusStyle.border}`,
            color: statusStyle.text, fontSize: "0.78rem", fontWeight: 700,
            letterSpacing: "0.06em"
          }}>
            {status}
          </div>

          <button onClick={handleStart} disabled={!canStart} style={{
            padding: "0.45rem 1.25rem", borderRadius: "10px", cursor: canStart ? "pointer" : "not-allowed",
            fontWeight: 700, fontSize: "0.82rem",
            background: canStart ? "linear-gradient(135deg, #0891b2, #7c3aed)" : "rgba(55,65,81,0.5)",
            border: "none", color: "white", opacity: canStart ? 1 : 0.5,
            transition: "all 0.2s", boxShadow: canStart ? "0 4px 20px rgba(124, 58, 237, 0.3)" : "none"
          }}>
            {isStarting ? "Synthesizing..." : "⚡ Launch JIT Swarm"}
          </button>

          {canReset && (
            <button onClick={handleReset} style={{
              padding: "0.4rem 0.8rem", borderRadius: "8px",
              background: "none", border: "1px solid rgba(239,68,68,0.4)",
              color: "#f87171", fontWeight: 600, fontSize: "0.78rem", cursor: "pointer"
            }}>
              ↺ Reset
            </button>
          )}
        </div>
      </header>

      {/* ═══ PIPELINE PROGRESS ═══ */}
      <PipelineProgress activePhase={activePhase} />

      {/* ═══ MAIN CONTENT GRID ═══ */}
      <div className="main-grid" style={{
        display: "grid", gridTemplateColumns: "minmax(380px, 1fr) minmax(480px, 1.4fr)",
        gap: "1.5rem", flex: 1, minHeight: 0
      }}>
        {/* ─── LEFT COLUMN ─── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", overflowY: "auto", minHeight: 0 }}>

          {/* Phase 1: INGEST — PR Loader */}
          <section className="glass-panel" style={{ padding: "1.25rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1rem" }}>
              <span style={{ fontSize: "1.1rem" }}>🎯</span>
              <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "#06b6d4" }}>PR Ingest</h2>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.68rem", color: "#6b7280", marginBottom: "0.2rem", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                  Repository
                </label>
                <div style={{ display: "flex", gap: "0.4rem" }}>
                  <input type="text" value={selectedRepo} onChange={(e) => setSelectedRepo(e.target.value)}
                    placeholder="owner/repo"
                    style={{
                      flex: 1, padding: "0.4rem 0.6rem", borderRadius: "8px",
                      border: "1px solid rgba(255,255,255,0.1)", background: "rgba(0,0,0,0.3)",
                      color: "white", fontSize: "0.82rem", fontFamily: "'JetBrains Mono', monospace"
                    }}
                  />
                  <button onClick={() => fetchPRs(selectedRepo)} disabled={isFetchingPrs}
                    style={{
                      padding: "0.4rem 0.8rem", borderRadius: "8px",
                      background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)",
                      color: "#67e8f9", fontSize: "0.75rem", cursor: "pointer", fontWeight: 600
                    }}
                  >
                    {isFetchingPrs ? "..." : "Load"}
                  </button>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.68rem", color: "#6b7280", marginBottom: "0.2rem", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                  Pull Request
                </label>
                <select value={selectedPrNumber}
                  onChange={(e) => { const prNum = e.target.value; setSelectedPrNumber(prNum); if (prNum) fetchPRDetails(selectedRepo, parseInt(prNum, 10)); }}
                  style={{
                    width: "100%", padding: "0.4rem 0.6rem", borderRadius: "8px",
                    border: "1px solid rgba(255,255,255,0.1)", background: "rgba(0,0,0,0.3)",
                    color: "white", fontSize: "0.82rem"
                  }}
                >
                  {prsList.length === 0 ? (
                    <option value="">-- No open PRs --</option>
                  ) : prsList.map(pr => (
                    <option key={pr.number} value={String(pr.number)}>#{pr.number} — {pr.title}</option>
                  ))}
                </select>
              </div>

              {githubErrorMsg && (
                <div style={{
                  padding: "0.4rem 0.6rem", borderRadius: "6px",
                  background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.2)",
                  color: "#fde047", fontSize: "0.7rem"
                }}>
                  ⚠️ {githubErrorMsg}
                </div>
              )}

              {/* PR Summary mini-card */}
              {selectedPrDetails && (
                <div style={{
                  padding: "0.6rem 0.75rem", borderRadius: "8px",
                  background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.12)"
                }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#e5e7eb", marginBottom: "0.3rem" }}>
                    {displayPrNumber} · {displayPrTitle}
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "#6b7280", marginBottom: "0.3rem" }}>
                    Branch: <code style={{ color: "#67e8f9" }}>{displayBranch}</code>
                  </div>
                  <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                    {(displayDiffFiles || []).map((f, i) => (
                      <span key={i} style={{
                        fontSize: "0.65rem", padding: "0.08rem 0.35rem", borderRadius: "4px",
                        background: "rgba(244,114,182,0.1)", border: "1px solid rgba(244,114,182,0.15)",
                        color: "#f472b6", fontFamily: "'JetBrains Mono', monospace"
                      }}>{f}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Swarm Model Routing Card */}
          <section className="glass-panel fade-in" style={{ padding: "1.25rem" }}>
            <div 
              onClick={() => setShowSwarmConfig(!showSwarmConfig)}
              style={{ 
                display: "flex", 
                alignItems: "center", 
                gap: "0.6rem", 
                cursor: "pointer", 
                userSelect: "none"
              }}
            >
              <span style={{ fontSize: "1.1rem" }}>🎛️</span>
              <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "#a855f7", flex: 1 }}>Swarm Model Routing</h2>
              <span style={{
                fontSize: "0.65rem",
                padding: "0.15rem 0.45rem",
                borderRadius: "4px",
                background: "rgba(168,85,247,0.1)",
                border: "1px solid rgba(168,85,247,0.2)",
                color: "#c084fc",
                fontWeight: 600,
                marginRight: "0.2rem"
              }}>
                {modelPreset === "hybrid" ? "Hybrid Swarm" :
                 modelPreset === "featherless" ? "Featherless AI (OS)" :
                 modelPreset === "aiml" ? "AIML API (Comm)" : "Custom Routing"}
              </span>
              <span style={{ fontSize: "0.75rem", color: "#a855f7", transition: "transform 0.2s ease" }}>
                {showSwarmConfig ? "▲" : "▼"}
              </span>
            </div>

            {showSwarmConfig && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem", marginTop: "1rem" }}>
                {/* Presets Toggle */}
                <div>
                  <label style={{ display: "block", fontSize: "0.68rem", color: "#6b7280", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                    Model Preset
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.4rem" }}>
                    {[
                      { id: "hybrid", label: "Hybrid Swarm" },
                      { id: "featherless", label: "Featherless AI (OS)" },
                      { id: "aiml", label: "AIML API (Comm)" },
                      { id: "custom", label: "Custom Routing" }
                    ].map((p) => {
                      const isActive = modelPreset === p.id;
                      const disabled = status !== "IDLE";
                      return (
                        <button
                          key={p.id}
                          disabled={disabled}
                          onClick={() => handlePresetChange(p.id)}
                          style={{
                            padding: "0.45rem 0.5rem",
                            borderRadius: "6px",
                            fontSize: "0.75rem",
                            fontWeight: isActive ? 600 : 500,
                            cursor: disabled ? "not-allowed" : "pointer",
                            transition: "all 0.2s ease",
                            background: isActive 
                              ? "rgba(168,85,247,0.15)" 
                              : "rgba(255,255,255,0.02)",
                            border: isActive 
                              ? "1px solid rgba(168,85,247,0.4)" 
                              : "1px solid rgba(255,255,255,0.08)",
                            color: isActive ? "#c084fc" : "#9ca3af",
                            opacity: disabled && !isActive ? 0.5 : 1
                          }}
                        >
                          {p.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Accordion Toggle */}
                <div 
                  onClick={() => setShowMappings(!showMappings)}
                  style={{ 
                    display: "flex", 
                    justifyContent: "space-between", 
                    alignItems: "center", 
                    cursor: "pointer", 
                    padding: "0.5rem 0.6rem", 
                    borderRadius: "6px",
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.06)",
                    color: "#9ca3af",
                    fontSize: "0.72rem",
                    fontWeight: 600,
                    userSelect: "none",
                    transition: "all 0.2s ease",
                    marginTop: "0.2rem"
                  }}
                >
                  <span>{showMappings ? "⚙️ Hide Swarm Mappings" : "⚙️ View Swarm Mappings"}</span>
                  <span style={{ fontSize: "0.6rem" }}>{showMappings ? "▲" : "▼"}</span>
                </div>

                {showMappings && (
                  <>
                    {/* Mappings */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", background: "rgba(0,0,0,0.15)", padding: "0.6rem", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.03)" }}>
                      {[
                        { key: "conductor", label: "Conductor (Orchestration)", desc: "Orchestrates Swarm Analysis & Debate" },
                        { key: "coder", label: "Coder (Implementation)", desc: "Implements fixes to resolve reviewer concerns" },
                        { key: "high_stakes", label: "High-Stakes SME (Auth/DB)", desc: "Routes reviewers in Auth, DB, Security & Billing" },
                        { key: "general", label: "General SME (QA/Docs)", desc: "Routes reviewers in QA, Docs, API & general code" }
                      ].map((role) => (
                        <div key={role.key} style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                          <div style={{ display: "flex", flexDirection: "column" }}>
                            <span style={{ fontSize: "0.72rem", color: "#e5e7eb", fontWeight: 600 }}>{role.label}</span>
                            <span style={{ fontSize: "0.58rem", color: "#9ca3af", fontStyle: "italic", marginBottom: "0.1rem" }}>{role.desc}</span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            <select
                              value={effectiveAssignments[role.key] || "gpt-4o-mini"}
                              disabled={modelPreset !== "custom" || status !== "IDLE"}
                              onChange={(e) => {
                                setModelAssignments(prev => ({ ...prev, [role.key]: e.target.value }));
                              }}
                              style={{
                                flex: 1,
                                padding: "0.35rem 0.5rem",
                                borderRadius: "6px",
                                border: "1px solid rgba(255,255,255,0.1)",
                                background: modelPreset === "custom" && status === "IDLE" ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.03)",
                                color: modelPreset === "custom" && status === "IDLE" ? "white" : "#9ca3af",
                                fontSize: "0.78rem",
                                cursor: modelPreset === "custom" && status === "IDLE" ? "pointer" : "default"
                              }}
                            >
                              <option value="gpt-4o-mini">GPT-4o Mini</option>
                              <option value="gpt-4o">GPT-4o</option>
                              <option value="unsloth/Meta-Llama-3.1-8B-Instruct">Llama 3.1 8B</option>
                              <option value="unsloth/Meta-Llama-3.1-70B-Instruct">Llama 3.1 70B</option>
                            </select>
                            {getModelBadge(effectiveAssignments[role.key])}
                          </div>
                        </div>
                      ))}
                    </div>

                    {modelPreset !== "custom" && (
                      <div style={{ fontSize: "0.65rem", color: "#6b7280", fontStyle: "italic", textAlign: "center" }}>
                        ℹ️ Selected preset defines routing. Select "Custom Routing" to modify.
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </section>

          {/* Phase 2: JIT SYNTHESIS — The Hero */}
          <JITSynthesisPanel agents={activeAgents} status={status} isAnalyzing={isAnalyzing} />

          {/* Phase 3: DEPLOY — Topology + Band.ai Room */}
          {(hasAgents || status === "RUNNING") && (
            <section className="glass-panel fade-in" style={{ padding: "1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.5rem" }}>
                <span style={{ fontSize: "1.1rem" }}>🔗</span>
                <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "#3b82f6" }}>Band.ai Swarm Deployment</h2>
                {roomId && (
                  <span style={{ fontSize: "0.65rem", color: "#6b7280", fontFamily: "'JetBrains Mono', monospace", marginLeft: "auto" }}>
                    Room: {roomId.substring(0, 12)}…
                  </span>
                )}
              </div>
              <AgentTopology status={status} activeSender={activeSender} activeAgents={activeAgents} lastActiveSenders={lastActiveSenders} />
            </section>
          )}

          {/* Triage & HITL panels — only show during debate phase onwards */}
          {triageResult && activePhase >= 3 && (
            <section className={`glass-panel fade-in ${status === "PENDING_HUMAN_APPROVAL" ? "glow-red" : ""}`} style={{ padding: "1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                <span style={{ fontSize: "1rem" }}>🛡️</span>
                <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: triageResult.is_high_stakes ? "#ef4444" : "#10b981" }}>
                  Compliance Triage
                </h2>
                <span style={{
                  fontSize: "0.65rem", fontWeight: 700, padding: "0.1rem 0.4rem", borderRadius: "4px",
                  background: triageResult.is_high_stakes ? "rgba(239,68,68,0.12)" : "rgba(16,185,129,0.12)",
                  color: triageResult.is_high_stakes ? "#ef4444" : "#10b981",
                  marginLeft: "auto"
                }}>
                  {triageResult.is_high_stakes ? "HIGH STAKES" : "CLEAN"}
                </span>
              </div>

              <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: triageResult.is_high_stakes ? "1rem" : 0 }}>
                {triageResult.required_approvals?.map((appr, idx) => (
                  <span key={idx} style={{
                    padding: "0.15rem 0.4rem", borderRadius: "4px",
                    background: "rgba(244,114,182,0.1)", border: "1px solid rgba(244,114,182,0.2)",
                    color: "#f472b6", fontSize: "0.72rem"
                  }}>{appr}</span>
                ))}
              </div>

              {/* HITL Action Bars */}
              {status === "PENDING_HUMAN_APPROVAL" && (
                <div style={{ padding: "0.75rem", borderRadius: "10px", border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.04)" }}>
                  <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.82rem", color: "#f87171", fontWeight: 600 }}>
                    ⚠️ Human approval required to proceed
                  </p>
                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <button onClick={() => handleConsent(true)} style={{
                      flex: 1, padding: "0.45rem", borderRadius: "8px",
                      background: "#dc2626", border: "none", color: "white", fontWeight: 700, cursor: "pointer", fontSize: "0.8rem"
                    }}>Approve Exception</button>
                    <button onClick={() => handleConsent(false)} style={{
                      flex: 1, padding: "0.45rem", borderRadius: "8px",
                      background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.8rem"
                    }}>Reject PR</button>
                  </div>
                </div>
              )}

              {status === "HALTED" && !resolutionType && (
                <div style={{ padding: "0.75rem", borderRadius: "10px", border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.04)" }}>
                  <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.82rem", color: "#f87171", fontWeight: 600 }}>
                    ⚠️ Consensus Deadlock — Human intervention required
                  </p>
                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <button onClick={() => handleConsent(true)} style={{
                      flex: 1, padding: "0.45rem", borderRadius: "8px",
                      background: "#2563eb", border: "none", color: "white", fontWeight: 700, cursor: "pointer", fontSize: "0.8rem"
                    }}>Override & Approve</button>
                    <button onClick={() => handleConsent(false)} style={{
                      flex: 1, padding: "0.45rem", borderRadius: "8px",
                      background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.8rem"
                    }}>Reject PR</button>
                  </div>
                </div>
              )}
            </section>
          )}



          {/* Phase 5: Verdict Summary — Rich Scorecard */}
          {debateSummary && (status === "HALTED" || status === "COMPLETED" || status === "CRASHED") && (() => {
            const jitAgentCount = activeAgents.filter(a => a.id?.startsWith("reviewer")).length;
            const uniqueDomains = [...new Set(activeAgents.filter(a => a.id?.startsWith("reviewer") && a.domain).map(a => a.domain))];
            const totalFilesAnalyzed = (diffFiles?.length || displayDiffFiles?.length || 0);

            const verdictColor = status === "COMPLETED" ? "#22c55e" : "#ef4444";

            return (
            <section className="glass-panel fade-in" style={{ padding: "1.5rem", borderLeft: `3px solid ${verdictColor}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.25rem" }}>
                <span style={{ fontSize: "1.2rem" }}>📊</span>
                <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 800, color: verdictColor }}>
                  Verdict Scorecard
                </h2>
                <span style={{
                  fontSize: "0.6rem", fontWeight: 700, padding: "0.15rem 0.5rem", borderRadius: "6px",
                  background: `${verdictColor}15`, border: `1px solid ${verdictColor}30`, color: verdictColor,
                  textTransform: "uppercase", letterSpacing: "0.08em", marginLeft: "auto"
                }}>
                  {status === "COMPLETED" ? "✓ PASSED" : status === "CRASHED" ? "💥 CRASHED" : "⚠ HALTED"}
                </span>
              </div>

              {/* Stats Grid — 3x2 */}
              <div className="verdict-stats-grid" style={{
                display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.6rem", marginBottom: "1.25rem"
              }}>
                {[
                  { icon: "🔄", label: "Rounds", value: debateSummary.total_rounds, color: "#f59e0b" },
                  { icon: "🤖", label: "JIT Agents", value: jitAgentCount, color: "#a855f7" },
                  { icon: "📁", label: "Files Analyzed", value: totalFilesAnalyzed, color: "#06b6d4" },
                  { icon: "✅", label: "Approvals", value: debateSummary.approvals, color: "#22c55e" },
                  { icon: "❌", label: "Rejections", value: debateSummary.rejections, color: "#ef4444" },
                  { icon: "⚡", label: "Swarm Model", value: "Multi-LLM", color: "#f97316" },
                ].map(({ icon, label, value, color }) => (
                  <div key={label} className="verdict-stat-card" style={{
                    background: `${color}08`, borderRadius: "12px",
                    padding: "0.75rem 0.6rem", textAlign: "center",
                    border: `1px solid ${color}18`,
                    transition: "all 0.3s"
                  }}>
                    <div style={{ fontSize: "1rem", marginBottom: "0.2rem" }}>{icon}</div>
                    <div style={{ fontSize: "1.4rem", fontWeight: 800, color, lineHeight: 1.1 }}>{value}</div>
                    <div style={{ fontSize: "0.62rem", color: "#6b7280", fontWeight: 600, marginTop: "0.2rem", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
                  </div>
                ))}
              </div>

              {/* Outcome + Domains */}
              <div style={{ display: "flex", gap: "0.6rem", marginBottom: "1rem" }}>
                <div style={{
                  flex: 1, padding: "0.65rem 0.75rem", borderRadius: "10px",
                  background: debateSummary.is_deadlocked ? "rgba(239,68,68,0.06)" : "rgba(34,197,94,0.06)",
                  border: `1px solid ${debateSummary.is_deadlocked ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)"}`
                }}>
                  <div style={{ fontSize: "0.62rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.25rem" }}>Outcome</div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 700, color: debateSummary.is_deadlocked ? "#ef4444" : "#22c55e" }}>
                    {debateSummary.is_deadlocked ? "⚠️ Deadlock" : "✓ Consensus"}
                  </div>
                </div>
                <div style={{
                  flex: 1.5, padding: "0.65rem 0.75rem", borderRadius: "10px",
                  background: "rgba(168,85,247,0.04)", border: "1px solid rgba(168,85,247,0.12)"
                }}>
                  <div style={{ fontSize: "0.62rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.3rem" }}>Domains Covered</div>
                  <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                    {uniqueDomains.length > 0 ? uniqueDomains.map(d => (
                      <span key={d} style={{
                        fontSize: "0.65rem", padding: "0.1rem 0.4rem", borderRadius: "4px",
                        background: `${getDomainColor(d)}15`, color: getDomainColor(d),
                        border: `1px solid ${getDomainColor(d)}25`, fontWeight: 600
                      }}>{getDomainIcon(d)} {d}</span>
                    )) : <span style={{ fontSize: "0.7rem", color: "#4b5563", fontStyle: "italic" }}>—</span>}
                  </div>
                </div>
              </div>

              {/* Per-reviewer breakdown */}
              {debateSummary.rejections_by_reviewer && Object.keys(debateSummary.rejections_by_reviewer).length > 0 && (
                <div style={{ marginBottom: "0.75rem" }}>
                  <div style={{ fontSize: "0.65rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.4rem" }}>Rejection Breakdown</div>
                  {Object.entries(debateSummary.rejections_by_reviewer).map(([name, info]) => (
                    <div key={name} style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "0.4rem 0.6rem", marginBottom: "0.3rem", borderRadius: "8px",
                      background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.1)"
                    }}>
                      <div>
                        <span style={{ fontWeight: 600, fontSize: "0.8rem", color: "#e5e7eb" }}>{info.role}</span>
                        <span style={{
                          fontSize: "0.6rem", marginLeft: "0.4rem",
                          background: `${getDomainColor(info.domain)}12`, color: getDomainColor(info.domain),
                          padding: "0.05rem 0.3rem", borderRadius: "3px"
                        }}>{info.domain}</span>
                      </div>
                      <span style={{ color: "#ef4444", fontWeight: 700, fontSize: "0.8rem" }}>{info.count}× rejected</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Final resolution banner */}
              <div style={{
                padding: "0.5rem 0.75rem", borderRadius: "10px",
                background: status === "COMPLETED" ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
                border: `1px solid ${status === "COMPLETED" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)"}`
              }}>
                <span style={{ fontSize: "0.82rem", color: status === "COMPLETED" ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
                  {resolutionType === "consensus" ? "✓ Approved by Swarm Consensus"
                    : resolutionType === "human_override" ? "✓ Approved (Human Override)"
                    : resolutionType === "halted" ? "⚠️ Halted — PR Rejected"
                    : status === "COMPLETED" ? (debateSummary?.is_deadlocked ? "✓ Approved (Human Override)" : "✓ Approved by Swarm Consensus")
                    : status === "CRASHED" ? "💥 Pipeline Crashed"
                    : "⚠️ Halted — Awaiting HITL"}
                </span>
              </div>
            </section>
            );
          })()}
        </div>

        {/* ─── RIGHT COLUMN: Live Feed ─── */}
        <section className="glass-panel" style={{
          display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden", padding: "1.25rem"
        }}>
          {/* Tabs */}
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "0.6rem", marginBottom: "0.75rem"
          }}>
            <div style={{ display: "flex", gap: "1rem" }}>
              {[
                { key: "debate", label: "⚔️ Live Debate Feed" },
                { key: "code", label: "💻 Proposed Code" }
              ].map(tab => (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    color: activeTab === tab.key ? "#06b6d4" : "#6b7280",
                    fontWeight: 700, fontSize: "0.88rem",
                    borderBottom: activeTab === tab.key ? "2px solid #06b6d4" : "2px solid transparent",
                    paddingBottom: "0.4rem", transition: "all 0.2s"
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            {roomId && (
              <span style={{ fontSize: "0.68rem", color: "#4b5563", fontFamily: "'JetBrains Mono', monospace" }}>
                {roomId.substring(0, 10)}…
              </span>
            )}
          </div>

          {activeTab === "debate" ? (
            <div ref={chatContainerRef} style={{
              flex: 1, overflowY: "auto", display: "flex", flexDirection: "column",
              gap: "0.6rem", paddingRight: "0.25rem"
            }}>
              {events.length === 0 ? (
                <div style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
                  justifyContent: "center", gap: "1rem", color: "#4b5563"
                }}>
                  <div style={{ fontSize: "2.5rem", opacity: 0.5 }}>⚔️</div>
                  <div style={{ fontSize: "0.9rem", fontStyle: "italic" }}>
                    Debate room idle. Launch a JIT swarm to begin.
                  </div>
                </div>
              ) : (
                events.map((evt, idx) => (
                  <DebateMessage key={idx} evt={evt} activeAgents={activeAgents} />
                ))
              )}

              {status === "RUNNING" && (
                <div style={{
                  display: "flex", alignItems: "center", gap: "0.5rem",
                  padding: "0.6rem 0.8rem", borderRadius: "10px",
                  background: "rgba(34,197,94,0.04)", border: "1px solid rgba(34,197,94,0.1)"
                }}>
                  <div style={{ display: "flex", gap: "3px" }}>
                    {[0, 1, 2].map(i => (
                      <span key={i} style={{
                        width: "5px", height: "5px", borderRadius: "50%",
                        background: "#22c55e",
                        animation: `thinkingDot 1.4s ease-in-out ${i * 0.2}s infinite`
                      }} />
                    ))}
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "#22c55e", fontStyle: "italic" }}>
                    JIT Agents reasoning via Band.ai swarm room…
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div style={{ flex: 1, overflow: "auto", background: "#060810", borderRadius: "10px", padding: "1rem" }}>
              {currentCode ? (
                <div>
                  <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.85rem", color: "#22c55e" }}>
                    🛠️ Swarm Proposed Fix (Round {consensusRound}):
                  </h3>
                  <HighlightedCode code={currentCode} />
                </div>
              ) : (prDiff || selectedPrDetails?.diff) ? (
                <div>
                  <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.85rem", color: "#06b6d4" }}>
                    📄 PR Diff Under Review:
                  </h3>
                  <pre style={{
                    margin: 0, padding: "0.5rem", color: "#d1d5db",
                    fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem",
                    whiteSpace: "pre-wrap", background: "rgba(0,0,0,0.3)",
                    borderRadius: "6px", border: "1px solid rgba(255,255,255,0.04)"
                  }}>{prDiff || selectedPrDetails?.diff}</pre>
                </div>
              ) : (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#4b5563", fontStyle: "italic" }}>
                  No code proposed yet.
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {/* Back to top */}
      {showBackToTop && (
        <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="Back to top"
          style={{
            position: "fixed", bottom: "1.5rem", left: "1.5rem",
            width: "38px", height: "38px", borderRadius: "50%",
            border: "1px solid rgba(6,182,212,0.4)", background: "rgba(6,182,212,0.12)",
            backdropFilter: "blur(12px)", color: "#06b6d4", cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1rem", zIndex: 1000,
            boxShadow: "0 4px 16px rgba(0,0,0,0.5)"
          }}
        >↑</button>
      )}
    </div>
  );
}

// ─── MCP Check Row Component ───────────────────────────────────────────
function McpCheckRow({ title, target, check, status }) {
  const icon = check === null || check === undefined
    ? (status === "IDLE" ? "⚪" : "⏳")
    : check.compliant ? "✅" : "❌";

  return (
    <div style={{
      display: "flex", gap: "0.75rem", padding: "0.6rem 0.75rem",
      borderRadius: "8px", background: "rgba(0,0,0,0.12)",
      border: "1px solid rgba(255,255,255,0.03)"
    }}>
      <div style={{ fontSize: "1.2rem", flexShrink: 0 }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{
          fontWeight: 600, fontSize: "0.82rem",
          color: check && !check.compliant ? "#ef4444" : "#e5e7eb"
        }}>{title}</div>
        {target && target !== "None" && target !== "null" && (
          <div style={{ fontSize: "0.7rem", color: "#6b7280", marginTop: "0.15rem" }}>
            Target: <code style={{ color: "#67e8f9" }}>{target}</code>
          </div>
        )}
        {check && !check.compliant && check.violations && (
          <div style={{
            fontSize: "0.7rem", color: "#f87171", marginTop: "0.4rem",
            fontFamily: "'JetBrains Mono', monospace",
            background: "rgba(239,68,68,0.06)", padding: "0.4rem",
            borderRadius: "6px"
          }}>
            {check.violations.join("\n")}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

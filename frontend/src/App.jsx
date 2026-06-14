import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 1000;

// ─── Utility: Python Syntax Highlighter ────────────────────────────────
function HighlightedCode({ code }) {
  return (
    <pre style={{
      margin: '0.5rem 0 0 0',
      padding: '0.75rem',
      borderRadius: '8px',
      backgroundColor: '#0c0f16',
      overflowX: 'auto',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: '0.8rem',
      lineHeight: '1.6',
      border: '1px solid rgba(255,255,255,0.06)',
      color: '#e5e7eb',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-all'
    }}>
      <code>{code}</code>
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

// ─── JIT Synthesis Status Helpers ───────────────────────────────────────
const JIT_STATUSES = ["Synthesizing...", "Registered on Band", "Joined Room", "Ready"];

function useAgentStatuses(agents, status) {
  const [agentStatuses, setAgentStatuses] = useState({});
  const prevAgentIdsRef = useRef([]);

  useEffect(() => {
    const reviewerAgents = agents.filter(a => a.id?.startsWith("reviewer"));
    const currentIds = reviewerAgents.map(a => a.id);
    const newIds = currentIds.filter(id => !prevAgentIdsRef.current.includes(id));

    if (newIds.length > 0) {
      // New agents appeared — start their status progression
      newIds.forEach((id, idx) => {
        const delay = idx * 400;
        setAgentStatuses(prev => ({ ...prev, [id]: 0 }));
        // Progress through statuses
        setTimeout(() => setAgentStatuses(prev => ({ ...prev, [id]: 1 })), delay + 800);
        setTimeout(() => setAgentStatuses(prev => ({ ...prev, [id]: 2 })), delay + 1600);
        setTimeout(() => setAgentStatuses(prev => ({ ...prev, [id]: 3 })), delay + 2400);
      });
    }

    prevAgentIdsRef.current = currentIds;
  }, [agents]);

  // When debate is running, all are "Ready"
  useEffect(() => {
    if (status === "RUNNING") {
      const reviewerAgents = agents.filter(a => a.id?.startsWith("reviewer"));
      const all = {};
      reviewerAgents.forEach(a => { all[a.id] = 3; });
      setAgentStatuses(all);
    }
  }, [status]);

  return agentStatuses;
}

// ─── JIT Synthesis Hero Panel ──────────────────────────────────────────
function JITSynthesisPanel({ agents, status, isAnalyzing, activeSender }) {
  const reviewerAgents = agents.filter(a => a.id?.startsWith("reviewer"));
  const agentStatuses = useAgentStatuses(agents, status);
  const isDebating = status === "RUNNING" || status === "COMPLETED" || status === "HALTED" || status === "CRASHED";

  if (status === "IDLE" && !isAnalyzing && reviewerAgents.length === 0) {
    return (
      <section className="glass-panel jit-hero" style={{ textAlign: "center", padding: "3rem 2rem" }}>
        {/* Particle decoration */}
        <div style={{ position: "relative", display: "inline-block", marginBottom: "1rem" }}>
          <div style={{ fontSize: "3rem", opacity: 0.6 }}>🧠</div>
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} style={{
              position: "absolute",
              width: "4px", height: "4px", borderRadius: "50%",
              background: i % 2 === 0 ? "#a855f7" : "#ec4899",
              top: `${10 + i * 12}px`, left: `${-10 + i * 18}px`,
              animation: `particle-float ${2 + i * 0.3}s ease-in-out ${i * 0.4}s infinite`,
              opacity: 0.4
            }} />
          ))}
        </div>
        <h2 style={{ margin: "0 0 0.75rem 0", fontSize: "1.4rem", background: "linear-gradient(135deg, #a855f7, #ec4899)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", fontWeight: 800 }}>
          Just-in-Time Agent Synthesis
        </h2>
        <p style={{ margin: "0 0 1.5rem 0", color: "#9ca3af", fontSize: "0.9rem", maxWidth: "500px", marginLeft: "auto", marginRight: "auto", lineHeight: 1.6 }}>
          When a PR arrives, the Conductor AI reads the diff, identifies domains & compliance regimes,
          and <strong style={{ color: "#c084fc" }}>invents bespoke reviewer agents</strong> with custom prompts — in real time.
          No pre-configured agents. Pure JIT governance compute.
        </p>
        {/* Empty placeholder slots */}
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{
              width: "140px", height: "90px", borderRadius: "12px",
              border: "2px dashed rgba(168,85,247,0.2)",
              background: "rgba(168,85,247,0.02)",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexDirection: "column", gap: "0.3rem"
            }}>
              <span style={{ fontSize: "1.5rem", opacity: 0.3 }}>🤖</span>
              <span style={{ fontSize: "0.58rem", color: "#6b7280", textAlign: "center", padding: "0 0.4rem" }}>
                Agent slot {i}
              </span>
            </div>
          ))}
        </div>
        <p style={{ margin: "1rem 0 0 0", fontSize: "0.7rem", color: "#4b5563", fontStyle: "italic" }}>
          Agent slots will be synthesized from PR diff...
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

        {/* Animated shimmer skeleton cards with dotted border placeholders */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ position: "relative" }}>
              <div className="shimmer" style={{
                height: "70px", borderRadius: "12px",
                border: "1px solid rgba(168,85,247,0.1)"
              }} />
              <div style={{
                position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
                display: "flex", alignItems: "center", gap: "0.5rem",
                fontSize: "0.7rem", color: "rgba(168,85,247,0.5)"
              }}>
                <span style={{ animation: `pulse 1.5s ease-in-out ${i * 0.3}s infinite` }}>⟡</span>
                <span>Coalescing agent {i}...</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  // Agents have materialized — show them with entrance animation + status
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
            modelLabel = modelName.includes("70B") ? "Llama-3.1-70B via AIML API" : "Llama-3.1-8B via AIML API";
          } else {
            modelLabel = modelName.includes("mini") ? "GPT-4o Mini via AIML API" : "GPT-4o via AIML API";
          }
          const domainColor = getDomainColor(agent.domain);
          const statusIdx = agentStatuses[agent.id] ?? 3;
          const statusLabel = JIT_STATUSES[statusIdx];
          const isReady = statusIdx === 3;
          const isSpeaking = activeSender && normalizeName(activeSender).includes(normalizeName(agent.name));
          const cardClass = isReady ? "jit-agent-card-settled" : "jit-agent-card";

          return (
            <div key={agent.id} className={cardClass} style={{
              padding: "1rem",
              borderRadius: "12px",
              background: `linear-gradient(135deg, ${domainColor}08, ${domainColor}03, rgba(13,19,33,0.6))`,
              border: `1px solid ${domainColor}30`,
              position: "relative",
              overflow: "hidden",
              ...(isSpeaking ? { animation: "pulse-active 1.5s ease-in-out infinite" } : {})
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

                {/* Status badge */}
                <div style={{
                  display: "flex", alignItems: "center", gap: "0.3rem",
                  padding: "0.15rem 0.5rem", borderRadius: "6px",
                  background: isReady ? "rgba(34,197,94,0.12)" : "rgba(168,85,247,0.12)",
                  border: `1px solid ${isReady ? "rgba(34,197,94,0.3)" : "rgba(168,85,247,0.3)"}`,
                  fontSize: "0.6rem", fontWeight: 600,
                  color: isReady ? "#22c55e" : "#c084fc"
                }}>
                  {!isReady && (
                    <span style={{
                      width: "5px", height: "5px", borderRadius: "50%",
                      background: "#c084fc",
                      animation: "pulse 1s ease-in-out infinite"
                    }} />
                  )}
                  {isReady && <span>✓</span>}
                  {statusLabel}
                </div>
              </div>

              {/* Status progress bar */}
              <div style={{
                marginLeft: "0.75rem", marginTop: "0.35rem", marginBottom: agent.prompt ? "0.35rem" : 0,
                height: "2px", borderRadius: "2px",
                background: "rgba(255,255,255,0.06)",
                overflow: "hidden"
              }}>
                <div style={{
                  height: "100%",
                  width: `${((statusIdx + 1) / JIT_STATUSES.length) * 100}%`,
                  background: isReady ? domainColor : `linear-gradient(90deg, ${domainColor}, #c084fc)`,
                  borderRadius: "2px",
                  transition: "width 0.5s cubic-bezier(0.4, 0, 0.2, 1)"
                }} />
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

// ─── Band Platform Activity Panel ──────────────────────────────────────
function BandPlatformPanel({ bandTelemetry, activeAgents, roomId, status }) {
  const tel = bandTelemetry || {};
  const isConnected = tel.platform_healthy !== false && (status !== "IDLE" || !!roomId);
  const agents = tel.agents_registered || activeAgents.map(a => ({ id: a.id, name: a.name || a.role, identity_verified: true }));
  const contacts = (tel.contacts_exchanged || []).map(c => ({
    from: c.from || c.requester || "unknown",
    to: c.to || c.recipient || "unknown",
    status: (c.status === "approved" || c.status === "exchanged") ? "exchanged" : (c.status || "exchanged")
  }));
  const room = tel.room || (roomId ? { id: roomId, participants: activeAgents.map(a => ({ id: a.id, name: a.name, role: a.role })), messages_processed: 0 } : null);
  const memories = tel.memories || [];
  const heartbeatCount = tel.heartbeat_count || 0;
  const eventsPosted = tel.events_posted || [];

  const [userMemories, setUserMemories] = useState([]);
  const [loadingMemories, setLoadingMemories] = useState(false);

  const fetchUserMemories = async () => {
    setLoadingMemories(true);
    try {
      const res = await fetch(`${API_BASE}/api/memories`);
      if (res.ok) {
        const data = await res.json();
        setUserMemories(data);
      }
    } catch (e) {
      console.error("Failed to fetch user memories:", e);
    } finally {
      setLoadingMemories(false);
    }
  };

  useEffect(() => {
    fetchUserMemories();
  }, []);

  const handleArchiveMemory = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/api/memories/archive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        fetchUserMemories();
      }
    } catch (e) {
      console.error("Failed to archive memory:", e);
    }
  };

  if (status === "IDLE" && !roomId && !tel.platform_healthy) {
    return (
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", gap: "1rem", color: "#4b5563"
      }}>
        <div style={{ fontSize: "2.5rem", opacity: 0.5 }}>🔮</div>
        <div style={{ fontSize: "0.9rem", fontStyle: "italic" }}>
          Band.ai platform telemetry will appear here during a run.
        </div>
      </div>
    );
  }

  return (
    <div style={{
      flex: 1, overflowY: "auto", display: "flex", flexDirection: "column",
      gap: "0.75rem", paddingRight: "0.25rem"
    }}>
      {/* Connection Status */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0.65rem 0.75rem", borderRadius: "10px",
        background: isConnected ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
        border: `1px solid ${isConnected ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)"}`
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className={isConnected ? "band-heartbeat" : ""} style={{
            width: "8px", height: "8px", borderRadius: "50%",
            background: isConnected ? "#22c55e" : "#ef4444",
            display: "inline-block"
          }} />
          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: isConnected ? "#22c55e" : "#ef4444" }}>
            {isConnected ? "Connected to Band.ai" : "Disconnected"}
          </span>
        </div>
        <span style={{ fontSize: "0.6rem", color: "#6b7280", fontFamily: "'JetBrains Mono', monospace" }}>
          v{tel.platform_version || "1.0.0"}
        </span>
      </div>

      {/* Agent Identity Verification */}
      {agents.length > 0 && (
        <div style={{
          padding: "0.65rem 0.75rem", borderRadius: "10px",
          background: "rgba(168,85,247,0.04)", border: "1px solid rgba(168,85,247,0.12)"
        }}>
          <div style={{ fontWeight: 700, color: "#c084fc", fontSize: "0.72rem", marginBottom: "0.5rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            🔐 Agent Identity Verification
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            {agents.map((a, idx) => (
              <div key={a.id || idx} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "0.3rem 0.5rem", borderRadius: "6px",
                background: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.03)"
              }}>
                <span style={{ fontSize: "0.75rem", color: "#e5e7eb" }}>
                  {getDomainIcon(activeAgents.find(ag => ag.id === a.id)?.domain)} {a.name}
                </span>
                <span style={{
                  fontSize: "0.58rem", fontWeight: 600,
                  padding: "0.08rem 0.3rem", borderRadius: "4px",
                  background: a.identity_verified !== false ? "rgba(34,197,94,0.12)" : "rgba(245,158,11,0.12)",
                  color: a.identity_verified !== false ? "#22c55e" : "#f59e0b"
                }}>
                  {a.identity_verified !== false ? "✓ Verified" : "⏳ Pending"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Contact Exchange */}
      {contacts.length > 0 && (
        <div style={{
          padding: "0.65rem 0.75rem", borderRadius: "10px",
          background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.12)"
        }}>
          <div style={{ fontWeight: 700, color: "#67e8f9", fontSize: "0.72rem", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            🤝 Contact Exchange
          </div>
          {contacts.map((c, idx) => (
            <div key={idx} style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.7rem", color: "#9ca3af", marginBottom: "0.2rem" }}>
              <span style={{ color: "#67e8f9" }}>{c.from}</span>
              <span>→</span>
              <span style={{ color: "#67e8f9" }}>{c.to}</span>
              <span style={{
                fontSize: "0.55rem", padding: "0.05rem 0.25rem", borderRadius: "3px",
                background: c.status === "exchanged" ? "rgba(34,197,94,0.12)" : "rgba(245,158,11,0.12)",
                color: c.status === "exchanged" ? "#22c55e" : "#f59e0b",
                marginLeft: "auto"
              }}>
                {c.status || "exchanged"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Room Participant List */}
      {room && (
        <div style={{
          padding: "0.65rem 0.75rem", borderRadius: "10px",
          background: "rgba(59,130,246,0.04)", border: "1px solid rgba(59,130,246,0.12)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
            <span style={{ fontWeight: 700, color: "#93c5fd", fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🏠 Room Participants
            </span>
            <span style={{ fontSize: "0.58rem", color: "#4b5563", fontFamily: "'JetBrains Mono', monospace" }}>
              {room.id ? room.id.substring(0, 12) + "…" : "—"}
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
            {(room.participants || []).map((p, idx) => (
              <span key={idx} style={{
                fontSize: "0.65rem", padding: "0.1rem 0.4rem", borderRadius: "4px",
                background: "rgba(59,130,246,0.1)", color: "#93c5fd",
                border: "1px solid rgba(59,130,246,0.2)"
              }}>
                {p.name || p.role || p.id}
              </span>
            ))}
          </div>
          {room.messages_processed > 0 && (
            <div style={{ marginTop: "0.4rem", fontSize: "0.65rem", color: "#6b7280" }}>
              📨 {room.messages_processed} messages processed
            </div>
          )}
        </div>
      )}

      {/* Memory Timeline */}
      {memories.length > 0 && (
        <div style={{
          padding: "0.65rem 0.75rem", borderRadius: "10px",
          background: "rgba(236,72,153,0.04)", border: "1px solid rgba(236,72,153,0.12)"
        }}>
          <div style={{ fontWeight: 700, color: "#f472b6", fontSize: "0.72rem", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            🧠 Memory Timeline
          </div>
          {memories.slice(-5).map((m, idx) => (
            <div key={m.id || idx} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "0.25rem 0.4rem", borderRadius: "4px",
              background: "rgba(0,0,0,0.12)", marginBottom: "0.2rem",
              border: "1px solid rgba(255,255,255,0.02)"
            }}>
              <span style={{ fontSize: "0.68rem", color: "#d1d5db", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {m.content?.substring(0, 50) || "—"}{m.content?.length > 50 ? "…" : ""}
              </span>
              <span style={{
                fontSize: "0.55rem", padding: "0.05rem 0.25rem", borderRadius: "3px", marginLeft: "0.3rem",
                background: m.status === "archived" ? "rgba(107,114,128,0.2)" : m.status === "superseded" ? "rgba(245,158,11,0.12)" : "rgba(34,197,94,0.12)",
                color: m.status === "archived" ? "#9ca3af" : m.status === "superseded" ? "#f59e0b" : "#22c55e",
                flexShrink: 0
              }}>
                {m.status || "created"}
              </span>
            </div>
          ))}
        </div>
      )}



      {/* Activity Heartbeat */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0.5rem 0.75rem", borderRadius: "10px",
        background: "rgba(245,158,11,0.04)", border: "1px solid rgba(245,158,11,0.1)"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className="band-heartbeat" style={{ fontSize: "0.9rem" }}>💓</span>
          <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#fbbf24" }}>Activity Heartbeat</span>
        </div>
        <span style={{ fontSize: "0.7rem", color: "#9ca3af", fontFamily: "'JetBrains Mono', monospace" }}>
          {heartbeatCount || (status !== "IDLE" ? "Active" : "—")} {heartbeatCount ? "beats" : ""}
        </span>
      </div>

      {/* Recent Events */}
      {eventsPosted.length > 0 && (
        <div style={{
          padding: "0.65rem 0.75rem", borderRadius: "10px",
          background: "rgba(139,92,246,0.04)", border: "1px solid rgba(139,92,246,0.12)"
        }}>
          <div style={{ fontWeight: 700, color: "#a78bfa", fontSize: "0.72rem", marginBottom: "0.4rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            📡 Recent Platform Events
          </div>
          {eventsPosted.slice(-5).map((ev, idx) => (
            <div key={idx} style={{ fontSize: "0.68rem", color: "#9ca3af", padding: "0.2rem 0", borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
              <span style={{ color: "#a78bfa", fontWeight: 600, marginRight: "0.3rem" }}>{ev.type}</span>
              {ev.content?.substring(0, 60) || ""}
            </div>
          ))}
        </div>
      )}
    </div>
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
    ? (isLlama ? `AIML (Llama): ${modelLabel}` : `AIML: ${modelLabel}`)
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

  // Render standard system logs in a minimal inline style to reduce noise
  if (!isAgent && evt.sender === "SYSTEM" && !isToolCall && !isTriage && !isBandRoom && !isPrSummary && !isWatchdog) {
    const isSuccess = rawMsg.startsWith("✓") || rawMsg.toLowerCase().includes("success") || rawMsg.toLowerCase().includes("passed");
    const isWarn = rawMsg.startsWith("⚠️") || rawMsg.toLowerCase().includes("warning") || rawMsg.toLowerCase().includes("skip");
    const isError = rawMsg.startsWith("❌") || rawMsg.startsWith("💥") || rawMsg.toLowerCase().includes("failed") || rawMsg.toLowerCase().includes("error");
    
    let color = "#9ca3af"; // muted grey
    let icon = "⚙️";
    
    if (isSuccess) {
      color = "#34d399"; // light green
      icon = "✓";
    } else if (isWarn) {
      color = "#fbbf24"; // light yellow
      icon = "⚠️";
    } else if (isError) {
      color = "#f87171"; // light red
      icon = "❌";
    }
    
    // Strip redundant status/SYSTEM prefixes
    const cleanText = rawMsg
      .replace(/^[✓⚠️❌💥]\s*/, "")
      .replace(/^SYSTEM:\s*/i, "");

    return (
      <div style={{
        fontSize: "0.72rem",
        color: color,
        padding: "0.2rem 0.5rem",
        fontStyle: "italic",
        display: "flex",
        alignItems: "center",
        gap: "0.4rem",
        fontFamily: "'JetBrains Mono', monospace",
        background: "rgba(255,255,255,0.01)",
        borderRadius: "6px",
        border: "1px solid rgba(255,255,255,0.02)"
      }}>
        <span style={{ opacity: 0.8, fontWeight: 700 }}>{icon}</span>
        <span>{cleanText}</span>
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
      {isLlama ? "🦙 Llama (AIML)" : "☁️ AIML API"}
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
  const [bandTelemetry, setBandTelemetry] = useState(null);
  const [events, setEvents] = useState([]);
  const [visibleEvents, setVisibleEvents] = useState([]);
  const [eventQueue, setEventQueue] = useState([]);
  const [debateSpeed, setDebateSpeed] = useState(1000);
  const [pauseAutoScroll, setPauseAutoScroll] = useState(false);
  const [eventFilter, setEventFilter] = useState("all");
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
  const [showControlPanel, setShowControlPanel] = useState(true);


  const [demoMode, setDemoMode] = useState(true);
  const [compromisePrompt, setCompromisePrompt] = useState("");
  const [isCommitting, setIsCommitting] = useState(false);
  const [commitStatus, setCommitStatus] = useState("");

  const [selectedRepo, setSelectedRepo] = useState("vjb/WellActually.ai");
  const [prsList, setPrsList] = useState([]);
  const [selectedPrNumber, setSelectedPrNumber] = useState("");
  const [selectedPrDetails, setSelectedPrDetails] = useState(null);
  const [isFetchingPrs, setIsFetchingPrs] = useState(false);
  const [isFetchingPrDetails, setIsFetchingPrDetails] = useState(false);
  const [githubErrorMsg, setGithubErrorMsg] = useState("");

  const [activeTab, setActiveTab] = useState("debate");
  const [reportMarkdown, setReportMarkdown] = useState("");
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

  const getCostEstimation = () => {
    if (!debateSummary || !activeAgents || activeAgents.length === 0) return { active: 0, baseline: 0, savings: 0, percentage: 0 };
    
    const rounds = debateSummary.total_rounds || 1;
    
    let activeCost = 0;
    let baselineCost = 0;
    
    activeAgents.forEach(agent => {
      const model = agent.model || "gpt-4o-mini";
      let isReviewer = agent.id?.startsWith("reviewer");
      let isConductor = agent.id === "conductor";
      let isCoder = agent.id === "coder";
      
      let inputTokens = 0;
      let outputTokens = 0;
      
      if (isConductor) {
        inputTokens = 1500 * rounds;
        outputTokens = 300 * rounds;
      } else if (isCoder) {
        inputTokens = 2500 * rounds;
        outputTokens = 800 * rounds;
      } else { // Reviewer
        inputTokens = 2000 * rounds;
        outputTokens = 400 * rounds;
      }
      
      let inPrice = 0.15; // default gpt-4o-mini
      let outPrice = 0.60;
      
      if (model.includes("gpt-4o-mini")) {
        inPrice = 0.15;
        outPrice = 0.60;
      } else if (model === "gpt-4o") {
        inPrice = 5.00;
        outPrice = 15.00;
      } else if (model.includes("8B")) {
        inPrice = 0.07;
        outPrice = 0.07;
      } else if (model.includes("70B")) {
        inPrice = 0.35;
        outPrice = 0.35;
      }
      
      activeCost += (inputTokens * inPrice + outputTokens * outPrice) / 1000000;
      baselineCost += (inputTokens * 5.00 + outputTokens * 15.00) / 1000000;
    });
    
    const savings = baselineCost - activeCost;
    const percentage = baselineCost > 0 ? (savings / baselineCost) * 100 : 0;
    
    return {
      active: activeCost.toFixed(4),
      baseline: baselineCost.toFixed(4),
      savings: savings.toFixed(4),
      percentage: percentage.toFixed(1)
    };
  };

  const generateReportMarkdown = () => {
    if (!debateSummary) return "";
    
    const costs = getCostEstimation();
    const uniqueDomains = [...new Set(activeAgents.filter(a => a.id?.startsWith("reviewer") && a.domain).map(a => a.domain))];
    const isReal = (val) => val && !val.startsWith("No ") && val !== "None" && val !== "null";
    
    let md = `# 🛡️ WellActually.ai — JIT Swarm Governance Audit\n\n`;
    md += `> **${prId}** · \`${status}\` · ${(diffFiles?.length || 0)} files analyzed\n\n`;
    md += `**Date:** ${new Date().toLocaleString()}\n`;
    md += `**Title:** ${prTitle}\n`;
    md += `**Branch:** ${prBranch}\n\n`;
    
    md += `## 📊 Summary\n`;
    md += `- **Resolution:** ${resolutionType || "Awaiting Consent"}\n`;
    md += `- **Consensus Rounds:** ${consensusRound}\n`;
    md += `- **Approvals:** ${debateSummary.approvals}\n`;
    md += `- **Rejections:** ${debateSummary.rejections}\n`;
    md += `- **Domains Checked:** ${uniqueDomains.join(", ") || "N/A"}\n\n`;
    
    md += `## 🧠 JIT Synthesized Swarm Topology\n`;
    activeAgents.forEach(a => {
      const jit = a.id?.startsWith("reviewer") ? " · ⚡ JIT Synthesized" : "";
      md += `- **${a.role}** (\`@${a.name}\`): \`${a.model}\` · Domain: \`${a.domain || "system"}\`${jit}\n`;
    });
    md += `\n`;
    
    // Domains analyzed
    md += `## 🛠️ Domains Analyzed\n`;
    if (uniqueDomains.length > 0) {
      uniqueDomains.forEach(d => {
        md += `- \`${d}\`\n`;
      });
    } else {
      md += `- General code-quality review\n`;
    }
    md += `\n`;
    
    md += `## 💰 Compute Cost Estimation\n`;
    md += `- **Baseline (All GPT-4o):** $${costs.baseline}\n`;
    md += `- **JIT Model Routing (Active):** $${costs.active}\n`;
    md += `- **Savings:** ${costs.percentage}% ($${costs.savings})\n\n`;

    
    md += `## 💬 Adversarial Debate Log\n\n`;
    events.forEach(evt => {
      md += `### [${new Date(evt.timestamp * 1000).toLocaleTimeString()}] @${evt.sender} (${evt.role})\n`;
      md += `\`\`\`\n${evt.message}\n\`\`\`\n\n`;
    });
    
    md += `---\n*Generated by [WellActually.ai](https://github.com/vjb/WellActually.ai) — JIT Swarm Intelligence powered by [Band.ai](https://band.ai)*\n`;
    
    return md;
  };

  const handleDownloadReport = () => {
    const md = generateReportMarkdown();
    if (!md) return;
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `WellActually_Audit_Report_${prId}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      const payload = {
        scenario: "dynamic",
        repo: selectedRepo,
        pr_number: selectedPrNumber ? parseInt(selectedPrNumber, 10) : null,
        model_preset: modelPreset,
        model_assignments: effectiveAssignments,
        demo_mode: demoMode
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

  const handleMediate = async (action, compromiseText = null) => {
    try {
      const payload = {
        action,
        compromise_prompt: compromiseText
      };
      await fetch(`${API_BASE}/api/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (action === "compromise") {
        setCompromisePrompt("");
      }
    } catch (err) {
      console.error("Error submitting human mediation decision:", err);
    }
  };

  const handleCommitFix = async () => {
    setIsCommitting(true);
    setCommitStatus("");
    try {
      const resp = await fetch(`${API_BASE}/api/commit-fix`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      const data = await resp.json();
      if (resp.ok && data.status === "success") {
        setCommitStatus("success");
      } else {
        setCommitStatus("error");
      }
    } catch (err) {
      console.error("Error applying fix:", err);
      setCommitStatus("error");
    } finally {
      setIsCommitting(false);
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
          if (d.band_telemetry) setBandTelemetry(d.band_telemetry);
          if (d.status !== "IDLE") {
            if (d.model_preset) setModelPreset(d.model_preset);
            if (d.model_assignments) setModelAssignments(d.model_assignments);
            if (d.demo_mode !== undefined) setDemoMode(d.demo_mode);
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

  useEffect(() => {
    // If events is cleared or has fewer items, reset visibleEvents
    if (events.length < visibleEvents.length) {
      setVisibleEvents(events);
      setEventQueue([]);
      return;
    }
    
    // If we are at idle, sync immediately
    if (status === "IDLE") {
      setVisibleEvents(events);
      setEventQueue([]);
      return;
    }

    // Otherwise, add any new events to the queue
    const processedCount = visibleEvents.length + eventQueue.length;
    if (events.length > processedCount) {
      const newEvents = events.slice(processedCount);
      setEventQueue(prev => [...prev, ...newEvents]);
    }
  }, [events, status]);

  useEffect(() => {
    if (eventQueue.length === 0) return;

    const timer = setTimeout(() => {
      setVisibleEvents(prev => [...prev, eventQueue[0]]);
      setEventQueue(prev => prev.slice(1));
    }, debateSpeed);

    return () => clearTimeout(timer);
  }, [eventQueue, debateSpeed]);

  const filteredEvents = useMemo(() => {
    return visibleEvents.filter(evt => {
      if (eventFilter === "all") return true;
      const rawMsg = cleanMessageText(evt.message) || "";
      const isAgent = evt.sender !== "SYSTEM" && evt.sender !== "TriageScanner" && evt.sender !== "TelemetryScanner" && evt.sender !== "WatchdogDaemon";
      const isToolCall = rawMsg.startsWith("🔌");
      const isTriage = evt.sender === "TriageScanner" || rawMsg.includes("Zero-Trust");
      const isWatchdog = evt.sender === "WatchdogDaemon" || evt.sender === "TelemetryScanner" || rawMsg.includes("Anomaly detected");
      const isWarningOrError = evt.level === "warning" || evt.level === "error";

      if (eventFilter === "debates") {
        return isAgent && !isToolCall;
      }
      if (eventFilter === "tool_calls") {
        return isToolCall;
      }
      if (eventFilter === "security_warnings") {
        return isTriage || isWatchdog || isWarningOrError;
      }
      return true;
    });
  }, [visibleEvents, eventFilter]);

  useEffect(() => {
    if (chatContainerRef.current && !pauseAutoScroll) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [filteredEvents.length, pauseAutoScroll]);

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

  const lastEvent = visibleEvents[visibleEvents.length - 1];
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

  const isRealTarget = (val) => val && val !== "None" && val !== "null" && !val.startsWith("No ");
  const showSchemaCheck = displaySchemaCheck || isRealTarget(mcpTargets.table);
  const showOpenapiCheck = displayOpenapiCheck || isRealTarget(mcpTargets.endpoint);
  const showRbacCheck = displayRbacCheck || isRealTarget(mcpTargets.rbac);
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

          {/* Collapsible Control Panel */}
          <section className="glass-panel" style={{ padding: "1.25rem" }}>
            <div 
              onClick={() => setShowControlPanel(!showControlPanel)}
              style={{ 
                display: "flex", 
                alignItems: "center", 
                gap: "0.6rem", 
                cursor: "pointer", 
                userSelect: "none"
              }}
            >
              <span style={{ fontSize: "1.1rem" }}>🎛️</span>
              <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "#06b6d4", flex: 1 }}>
                Control Panel & Configs
              </h2>
              <span style={{ fontSize: "0.75rem", color: "#06b6d4", transition: "transform 0.2s ease" }}>
                {showControlPanel ? "Hide ▲" : "Show ▼"}
              </span>
            </div>

            {showControlPanel && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", marginTop: "1rem" }}>
                {/* PR Ingest Sub-panel */}
                <div style={{ 
                  padding: "1rem", borderRadius: "10px", 
                  background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.8rem" }}>
                    <span style={{ fontSize: "1rem" }}>🎯</span>
                    <h3 style={{ margin: 0, fontSize: "0.88rem", fontWeight: 700, color: "#06b6d4" }}>PR Ingest</h3>
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
                        ) : prsList.map(pr => {
                          const label = `#${pr.number} — ${pr.title}`;
                          return (
                            <option key={pr.number} value={String(pr.number)}>{label}</option>
                          );
                        })}

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
                </div>

              </div>
            )}
          </section>



          {/* Phase 2: JIT SYNTHESIS — The Hero */}
          <JITSynthesisPanel agents={activeAgents} status={status} isAnalyzing={isAnalyzing} activeSender={activeSender} />

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
                <div style={{ padding: "0.85rem", borderRadius: "12px", border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.04)", marginTop: "0.75rem" }}>
                  <p style={{ margin: "0 0 0.6rem 0", fontSize: "0.85rem", color: "#f87171", fontWeight: 700, display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <span>⚠️</span> Consensus Deadlock — Human Operator Intervention
                  </p>
                  
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "0.75rem" }}>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button onClick={() => handleMediate("approve")} style={{
                        flex: 1, padding: "0.45rem", borderRadius: "8px",
                        background: "#059669", border: "none", color: "white", fontWeight: 700, cursor: "pointer", fontSize: "0.78rem"
                      }}>Force Approve PR</button>
                      <button onClick={() => handleMediate("reject")} style={{
                        flex: 1, padding: "0.45rem", borderRadius: "8px",
                        background: "#dc2626", border: "none", color: "white", fontWeight: 700, cursor: "pointer", fontSize: "0.78rem"
                      }}>Side with SMEs (Reject)</button>
                    </div>
                  </div>

                  <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "0.75rem" }}>
                    <label style={{ display: "block", fontSize: "0.68rem", color: "#9ca3af", marginBottom: "0.4rem", fontWeight: 600 }}>
                      Inject Compromise Prompt (Triggers Round 3)
                    </label>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <input 
                        type="text"
                        value={compromisePrompt}
                        onChange={(e) => setCompromisePrompt(e.target.value)}
                        placeholder="e.g., Use parameterized query for billing profiles..."
                        style={{
                          flex: 1, padding: "0.45rem 0.6rem", borderRadius: "8px",
                          border: "1px solid rgba(255,255,255,0.15)", background: "rgba(0,0,0,0.4)",
                          color: "white", fontSize: "0.75rem"
                        }}
                      />
                      <button 
                        disabled={!compromisePrompt.trim()}
                        onClick={() => handleMediate("compromise", compromisePrompt)}
                        style={{
                          padding: "0.45rem 0.85rem", borderRadius: "8px",
                          background: compromisePrompt.trim() ? "#4f46e5" : "rgba(79,70,229,0.3)",
                          border: "none", color: "white", fontWeight: 700,
                          cursor: compromisePrompt.trim() ? "pointer" : "not-allowed", fontSize: "0.75rem"
                        }}
                      >
                        Submit
                      </button>
                    </div>
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

              {/* Swarm Model & Token Audit Section */}
              {(() => {
                const rounds = debateSummary?.total_rounds || 1;
                const agentAudits = activeAgents.map(agent => {
                  const model = agent.model || "gpt-4o-mini";
                  const isConductor = agent.id === "conductor";
                  const isCoder = agent.id === "coder";
                  
                  let inputTokens = 0;
                  let outputTokens = 0;
                  
                  if (isConductor) {
                    inputTokens = 1500 * rounds;
                    outputTokens = 300 * rounds;
                  } else if (isCoder) {
                    inputTokens = 2500 * rounds;
                    outputTokens = 800 * rounds;
                  } else { // Reviewer
                    inputTokens = 2000 * rounds;
                    outputTokens = 400 * rounds;
                  }
                  
                  let inPrice = 0.15; // default gpt-4o-mini
                  let outPrice = 0.60;
                  
                  if (model.includes("gpt-4o-mini")) {
                    inPrice = 0.15;
                    outPrice = 0.60;
                  } else if (model === "gpt-4o") {
                    inPrice = 5.00;
                    outPrice = 15.00;
                  } else if (model.includes("8B") || model.includes("8b")) {
                    inPrice = 0.07;
                    outPrice = 0.07;
                  } else if (model.includes("70B") || model.includes("70b") || model.includes("llama-3.3")) {
                    inPrice = 0.35;
                    outPrice = 0.35;
                  }
                  
                  const cost = (inputTokens * inPrice + outputTokens * outPrice) / 1000000;
                  return {
                    name: agent.name || (isConductor ? "Conductor" : isCoder ? "Lead Coder" : agent.role || "Reviewer"),
                    role: agent.role || (isConductor ? "Orchestrator" : isCoder ? "Implementation" : "JIT Reviewer"),
                    model: model,
                    inputTokens,
                    outputTokens,
                    totalTokens: inputTokens + outputTokens,
                    cost: cost
                  };
                });

                const totalCost = agentAudits.reduce((acc, a) => acc + a.cost, 0);
                const totalTokens = agentAudits.reduce((acc, a) => acc + a.totalTokens, 0);

                return (
                  <div style={{
                    padding: "0.85rem", borderRadius: "12px",
                    background: "linear-gradient(135deg, rgba(6,182,212,0.06) 0%, rgba(168,85,247,0.06) 100%)",
                    border: "1px solid rgba(6,182,212,0.15)",
                    marginBottom: "1rem", marginTop: "0.75rem"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.4rem" }}>
                      <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#06b6d4", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                        🤖 Swarm Model & Token Audit
                      </span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "0.7rem", color: "#10b981", fontWeight: 700 }}>
                        Total: ${totalCost.toFixed(5)}
                      </span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: "150px", overflowY: "auto", paddingRight: "0.2rem", marginBottom: "0.5rem" }}>
                      {agentAudits.map((a, idx) => (
                        <div key={idx} style={{
                          background: "rgba(0,0,0,0.15)", padding: "0.4rem", borderRadius: "6px",
                          border: "1px solid rgba(255,255,255,0.03)", display: "flex", flexDirection: "column", gap: "0.15rem"
                        }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#f3f4f6" }}>{a.name}</span>
                            <span style={{
                              fontSize: "0.58rem", fontFamily: "'JetBrains Mono', monospace", color: "#10b981", fontWeight: 600
                            }}>
                              ${a.cost.toFixed(5)}
                            </span>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.6rem" }}>
                            <span style={{ color: "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>
                              {a.model}
                            </span>
                            <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "#6b7280" }}>
                              Tokens: {a.totalTokens}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#9ca3af", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "0.4rem" }}>
                      <span>Total Swarm Tokens:</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", color: "#f3f4f6" }}>{totalTokens}</span>
                    </div>
                  </div>
                );
              })()}

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

              {/* Export Button */}
              <button 
                onClick={handleDownloadReport}
                style={{
                  width: "100%", marginTop: "0.85rem", padding: "0.5rem", borderRadius: "10px",
                  background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.1)",
                  color: "#d1d5db", fontWeight: 600, cursor: "pointer", fontSize: "0.8rem",
                  transition: "all 0.2s ease", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem"
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.15)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"; }}
              >
                <span>📥</span> Download Compliance Report (.md)
              </button>
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
                { key: "code", label: "💻 Proposed Code" },
                { key: "report", label: "📋 Audit Report" },
                { key: "band", label: "🔮 Band Platform" }
              ].map(tab => (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    color: activeTab === tab.key ? "#06b6d4" : "#6b7280",
                    fontWeight: 700, fontSize: "0.82rem",
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
            <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
              {/* Controls Panel */}
              <div style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                flexWrap: "wrap", gap: "0.75rem", padding: "0.6rem 0.8rem", borderRadius: "8px",
                background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
                marginBottom: "0.75rem"
              }}>
                {/* Event Filters */}
                <div style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 600, marginRight: "0.25rem" }}>Filter:</span>
                  {[
                    { key: "all", label: "[All]" },
                    { key: "debates", label: "[Debates]" },
                    { key: "tool_calls", label: "[Tool Calls]" },
                    { key: "security_warnings", label: "[Security Warnings]" }
                  ].map(btn => (
                    <button key={btn.key} onClick={() => setEventFilter(btn.key)}
                      style={{
                        background: eventFilter === btn.key ? "rgba(6,182,212,0.12)" : "none",
                        border: "none", cursor: "pointer",
                        color: eventFilter === btn.key ? "#06b6d4" : "#4b5563",
                        fontWeight: 700, fontSize: "0.72rem",
                        padding: "0.25rem 0.5rem", borderRadius: "4px",
                        border: eventFilter === btn.key ? "1px solid rgba(6,182,212,0.25)" : "1px solid transparent",
                        transition: "all 0.15s"
                      }}
                    >
                      {btn.label}
                    </button>
                  ))}
                </div>

                {/* Auto Scroll & Speed controls */}
                <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                  {/* Pause Auto-Scroll Checkbox */}
                  <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer", fontSize: "0.75rem", color: "#9ca3af", userSelect: "none" }}>
                    <input type="checkbox" checked={pauseAutoScroll} onChange={(e) => setPauseAutoScroll(e.target.checked)}
                      style={{ cursor: "pointer", accentColor: "#06b6d4" }}
                    />
                    Pause Auto-Scroll
                  </label>

                  {/* Debate Speed Slider */}
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>Delay:</span>
                    <input type="range" min="100" max="3000" step="100" value={debateSpeed} onChange={(e) => setDebateSpeed(Number(e.target.value))}
                      style={{ cursor: "pointer", accentColor: "#06b6d4", width: "80px" }}
                    />
                    <span style={{ fontSize: "0.7rem", color: "#9ca3af", width: "45px", textAlign: "right", fontFamily: "monospace" }}>
                      {(debateSpeed / 1000).toFixed(1)}s
                    </span>
                  </div>
                </div>
              </div>

              {/* Chat room messages container */}
              <div ref={chatContainerRef} style={{
                flex: 1, overflowY: "auto", display: "flex", flexDirection: "column",
                gap: "0.6rem", paddingRight: "0.25rem"
              }}>
                {filteredEvents.length === 0 ? (
                  <div style={{
                    flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
                    justifyContent: "center", gap: "1rem", color: "#4b5563"
                  }}>
                    <div style={{ fontSize: "2.5rem", opacity: 0.5 }}>⚔️</div>
                    <div style={{ fontSize: "0.9rem", fontStyle: "italic" }}>
                      {visibleEvents.length === 0 ? "Debate room idle. Launch a JIT swarm to begin." : "No events match this filter."}
                    </div>
                  </div>
                ) : (
                  filteredEvents.map((evt, idx) => (
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
            </div>
          ) : activeTab === "code" ? (
            <div style={{ flex: 1, overflow: "auto", background: "#060810", borderRadius: "10px", padding: "1rem" }}>
              {currentCode ? (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.55rem" }}>
                    <h3 style={{ margin: 0, fontSize: "0.85rem", color: "#22c55e" }}>
                      🛠️ Swarm Proposed Fix (Round {consensusRound}):
                    </h3>
                    <button 
                      onClick={handleCommitFix} 
                      disabled={isCommitting || status === "RUNNING"}
                      style={{
                        padding: "0.35rem 0.75rem", borderRadius: "6px",
                        background: commitStatus === "success" ? "#059669" : commitStatus === "error" ? "#dc2626" : "linear-gradient(135deg, #06b6d4 0%, #a855f7 100%)",
                        border: "none", color: "white", fontWeight: 700, cursor: "pointer", fontSize: "0.72rem",
                        display: "flex", alignItems: "center", gap: "0.3rem", transition: "all 0.3s"
                      }}
                    >
                      {isCommitting ? "Applying..." : 
                       commitStatus === "success" ? "✓ Fix Applied!" : 
                       commitStatus === "error" ? "❌ Apply Failed" : "Apply Swarm Fix"}
                    </button>
                  </div>
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
          ) : activeTab === "report" ? (
            <div style={{ flex: 1, overflow: "auto", padding: "1rem" }}>
              {(status === "COMPLETED" || status === "HALTED" || status === "CRASHED") && debateSummary ? (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    <h3 style={{ margin: 0, fontSize: "0.9rem", color: "#a855f7" }}>
                      📋 JIT Swarm Governance Audit Report
                    </h3>
                    <button
                      onClick={handleDownloadReport}
                      style={{
                        padding: "0.3rem 0.65rem", borderRadius: "6px",
                        background: "rgba(168,85,247,0.15)", border: "1px solid rgba(168,85,247,0.3)",
                        color: "#c084fc", fontWeight: 600, cursor: "pointer", fontSize: "0.7rem",
                        display: "flex", alignItems: "center", gap: "0.3rem"
                      }}
                    >
                      📥 Download .md
                    </button>
                  </div>
                  <ReportRenderer markdown={generateReportMarkdown()} />
                </div>
              ) : (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#4b5563", fontStyle: "italic" }}>
                  Report will be available after the swarm completes.
                </div>
              )}
            </div>
          ) : (
            <BandPlatformPanel bandTelemetry={bandTelemetry} activeAgents={activeAgents} roomId={roomId} status={status} />
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
// ─── Report Markdown Renderer ────────────────────────────────────────────
function ReportRenderer({ markdown }) {
  if (!markdown) return null;
  
  // Lightweight markdown-to-HTML conversion
  const renderMarkdown = (md) => {
    const lines = md.split("\n");
    let html = "";
    let inCodeBlock = false;
    let inTable = false;
    let tableRows = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // Code blocks
      if (line.startsWith("```")) {
        if (inCodeBlock) {
          html += "</code></pre>";
          inCodeBlock = false;
        } else {
          inCodeBlock = true;
          html += `<pre style="background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:0.75rem;overflow-x:auto;margin:0.4rem 0"><code style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#d1d5db">`;
        }
        continue;
      }
      if (inCodeBlock) { html += line.replace(/</g,"&lt;").replace(/>/g,"&gt;") + "\n"; continue; }
      
      // Close table if line doesn't start with |
      if (inTable && !line.startsWith("|")) {
        html += "</tbody></table></div>";
        inTable = false;
        tableRows = [];
      }
      
      // Table
      if (line.startsWith("|")) {
        if (line.match(/^\|\s*:?-+:?\s*\|/)) continue; // skip separator row
        const cells = line.split("|").filter(c => c.trim()).map(c => c.trim());
        if (!inTable) {
          inTable = true;
          html += `<div style="overflow-x:auto;margin:0.5rem 0"><table style="width:100%;border-collapse:collapse;font-size:0.78rem"><thead><tr>`;
          cells.forEach(c => { html += `<th style="text-align:left;padding:0.4rem 0.6rem;border-bottom:1px solid rgba(255,255,255,0.1);color:#a855f7;font-weight:600">${inlineFormat(c)}</th>`; });
          html += "</tr></thead><tbody>";
        } else {
          html += "<tr>";
          cells.forEach(c => { html += `<td style="padding:0.35rem 0.6rem;border-bottom:1px solid rgba(255,255,255,0.04);color:#d1d5db">${inlineFormat(c)}</td>`; });
          html += "</tr>";
        }
        continue;
      }
      
      // Empty line
      if (line.trim() === "") { html += "<br/>"; continue; }
      // HR
      if (line.match(/^---+$/)) { html += `<hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:1rem 0"/>`; continue; }
      // Headers
      if (line.startsWith("# ")) { html += `<h1 style="font-size:1.15rem;font-weight:800;color:#e5e7eb;margin:0.8rem 0 0.4rem">${inlineFormat(line.slice(2))}</h1>`; continue; }
      if (line.startsWith("## ")) { html += `<h2 style="font-size:0.95rem;font-weight:700;color:#a855f7;margin:0.7rem 0 0.3rem">${inlineFormat(line.slice(3))}</h2>`; continue; }
      if (line.startsWith("### ")) { html += `<h3 style="font-size:0.85rem;font-weight:600;color:#06b6d4;margin:0.5rem 0 0.25rem">${inlineFormat(line.slice(4))}</h3>`; continue; }
      // Blockquote
      if (line.startsWith("> ")) {
        html += `<blockquote style="border-left:3px solid #a855f7;padding:0.4rem 0.8rem;margin:0.5rem 0;color:#d1d5db;font-size:0.82rem;background:rgba(168,85,247,0.04);border-radius:0 6px 6px 0">${inlineFormat(line.slice(2))}</blockquote>`;
        continue;
      }
      // List items
      if (line.match(/^- /)) { html += `<div style="padding-left:1rem;margin:0.15rem 0;color:#d1d5db;font-size:0.8rem">• ${inlineFormat(line.slice(2))}</div>`; continue; }
      // Regular paragraph
      html += `<p style="margin:0.2rem 0;color:#9ca3af;font-size:0.8rem;line-height:1.5">${inlineFormat(line)}</p>`;
    }
    
    if (inTable) html += "</tbody></table></div>";
    return html;
  };
  
  // Inline formatting: bold, code, links, emoji
  function inlineFormat(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#e5e7eb">$1</strong>')
      .replace(/`(.+?)`/g, '<code style="background:rgba(6,182,212,0.1);padding:0.1rem 0.3rem;border-radius:3px;font-size:0.75rem;color:#67e8f9;font-family:\'JetBrains Mono\',monospace">$1</code>')
      .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" style="color:#06b6d4;text-decoration:none">$1</a>');
  }
  
  return (
    <div
      style={{
        background: "rgba(0,0,0,0.2)", borderRadius: "10px",
        border: "1px solid rgba(255,255,255,0.04)", padding: "1.25rem",
        maxHeight: "100%", overflow: "auto"
      }}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(markdown) }}
    />
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

import { FormEvent, useEffect, useRef, useState } from "react";
import type { Case, InvestigationGuidance, Rule, Scenario, ScenarioSummary, Vehicle } from "./types";

// In development Vite proxies /api to FastAPI. In a deployed build, set
// VITE_API_URL when the API is hosted on a different origin.
const API_URL = import.meta.env.VITE_API_URL || "";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function titleCase(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function drawVehicle(context: CanvasRenderingContext2D, vehicle: Vehicle, x: number, y: number) {
  context.save();
  context.translate(x, y);
  context.rotate(-vehicle.heading);
  context.fillStyle = vehicle.color;
  context.shadowColor = vehicle.color;
  context.shadowBlur = 8;
  context.fillRect(-8, -4, 16, 8);
  context.fillStyle = "#06111c";
  context.fillRect(3, -3, 3, 6);
  context.restore();
}

function ScenarioReplay({ scenario, frameIndex, onFrameChange }: {
  scenario: Scenario;
  frameIndex: number;
  onFrameChange: (index: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frame = scenario.frames[frameIndex] ?? scenario.frames[0];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !frame) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const width = canvas.width;
    const height = canvas.height;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#07131f";
    context.fillRect(0, 0, width, height);
    const scale = 5;
    const project = (vehicle: Vehicle) => ({
      x: width / 2 + (vehicle.x - frame.ego.x) * scale,
      y: height / 2 - (vehicle.y - frame.ego.y) * scale,
    });
    const projectPoint = ([x, y]: [number, number]) => ({
      x: width / 2 + (x - frame.ego.x) * scale,
      y: height / 2 - (y - frame.ego.y) * scale,
    });
    for (const lane of scenario.road_geometry) {
      if (lane.polygon.length < 3 || lane.centerline.length < 2) continue;
      const first = projectPoint(lane.polygon[0]);
      context.beginPath();
      context.moveTo(first.x, first.y);
      for (const point of lane.polygon.slice(1)) {
        const projected = projectPoint(point);
        context.lineTo(projected.x, projected.y);
      }
      context.closePath();
      context.fillStyle = "#24536b";
      context.fill();
      context.strokeStyle = "rgba(222, 241, 247, 0.62)";
      context.lineWidth = 1.5;
      context.stroke();

      const centerStart = projectPoint(lane.centerline[0]);
      context.beginPath();
      context.setLineDash([6, 8]);
      context.moveTo(centerStart.x, centerStart.y);
      for (const point of lane.centerline.slice(1)) {
        const projected = projectPoint(point);
        context.lineTo(projected.x, projected.y);
      }
      context.strokeStyle = "rgba(255, 221, 128, 0.82)";
      context.stroke();
      context.setLineDash([]);
    }
    for (const actor of frame.actors) {
      const point = project(actor);
      if (point.x > -30 && point.x < width + 30 && point.y > -30 && point.y < height + 30) {
        drawVehicle(context, actor, point.x, point.y);
      }
    }
    drawVehicle(context, frame.ego, width / 2, height / 2);
    context.fillStyle = "#d9f9f4";
    context.font = "600 12px ui-monospace, monospace";
    context.fillText(`t ${frame.timestamp_s.toFixed(1)}s`, 18, 26);
    context.fillText(`ego ${frame.ego.speed_mps.toFixed(1)} m/s`, 18, 46);
    if (frame.alerts.length) {
      context.fillStyle = "#ffb4a8";
      context.fillText(frame.alerts[0], 18, height - 20);
    }
  }, [frame, scenario]);

  return (
    <section className="replay-panel panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">15-second evidence window</p>
          <h2>Scenario replay</h2>
        </div>
        <span className="live-badge">MetaDrive map + tracks</span>
      </div>
      <canvas className="replay-canvas" ref={canvasRef} width="760" height="360" aria-label="Top-down scenario replay" />
      <div className="timeline">
        <input
          aria-label="Replay timeline"
          type="range"
          min="0"
          max={scenario.frames.length - 1}
          value={frameIndex}
          onChange={(event) => onFrameChange(Number(event.target.value))}
        />
        <div className="timeline-labels"><span>-10.0s</span><span className="event-label">disengagement t=0</span><span>+5.0s</span></div>
      </div>
    </section>
  );
}

function RuleCard({ rule, onTest, onApprove }: { rule: Rule; onTest: (id: string) => void; onApprove: (id: string) => void }) {
  return (
    <article className="rule-card">
      <div className="rule-meta"><span className={`status ${rule.status}`}>{rule.status}</span><code>{rule.id}</code></div>
      <p>{rule.definition}</p>
      {rule.test && <p className="test-result">Regression: {rule.test.precision * 100}% precision · {rule.test.recall * 100}% recall · {rule.test.support} supporting cases</p>}
      <div className="rule-actions">
        {rule.status === "candidate" && <button className="secondary" onClick={() => onTest(rule.id)}>Run regression</button>}
        {rule.status === "tested" && rule.test?.passed && <button className="primary small" onClick={() => onApprove(rule.id)}>Approve as owner</button>}
        {rule.status === "tested" && !rule.test?.passed && <span className="muted">Needs refinement before approval</span>}
        {rule.status === "active" && <span className="approved">Approved by {rule.approved_by}</span>}
      </div>
    </article>
  );
}

function InvestigationGuidanceCard({ guidance }: { guidance: InvestigationGuidance }) {
  if (guidance.status === "disabled") return null;
  if (guidance.status === "no_match") {
    return <section className="investigation-guidance"><p className="eyebrow">Investigation guidance</p><p className="muted">No relevant approved document passage was retrieved. Ask an expert to define the next evidence request.</p></section>;
  }
  const sources = new Map(guidance.sources.map((source) => [source.id, source]));
  const passages = guidance.retrieved_passages ?? [];
  return (
    <section className="investigation-guidance">
      <div className="guidance-heading"><div><p className="eyebrow">Retrieved investigation guidance</p><h3>Where to look next</h3></div><span className="retrieval-badge">{guidance.retrieval_method.replaceAll("_", " ")}</span></div>
      <p className="guidance-boundary">{guidance.decision_boundary}</p>
      <ol className="guidance-directions">{guidance.directions.map((direction, index) => {
        const source = sources.get(direction.source_id);
        return <li key={`${direction.source_id}-${index}`}><span>{direction.text}</span>{source && <a href={source.url} target="_blank" rel="noreferrer">[{source.id}]</a>}</li>;
      })}</ol>
      {passages.length > 0 && <details className="guidance-passages"><summary>Retrieved document passages ({passages.length})</summary>{passages.map((passage) => {
        const source = sources.get(passage.document_id);
        return <article key={passage.id}><p className="passage-heading">{source?.title ?? passage.document_id} · {passage.heading}</p><p>{passage.text}</p><small>Chunk {passage.id} · relevance {passage.relevance_score.toFixed(3)}</small></article>;
      })}</details>}
      <div className="guidance-sources">{guidance.sources.map((source) => <details key={source.id}><summary><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> · {source.publisher}</summary><p>{source.summary}</p><p>{source.reuse_basis}</p><p><strong>Limit:</strong> {source.limitations}</p></details>)}</div>
    </section>
  );
}

function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [caseRecord, setCaseRecord] = useState<Case | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [role, setRole] = useState("Safety reviewer");
  const [simulated, setSimulated] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialScenario() {
      setLoading(true);
      try {
        const items = await api<ScenarioSummary[]>("/api/scenarios");
        if (cancelled) return;
        setScenarios(items);
        if (!items[0]) return;

        const selected = await api<Scenario>(`/api/scenarios/${items[0].id}`);
        if (cancelled) return;
        setScenario(selected);
        setCaseRecord(null);
        setFrameIndex(Math.max(0, selected.event_frame - 20));
        setError(null);
      } catch (reason) {
        if (!cancelled) setError((reason as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadInitialScenario();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!playing || !scenario) return;
    const timer = window.setInterval(() => setFrameIndex((current) => (current + 1) % scenario.frames.length), 110);
    return () => window.clearInterval(timer);
  }, [playing, scenario]);

  async function selectScenario(id: string) {
    try {
      setLoading(true);
      const selected = await api<Scenario>(`/api/scenarios/${id}`);
      setScenario(selected);
      setCaseRecord(null);
      setFrameIndex(Math.max(0, selected.event_frame - 20));
      setError(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function runTriage() {
    if (!scenario) return;
    try {
      setLoading(true);
      setCaseRecord(await api<Case>(`/api/scenarios/${scenario.id}/triage`, { method: "POST" }));
      setError(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function submitComment(event: FormEvent) {
    event.preventDefault();
    if (!caseRecord || !comment.trim()) return;
    try {
      const result = await api<{ case: Case }>(`/api/cases/${caseRecord.id}/comments`, {
        method: "POST",
        body: JSON.stringify({ author: simulated ? "Simulated expert" : "Human expert", role, body: comment, is_simulated_persona: simulated }),
      });
      setCaseRecord(result.case);
      setComment("");
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  async function testRule(id: string) {
    try {
      const updated = await api<Rule>(`/api/rules/${id}/test`, { method: "POST" });
      setCaseRecord((current) => current ? { ...current, rules: current.rules.map((rule) => rule.id === id ? updated : rule) } : current);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function approveRule(id: string) {
    try {
      const updated = await api<Rule>(`/api/rules/${id}/approve`, { method: "POST", body: JSON.stringify({ owner: "Sam Owner", note: "Approved after synthetic regression review." }) });
      setCaseRecord((current) => current ? { ...current, rules: current.rules.map((rule) => rule.id === id ? updated : rule) } : current);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function recordReview(action: "approve" | "request_more_evidence" | "reject") {
    if (!caseRecord) return;
    const notes = {
      approve: "Evidence packet is sufficient for follow-up.",
      request_more_evidence: "Please add supporting telemetry or an expert assessment.",
      reject: "The preliminary routing needs reassessment by the triage team.",
    };
    try {
      const updated = await api<Case>(`/api/cases/${caseRecord.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          reviewer: "Sam Owner",
          reviewer_role: "System owner",
          action,
          note: notes[action],
        }),
      });
      setCaseRecord(updated);
    } catch (reason) { setError((reason as Error).message); }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div><p className="eyebrow">Agentic safety workflow · POC</p><h1>Disengagement Triage Room</h1></div>
        <div className="header-status"><span className="dot" /> {scenarios.length || "No"} MetaDrive cases loaded</div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {!loading && scenarios.length === 0 && <section className="empty panel"><h2>Generate the MetaDrive corpus</h2><p>Run <code>python -m app.scenarios.generate --count 30 --output ../data/generated</code> from <code>backend</code>, then refresh this page.</p></section>}

      {scenarios.length > 0 && <div className="workspace">
        <aside className="case-queue panel">
          <div className="panel-heading"><div><p className="eyebrow">Case queue</p><h2>Disengagements</h2></div></div>
          <div className="queue-list">{scenarios.map((item) => <button key={item.id} className={`queue-item ${scenario?.id === item.id ? "selected" : ""}`} onClick={() => selectScenario(item.id)}><span>{item.id.replace("scenario-", "#")}</span><small>{item.metadata.disengagement_initiator === "user" ? "User takeover" : "System disengagement"}</small></button>)}</div>
        </aside>

        <section className="center-column">
          {scenario && <>
            <div className="case-title"><div><p className="eyebrow">{scenario.id} · {scenario.metadata.map_pattern as string}</p><h2>{scenario.title}</h2></div><div className="play-controls"><button className="secondary" onClick={() => setPlaying((value) => !value)}>{playing ? "Pause" : "Play"}</button><button className="primary" onClick={runTriage} disabled={loading}>{caseRecord ? "Re-run triage" : "Run triage"}</button></div></div>
            <ScenarioReplay scenario={scenario} frameIndex={frameIndex} onFrameChange={setFrameIndex} />
            <section className="metrics-strip panel"><Metric label="TTC" value={`${(scenario.frames[frameIndex]?.metrics.ttc_s ?? 0).toFixed(1)}s`} /><Metric label="Perception" value={`${Math.round((scenario.frames[frameIndex]?.metrics.perception_confidence ?? 0) * 100)}%`} /><Metric label="Lane dev." value={`${(scenario.frames[frameIndex]?.metrics.lane_deviation_m ?? 0).toFixed(1)}m`} /><Metric label="System risk" value={`${Math.round((scenario.frames[frameIndex]?.metrics.system_health_risk ?? 0) * 100)}%`} /></section>
          </>}

          {caseRecord && <section className="triage-result panel"><div className="panel-heading"><div><p className="eyebrow">AI recommendation — requires review</p><h2>{caseRecord.triage.primary_family_label}</h2></div><span className={`severity ${caseRecord.triage.severity.toLowerCase()}`}>{caseRecord.triage.severity}</span></div><div className="provenance-strip"><span>Route: deterministic telemetry</span><span>Explanation: {caseRecord.triage.narrative_provenance?.source.startsWith("llm") ? `LLM${caseRecord.triage.narrative_provenance.model ? ` · ${caseRecord.triage.narrative_provenance.model}` : ""}` : "deterministic fallback"}</span><span>Workflow: {caseRecord.workflow?.engine ?? "LangGraph"}</span></div><p className="narrative">{caseRecord.triage.narrative}</p><div className="evidence-grid">{caseRecord.triage.evidence.map((item) => <div className="evidence" key={item.metric}><span>{item.metric}</span><strong>{item.value}<small>{item.unit}</small></strong></div>)}</div>{caseRecord.triage.contributing_factors.length > 0 && <p className="contributing">Contributing: {caseRecord.triage.contributing_factors.join(" · ")}</p>}{caseRecord.triage.investigation_guidance && <InvestigationGuidanceCard guidance={caseRecord.triage.investigation_guidance} />}</section>}
        </section>

        <aside className="right-column">
          {caseRecord && <section className="collaboration panel"><p className="eyebrow">Shared workspace</p><h2>Expert collaboration</h2><div className="review-gate"><strong>{caseRecord.human_review?.status === "pending" ? "Human review required" : "Review recorded"}</strong><span>{caseRecord.human_review?.reviewers.join(" → ")}</span><small>{caseRecord.human_review?.decision_boundary}</small>{caseRecord.human_review?.status === "pending" ? <div className="review-actions"><button className="primary small" onClick={() => recordReview("approve")}>Approve triage</button><button className="secondary small" onClick={() => recordReview("request_more_evidence")}>Request evidence</button><button className="secondary small" onClick={() => recordReview("reject")}>Reject route</button></div> : <small>{caseRecord.human_review?.reviewed_by}: {caseRecord.human_review?.note}</small>}</div><div className="activity-list">{caseRecord.activity.slice().reverse().slice(0, 5).map((activity) => <div className="activity" key={activity.id}><strong>{activity.actor}</strong><span>{activity.message}</span></div>)}</div><form onSubmit={submitComment}><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add evidence, dissent, or a proposed triage refinement…" /><div className="form-row"><select value={role} onChange={(event) => setRole(event.target.value)}><option>Safety reviewer</option><option>Perception and localization expert</option><option>Prediction and behavior expert</option><option>Planning and controls expert</option><option>System health and ODD expert</option></select><label><input type="checkbox" checked={simulated} onChange={(event) => setSimulated(event.target.checked)} /> Persona</label></div><button className="primary small" type="submit">Submit to case</button></form></section>}
          {caseRecord && <section className="rules panel"><p className="eyebrow">Knowledge graph</p><h2>Rule lifecycle</h2>{caseRecord.rules.length === 0 ? <p className="muted">Expert input will create a candidate rule with full provenance.</p> : caseRecord.rules.map((rule) => <RuleCard key={rule.id} rule={rule} onTest={testRule} onApprove={approveRule} />)}</section>}
        </aside>
      </div>}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }

export default App;

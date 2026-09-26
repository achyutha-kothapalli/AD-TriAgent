export type ScenarioSummary = {
  id: string;
  title: string;
  source: string;
  event_frame: number;
  metadata: Record<string, unknown>;
};

export type Vehicle = {
  id: string;
  kind: string;
  x: number;
  y: number;
  heading: number;
  speed_mps: number;
  color: string;
};

export type ReplayFrame = {
  index: number;
  timestamp_s: number;
  ego: Vehicle;
  actors: Vehicle[];
  metrics: Record<string, number>;
  alerts: string[];
};

export type RoadLane = {
  id: string;
  polygon: Array<[number, number]>;
  centerline: Array<[number, number]>;
  width_m: number;
};

export type Scenario = ScenarioSummary & {
  sampling_hz: number;
  frames: ReplayFrame[];
  road_geometry: RoadLane[];
};

export type Evidence = { metric: string; value: number; unit: string };

export type Triage = {
  primary_family: string;
  primary_family_label: string;
  severity: string;
  confidence: number;
  evidence: Evidence[];
  contributing_factors: string[];
  narrative: string;
  narrative_provenance?: { source: string; model?: string | null; fallback_reason?: string | null };
  active_rules: Rule[];
};

export type Rule = {
  id: string;
  version: number;
  status: "candidate" | "tested" | "active" | "rejected";
  family: string;
  definition: string;
  test?: { precision: number; recall: number; support: number; passed: boolean };
  approved_by?: string;
};

export type Activity = { id: string; at: string; kind: string; actor: string; message: string };

export type Case = {
  id: string;
  scenario_id: string;
  scenario_title: string;
  status: string;
  triage: Triage;
  comments: Array<{ id: string; author: string; role: string; body: string; at: string; is_simulated_persona: boolean }>;
  rules: Rule[];
  activity: Activity[];
  workflow?: { engine: string; state: string; review_route: string[] };
  human_review?: { status: string; required: boolean; reviewers: string[]; decision_boundary: string };
};

# Planning and control evidence review

## Preserve the distinction between motion and cause

Lane deviation, jerk, trajectory curvature, speed change, and compliance-risk indicators describe vehicle motion. They can identify a review path for planning or control, but they do not distinguish an incorrect plan from a controller limitation, map or localisation uncertainty, an obstacle response, vehicle dynamics, or a deliberate fallback maneuver.

Start with the intended maneuver and constraints that are visible in the evidence. Compare the ego trajectory with lane geometry, route context, nearby actors, and criticality signals. State whether the trajectory is merely unusual, violates an available local constraint, or is unsupported because the necessary context is missing.

## Investigation sequence

Inspect the time order of signals. Did prediction divergence or track uncertainty occur before a plan change? Did lane deviation begin before high jerk? Did the vehicle respond to an actor conflict or begin moving independently of it? These questions help reviewers decide whether to involve perception, prediction, planning, control, or an ODD expert in the same case.

Compare the planned path, if available, with actual motion. If only actual motion exists, document that limitation rather than inferring a planner intent. For control, inspect steering and acceleration commands, actuator feedback, stability limits, and the relevant vehicle state. Compact replay metrics alone may justify a review route but are not enough for a subsystem root-cause conclusion.

## Follow-up experiment

Define a narrow replay test around one hypothesis. Hold actor behavior and road geometry stable while varying the suspected input or constraint. Record whether the same lane or jerk pattern appears, what evidence changed, and whether the case remains within the same logical scenario family. Human review must decide how the result changes any rule or follow-up action.

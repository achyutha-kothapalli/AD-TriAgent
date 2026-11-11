# Scenario, ODD, fallback, and handover review

## Describe the scenario before interpreting it

Every replay is one concrete example. Convert it into a logical scenario before drawing broader conclusions. Record road and map context, traffic configuration, ego maneuver, relevant actor behavior, weather or visibility context when available, criticality signals, and the automation state. This makes it possible to compare later events without pretending that one replay represents a whole operating domain.

The scenario description should make missing information visible. If weather, route policy, map version, system health, or handover prompts are not available, mark them as unknown. An unknown field is not evidence that the system was outside its operational design domain.

## ODD and fallback questions

An operational design domain question asks whether the current conditions fall inside the system's configured capability. A fallback question asks what the system was expected to do when confidence, health, or conditions crossed a limit. A handover question asks whether the request, timing, driver availability, and vehicle state should be reviewed. These are related but distinct questions.

Check whether the event includes an explicit capability-boundary indicator, a system-health signal, a fallback state transition, or a takeover request. Then compare its timing to the evolving interaction. A deliberate, well-timed capability transition is not automatically a failure; an absent or delayed transition is not automatically a root cause without the policy and system-state record.

## Follow-up experiment

Use the logical scenario to define a parameter sweep. For example, vary visibility, road type, actor density, or handover lead time while keeping the rest of the scenario stable. The goal is to locate evidence gaps and test repeatability. It is not a claim that a synthetic sweep validates real-vehicle safety coverage.

# Perception, localisation, and occlusion review

## Separate observability from diagnosis

Perception confidence, localisation error, delayed observation, and an apparent occlusion are evidence categories. They should be separated before a reviewer calls the event a perception failure. An actor may be difficult to observe because of geometry, weather, sensor placement, map error, a temporary line-of-sight obstruction, or an incomplete logging packet. A poor downstream response may also appear near the same time without being caused by perception.

Begin with what was observable. Compare the actor location and movement in the replay with the available tracks and alerts. Identify the first frame in which the actor should plausibly be observable, the first frame in which a system track appears, and any confidence or position changes that follow. Record gaps rather than filling them with an assumption.

## Localisation and map context

Review ego pose, lane relationship, map segment identity, and coordinate continuity separately from object tracking. A localisation concern can alter how road geometry, lane boundaries, and other actors are interpreted. It does not automatically mean that the map or localisation subsystem is defective. Check for discontinuities, unexpected lane association, route changes, or missing map context before escalating.

## Investigation sequence

Create a short evidence table: visibility or occlusion hypothesis, track availability, confidence trend, localisation trend, downstream prediction response, and downstream planning response. Then ask which row is authoritative and which is inferred from the compact replay. If the compact data cannot establish a timing relationship, request the original sensor, perception, or localisation logs.

An edge case may involve multiple weak signals. Do not use one degraded KPI as a root-cause label. Use the interaction timeline to determine whether the uncertainty was present early enough to affect prediction or planning and whether the vehicle entered a safety-critical interaction before the uncertainty could reasonably be resolved.

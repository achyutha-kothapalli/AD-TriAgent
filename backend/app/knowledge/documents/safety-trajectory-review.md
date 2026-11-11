# Safety and trajectory conflict review

## Purpose and boundary

Use a trajectory conflict signal to decide what evidence needs review, not to name a root cause. Time to collision, relative speed, distance, trajectory overlap, braking, steering, and post-encroachment timing describe the seriousness and shape of an interaction. They do not establish whether perception, prediction, planning, control, another road user, or an intended fallback created the observed situation.

The review should preserve the event timeline. Start before the minimum criticality point and inspect what changed in ego motion, actor motion, alerts, and available perception or prediction signals. A late reaction can be a useful question, but it is not a conclusion without checking which information was available and when.

## Investigation sequence

First, identify the actors involved and reconstruct relative position, heading, speed, and trajectory over the event window. Record the minimum time-to-collision value together with the closing-speed assumption used to interpret it. Check whether the actor path actually overlapped the intended ego path, whether the conflict was transient, and whether either participant made an evasive maneuver.

Second, correlate the conflict with upstream evidence. A low TTC with stable perception and a sudden actor maneuver invites a different review path from a low TTC preceded by falling track confidence or diverging motion prediction. Likewise, a sharp change in ego jerk or lane relation may indicate that the desired maneuver, constraint handling, and vehicle response need inspection.

Third, identify missing data explicitly. Without authoritative object tracks, planning intent, actuator state, map context, or policy state, the case may support only a safety-conflict route and a request for more evidence. Keep the case in human review rather than translating one metric into an engineering verdict.

## Follow-up experiment

Describe the replay as a parameterised interaction: approach speed, actor position, actor maneuver, visibility, road geometry, and timing. Vary one parameter at a time in simulation or offline replay. The follow-up test should answer a narrow question, such as whether a changing actor speed causes the criticality signal to cross the local investigation threshold, rather than claiming broad scenario coverage.

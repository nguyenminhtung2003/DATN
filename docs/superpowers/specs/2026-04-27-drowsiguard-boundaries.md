# DrowsiGuard Boundary Spec

## Goal

Keep the Jetson runtime and WebQuanLi dashboard stable while making ownership
boundaries explicit around AI thresholds, AI session state, WebSocket contracts,
and face reference enrollment.

## Stable WebSocket Boundary

Version3 remains the sender for runtime messages and WebQuanLi remains the
schema validator and persistence/UI boundary. Existing message types must stay
compatible:

- `hardware`
- `alert`
- `verify_snapshot`
- `verify_error`
- `session_start`
- `session_end`

New fields may be added only as optional data. Existing fields must not be
renamed or removed without a separate migration plan and contract tests in both
projects.

## AI Threshold Boundary

Threshold payload construction is centralized in `ai.threshold_policy`. The
policy reads the existing calibration profile values and preserves current
behavior. Adaptive EAR changes are intentionally out of scope for this boundary
stabilization pass.

## AI Session Boundary

`ai.session_controller.AiSessionController` owns per-session calibration state,
classifier reset/update calls, and calibration payload generation. `main.py`
keeps orchestration responsibilities and delegates AI session details through
thin wrappers.

## Face Reference Boundary

`camera.face_verifier.FaceVerifier` remains responsible for comparing a live
face crop against local references. `camera.face_enrollment.FaceEnrollmentService`
owns enrollment writes and source metadata.

Primary face references should be captured from the same Jetson IR camera path
used for live verification. WebQuanLi-synced images remain supported as fallback
references unless their manifest metadata explicitly identifies a trusted Jetson
IR source.

## Verification Expectations

Any change that touches these boundaries must run focused tests for the relevant
side and at least one cross-project WebSocket contract check.

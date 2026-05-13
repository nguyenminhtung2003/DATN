# DrowsiGuard Project Scorecard

Date: 2026-05-13

Purpose: summarize the current project quality for demo/defense readiness, with each claim tied to code, tests, or manual evidence.

## Current Score Estimate

Estimated current score: **9.0/10** for graduation demo readiness.

Conditional defense-presentation score: **9.1-9.2/10** if the final manual camera/RFID demo is repeated successfully on demo day and the stable snapshot is committed/pushed after user approval.

Reason for not claiming higher:

- Current face verification is practical and demo-ready, but not industrial biometric security.
- Round 6 found Jetson OpenCV lacks SFace/YuNet APIs, so embedding verification was not implemented.
- Live camera/RFID tests still need to be repeated immediately before presentation.

## Category Scores

| Category | Score | Evidence | Notes |
|---|---:|---|---|
| System architecture | 9.0 | `docs/images/system_overview.svg`, `docs/images/software_architecture.svg`, `Version3/main.py`, `WebQuanLi/app/ws/jetson_handler.py` | Clear Jetson/WebQuanLi split and realtime WebSocket path. |
| Identity-gated workflow | 8.8 | `Version3/main.py`, `Version3/tests/test_verify_flow.py`, `docs/demo-readiness/operator-runbook.md` | RFID -> face verify -> session start is implemented; manual no-face/correct-face checks remain mandatory before demo. |
| Face verification practicality | 8.0 | `Version3/camera/face_verifier.py`, `docs/demo-readiness/face-threshold-calibration.md`, `docs/demo-readiness/face-embedding-spike.md` | Multi-reference/fallback approach is practical; not biometric-grade. |
| Drowsiness AI pipeline | 8.8 | `Version3/camera/face_analyzer.py`, `Version3/ai/drowsiness_classifier.py`, `Version3/ai/threshold_policy.py`, `docs/demo-readiness/drowsiness-demo-script.md` | Uses MediaPipe Face Mesh plus EAR/MAR/PERCLOS/pitch temporal rules. |
| WebQuanLi integration | 9.0 | `WebQuanLi/app/ws/jetson_handler.py`, `WebQuanLi/app/services/jetson_session_service.py`, `Version3/tests/test_webquanli_contract.py`, `WebQuanLi/tests/test_verify_snapshot_contract.py` | Events are typed and dashboard-facing messages are clearer after Round 3. |
| Demo operations | 9.0 | `Version3/healthcheck.py`, `Version3/scripts/test_demo_readiness.py`, `docs/demo-readiness/operator-runbook.md` | One-command hardware readiness now reports strict mode, face verify, references, RFID and dashboard reachability. |
| Defense materials | 9.1 | `docs/demo-readiness/committee-demo-script.md`, this scorecard, rendered diagrams | User can explain system without improvising the core workflow. |

## Evidence Map

### Runtime Strict Mode

Claim: Jetson demo should not bypass identity verification.

Evidence:

- `DROWSIGUARD_DEMO_MODE=false`
- `DROWSIGUARD_FEATURE_FACE_VERIFY=true`
- `DROWSIGUARD_FACE_VERIFY_THRESHOLD=0.785`
- Launcher echo text was corrected in Round 5.
- Hardware readiness reports these fields in `Version3/healthcheck.py`.

Required final manual proof:

- Scan RFID with no face: session must not start.
- Scan RFID with correct face: session starts.
- Show face, leave camera, then scan RFID: session must not start.

### Identity Event Contract

Claim: WebQuanLi receives meaningful identity events.

Evidence:

- `Version3/main.py` pushes:
  - `verify_snapshot`
  - `verify_error`
  - `face_mismatch`
  - `session_start`
  - `session_end`
- `WebQuanLi/app/ws/jetson_handler.py` handles these event types.
- `Version3/tests/test_verify_flow.py` covers no-enrollment, no-face, mismatch, verified and low-confidence paths.
- `WebQuanLi/tests/test_verify_snapshot_contract.py` covers dashboard-facing verify schema.

### Drowsiness Event Contract

Claim: after a verified session, drowsiness alerts can be generated and sent to WebQuanLi.

Evidence:

- `Version3/alerts/alert_manager.py` maps AI state/hints to alert levels.
- `Version3/main.py` pushes `alert` payloads.
- `WebQuanLi/app/services/jetson_session_service.py` creates drowsiness alert records.
- `docs/demo-readiness/drowsiness-demo-script.md` records fixed drowsiness demo payload checks.

### Diagram Evidence

Primary report diagrams:

- `docs/images/system_overview.svg`
- `docs/images/hardware_block.svg`
- `docs/images/software_architecture.svg`
- `docs/images/ai_pipeline.svg`
- `docs/images/rfid_workflow.svg`
- `docs/images/websocket_sequence.svg`
- `docs/images/database_erd.svg`
- `docs/images/demo_network.svg`

Appendix/slide diagrams:

- `docs/images/drowsiness_algorithm_flow.svg`
- `docs/images/alert_state_flow.svg`
- `docs/images/project_mindmap.svg`

## Final Acceptance Checklist

| Requirement | Current status | Evidence |
|---|---|---|
| Jetson strict mode is enabled | Pass in latest readiness check | `healthcheck.py --quick` / hardware mode output |
| Face verify feature is enabled | Pass in latest readiness check | `face_verify=true` |
| Demo RFID has reference images | Pass in latest readiness check | `0199190080 references=6` |
| No-face scan rejects | Needs final live repeat | Manual RFID/camera test |
| Correct-face scan starts session | User previously reported pass; repeat before defense | Manual RFID/camera test |
| Stale/no-current-face scan rejects | Needs final live repeat | Manual RFID/camera test |
| Wrong-face/low-confidence rejects | Covered by tests; live optional | `tests/test_verify_flow.py` |
| Drowsiness alert after verified session | Scripted check exists; live repeat recommended | `drowsiness-demo-script.md` |
| WebQuanLi event path is tested | Pass in automated contract tests | `Version3/tests/test_webquanli_contract.py`, `WebQuanLi/tests/` |
| One-command hardware readiness exists | Pass | `scripts/test_demo_readiness.py --mode hardware` |
| Rollback notes exist | Pass | `operator-runbook.md`, round docs |
| Stable snapshot committed/pushed | Pending user approval | Git step intentionally not automatic |

## What To Say To The Committee

Use this framing:

> "Em danh gia he thong hien tai khoang 9/10 cho muc tieu demo do an. Diem manh la luong dau-cuoi da day du: RFID, xac thuc khuon mat live, AI phat hien buon ngu, dashboard realtime va lich su. Gioi han la phan xac thuc khuon mat chua phai sinh trac hoc cap cong nghiep va van phu thuoc anh sang/goc mat, nen em trinh bay no la co che xac thuc thuc dung cho demo va co huong nang cap bang embedding sau nay."

## Remaining Gaps

- Repeat the three live identity cases immediately before presentation.
- Confirm WebQuanLi is reachable from the demo phone/laptop network.
- Confirm speaker output if audio warnings are part of the live demo.
- Commit/push only after the user approves the final snapshot.
- Keep SFace/embedding as future work until Jetson OpenCV/model support is ready.

## Rollback

Docs-only rollback for this round:

```powershell
Remove-Item D:\DATN-testing1\docs\demo-readiness\committee-demo-script.md
Remove-Item D:\DATN-testing1\docs\demo-readiness\project-scorecard.md
```

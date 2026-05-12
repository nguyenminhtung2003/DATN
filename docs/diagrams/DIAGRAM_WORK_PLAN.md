# DATN Report-Grade Diagram Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Before editing any diagram source, use the installed `mermaid-diagrams` skill and read the relevant Mermaid C4, flowchart, ERD, and sequence references. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thiết kế lại bộ sơ đồ báo cáo DrowsiGuard để SVG đưa vào Word/PDF rõ ràng, ít rối mắt, có khuôn khổ C4/report-grade, và vẫn bám đúng code `Version3` + `WebQuanLi`.

**Architecture:** Giữ nguyên workflow diagram-as-code. Mermaid dùng cho tổng quan, phần cứng, workflow, ERD và các sơ đồ phụ; D2 dùng cho kiến trúc phần mềm, pipeline AI và mạng demo; PlantUML dùng cho sequence. Các sơ đồ lớn phải được tách theo tầng: Context -> Container/Component -> Workflow/Detail, mỗi hình chỉ truyền một thông điệp chính.

**Tech Stack:** Mermaid CLI qua `cmd /c npx mmdc`, D2 CLI qua `d2`, PlantUML qua `java -jar tools/plantuml/plantuml.jar`, PowerShell render script, SVG output, skill `mermaid-diagrams`.

---

## 0. Design Diagnosis

### 0.1 Current Problem

Bộ SVG hiện tại đã render được nhưng chưa phù hợp để đưa vào báo cáo vì:

- Nhiều sơ đồ nhồi quá nhiều node vào một hình.
- Chưa có hệ phân cấp thị giác: actor, runtime, backend, database và thiết bị cảnh báo nhìn gần như ngang nhau.
- Một số sơ đồ giống bản ghi kỹ thuật nội bộ hơn là hình minh họa luận văn.
- ERD quá nhiều field nên rộng và khó đọc khi chèn Word/PDF.
- Architecture diagram chưa theo tầng C4 nên người đọc khó hiểu từ tổng quan đến chi tiết.
- Các sơ đồ phụ chưa được phân vai rõ: dùng ở chương chính, phụ lục hay slide bảo vệ.

### 0.2 Redesign Standard

Mọi sơ đồ sau redesign phải tuân thủ các quy tắc sau:

- Một sơ đồ chỉ trả lời một câu hỏi.
- Tối đa 6-8 node chính trong sơ đồ tổng quan hoặc workflow.
- Tối đa 12 node chính trong architecture/pipeline khi đã chia cụm rõ.
- Nhãn tiếng Việt ngắn, phù hợp báo cáo tốt nghiệp.
- Không đưa tên class/file vào sơ đồ tổng quan hoặc phần cứng.
- Chỉ đưa tên module/class vào sơ đồ architecture hoặc pipeline khi cần chứng minh bám code.
- Cùng một kiểu node phải có cùng màu và cùng vai trò trong mọi hình.
- Ưu tiên layout trái sang phải cho kiến trúc; trên xuống dưới cho quy trình.
- ERD chỉ hiển thị khóa và field nhận diện chính; field chi tiết để trong thuyết minh báo cáo.
- Sequence diagram chỉ giữ message chính của kịch bản demo, không ghi mọi event phụ.

### 0.3 Visual Style Tokens

Áp dụng bảng màu nhất quán:

| Role | Color | Usage |
|---|---|---|
| Người dùng / quản lý | `#E8F2FF` | Người lái, người quản lý, dashboard user |
| Jetson / runtime tại xe | `#E9F8EF` | Jetson Nano, Version3, AI runtime |
| WebQuanLi / backend | `#FFF4E6` | FastAPI, WebSocket handler, dashboard backend |
| Database / lưu trữ | `#F2F0FF` | SQLite WebQuanLi, local queue |
| Cảnh báo / rủi ro | `#FFE8E8` | alert device, warning states |
| Network / giao tiếp | `#F4F4F4` | Wi-Fi, WebSocket, SSE |

Mermaid source nên dùng `theme: base` và `themeVariables` khi cú pháp diagram hỗ trợ. D2 source nên dùng shape/group rõ, ít màu, label ngắn. PlantUML nên dùng `skinparam monochrome false`, font dễ đọc, message ngắn.

---

## 1. Scope And Boundaries

### 1.1 Files Allowed

- Modify: `docs/diagrams/DIAGRAM_WORK_PLAN.md`
- Modify: `docs/diagrams/system_overview.mmd`
- Modify: `docs/diagrams/hardware_block.mmd`
- Modify: `docs/diagrams/software_architecture.d2`
- Modify: `docs/diagrams/ai_pipeline.d2`
- Modify: `docs/diagrams/rfid_workflow.mmd`
- Modify: `docs/diagrams/websocket_sequence.puml`
- Modify: `docs/diagrams/database_erd.mmd`
- Modify: `docs/diagrams/demo_network.d2`
- Modify: `docs/diagrams/drowsiness_algorithm_flow.mmd`
- Modify: `docs/diagrams/project_mindmap.mmd`
- Modify: `docs/diagrams/alert_state_flow.mmd`
- Modify: `docs/diagrams/report_diagram_index.md`
- Modify: `docs/diagrams/puppeteer-config.json`
- Modify: `docs/render_diagrams.ps1`
- Create or overwrite rendered SVG under `docs/images/`

### 1.2 Files Forbidden

- Do not modify files under `Version3/`.
- Do not modify files under `WebQuanLi/`.
- Do not modify `.env`, database files, launcher `.bat`, deployment scripts, or runtime config.
- Do not modify `package.json` or `package-lock.json`.
- Do not stage, commit, push, or deploy.

### 1.3 Evidence Files To Read Before Redesign

- `Version3/main.py`
- `Version3/camera/face_analyzer.py`
- `Version3/ai/calibration.py`
- `Version3/ai/threshold_policy.py`
- `Version3/ai/drowsiness_classifier.py`
- `Version3/alerts/alert_manager.py`
- `Version3/storage/local_queue.py`
- `WebQuanLi/app/models.py`
- `WebQuanLi/app/ws/jetson_handler.py`
- `WebQuanLi/app/services/jetson_session_service.py`
- `WebQuanLi/app/core/event_bus.py`
- `WebQuanLi/app/api/sse.py`

---

## 2. Diagram Redesign Matrix

| File | New role | Framework | Chapter | Main question |
|---|---|---|---|---|
| `system_overview.mmd` | System context | Mermaid C4-style context or flowchart fallback | Chương 3 | Hệ thống gồm ai, thiết bị nào, giao tiếp ra sao? |
| `hardware_block.mmd` | Hardware block | Mermaid flowchart TB | Chương 3 | Các khối phần cứng demo nối với nhau thế nào? |
| `software_architecture.d2` | Container/component view | D2 C4-style grouped architecture | Chương 3 | Jetson và WebQuanLi chia module phần mềm ra sao? |
| `ai_pipeline.d2` | AI processing pipeline | D2 staged pipeline | Chương 3 | Frame camera đi qua các bước AI nào để ra cảnh báo? |
| `rfid_workflow.mmd` | Check-in/check-out workflow | Mermaid flowchart TD | Chương 3 | RFID tạo/kết thúc phiên lái như thế nào? |
| `websocket_sequence.puml` | Runtime interaction sequence | PlantUML sequence | Chương 3 | Jetson và WebQuanLi trao đổi message chính ra sao? |
| `database_erd.mmd` | Compact data model | Mermaid ERD compact | Chương 3 | Bảng chính và quan hệ chính trong SQLite là gì? |
| `demo_network.d2` | Deployment/demo network | D2 deployment view | Chương 4 | Demo chạy trên LAN/hotspot như thế nào? |
| `drowsiness_algorithm_flow.mmd` | Algorithm detail | Mermaid flowchart TD | Phụ lục hoặc slide | Classifier quyết định trạng thái buồn ngủ ra sao? |
| `alert_state_flow.mmd` | Alert state detail | Mermaid state diagram | Phụ lục hoặc slide | Trạng thái AI chuyển thành mức cảnh báo ra sao? |
| `project_mindmap.mmd` | Defense overview | Mermaid mindmap simplified | Slide mở đầu hoặc phụ lục | Toàn bộ đồ án gồm các mảng nào? |

---

## 3. Task 1: Redesign `system_overview.mmd`

**Files:**
- Modify: `docs/diagrams/system_overview.mmd`
- Render: `docs/images/system_overview.svg`

- [ ] **Step 1: Read C4 guidance**

Read:

```powershell
Get-Content C:\Users\Tung\.codex\skills\mermaid-diagrams\references\c4-diagrams.md -TotalCount 220
```

Expected: Use System Context principles: people, system, external systems, database, concise relationships.

- [ ] **Step 2: Rewrite the diagram as a C4-style context view**

Primary nodes:

```text
Người lái
Người quản lý
DrowsiGuard trên Jetson Nano
Camera + RFID
Thiết bị cảnh báo tại xe
WebQuanLi
SQLite WebQuanLi
Dashboard
```

Rules:

- Keep labels short.
- Group camera/RFID as input devices instead of separate detailed components.
- Show only four relationship types: quan sát, xác thực, cảnh báo tại xe, đồng bộ WebSocket/realtime.
- If Mermaid C4 syntax fails under local CLI, implement the same C4-style structure using `flowchart LR` with strict grouping.

- [ ] **Step 3: Render and check**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File docs\render_diagrams.ps1
```

Expected: `docs/images/system_overview.svg` exists and is readable at report width.

---

## 4. Task 2: Redesign `hardware_block.mmd`

**Files:**
- Modify: `docs/diagrams/hardware_block.mmd`
- Render: `docs/images/hardware_block.svg`

- [ ] **Step 1: Rewrite as three visual bands**

Bands:

```text
Đầu vào: Camera, đầu đọc RFID
Xử lý tại xe: Jetson Nano
Đầu ra/giao tiếp: loa/còi/LED, Wi-Fi/hotspot, laptop WebQuanLi, dashboard
```

Rules:

- Do not include class names or filenames.
- Use top-to-bottom layout.
- Use only hardware/network nouns.
- Keep every label under 35 characters.

- [ ] **Step 2: Render and check**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File docs\render_diagrams.ps1
```

Expected: `hardware_block.svg` has no more than 7 main nodes and no crossing-heavy edges.

---

## 5. Task 3: Redesign `software_architecture.d2`

**Files:**
- Modify: `docs/diagrams/software_architecture.d2`
- Render: `docs/images/software_architecture.svg`

- [ ] **Step 1: Use C4 container/component thinking in D2**

Create three grouped regions:

```text
Jetson Nano - Version3
Giao tiếp realtime
WebQuanLi
```

Jetson group nodes:

```text
Điều phối runtime
Phân tích khuôn mặt
Phân loại buồn ngủ
Hiệu chuẩn tài xế
RFID + xác minh
Cảnh báo tại xe
Hàng đợi offline
```

WebQuanLi group nodes:

```text
WebSocket handler
Session service
EventBus + SSE
Dashboard
SQLAlchemy models
SQLite database
```

Rules:

- Avoid showing all file names as boxes.
- Put file/module names in smaller labels or notes only.
- Edge labels must be short: `metrics`, `alert`, `session`, `SSE`, `SQL`.
- Keep Jetson on the left, WebQuanLi on the right, realtime bridge in the center.

- [ ] **Step 2: Render and check**

Run:

```powershell
d2 docs/diagrams/software_architecture.d2 docs/images/software_architecture.svg
```

Expected: `software_architecture.svg` has three readable groups and can fit one report page in landscape orientation.

---

## 6. Task 4: Redesign `ai_pipeline.d2`

**Files:**
- Modify: `docs/diagrams/ai_pipeline.d2`
- Render: `docs/images/ai_pipeline.svg`

- [ ] **Step 1: Rewrite as staged pipeline**

Stages:

```text
1. Thu nhận frame
2. Phát hiện khuôn mặt
3. Trích xuất đặc trưng
4. Hiệu chuẩn và ngưỡng
5. Phân loại trạng thái
6. Cảnh báo và realtime
```

Details inside stages:

```text
EAR / MAR / pitch
eye quality
baseline EAR
adaptive threshold
PERCLOS
alert_hint
```

Rules:

- Do not use more than 6 stage boxes.
- Put technical terms in small secondary labels.
- Use one direction left-to-right.
- Show `WebQuanLi realtime status` as output, not part of the AI core.

- [ ] **Step 2: Render and check**

Run:

```powershell
d2 docs/diagrams/ai_pipeline.d2 docs/images/ai_pipeline.svg
```

Expected: `ai_pipeline.svg` reads as a clean pipeline, not a component graph.

---

## 7. Task 5: Redesign `rfid_workflow.mmd`

**Files:**
- Modify: `docs/diagrams/rfid_workflow.mmd`
- Render: `docs/images/rfid_workflow.svg`

- [ ] **Step 1: Rewrite as a narrow vertical workflow**

Main flow:

```text
Quẹt thẻ RFID
Đọc UID
Tra cứu tài xế
Xác minh khuôn mặt
Tạo phiên lái
Giám sát trong phiên
Quẹt lại để kết thúc
```

Decision nodes:

```text
Tài xế hợp lệ?
Đang có phiên lái?
```

Rules:

- Use one happy path down the center.
- Put error paths on the right.
- Do not include WebSocket implementation detail except one label: `gửi session_start/session_end`.

- [ ] **Step 2: Render and check**

Run:

```powershell
cmd /c npx mmdc -p docs/diagrams/puppeteer-config.json -i docs/diagrams/rfid_workflow.mmd -o docs/images/rfid_workflow.svg
```

Expected: `rfid_workflow.svg` fits portrait width and has no more than 2 decision diamonds.

---

## 8. Task 6: Redesign `websocket_sequence.puml`

**Files:**
- Modify: `docs/diagrams/websocket_sequence.puml`
- Render: `docs/images/websocket_sequence.svg`

- [ ] **Step 1: Reduce sequence to demo-critical messages**

Participants:

```text
Jetson Version3
WebQuanLi WebSocket
Session Service
SQLite
EventBus/SSE
Dashboard
```

Message groups:

```text
Kết nối thiết bị
RFID và xác minh tài xế
Bắt đầu phiên lái
Cảnh báo buồn ngủ realtime
Kết thúc phiên lái
Mất kết nối
```

Rules:

- Keep message labels under 45 characters.
- Use `== group title ==` separators.
- Use one `loop Trong phiên lái` block for repeated alert updates.
- Use one `alt Không tìm thấy tài xế` block for verification failure.

- [ ] **Step 2: Render and check**

Run:

```powershell
java -jar tools/plantuml/plantuml.jar -tsvg -o ..\images docs/diagrams/websocket_sequence.puml
```

Expected: `websocket_sequence.svg` is readable without horizontal scrolling when inserted into Word landscape.

---

## 9. Task 7: Redesign `database_erd.mmd`

**Files:**
- Modify: `docs/diagrams/database_erd.mmd`
- Render: `docs/images/database_erd.svg`

- [ ] **Step 1: Convert to compact ERD**

Entities:

```text
USERS
VEHICLES
DRIVERS
DRIVER_SESSIONS
SYSTEM_ALERTS
HARDWARE_STATUSES
OTA_AUDIT_LOGS
```

Keep only these attributes:

```text
id
vehicle_id
driver_id
session_id
rfid_tag
device_id
alert_type
alert_level
checkin_at
checkout_at
timestamp
```

Rules:

- Preserve the comment that RFID is stored in `drivers.rfid_tag`.
- Do not create a separate RFID card table.
- Keep relationships from `WebQuanLi/app/models.py`.
- Put detailed field list in `report_diagram_index.md`, not in the ERD image.

- [ ] **Step 2: Render and check**

Run:

```powershell
cmd /c npx mmdc -p docs/diagrams/puppeteer-config.json -i docs/diagrams/database_erd.mmd -o docs/images/database_erd.svg
```

Expected: `database_erd.svg` is less wide than the current version and readable in Chương 3.

---

## 10. Task 8: Redesign `demo_network.d2`

**Files:**
- Modify: `docs/diagrams/demo_network.d2`
- Render: `docs/images/demo_network.svg`

- [ ] **Step 1: Rewrite as deployment view**

Columns:

```text
Thiết bị trên xe
Mạng demo
Laptop/WebQuanLi
Người xem dashboard
```

Required labels:

```text
Jetson Nano
Camera + RFID
Hotspot/router
ws://<laptop-ip>:8000/ws/jetson/JETSON-001
WebQuanLi 0.0.0.0:8000
SQLite
Dashboard browser
```

Rules:

- Show IP/URL as an edge label, not a large node.
- Keep WebQuanLi and SQLite inside the laptop/server group.
- Keep the diagram as a deployment view, not a software architecture view.

- [ ] **Step 2: Render and check**

Run:

```powershell
d2 docs/diagrams/demo_network.d2 docs/images/demo_network.svg
```

Expected: `demo_network.svg` is clear for Chương 4 demo setup.

---

## 11. Task 9: Redesign Supplementary Diagrams

**Files:**
- Modify: `docs/diagrams/drowsiness_algorithm_flow.mmd`
- Modify: `docs/diagrams/alert_state_flow.mmd`
- Modify: `docs/diagrams/project_mindmap.mmd`
- Render: matching SVG files under `docs/images/`

- [ ] **Step 1: Redesign `drowsiness_algorithm_flow.mmd`**

Keep this as algorithm explanation for defense, not a main report architecture diagram.

Final sections:

```text
Nhận frame
Kiểm tra khuôn mặt
Kiểm tra chất lượng mắt
Tính đặc trưng
So ngưỡng cá nhân hóa
Phân loại trạng thái
Sinh alert_hint
```

Expected: at most 9 nodes.

- [ ] **Step 2: Redesign `alert_state_flow.mmd`**

Keep only the states that help explain alert escalation:

```text
NORMAL
LOW_CONFIDENCE
NO_FACE
EYES_CLOSED
DROWSY
YAWNING
HEAD_DOWN
Alert Level 1
Alert Level 2
Alert Level 3
```

Expected: no more than 12 transitions.

- [ ] **Step 3: Redesign `project_mindmap.mmd`**

Use only top-level branches:

```text
Phần cứng
Jetson Version3
AI buồn ngủ
RFID và tài xế
WebQuanLi
Database
Realtime
Demo
```

Expected: one-page overview for slide/phụ lục, not chapter evidence.

---

## 12. Task 10: Update `report_diagram_index.md`

**Files:**
- Modify: `docs/diagrams/report_diagram_index.md`

- [ ] **Step 1: Reclassify diagrams**

Use this classification:

```text
Chương 3 chính: system_overview, hardware_block, software_architecture, ai_pipeline, rfid_workflow, websocket_sequence, database_erd
Chương 4 chính: demo_network
Phụ lục hoặc slide: drowsiness_algorithm_flow, alert_state_flow, project_mindmap
```

- [ ] **Step 2: Add visual purpose and manual check columns**

Table columns:

```text
Diagram
Source
Image
Purpose
Suggested placement
Evidence
Manual check
```

Manual check examples:

```text
Readable at Word width
No crossed critical edges
No more than 8 primary nodes
Matches WebQuanLi/app/models.py
Matches Version3 runtime path
```

---

## 13. Task 11: Render Script And Verification

**Files:**
- Modify: `docs/render_diagrams.ps1`
- Create or overwrite: `docs/images/*.svg`

- [ ] **Step 1: Keep current Puppeteer config**

Keep:

```text
docs/diagrams/puppeteer-config.json
```

Reason: local Mermaid CLI previously timed out without this config.

- [ ] **Step 2: Run full render**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File docs\render_diagrams.ps1
```

Expected:

```text
11 SVG files generated
0 render failures
All SVG files have non-zero length
```

- [ ] **Step 3: Verify outputs**

Run:

```powershell
Get-ChildItem docs\images -Filter *.svg | Sort-Object Name | Select-Object Name,Length,LastWriteTime
```

Expected:

```text
ai_pipeline.svg
alert_state_flow.svg
database_erd.svg
demo_network.svg
drowsiness_algorithm_flow.svg
hardware_block.svg
project_mindmap.svg
rfid_workflow.svg
software_architecture.svg
system_overview.svg
websocket_sequence.svg
```

- [ ] **Step 4: Scan for placeholder text**

Run:

```powershell
rg -n "T[B]D|T[O]DO|FIXM[E]|PLACEHOLD[E]R|implement late[r]|fill i[n]" docs/diagrams docs/render_diagrams.ps1
```

Expected: no matches.

- [ ] **Step 5: Confirm allowed paths only**

Run:

```powershell
git status --short -- docs/diagrams docs/images docs/render_diagrams.ps1 Version3 WebQuanLi package.json package-lock.json
```

Expected:

```text
Only docs/diagrams, docs/images, and docs/render_diagrams.ps1 are changed by this redesign work.
No Version3 or WebQuanLi files are changed.
No package.json or package-lock.json changes are introduced by this redesign work.
```

---

## 14. Final Report Format

After implementation, report in Vietnamese with:

```text
1. Files modified
2. SVG files rendered successfully
3. Files failed, with error text
4. Commands used
5. Design changes made per diagram
6. Manual checks needed before inserting into Word/PDF
7. Confirmation that Version3/WebQuanLi runtime was not modified
```

Manual checks to request from the user:

```text
Open each SVG from docs/images in Chrome/Edge.
Insert system_overview.svg, software_architecture.svg, ai_pipeline.svg, and database_erd.svg into Word to check page fit.
Confirm whether supplementary diagrams should be kept in appendix or moved to slide deck.
Confirm real demo IP before finalizing demo_network.svg.
```

---

## Self-Review

- Spec coverage: This plan covers all 8 required diagrams, 3 supplementary diagrams, render script, SVG outputs, and final reporting.
- Skill coverage: This plan applies `mermaid-diagrams` guidance: choose the correct diagram type, use C4 hierarchy, split large diagrams, keep focused views, and validate render output.
- Scope control: This plan keeps changes inside `docs/diagrams/`, `docs/images/`, and `docs/render_diagrams.ps1`; runtime code is forbidden.
- Design correction: This plan explicitly fixes the current issue of cluttered diagrams by applying node budgets, C4 hierarchy, compact ERD, staged pipeline, and simplified sequence messages.
- Execution gate: Do not implement this redesign until the user approves this rewritten plan.

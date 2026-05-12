# AGENTS.md — Diagram Workflow for DATN

## Project Context

This is a graduation thesis project about an AI-based drowsiness warning system using Jetson Nano, Camera, RFID, WebQuanLi dashboard, WebSocket communication, and SQLite database.

## Diagram Work Rules

When asked to create diagrams for the report:

1. Do not rewrite the main application code.
2. Do not change runtime behavior of Version3 or WebQuanLi.
3. Only create or edit files under:
   - docs/diagrams/
   - docs/images/
   - docs/render_diagrams.ps1
   - tools/plantuml/ if needed
4. Use diagram-as-code, not manually drawn raster images.
5. Prefer:
   - Mermaid for system overview, hardware block, workflow, ERD.
   - D2 for software architecture, AI pipeline, deployment architecture.
   - PlantUML for sequence diagrams.
6. Every generated diagram must have:
   - Source file in docs/diagrams/
   - Rendered image in docs/images/
7. Prefer SVG for report images. Use PNG only when the tool does not render SVG well.
8. Diagram labels should be in Vietnamese and suitable for a graduation thesis report.
9. After editing, run docs/render_diagrams.ps1 if possible.
10. Report clearly:
   - files created
   - files rendered successfully
   - files failed
   - commands used
   - next manual checks needed

## Required Diagrams

Create these diagrams:

1. system_overview.mmd — Sơ đồ tổng quan hệ thống
2. hardware_block.mmd — Sơ đồ khối phần cứng
3. software_architecture.d2 — Sơ đồ kiến trúc phần mềm
4. ai_pipeline.d2 — Pipeline xử lý AI buồn ngủ
5. rfid_workflow.mmd — Workflow RFID/check-in/check-out
6. websocket_sequence.puml — Sequence Jetson ↔ WebQuanLi
7. database_erd.mmd — ERD database
8. demo_network.d2 — Sơ đồ triển khai mạng demo

## Rendering Commands

Use these commands when possible:

```powershell
npx mmdc -i docs/diagrams/system_overview.mmd -o docs/images/system_overview.svg
npx mmdc -i docs/diagrams/hardware_block.mmd -o docs/images/hardware_block.svg
npx mmdc -i docs/diagrams/rfid_workflow.mmd -o docs/images/rfid_workflow.svg
npx mmdc -i docs/diagrams/database_erd.mmd -o docs/images/database_erd.svg

d2 docs/diagrams/software_architecture.d2 docs/images/software_architecture.svg
d2 docs/diagrams/ai_pipeline.d2 docs/images/ai_pipeline.svg
d2 docs/diagrams/demo_network.d2 docs/images/demo_network.svg

java -jar tools/plantuml/plantuml.jar -tsvg docs/diagrams/websocket_sequence.puml
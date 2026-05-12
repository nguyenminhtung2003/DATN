# Giao trình C2: Giải thích từng file code quan trọng để bảo vệ đồ án

Tài liệu này là bản hướng dẫn đọc code. Khi hội đồng yêu cầu “mở code giải thích”, bạn không nên mở ngẫu nhiên. Bạn cần biết mở file nào trước, chỉ vào hàm nào, nói ý gì, và liên hệ nó với kiến trúc tổng thể.

Quy tắc học C2:

- Đừng học thuộc từng dòng.
- Học vai trò file, luồng dữ liệu, input/output, lỗi được xử lý ra sao.
- Với mỗi file, nhớ một câu “đây là file làm gì”.
- Khi trả lời, luôn nối code với yêu cầu thực tế: realtime, bảo mật, chống mất mạng, giảm database I/O, xác thực tài xế.

## Cập nhật theo trạng thái project hiện tại

Khi mở code trước hội đồng, nên gọi theo tên sản phẩm/chức năng thay vì tên folder:

| Folder/file | Cách gọi khi trình bày | Ý cần nói |
|---|---|---|
| `Version3` | **DrowsiGuard Edge Runtime** | Runtime chạy trên Jetson Nano: camera, RFID, GPS, AI, cảnh báo tại chỗ, WebSocket client |
| `WebQuanLi` | **DrowsiGuard Monitoring Hub** / **Trung tâm giám sát** | Backend FastAPI + dashboard realtime để quản lý xe, tài xế, session, alert |
| `WebQuanLi/templates/base.html` | Layout của Monitoring Hub | Sidebar đã hiển thị thương hiệu DrowsiGuard và menu Trung tâm giám sát |
| `WebQuanLi/templates/dashboard.html` | Màn hình Monitoring Hub | Màn hình chính hiển thị session, xác minh RFID + Face ID, thiết bị, alert gần đây, phần cứng, tài xế, GPS và nhật ký cảnh báo |
| `Version3/config.py` | Cấu hình runtime Jetson | `DROWSIGUARD_WS_URL` quyết định WebSocket server; demo hiện nên dùng Tailscale thay vì IP LAN cố định |
| `Version3/sensors/gps_reader.py` | GPS UART reader | Tách trạng thái UART/NMEA và trạng thái fix vệ tinh |
| `WebQuanLi/app/api/control.py` | Kênh điều khiển Jetson | Test loa và monitoring còn dùng; upload OTA hiện bị vô hiệu hóa bằng HTTP 410 |

Kịch bản code nên nhấn mạnh hiện tại:

1. WebQuanLi chạy trên Windows và lắng nghe `0.0.0.0:8000`.
2. Jetson chạy `DrowsiGuard-Full.desktop`, launcher/env đặt `DROWSIGUARD_WS_URL` trỏ về IP Tailscale của máy Windows.
3. Jetson kết nối WebSocket `/ws/jetson/JETSON-001`.
4. Dashboard browser nhận realtime qua SSE `/sse/vehicle/JETSON-001`.
5. GPS dùng `/dev/ttyTHS1`; nếu GPS hiện “chưa có fix” thì vẫn phải xem UART/NMEA có hoạt động không trước khi kết luận hỏng.

---

## 1. Bản đồ repository

Repo có 2 phần chính:

| Thư mục | Vai trò | Khi nào mở trước hội đồng |
|---|---|---|
| `Version3` | Code chạy trên Jetson | Khi hỏi AI, camera, RFID, GPS, cảnh báo, WebSocket client, offline queue |
| `WebQuanLi` | Backend và dashboard quản lý | Khi hỏi web, database, API, WebSocket server, SSE, auth, lịch sử |
| `docs` | Kế hoạch, spec, tài liệu học | Khi cần chứng minh bạn có tài liệu thiết kế/triển khai |

Một câu giới thiệu:

> Repo được chia đúng theo ranh giới triển khai. `Version3` là runtime edge device trên Jetson, còn `WebQuanLi` là hệ thống backend/dashboard trung tâm.

Nếu muốn gọi chuyên nghiệp hơn khi thuyết trình, nói:

> `Version3` là DrowsiGuard Edge Runtime trên Jetson Nano, còn `WebQuanLi` là DrowsiGuard Monitoring Hub ở phía trung tâm giám sát.

---

## 2. Cách mở code khi bảo vệ

Nếu hội đồng hỏi tổng quan, mở theo thứ tự này:

1. `Version3/main.py`
2. `Version3/state_machine.py`
3. `Version3/ai/drowsiness_classifier.py`
4. `Version3/alerts/alert_manager.py`
5. `Version3/network/ws_client.py`
6. `WebQuanLi/app/main.py`
7. `WebQuanLi/app/ws/jetson_handler.py`
8. `WebQuanLi/app/core/event_bus.py`
9. `WebQuanLi/app/api/sse.py`
10. `WebQuanLi/app/models.py`

Nếu hội đồng hỏi “luồng một cảnh báo đi từ camera lên web”, mở:

1. `Version3/camera/face_analyzer.py`
2. `Version3/ai/drowsiness_classifier.py`
3. `Version3/alerts/alert_manager.py`
4. `Version3/main.py`, hàm `_on_alert`
5. `Version3/network/ws_client.py`
6. `WebQuanLi/app/ws/jetson_handler.py`, nhánh `msg_type == "alert"`
7. `WebQuanLi/app/services/jetson_session_service.py`, hàm `create_drowsiness_alert`
8. `WebQuanLi/app/core/event_bus.py`
9. `WebQuanLi/app/api/sse.py`

Nếu hội đồng hỏi “web realtime hoạt động thế nào”, mở:

1. `WebQuanLi/app/ws/jetson_handler.py`
2. `WebQuanLi/app/core/event_bus.py`
3. `WebQuanLi/app/api/sse.py`
4. `WebQuanLi/templates/dashboard.html`
5. `WebQuanLi/templates/partials/*`

---

## 3. `Version3/main.py`: Bộ điều phối trung tâm trên Jetson

### 3.1 Vai trò

Đây là file quan trọng nhất của `Version3`. Nó không chỉ là entry point, mà là orchestrator:

- Khởi tạo camera, frame buffer.
- Khởi tạo FaceAnalyzer, AI classifier, calibration.
- Khởi tạo AlertManager, buzzer, LED, speaker.
- Khởi tạo RFID reader, GPS reader, hardware monitor.
- Khởi tạo WebSocket client và local queue.
- Khởi tạo OTA handler, runtime status, local GUI.
- Điều phối state machine.
- Nhận callback khi có RFID, alert, command từ backend.

Câu nói ngắn:

> `main.py` là bộ điều phối runtime trên Jetson, gom các module phần cứng, AI, cảnh báo, mạng và trạng thái hệ thống thành một vòng vận hành thống nhất.

### 3.2 Class `DrowsiGuard`

Class `DrowsiGuard` đại diện cho ứng dụng đang chạy trên thiết bị.

Trong `__init__`, nó tạo các thành phần:

- `StateMachine`: quản lý trạng thái.
- `CSICamera`: lấy frame camera.
- `FrameBuffer`: giữ frame mới nhất.
- `FaceAnalyzer`: trích xuất metrics mặt.
- `DrowsinessClassifier`: phân loại trạng thái AI.
- `DriverCalibrator`: tạo profile ngưỡng theo tài xế.
- `AlertManager`: quyết định cảnh báo.
- `RFIDReader`: đọc thẻ.
- `GPSReader`: lấy vị trí.
- `LocalQueue`: lưu event khi offline.
- `WSClient`: kết nối WebQuanLi.
- `OTAHandler`: cập nhật từ xa.
- `RuntimeStatusStore`: ghi trạng thái runtime cho dashboard local.

### 3.3 Hàm `run`

Hàm `run` là vòng đời chính:

- Start camera.
- Start RFID/GPS/network nếu feature bật.
- Chuyển state từ BOOTING sang IDLE.
- Lặp xử lý frame.
- Cập nhật AI.
- Cập nhật alert.
- Gửi runtime status.
- Cập nhật local GUI nếu bật.
- Dừng an toàn khi shutdown.

Cách giải thích:

> Vòng lặp chính không trực tiếp làm hết mọi thứ. Nó lấy dữ liệu mới, gọi các module chuyên trách, rồi các callback như `_on_alert`, `_on_rfid_scan`, `_on_backend_command` sẽ phát sinh hành động tương ứng.

### 3.4 Hàm `_on_rfid_scan`

Khi RFID reader đọc được UID:

- Nếu hệ thống đang ở trạng thái phù hợp, chuyển sang `VERIFYING_DRIVER`.
- Gọi `_verify_driver(uid)`.
- Có thể phát driver probe event để dashboard biết vừa có thẻ.

Câu trả lời mẫu:

> RFID không tự mở session. Nó chỉ kích hoạt luồng xác thực. Session chỉ bắt đầu khi verify thành công hoặc khi demo mode cho phép.

### 3.5 Hàm `_verify_driver`

Đây là nơi xử lý logic xác thực tài xế:

- Kiểm tra face verifier có sẵn không.
- Kiểm tra có frame khuôn mặt hiện tại không.
- Kiểm tra RFID có enrollment không.
- Gọi verifier so khớp mặt.
- Nếu match: `_start_verified_session`.
- Nếu mismatch: gửi `face_mismatch` hoặc `verify_error`.
- Nếu demo mode cho phép: `_start_demo_session`.

Điểm cần nắm:

> RFID xác định danh tính khai báo, face verification xác thực người thật đang ngồi trước camera.

### 3.6 Hàm `_start_verified_session`

Khi xác thực thành công:

- Lưu UID tài xế hiện tại.
- Reset/calibrate AI session.
- Reset AlertManager.
- Chuyển state sang RUNNING.
- Queue message `session_start`.
- Queue message `verify_snapshot` với status `VERIFIED`.

Khi hội đồng hỏi “session bắt đầu ở đâu”, mở hàm này.

### 3.7 Hàm `_on_alert`

Đây là callback được AlertManager gọi khi level cảnh báo thay đổi.

Nó tạo payload alert gồm:

- `level`
- `ear`
- `mar`
- `pitch`
- `perclos`
- `ai_state`
- `ai_confidence`
- `ai_reason`
- `timestamp`

Sau đó gửi vào `WSClient.send("alert", payload)`, thực chất là đẩy vào local queue trước.

Câu trả lời mẫu:

> Khi AlertManager đổi mức cảnh báo, `main.py` không gửi socket trực tiếp mà đẩy event vào WSClient. WSClient kết hợp LocalQueue để nếu mất mạng thì event vẫn được giữ lại.

### 3.8 Hàm `_on_backend_command`

Đây là cửa nhận lệnh từ WebQuanLi:

- `test_alert`: bật/tắt cảnh báo demo.
- `update_software`: xử lý cập nhật nếu tính năng bảo trì từ xa được bật lại.
- `sync_driver_registry`: tải manifest tài xế từ WebQuanLi.
- `connect_monitoring`: bật giám sát.
- `disconnect_monitoring`: tắt giám sát.

Câu trả lời mẫu:

> WebQuanLi không chỉ nhận dữ liệu. Nó có thể gửi command xuống Jetson qua WebSocket, và Jetson xử lý tập trung ở `_on_backend_command`.

---

## 4. `Version3/state_machine.py`: Khung trạng thái an toàn

### 4.1 Vai trò

File này định nghĩa các trạng thái hệ thống và các transition hợp lệ.

Các trạng thái:

- `BOOTING`
- `IDLE`
- `VERIFYING_DRIVER`
- `RUNNING`
- `MISMATCH_ALERT`
- `OFFLINE_DEGRADED`
- `UPDATING`

### 4.2 `VALID_TRANSITIONS`

Đây là bảng luật. Ví dụ:

- `BOOTING` chỉ được sang `IDLE`.
- `IDLE` được sang `VERIFYING_DRIVER`, `UPDATING`, `OFFLINE_DEGRADED`.
- `VERIFYING_DRIVER` được sang `RUNNING`, `IDLE`, `MISMATCH_ALERT`.

Ý nghĩa:

> Code không cho chuyển trạng thái tùy tiện. Nếu chuyển sai, hệ thống log invalid transition và trả False.

### 4.3 Cách trả lời khi bị hỏi

**Câu hỏi:** Vì sao phải có state machine?

**Trả lời mẫu:**

> Vì thiết bị có nhiều trạng thái nghiệp vụ: chưa xác thực, đang xác thực, đang chạy, sai tài xế, mất mạng, cập nhật/bảo trì. State machine giúp em ràng buộc transition hợp lệ, tránh tình trạng chưa xác thực nhưng vẫn chạy, hoặc đang bảo trì mà vẫn xử lý session bình thường.

---

## 5. `Version3/camera/face_analyzer.py`: Trích xuất đặc trưng khuôn mặt

### 5.1 Vai trò

File này chuyển frame camera thành metrics cho AI:

- Có thấy mặt không.
- EAR trái/phải.
- EAR được chọn.
- MAR.
- Pitch.
- Chất lượng mắt.
- Chất lượng khuôn mặt.
- Bounding box mặt.
- Landmark mắt/miệng.

### 5.2 Các hàm quan trọng

- `_dist`: tính khoảng cách hai điểm.
- `_mouth_aspect_ratio`: tính MAR.
- `_eye_side_quality`: đánh giá một bên mắt có dùng được không.
- `_build_eye_quality`: chọn mắt đáng tin nếu một bên bị glare/kính.
- `_build_face_quality`: kiểm tra mặt quá nhỏ, confidence thấp.
- `FaceAnalyzer`: class chính phân tích frame.

### 5.3 Điểm ăn điểm

Hệ thống không chỉ tính EAR trung bình mù quáng. Nó có logic chất lượng mắt:

- Nếu cả hai mắt tốt: dùng cả hai.
- Nếu một mắt bị glare nhưng mắt kia rõ: chọn mắt rõ.
- Nếu cả hai mắt không tin cậy: không nâng cảnh báo sai.

Câu trả lời mẫu:

> Em có xử lý chất lượng vùng mắt để giảm báo nhầm khi tài xế đeo kính hoặc ánh sáng phản chiếu. Nếu mắt không tin cậy, classifier nhận trạng thái low confidence thay vì kết luận buồn ngủ từ dữ liệu xấu.

---

## 6. `Version3/ai/drowsiness_classifier.py`: Phân loại buồn ngủ theo thời gian

### 6.1 Vai trò

File này nhận metrics từ FaceAnalyzer và trả kết quả AI:

- `state`
- `confidence`
- `reason`
- `alert_hint`
- `features`
- `durations`
- `thresholds`
- `latency_ms`

### 6.2 Class `AIState`

Các trạng thái:

- `UNKNOWN`
- `NORMAL`
- `BLINK`
- `EYES_CLOSED`
- `DROWSY`
- `YAWNING`
- `HEAD_DOWN`
- `NO_FACE`
- `LOW_CONFIDENCE`

### 6.3 Class `DrowsinessClassifier`

Các điểm chính:

- Dùng `deque` làm cửa sổ mẫu thời gian.
- Theo dõi số frame mắt nhắm.
- Theo dõi số frame miệng mở.
- Theo dõi số frame cúi đầu.
- Theo dõi số frame mất mặt.
- Tính PERCLOS ngắn và dài.
- Dùng threshold từ `ThresholdPolicy`.

### 6.4 Hàm `update`

Luồng:

1. Nhận metrics.
2. Chuẩn hóa sample bằng `_coerce_sample`.
3. Phân loại bằng `_classify_sample`.
4. Trích xuất feature.
5. Trả result đầy đủ.

### 6.5 Hàm `_classify_sample`

Đây là trái tim phân loại:

- Nếu không có mặt đủ lâu: `NO_FACE`.
- Nếu chất lượng thấp: `LOW_CONFIDENCE`.
- Nếu MAR cao đủ lâu: `YAWNING`.
- Nếu EAR thấp lâu: `DROWSY` với alert_hint 1, 2 hoặc 3.
- Nếu pitch cúi lâu: `HEAD_DOWN`.
- Nếu PERCLOS dài cao: `DROWSY`.
- Nếu bình thường: `NORMAL`.

### 6.6 Cách nói trước hội đồng

> Classifier của em là rule-based theo thời gian, không kết luận từ một frame. Nó phân biệt blink, eyes closed và drowsy dựa vào thời lượng EAR thấp; đồng thời kết hợp MAR, pitch và PERCLOS. Result trả ra có reason và confidence nên dễ debug và dễ hiển thị lên dashboard.

---

## 7. `Version3/ai/calibration.py` và `threshold_policy.py`: Ngưỡng thích nghi

### 7.1 `calibration.py`

File này tạo profile theo tài xế:

- `CalibrationSample`: một mẫu calibration.
- `CalibrationProfile`: kết quả calibration.
- `DriverCalibrator`: thu mẫu và build profile.

`DriverCalibrator._build_profile`:

- Kiểm tra đủ sample.
- Tính median EAR, MAR, pitch, face height.
- Reject nếu mặt quá nhỏ.
- Reject nếu EAR mở mắt quá thấp.
- Reject nếu MAR đóng miệng quá cao.
- Tạo threshold EAR/MAR/pitch.

### 7.2 `threshold_policy.py`

File này gom ngưỡng từ profile thành dict cho classifier và alert manager.

Ý nghĩa:

> Các module không tự tính ngưỡng mỗi nơi một kiểu. ThresholdPolicy giúp thống nhất cách lấy ngưỡng từ calibration profile.

### 7.3 Câu trả lời mẫu

> Em dùng calibration để không áp một ngưỡng cố định cho mọi tài xế. Nếu profile hợp lệ, classifier dùng ngưỡng theo median của tài xế; nếu profile không hợp lệ, hệ thống dùng fallback an toàn.

---

## 8. `Version3/ai/session_controller.py`: Quản lý AI theo từng phiên lái

### 8.1 Vai trò

Session controller liên kết classifier và calibrator theo vòng đời session:

- Reset khi bắt đầu session.
- Thu calibration sample.
- Áp profile khi đủ điều kiện.
- Cập nhật classifier bằng metrics mới.

### 8.2 Vì sao cần tách file này?

Nếu để calibration logic rải trong `main.py`, file main sẽ quá lớn và khó test. `AiSessionController` giúp tách phần “AI theo phiên lái” khỏi phần điều phối phần cứng.

### 8.3 Câu trả lời mẫu

> `AiSessionController` giúp em quản lý calibration và classifier theo từng session. Khi tài xế mới bắt đầu lái, trạng thái AI được reset để dữ liệu tài xế trước không ảnh hưởng tài xế sau.

---

## 9. `Version3/alerts/alert_manager.py`: Cảnh báo 3 mức

### 9.1 Vai trò

AlertManager nhận metrics và `ai_result`, rồi quyết định mức cảnh báo:

- `NONE`
- `LEVEL_1` / WARNING
- `LEVEL_2` / DANGER
- `LEVEL_3` / CRITICAL

### 9.2 Class `AlertEvent`

AlertEvent chứa dữ liệu cần gửi ra ngoài:

- level.
- ear/mar/pitch/perclos.
- trạng thái AI.
- confidence.
- reason.
- timestamp.

### 9.3 Hàm `update`

Logic chính:

- Nếu classifier đã có `alert_hint`, ưu tiên dùng hint.
- Nếu không, tự xét EAR low duration, yawn count, pitch, PERCLOS.
- Áp cooldown.
- Nếu đổi level, kích hoạt output và gọi callback.

### 9.4 Hàm `_activate_outputs`

Mỗi level kích hoạt phần cứng khác nhau:

- Level 1: cảnh báo nhẹ.
- Level 2: cảnh báo mạnh hơn.
- Level 3: full alarm.

Nó cũng log nếu thiếu buzzer/LED/speaker, giúp demo trên máy không có phần cứng vẫn không crash.

### 9.5 Câu trả lời mẫu

> AlertManager là lớp quyết định cảnh báo cuối cùng. Nó tách khỏi classifier để AI chỉ nói trạng thái và hint, còn AlertManager chịu trách nhiệm cooldown, escalation và kích hoạt phần cứng như buzzer, LED, speaker.

---

## 10. `Version3/network/ws_client.py`: WebSocket client và reconnect

### 10.1 Vai trò

File này quản lý kết nối từ Jetson lên WebQuanLi:

- Mở WebSocket đến `WS_SERVER_URL`.
- Auto reconnect khi mất kết nối.
- Gửi hardware snapshot khi reconnect.
- Nhận command từ WebQuanLi.
- Flush local queue khi online.

### 10.2 Hàm `send`

`send(msg_type, data)` không gửi trực tiếp nếu có LocalQueue. Nó push vào queue.

Ý nghĩa:

> Mọi event đi qua một đường thống nhất, có thể gửi lại khi mạng có lại.

### 10.3 `_ws_loop`

Vòng lặp giữ kết nối:

- Tạo `WebSocketApp`.
- `run_forever` với ping.
- Nếu disconnect, sleep theo reconnect delay.
- Delay tăng dần đến max.

### 10.4 `_flush_loop`

Khi connected:

- Kiểm tra queue pending.
- Lấy batch.
- Gửi từng payload.
- Mark sent.
- Cleanup.

### 10.5 Câu trả lời mẫu

> WSClient của em có cơ chế offline-first. Khi mất mạng, event không bị gửi lỗi rồi mất, mà được LocalQueue lưu lại. Khi WebSocket mở lại, flush loop gửi batch lên server theo thứ tự ưu tiên.

---

## 11. `Version3/storage/local_queue.py`: Queue SQLite local

### 11.1 Vai trò

LocalQueue là hàng đợi bền vững trên Jetson.

Nó lưu:

- `msg_type`
- `priority`
- `payload`
- `created_at`
- `sent`

### 11.2 Priority

Thứ tự ưu tiên:

- session_start.
- session_end.
- alert.
- face_mismatch.
- ota_status.
- gps.
- hardware.
- driver/verify_snapshot.

Nói với hội đồng:

> Dữ liệu nghiệp vụ quan trọng được gửi trước dữ liệu trạng thái tần suất cao.

### 11.3 Coalescing

Các loại như `hardware`, `gps`, `verify_snapshot` có thể thay bản cũ bằng bản mới nếu chưa gửi.

Lý do:

> GPS cũ sau 30 phút không còn giá trị bằng GPS mới nhất, nên không cần giữ hàng nghìn dòng GPS làm đầy queue.

### 11.4 Câu trả lời mẫu

> LocalQueue vừa chống mất dữ liệu quan trọng, vừa chống phình dữ liệu bằng priority và coalescing. Alert/session được ưu tiên, còn GPS/hardware có thể chỉ giữ trạng thái mới nhất.

---

## 12. `Version3/storage/driver_registry.py`: Cache tài xế và ảnh mặt local

### 12.1 Vai trò

DriverRegistry quản lý dữ liệu tài xế local trên Jetson:

- Manifest tài xế.
- Thư mục ảnh mặt theo RFID.
- File reference.jpg.
- Sync từ WebQuanLi.
- Xóa stale entries không còn trong manifest.

### 12.2 Các hàm quan trọng

- `has_enrollment`: kiểm tra RFID có ảnh tham chiếu không.
- `upsert_local_driver`: thêm/cập nhật tài xế local.
- `sync_from_manifest_url`: tải manifest từ WebQuanLi.
- `sync_from_manifest`: download ảnh mặt và ghi manifest local.
- `_remove_stale_entries`: xóa tài xế không còn hợp lệ.

### 12.3 Metadata nguồn ảnh

Registry lưu:

- `reference_source`
- `reference_role`

Ý nghĩa:

> Ảnh từ Jetson IR nên là nguồn primary cho xác thực thực tế; ảnh sync từ WebQuanLi có thể là fallback nếu chưa có ảnh IR.

### 12.4 Câu trả lời mẫu

> WebQuanLi là nơi quản lý tài xế, nhưng Jetson cần cache local để xác thực nhanh và chịu được offline. DriverRegistry đồng bộ manifest và ảnh mặt về thiết bị, đồng thời lưu metadata nguồn ảnh để phân biệt ảnh primary từ Jetson IR và ảnh fallback từ web.

---

## 13. `Version3/sensors/*`: RFID, GPS, hardware monitor

### 13.1 `sensors/rfid_reader.py`

Vai trò:

- Đọc RFID từ thiết bị input HID.
- Hỗ trợ keyboard wedge.
- Decode key event thành UID.
- Gọi callback khi có thẻ.

Câu trả lời:

> RFIDReader không quyết định nghiệp vụ. Nó chỉ đọc UID và gọi callback `_on_rfid_scan`; nghiệp vụ xác thực nằm ở `main.py`.

### 13.2 `sensors/gps_reader.py`

Vai trò:

- Mở serial GPS.
- Parse NMEA sentence.
- Trả `GPSData` gồm lat/lng/speed/heading/fix.
- Phân loại lỗi serial.

Câu trả lời:

> GPS reader tách UART hoạt động và GPS fix hợp lệ, giúp dashboard biết module GPS còn sống nhưng chưa có tọa độ hay thật sự lỗi.

### 13.3 `sensors/hardware_monitor.py`

Vai trò:

- Gom trạng thái camera, RFID, GPS, Bluetooth, speaker, websocket, queue.
- Tạo snapshot gửi lên WebQuanLi.

Câu trả lời:

> Hardware monitor là health report của thiết bị, giúp trung tâm không chỉ thấy alert mà còn biết cảm biến nào đang lỗi.

---

## 14. `WebQuanLi/app/main.py`: Khởi động FastAPI

### 14.1 Vai trò

File này tạo FastAPI app:

- Setup logging.
- Khai báo lifespan.
- Init database.
- Purge alert cũ theo retention.
- Mount static files.
- Include router.

### 14.2 `lifespan`

Khi app start:

- `init_db()`.
- `purge_old_alerts(db)`.

Khi shutdown:

- log shutdown.

Câu trả lời mẫu:

> `main.py` của WebQuanLi là điểm khởi động server. Nó đảm bảo database và thư mục static sẵn sàng trước khi nhận request, đồng thời include toàn bộ router API, page, auth, SSE và WebSocket.

---

## 15. `WebQuanLi/app/database.py`: Kết nối database async

### 15.1 Vai trò

File này cấu hình:

- `create_async_engine`
- `async_sessionmaker`
- `Base`
- `get_db`
- `init_db`

### 15.2 `get_db`

Đây là dependency FastAPI cấp session database cho API.

Ý nghĩa:

> Mỗi request có session riêng và được close sau khi xử lý.

### 15.3 `init_db`

Làm các việc:

- Tạo thư mục data/upload.
- Tạo bảng từ models.
- Seed admin user nếu chưa có.
- Seed xe demo nếu chưa có admin.

Câu trả lời:

> Khi chạy lần đầu, WebQuanLi tự tạo schema và tài khoản admin mặc định theo cấu hình để demo không cần migration phức tạp.

---

## 16. `WebQuanLi/app/models.py`: Mô hình dữ liệu

### 16.1 Các bảng chính

`User`:

- username.
- hashed_password.
- role.

`Vehicle`:

- biển số.
- tên xe.
- device_id liên kết Jetson.
- số điện thoại quản lý.

`Driver`:

- tên, tuổi, giới tính, số điện thoại.
- RFID.
- ảnh mặt.
- vehicle_id.

`HardwareStatus`:

- trạng thái power/cellular/GPS/camera/RFID/speaker.
- timestamp.

`DriverSession`:

- vehicle_id.
- driver_id.
- checkin_at.
- checkout_at.

`SystemAlert`:

- vehicle_id.
- driver_id.
- session_id.
- alert_type.
- alert_level.
- EAR/MAR/pitch.
- GPS.
- message.
- timestamp.

`OtaAuditLog`:

- vehicle_id.
- username.
- filename.
- checksum.
- status.
- message.

### 16.2 Quan hệ

Một Vehicle có:

- nhiều Driver.
- nhiều HardwareStatus.
- nhiều DriverSession.
- nhiều SystemAlert.

Một Driver có:

- nhiều DriverSession.

Một DriverSession có:

- nhiều SystemAlert.

### 16.3 Câu trả lời mẫu

> Model dữ liệu bám theo nghiệp vụ: xe, tài xế, phiên lái và cảnh báo. Alert có thể gắn với session và driver hiện tại để khi xem lịch sử biết cảnh báo xảy ra trên xe nào, tài xế nào, trong phiên lái nào.

---

## 17. `WebQuanLi/app/schemas.py`: Hợp đồng dữ liệu

### 17.1 Vai trò

Schemas là lớp validate dữ liệu vào/ra:

- Input tạo xe/tài xế.
- Payload hardware/GPS/alert từ Jetson.
- Payload verify/session.
- Command gửi xuống Jetson.

### 17.2 Validation dữ liệu quản trị

Các regex:

- Biển số.
- Device ID.
- RFID.
- Số điện thoại.
- Gender.

Ý nghĩa:

> Không cho dữ liệu bẩn vào database ngay từ API boundary.

### 17.3 Schema payload Jetson

Các class quan trọng:

- `HardwareData`
- `GPSData`
- `AlertData`
- `FaceMismatchData`
- `SessionStartData`
- `SessionEndData`
- `DriverData`
- `VerifyErrorData`
- `VerifySnapshotData`
- `OTAStatusData`
- `WsCommandOut`

### 17.4 Backward compatibility

`HardwareData` có cả field mới như `camera_ok`, `rfid_reader_ok`, `gps_uart_ok`, và field legacy như `camera`, `rfid`, `gps`.

Ý nghĩa:

> WebQuanLi có thể nhận payload từ phiên bản Jetson cũ và mới.

### 17.5 Câu trả lời mẫu

> `schemas.py` là hợp đồng giao tiếp giữa Jetson, WebQuanLi và frontend. Nếu Jetson gửi sai level alert hoặc thiếu field bắt buộc, Pydantic sẽ báo validation error, giúp server không ghi dữ liệu sai vào database.

---

## 18. `WebQuanLi/app/auth/*`: Đăng nhập và phân quyền

### 18.1 `auth/utils.py`

Chứa:

- `hash_password`
- `verify_password`
- `create_access_token`

Điểm cần nói:

> Mật khẩu được hash bằng bcrypt, token tạo bằng JWT có hạn.

### 18.2 `auth/router.py`

Chứa route:

- `GET /login`
- `POST /login`
- `GET /logout`

Khi login đúng:

- Tạo JWT.
- Set cookie `access_token`.
- Cookie có `httponly`, `samesite`, `secure` nếu HTTPS.

### 18.3 `auth/dependencies.py`

Chứa:

- `get_current_user`: đọc token từ cookie, decode JWT, lấy user.
- `check_admin`: chỉ cho role admin.

### 18.4 Câu trả lời mẫu

> Em tách auth thành utils, router và dependencies. Router xử lý form login/logout, utils xử lý hash và token, dependencies được dùng ở các API để bảo vệ route. Những thao tác nhạy cảm như tạo xe, upload ảnh, test cảnh báo hoặc bật/tắt monitoring yêu cầu quyền admin. OTA hiện bị khóa trong bản demo, nếu bật lại cũng phải đặt sau `check_admin` và kiểm tra gói cập nhật chặt chẽ.

---

## 19. `WebQuanLi/app/ws/jetson_handler.py`: WebSocket server nhận Jetson

### 19.1 Vai trò

Đây là file xương sống realtime phía WebQuanLi.

Nó:

- Nhận WebSocket từ Jetson tại `/ws/jetson/{device_id}`.
- Quản lý thiết bị online bằng `ConnectionManager`.
- Cache vehicle_id, manager_phone, plate_number.
- Validate message theo schema.
- Ghi database với message quan trọng.
- Publish event sang EventBus.
- Gửi SMS khi face mismatch.
- Cho module API gửi command xuống Jetson qua `manager.send_command`.

### 19.2 `ConnectionManager`

Quản lý:

- `active`: device_id -> WebSocket.
- `last_seen`: device_id -> datetime.

Các hàm:

- `connect`
- `disconnect`
- `send_command`

### 19.3 Cache vehicle info

Khi Jetson connect, handler query `Vehicle` một lần theo `device_id`, lấy:

- `vid`
- `manager_phone`
- `plate_number`

Lý do:

> Tránh query database lặp lại cho các message tần suất cao như GPS.

### 19.4 Nhóm message chỉ realtime

Các message:

- `driver`
- `gps`
- `ota_status`
- `verify_error`
- `verify_snapshot`

Handler validate rồi publish qua EventBus, không ghi DB.

Câu trả lời:

> Những message tần suất cao hoặc chỉ phục vụ UI tức thời được publish realtime để giảm I/O database.

### 19.5 Nhóm message cần database

Các message:

- `hardware`: lưu `HardwareStatus`.
- `session_start`: tạo hoặc reuse session.
- `session_end`: đóng session active.
- `alert`: tạo `SystemAlert`.
- `face_mismatch`: tạo alert critical và gửi SMS.

### 19.6 Nhánh `alert`

Luồng:

1. Validate `AlertData`.
2. Map level text sang enum.
3. Gọi `create_drowsiness_alert`.
4. Publish alert sang EventBus.

### 19.7 Nhánh `face_mismatch`

Luồng:

1. Validate `FaceMismatchData`.
2. Tạo `SystemAlert` type `FACE_MISMATCH`.
3. Publish realtime.
4. Nếu có manager phone, gửi SMS async.

### 19.8 Câu trả lời mẫu

> `jetson_handler.py` là nơi WebQuanLi nhận dữ liệu thiết bị. File này phân loại message: dữ liệu realtime tần suất cao thì validate rồi publish EventBus, dữ liệu cần truy vết như session, alert, face mismatch thì ghi database. Nhờ cache vehicle_id lúc connect, hệ thống giảm query DB trong vòng lặp WebSocket.

---

## 20. `WebQuanLi/app/core/event_bus.py`: Cầu nối WebSocket sang SSE

### 20.1 Vai trò

EventBus là in-memory pub/sub:

- WebSocket handler publish.
- SSE endpoint subscribe.
- Dashboard nhận event.

### 20.2 `subscribe`

Tạo queue maxsize 50 cho từng subscriber. Nếu có cached state, gửi state mới nhất cho subscriber mới.

### 20.3 `publish`

Lưu latest state vào `_vehicle_state`, rồi đưa payload vào queue của các subscriber.

Nếu queue full:

- Bỏ bớt event cũ.
- Cố đưa event mới vào.

### 20.4 Câu trả lời mẫu

> EventBus giúp tách luồng nhận dữ liệu từ Jetson và luồng phát dữ liệu xuống browser. Mỗi browser có queue riêng nên browser chậm không làm nghẽn WebSocket handler.

---

## 21. `WebQuanLi/app/api/sse.py`: Stream realtime xuống browser

### 21.1 Vai trò

Endpoint:

`GET /sse/vehicle/{device_id}`

Nó:

- Kiểm tra user đăng nhập.
- Subscribe vào EventBus channel `vehicle:{device_id}`.
- Yield theo format SSE.
- Gửi keepalive nếu 30 giây không có event.
- Unsubscribe khi browser disconnect.

### 21.2 SSE format

Mỗi event gửi xuống browser có dạng:

```text
event: alert
data: {"level": "DANGER"}
```

### 21.3 Câu trả lời mẫu

> SSE endpoint giữ kết nối HTTP mở để server đẩy event xuống browser. Khi Jetson gửi alert, WebSocket handler publish vào EventBus, SSE nhận event từ queue và browser cập nhật UI ngay.

---

## 22. `WebQuanLi/app/services/jetson_session_service.py`: Nghiệp vụ session và alert

### 22.1 Vai trò

File này tách nghiệp vụ session/alert khỏi WebSocket handler.

Các hàm:

- `resolve_driver_by_rfid`
- `get_active_session`
- `start_or_reuse_session`
- `close_active_session`
- `create_drowsiness_alert`

### 22.2 `start_or_reuse_session`

Logic:

- Nếu đang có session cùng driver: reuse.
- Nếu có session driver khác: đóng session cũ.
- Tạo session mới.

Ý nghĩa:

> Một xe tại một thời điểm chỉ có một active session.

### 22.3 `create_drowsiness_alert`

Logic:

- Tìm active session hiện tại.
- Nếu có timestamp, kiểm tra duplicate.
- Tạo message từ AI state, confidence, reason, perclos.
- Lưu SystemAlert gắn với vehicle, driver, session.

### 22.4 Câu trả lời mẫu

> Em tách logic session ra service để WebSocket handler không bị quá nhiều nghiệp vụ. Service đảm bảo alert được gắn với active session, nhờ vậy khi xem lịch sử biết cảnh báo thuộc phiên lái nào.

---

## 23. `WebQuanLi/app/api/vehicles.py`: Quản lý xe, tài xế, ảnh mặt, driver registry

### 23.1 Vai trò

File này chứa API:

- List/create/update vehicle.
- List/create/update driver.
- Upload face image.
- Lấy driver registry manifest cho Jetson.
- Gửi lệnh sync registry xuống Jetson.

### 23.2 `_ensure_unique_vehicle`

Kiểm tra:

- Biển số không trùng.
- Device ID không trùng.

### 23.3 `_ensure_unique_driver_rfid`

RFID không được trùng, vì RFID là định danh tài xế.

### 23.4 `_build_driver_registry_manifest`

Tạo manifest gồm:

- device_id.
- generated_at.
- danh sách driver active có face_image_path.
- URL ảnh mặt tuyệt đối.

Jetson dùng manifest này để sync local registry.

### 23.5 `_dispatch_driver_registry_sync`

Nếu Jetson online:

- Tạo manifest_url.
- Gửi command `sync_driver_registry`.

Nếu offline:

- Trả false.

### 23.6 `upload_face_image`

Kiểm tra:

- Driver tồn tại.
- Content-type là jpg/png/webp.
- File không vượt 3MB.
- Lưu vào static/faces.
- Cập nhật `driver.face_image_path`.
- Nếu driver có vehicle, gửi sync command xuống Jetson.

### 23.7 Câu trả lời mẫu

> `vehicles.py` không chỉ CRUD xe và tài xế. Nó còn là cầu nối để WebQuanLi phát driver registry xuống Jetson. Khi admin upload ảnh mặt, WebQuanLi cập nhật database và nếu Jetson online thì gửi lệnh sync để thiết bị lấy manifest mới.

---

## 24. `WebQuanLi/app/api/control.py`: Điều khiển Jetson, monitoring và test alert

### 24.1 Vai trò

File này xử lý command từ web xuống thiết bị:

- Connect/disconnect monitoring.
- Test alert.
- Tạo test alert log.
- Route upload OTA vẫn tồn tại nhưng hiện trả HTTP 410 để vô hiệu hóa cập nhật từ dashboard.

### 24.2 `_sanitize_update_filename`

Chặn:

- Filename rỗng.
- `/`, `\`, `..`.
- Ký tự ngoài whitelist.
- Đuôi file không phải `.py` hoặc `.zip`.

### 24.3 `_validate_update_package`

Nếu file `.zip`, kiểm tra phải có `manifest.json`.

### 24.4 `upload_ota_code`

Theo trạng thái hiện tại, hàm này không còn chạy luồng upload/cập nhật thật. Nó trả:

```python
raise HTTPException(status_code=410, detail=OTA_DISABLED_MESSAGE)
```

Ý nghĩa khi bảo vệ:

> Đây là quyết định vận hành cho demo. Hệ thống vẫn có kênh command hai chiều qua WebSocket, nhưng upload OTA từ dashboard đã được khóa để tránh rủi ro cập nhật nhầm. Khi cần cập nhật Jetson, em dùng SSH/NoMachine.

### 24.5 `test_alert`

Admin chọn level và state. Nếu Jetson online, server gửi command:

- `action`: `test_alert`
- `level`: 1/2/3
- `state`: on/off

### 24.6 Câu trả lời mẫu

> `control.py` là kênh điều khiển ngược từ Monitoring Hub xuống Jetson. Trong bản hiện tại, phần dùng trực tiếp cho demo là connect/disconnect monitoring và test loa/cảnh báo. Route OTA được giữ như điểm mở rộng nhưng đang vô hiệu hóa bằng HTTP 410 để tránh rủi ro cập nhật trong lúc demo.

---

## 25. `WebQuanLi/app/services/history_service.py` và `time_service.py`

### 25.1 `time_service.py`

Vai trò:

- Chuyển UTC sang giờ Việt Nam.
- Format datetime.
- Chuyển ngày local thành khoảng UTC để query.

Câu trả lời:

> Database lưu UTC để nhất quán, còn UI hiển thị và lọc theo giờ Việt Nam để đúng trải nghiệm người dùng.

### 25.2 `history_service.py`

Vai trò:

- Lọc alert history.
- Xóa alert history theo filter.
- Purge old alerts theo retention.
- Lọc session history.
- Format item cho template.

Điểm đáng nói:

- Query có filter date/vehicle/type/search.
- Có pagination/default limit.
- Có retention cutoff.
- Có join Vehicle/Driver để hiển thị thông tin đầy đủ.

### 25.3 Câu trả lời mẫu

> Phần lịch sử được tách thành service để route không chứa query phức tạp. Service xử lý timezone, filter, join và format dữ liệu trước khi đưa ra template/API.

---

## 26. `WebQuanLi/app/api/pages.py`, `dashboard.py`, `alerts.py`, `sessions.py`

### 26.1 `pages.py`

Render các trang:

- History.
- Fleet.
- Statistics.

Nó gọi service để lấy dữ liệu rồi đưa vào template.

### 26.2 `dashboard.py`

Render dashboard chính:

- Lấy vehicle.
- Lấy trạng thái phần cứng gần nhất.
- Lấy cache realtime từ EventBus.
- Build context cho template.

### 26.3 `alerts.py`

API list alerts theo vehicle.

### 26.4 `sessions.py`

API list sessions và active session.

Câu trả lời:

> Các route page/API được tách theo chức năng để dễ bảo trì: dashboard cho màn hình realtime, pages cho lịch sử/fleet/statistics, alerts và sessions cho dữ liệu nghiệp vụ.

---

## 27. Templates và frontend

### 27.1 `templates/base.html`

Layout chung:

- Navbar/sidebar.
- CSS/JS chung.
- Block content.

### 27.2 `templates/dashboard.html`

Màn hình chính theo xe:

- Kết nối SSE.
- Khu vực trạng thái tài xế.
- Khu vực alert log.
- Khu vực hardware.
- Bản đồ.
- Nút điều khiển.

### 27.3 `templates/partials/*`

Partial HTML dùng cho cập nhật từng phần:

- `alert_log.html`
- `driver_info.html`
- `hardware_status.html`
- `map_data.html`
- `admin_controls.html`

Ý nghĩa:

> HTMX/SSE có thể thay một phần UI thay vì render lại toàn trang.

### 27.4 `static/js/*`

- `map.js`: xử lý bản đồ.
- `charts.js`: biểu đồ thống kê.
- `session_timer.js`: thời gian session.

### 27.5 Câu trả lời mẫu

> Frontend của WebQuanLi là server-rendered với Jinja2, sau đó cập nhật realtime bằng HTMX/SSE và JavaScript nhỏ cho bản đồ/biểu đồ. Cách này đủ mạnh cho dashboard quản trị nhưng không làm phức tạp thành một SPA riêng.

---

## 28. Các luồng code quan trọng cần thuộc

### 28.1 Luồng khởi động Jetson

1. Chạy `Version3/main.py`.
2. Tạo `DrowsiGuard`.
3. Khởi tạo state machine, camera, AI, alert, RFID, GPS, queue, WebSocket.
4. `run` start các module.
5. Chuyển `BOOTING -> IDLE`.
6. Chờ RFID hoặc monitoring.

Câu nói:

> Jetson khởi động theo mô hình orchestrator, mỗi module có trách nhiệm riêng, còn main điều phối vòng đời.

### 28.2 Luồng xác thực tài xế

1. `RFIDReader` đọc UID.
2. Callback `_on_rfid_scan`.
3. State sang `VERIFYING_DRIVER`.
4. `_verify_driver`.
5. `FaceVerifier` so khớp mặt.
6. Match: `_start_verified_session`.
7. Queue `session_start` và `verify_snapshot`.
8. WebQuanLi nhận, tạo session, dashboard cập nhật.

### 28.3 Luồng cảnh báo buồn ngủ

1. Camera tạo frame.
2. `FaceAnalyzer` tạo metrics.
3. `DrowsinessClassifier.update` phân loại.
4. `AlertManager.update` quyết định level.
5. `_activate_outputs` phát loa/buzzer/LED.
6. Callback `_on_alert`.
7. `WSClient.send("alert", payload)`.
8. `LocalQueue.push`.
9. Khi online, `WSClient._flush_loop` gửi payload.
10. WebQuanLi `jetson_handler` validate `AlertData`.
11. `create_drowsiness_alert` lưu DB.
12. `event_bus.publish`.
13. `sse.py` stream xuống browser.
14. Dashboard cập nhật alert log.

### 28.4 Luồng mất mạng và reconnect

1. WebSocket disconnect.
2. WSClient set connected false.
3. Event vẫn push vào LocalQueue.
4. `_ws_loop` reconnect với delay.
5. Khi open lại, gửi hardware snapshot.
6. `_flush_loop` pop batch và gửi event cũ.
7. WebQuanLi ghi những dữ liệu cần persistence.

### 28.5 Luồng đồng bộ tài xế

1. Admin tạo/cập nhật driver trên WebQuanLi.
2. Admin upload ảnh mặt.
3. WebQuanLi lưu `face_image_path`.
4. Nếu driver gắn xe, server gửi command `sync_driver_registry`.
5. Jetson nhận command ở `_on_backend_command`.
6. `DriverRegistry.sync_from_manifest_url`.
7. Jetson tải manifest và ảnh mặt về local.

### 28.6 Luồng bảo trì/cập nhật Jetson hiện tại

Không trình bày luồng OTA như chức năng demo chính. Cách nói đúng với code hiện tại:

1. Dashboard vẫn có kênh command xuống Jetson cho monitoring và test alert.
2. Route upload OTA trong `control.py` đã bị khóa bằng HTTP 410.
3. Khi cần cập nhật Jetson thật, dùng SSH/NoMachine để giảm rủi ro trong demo.
4. Nếu sau này bật lại OTA, cần khôi phục luồng validate package, checksum, gửi command `update_software`, Jetson tải gói và báo `ota_status`.

---

## 29. Các file test nên biết để chứng minh

### 29.1 Test phía Version3

`Version3/tests/test_drowsiness_classifier.py`

- Chứng minh classifier phân biệt normal, drowsy, yawning, no face, blink.

`Version3/tests/test_calibration.py`

- Chứng minh calibration profile hợp lệ hoặc fallback khi sample xấu.

`Version3/tests/test_threshold_policy.py`

- Chứng minh threshold lấy từ profile hoặc fallback.

`Version3/tests/test_ws_queue_hardening.py`

- Chứng minh queue và alert level mapping ổn.

`Version3/tests/test_offline_reconnect.py`

- Chứng minh reconnect và replay event.

`Version3/tests/test_webquanli_contract.py`

- Chứng minh payload Version3 khớp schema WebQuanLi.

`Version3/tests/test_verify_flow.py`

- Chứng minh luồng verify driver.

### 29.2 Test phía WebQuanLi

`WebQuanLi/tests/test_auth_cookie_security.py`

- Chứng minh cookie auth có cấu hình bảo mật.

`WebQuanLi/tests/test_api_validation_contract.py`

- Chứng minh validate input API.

`WebQuanLi/tests/test_driver_registry_sync.py`

- Chứng minh manifest/sync driver registry.

`WebQuanLi/tests/test_websocket_contract_fixtures.py`

- Chứng minh WebSocket schema.

`WebQuanLi/tests/test_history_service.py`

- Chứng minh history query/format.

`WebQuanLi/tests/test_time_service.py`

- Chứng minh timezone.

`WebQuanLi/tests/test_history_retention_startup.py`

- Chứng minh purge old alerts khi startup.

### 29.3 Câu trả lời mẫu

> Em có test ở cả hai phía. Phía Jetson kiểm tra AI, calibration, queue, verify flow và contract payload. Phía WebQuanLi kiểm tra auth, API validation, WebSocket schema, driver registry, lịch sử và timezone. Nhóm test này giúp chứng minh hệ thống không chỉ chạy demo mà còn có kiểm chứng hành vi.

---

## 30. Những điểm “ăn điểm” khi bảo vệ code

### 30.1 Tách ranh giới rõ

Jetson:

- AI.
- Phần cứng.
- Local resilience.
- WebSocket client.

WebQuanLi:

- Quản trị.
- Persistence.
- Dashboard.
- WebSocket server.
- SSE.

### 30.2 Không ghi database bừa bãi

Trong `jetson_handler.py`, GPS/driver/verify/ota realtime không ghi DB, chỉ publish EventBus. Alert/session/hardware/face mismatch mới ghi.

### 30.3 Có offline queue

Mất mạng không làm mất alert/session quan trọng.

### 30.4 Có contract schema

Jetson và WebQuanLi giao tiếp bằng JSON có schema rõ.

### 30.5 Có calibration

Không dùng threshold cứng cho mọi tài xế.

### 30.6 Có security baseline

- bcrypt.
- JWT.
- HttpOnly cookie.
- admin-only API.
- validate upload.
- khóa upload OTA trong bản demo; nếu bật lại thì phải có checksum/validate package/rollback.

### 30.7 Có test

Test nằm ở cả `Version3/tests` và `WebQuanLi/tests`.

---

## 31. Kịch bản hội đồng yêu cầu mở code

### 31.1 “Em chỉ cho thầy/cô phần realtime”

Mở:

- `WebQuanLi/app/ws/jetson_handler.py`
- `WebQuanLi/app/core/event_bus.py`
- `WebQuanLi/app/api/sse.py`
- `WebQuanLi/templates/dashboard.html`

Nói:

> Jetson gửi WebSocket vào handler. Handler validate và publish vào EventBus. Browser subscribe SSE endpoint, nhận event và dashboard update từng phần.

### 31.2 “Em chỉ cho phần AI”

Mở:

- `Version3/camera/face_analyzer.py`
- `Version3/ai/drowsiness_classifier.py`
- `Version3/ai/calibration.py`
- `Version3/alerts/alert_manager.py`

Nói:

> FaceAnalyzer lấy metrics từ frame, classifier phân loại theo chuỗi thời gian, calibration tạo ngưỡng theo tài xế, AlertManager đổi trạng thái thành cảnh báo phần cứng.

### 31.3 “Em chỉ cho phần mất mạng”

Mở:

- `Version3/network/ws_client.py`
- `Version3/storage/local_queue.py`
- `WebQuanLi/app/ws/jetson_handler.py`

Nói:

> WSClient luôn push message vào LocalQueue. Khi offline, queue giữ dữ liệu. Khi reconnect, flush loop gửi batch lên server. Server nhận và xử lý như message bình thường.

### 31.4 “Em chỉ cho phần bảo mật”

Mở:

- `WebQuanLi/app/auth/utils.py`
- `WebQuanLi/app/auth/router.py`
- `WebQuanLi/app/auth/dependencies.py`
- `WebQuanLi/app/api/control.py`
- `WebQuanLi/app/schemas.py`

Nói:

> Password dùng bcrypt, login tạo JWT cookie HttpOnly, route nhạy cảm dùng check_admin, input API có Pydantic validation. Riêng OTA trong bản demo hiện đã khóa upload; nếu bật lại phải kiểm tra filename/package/checksum và có cơ chế rollback.

### 31.5 “Em chỉ cho database”

Mở:

- `WebQuanLi/app/models.py`
- `WebQuanLi/app/database.py`
- `WebQuanLi/app/services/jetson_session_service.py`
- `WebQuanLi/app/services/history_service.py`

Nói:

> Models biểu diễn xe, tài xế, session, alert. Database async session cấp qua dependency. Service session đảm bảo alert gắn với active session. History service xử lý filter, timezone và retention.

---

## 32. Bản ghi nhớ theo file

| File | Một câu phải nhớ |
|---|---|
| `Version3/main.py` | Orchestrator điều phối toàn bộ runtime Jetson |
| `Version3/state_machine.py` | Ràng buộc trạng thái hợp lệ của thiết bị |
| `Version3/camera/face_analyzer.py` | Biến frame camera thành metrics EAR/MAR/pitch/chất lượng |
| `Version3/ai/drowsiness_classifier.py` | Phân loại buồn ngủ theo chuỗi thời gian |
| `Version3/ai/calibration.py` | Tạo ngưỡng theo tài xế từ sample ban đầu |
| `Version3/alerts/alert_manager.py` | Quyết định level cảnh báo và kích hoạt phần cứng |
| `Version3/network/ws_client.py` | Kết nối WebSocket, reconnect, flush queue |
| `Version3/storage/local_queue.py` | Lưu event offline bằng SQLite local |
| `Version3/storage/driver_registry.py` | Cache tài xế và ảnh mặt trên Jetson |
| `WebQuanLi/app/main.py` | Khởi động FastAPI, init DB, include router |
| `WebQuanLi/app/models.py` | Định nghĩa bảng dữ liệu nghiệp vụ |
| `WebQuanLi/app/schemas.py` | Hợp đồng dữ liệu và validation |
| `WebQuanLi/app/ws/jetson_handler.py` | Nhận WebSocket từ Jetson, ghi DB, publish EventBus |
| `WebQuanLi/app/core/event_bus.py` | Pub/sub trong RAM nối WebSocket với SSE |
| `WebQuanLi/app/api/sse.py` | Stream event realtime xuống browser |
| `WebQuanLi/app/api/vehicles.py` | CRUD xe/tài xế và sync driver registry |
| `WebQuanLi/app/api/control.py` | Gửi command monitoring/test alert; OTA hiện bị vô hiệu hóa trong demo |
| `WebQuanLi/app/auth/*` | Login, JWT cookie, bcrypt, admin check |
| `WebQuanLi/app/services/history_service.py` | Lọc, xóa, purge và format lịch sử |

---

## 33. Bài luyện cuối C2

Bạn hãy tự nói lại 5 luồng sau, mỗi luồng dưới 2 phút:

1. Từ RFID đến session_start.
2. Từ camera đến alert trên dashboard.
3. Từ mất mạng đến flush lại queue.
4. Từ admin upload ảnh mặt đến Jetson sync registry.
5. Từ admin bấm test loa/monitoring đến Jetson nhận command; nếu bị hỏi OTA thì giải thích vì sao bản demo đã khóa upload.

Nếu nói được 5 luồng này và mở đúng file, bạn đã đủ nền code để sang hướng B: bộ câu hỏi phản biện và cách trả lời hội đồng.

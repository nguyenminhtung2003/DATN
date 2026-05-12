# Bộ câu hỏi phản biện hội đồng và câu trả lời thuyết trình

Tài liệu này dùng để luyện trả lời bảo vệ đồ án DrowsiGuard. Mục tiêu không phải học thuộc từng chữ, mà là nắm ý chính và nói lại tự nhiên trước hội đồng.

Tên gọi nên dùng khi trình bày:

| Tên trong repo | Tên nên nói trước hội đồng |
|---|---|
| `Version3` | DrowsiGuard Edge Runtime / phần mềm Jetson trên xe |
| `WebQuanLi` | DrowsiGuard Monitoring Hub / Trung tâm giám sát |
| Dashboard | Monitoring Hub / Trung tâm giám sát realtime |

Luồng demo nên kể thống nhất:

1. WebQuanLi/Monitoring Hub chạy trên máy Windows.
2. Jetson chạy DrowsiGuard Edge Runtime bằng shortcut `DrowsiGuard-Full.desktop`.
3. Jetson kết nối WebSocket tới WebQuanLi qua `DROWSIGUARD_WS_URL`, bản demo dùng Tailscale để ổn định hơn IP LAN.
4. Tài xế quét RFID, Jetson xác thực khuôn mặt, sau đó mới bắt đầu session.
5. Camera tạo frame, AI phân tích dấu hiệu buồn ngủ, AlertManager quyết định mức cảnh báo.
6. Jetson cảnh báo tại chỗ và gửi event lên Monitoring Hub.
7. Dashboard nhận realtime qua SSE và cập nhật trạng thái xe, tài xế, GPS, phần cứng, alert log.

---

## 1. Câu hỏi tổng quan dự án

### 1. Đồ án của em giải quyết vấn đề gì?

**Trả lời thuyết trình:**

> Đồ án của em giải quyết bài toán giám sát an toàn tài xế theo thời gian thực. Hệ thống có hai mục tiêu chính: thứ nhất là xác thực đúng tài xế trước khi bắt đầu phiên lái bằng RFID kết hợp khuôn mặt; thứ hai là phát hiện dấu hiệu buồn ngủ như nhắm mắt kéo dài, ngáp, cúi đầu và cảnh báo kịp thời. Phần Jetson xử lý camera, RFID, GPS và cảnh báo tại xe, còn Monitoring Hub quản lý xe, tài xế, lịch sử phiên lái và hiển thị dashboard realtime cho người quản lý.

### 2. Vì sao em chia hệ thống thành Jetson và Monitoring Hub?

**Trả lời thuyết trình:**

> Em chia thành hai phần vì hai nhóm nhiệm vụ khác nhau. Jetson đặt trên xe để xử lý việc cần phản ứng nhanh như camera, AI, RFID, GPS và cảnh báo tại chỗ. Nếu mạng mất thì Jetson vẫn có thể cảnh báo tài xế. Monitoring Hub chạy ở trung tâm để làm phần quản trị: lưu xe, tài xế, session, alert, hiển thị dashboard và nhận dữ liệu realtime. Cách chia này giảm độ trễ, tiết kiệm băng thông vì không cần stream video lên server, và vẫn có dữ liệu tập trung để truy vết.

**Nếu hội đồng yêu cầu mở code:** mở `Version3/main.py`, `WebQuanLi/app/main.py`, `WebQuanLi/app/ws/jetson_handler.py`.

### 3. Điểm mới hoặc điểm nổi bật của đồ án là gì?

**Trả lời thuyết trình:**

> Điểm nổi bật là hệ thống không chỉ phát hiện buồn ngủ bằng camera, mà còn gắn với quy trình vận hành thực tế: tài xế phải quét RFID và xác thực khuôn mặt trước khi session hợp lệ bắt đầu. Dữ liệu từ Jetson gửi lên Monitoring Hub theo realtime qua WebSocket, dashboard nhận SSE để cập nhật ngay. Ngoài ra Jetson có local queue để không mất alert quan trọng khi mất mạng, AI có calibration theo tài xế và có kiểm tra chất lượng vùng mắt để giảm báo sai khi ánh sáng hoặc kính ảnh hưởng.

### 4. Nếu chỉ có camera phát hiện buồn ngủ thì có đủ không?

**Trả lời thuyết trình:**

> Chỉ camera thì mới giải quyết được phần phát hiện trạng thái buồn ngủ, nhưng chưa giải quyết được câu hỏi ai đang lái. Trong hệ thống vận hành xe, cần biết tài xế nào đang điều khiển xe để lưu session và truy vết cảnh báo. Vì vậy em kết hợp RFID để nhận dạng ban đầu và xác thực khuôn mặt để tránh trường hợp mượn thẻ. Sau khi xác thực thành công, cảnh báo buồn ngủ mới được gắn đúng với tài xế và phiên lái.

### 5. Tại sao không xử lý toàn bộ trên server?

**Trả lời thuyết trình:**

> Nếu đưa toàn bộ video lên server để xử lý thì sẽ tốn băng thông, độ trễ cao và phụ thuộc mạng. Bài toán cảnh báo buồn ngủ cần phản ứng nhanh tại xe, nên AI phải chạy gần camera trên Jetson. Server chỉ cần nhận kết quả dạng JSON như trạng thái AI, mức cảnh báo, EAR, MAR, PERCLOS và GPS. Như vậy phần cảnh báo an toàn không bị phụ thuộc hoàn toàn vào đường truyền.

### 6. Nếu hội đồng hỏi "đây là AI hay chỉ là xử lý ảnh?", em trả lời sao?

**Trả lời thuyết trình:**

> Trong bản hiện tại, hệ thống dùng hướng Computer Vision và rule-based temporal classifier, không phải một mô hình deep learning nặng. MediaPipe Face Mesh trích landmark khuôn mặt, sau đó hệ thống tính các đặc trưng như EAR, MAR, pitch và PERCLOS. Phần classifier theo dõi các đặc trưng này theo thời gian để phân biệt blink, eyes closed, drowsy, yawning, head down. Em vẫn gọi đây là AI theo nghĩa hệ thống nhận biết trạng thái tài xế từ dữ liệu camera, nhưng khi trình bày kỹ thuật em nói rõ đây là pipeline CV + rule-based theo thời gian, không nói quá thành CNN hay deep learning nếu code hiện tại không dùng.

---

## 2. Kiến trúc và luồng dữ liệu

### 7. Luồng dữ liệu từ camera lên dashboard đi như thế nào?

**Trả lời thuyết trình:**

> Camera trên Jetson tạo frame. `FaceAnalyzer` trích xuất metrics như EAR, MAR, pitch và chất lượng vùng mắt. `DrowsinessClassifier` phân loại trạng thái theo chuỗi thời gian. `AlertManager` quyết định mức cảnh báo, sau đó `main.py` tạo payload alert và đưa vào `WSClient`. `WSClient` dùng local queue rồi gửi WebSocket lên Monitoring Hub. Phía WebQuanLi, `jetson_handler.py` validate payload, service lưu alert vào database nếu cần, rồi publish event vào `EventBus`. Browser đang mở dashboard subscribe SSE nên nhận event và cập nhật giao diện realtime.

**File cần mở:** `Version3/camera/face_analyzer.py`, `Version3/ai/drowsiness_classifier.py`, `Version3/alerts/alert_manager.py`, `Version3/network/ws_client.py`, `WebQuanLi/app/ws/jetson_handler.py`, `WebQuanLi/app/core/event_bus.py`, `WebQuanLi/app/api/sse.py`.

### 8. Vì sao dùng kiến trúc event-driven?

**Trả lời thuyết trình:**

> Hệ thống có nhiều loại sự kiện phát sinh liên tục: GPS, hardware, driver, alert, session, verify. Nếu mỗi phần gọi trực tiếp lẫn nhau thì code sẽ chặt cứng và khó mở rộng. Event-driven giúp Jetson gửi event lên server, server xử lý theo loại message, rồi publish cho dashboard. Nhờ vậy WebSocket handler không cần biết có bao nhiêu browser đang xem, còn dashboard cũng không cần query liên tục để hỏi server có dữ liệu mới chưa.

### 9. WebSocket khác SSE như thế nào trong đồ án?

**Trả lời thuyết trình:**

> WebSocket là kết nối hai chiều, phù hợp cho Jetson vì thiết bị vừa gửi dữ liệu lên server, vừa nhận command từ server như test alert, sync driver registry hoặc connect monitoring. SSE là luồng một chiều từ server xuống browser, phù hợp cho dashboard vì trình duyệt chủ yếu chỉ cần nhận event realtime. Khi admin bấm nút, browser dùng HTTP POST; server sau đó gửi command xuống Jetson qua WebSocket.

### 10. Vì sao dashboard không dùng WebSocket luôn?

**Trả lời thuyết trình:**

> Dashboard chủ yếu là màn hình quan sát, nhu cầu chính là nhận trạng thái mới từ server. SSE đơn giản hơn WebSocket cho trường hợp server đẩy dữ liệu một chiều xuống browser, dễ debug và đủ cho dashboard realtime. Với các hành động như test loa hoặc bật/tắt monitoring, browser gửi HTTP POST bình thường, còn server dùng WebSocket đã có sẵn để truyền command xuống Jetson.

### 11. EventBus trong WebQuanLi giải quyết vấn đề gì?

**Trả lời thuyết trình:**

> EventBus là cầu nối trong RAM giữa WebSocket handler và SSE endpoint. Jetson gửi dữ liệu vào `jetson_handler.py`, handler publish vào EventBus, sau đó các browser subscribe SSE sẽ nhận event. Nhờ EventBus, một message từ Jetson có thể được phân phối cho nhiều dashboard mà WebSocket handler không cần quản lý từng browser. EventBus cũng có queue riêng cho từng subscriber để một browser chậm không làm nghẽn toàn bộ luồng realtime.

**File cần mở:** `WebQuanLi/app/core/event_bus.py`.

### 12. Dữ liệu nào ghi database, dữ liệu nào chỉ realtime?

**Trả lời thuyết trình:**

> Không phải mọi dữ liệu đều nên ghi database. Những dữ liệu cần truy vết như session start/end, alert buồn ngủ, face mismatch và hardware status thì được lưu. Những dữ liệu tần suất cao hoặc mang tính tức thời như GPS realtime, verify snapshot, driver probe hoặc OTA status thì chủ yếu publish qua EventBus để hiển thị ngay. Cách này tránh làm SQLite phình quá nhanh và giảm I/O không cần thiết.

**File cần mở:** `WebQuanLi/app/ws/jetson_handler.py`.

### 13. Vì sao cần local queue trên Jetson?

**Trả lời thuyết trình:**

> Xe có thể mất mạng khi đi qua vùng sóng yếu hoặc server tạm thời không truy cập được. Nếu Jetson gửi event trực tiếp mà lỗi thì alert/session quan trọng có thể bị mất. Local queue lưu event vào SQLite local trước, sau đó khi WebSocket online thì flush lên server. Các message quan trọng như alert/session có priority cao, còn dữ liệu tần suất cao như GPS/hardware có thể coalesce để chỉ giữ bản mới nhất.

**File cần mở:** `Version3/storage/local_queue.py`, `Version3/network/ws_client.py`.

### 14. Nếu mất mạng 30 phút thì dữ liệu có mất không?

**Trả lời thuyết trình:**

> Với dữ liệu quan trọng như session và alert, Jetson có local queue để lưu lại khi WebSocket offline. Khi kết nối trở lại, WSClient flush batch lên Monitoring Hub. Tuy nhiên với GPS/hardware tần suất cao, hệ thống không cố giữ mọi bản cũ vì GPS quá cũ ít giá trị realtime; thay vào đó có cơ chế coalesce để giảm phình queue. Vì vậy em phân biệt rõ dữ liệu cần truy vết và dữ liệu chỉ cần trạng thái mới nhất.

### 15. Vì sao demo dùng Tailscale?

**Trả lời thuyết trình:**

> Trong demo, IP LAN của máy Windows có thể thay đổi hoặc khác mạng với Jetson. Tailscale tạo một mạng riêng ổn định giữa Windows và Jetson, nên Jetson có thể trỏ `DROWSIGUARD_WS_URL` tới IP Tailscale của máy Windows. Cách này giảm lỗi "mất kết nối" do IP LAN đổi, router chặn hoặc hai thiết bị không cùng subnet. Về bản chất ứng dụng vẫn dùng WebSocket, Tailscale chỉ là lớp mạng giúp đường truyền ổn định hơn khi demo.

**File cần mở:** `Version3/config.py` phần `WS_SERVER_URL`.

---

## 3. AI, xử lý ảnh và cảnh báo buồn ngủ

### 16. EAR là gì và dùng để làm gì?

**Trả lời thuyết trình:**

> EAR là Eye Aspect Ratio, tỉ lệ hình học mô tả độ mở của mắt dựa trên các landmark quanh mắt. Khi mắt mở, EAR thường cao hơn; khi mắt nhắm, EAR giảm. Hệ thống không chỉ nhìn một frame EAR thấp rồi báo động ngay, mà theo dõi EAR theo thời gian để phân biệt chớp mắt bình thường với nhắm mắt kéo dài do buồn ngủ.

### 17. MAR là gì?

**Trả lời thuyết trình:**

> MAR là Mouth Aspect Ratio, tỉ lệ mô tả độ mở của miệng. Nếu MAR cao trong một khoảng thời gian đủ dài, hệ thống có thể xem đó là dấu hiệu ngáp. Ngáp không phải lúc nào cũng nguy hiểm như nhắm mắt kéo dài, nhưng là một tín hiệu phụ quan trọng trong đánh giá mệt mỏi của tài xế.

### 18. PERCLOS là gì?

**Trả lời thuyết trình:**

> PERCLOS là tỉ lệ thời gian mắt ở trạng thái đóng hoặc gần đóng trong một cửa sổ thời gian. Đây là chỉ số quan trọng vì buồn ngủ thường không chỉ thể hiện ở một frame, mà ở xu hướng mắt nhắm nhiều hơn bình thường. Trong project, classifier có cửa sổ theo thời gian để tính PERCLOS ngắn và dài, từ đó tăng độ tin cậy khi cảnh báo.

### 19. Vì sao không chỉ dùng một frame để phát hiện buồn ngủ?

**Trả lời thuyết trình:**

> Một frame rất dễ nhiễu: tài xế có thể chớp mắt, quay đầu, ánh sáng thay đổi hoặc camera bắt nhầm landmark. Buồn ngủ là trạng thái diễn ra theo thời gian, nên hệ thống dùng chuỗi frame và duration. Ví dụ mắt nhắm rất ngắn có thể là blink, nhưng nhắm kéo dài nhiều giây mới nâng mức cảnh báo. Cách này giảm báo sai và hợp lý hơn về mặt hành vi con người.

### 20. Classifier hiện tại là deep learning hay rule-based?

**Trả lời thuyết trình:**

> Classifier hiện tại là rule-based theo thời gian, dựa trên đặc trưng được trích từ MediaPipe Face Mesh. Nó nhận EAR, MAR, pitch, PERCLOS và chất lượng vùng mắt, sau đó phân loại thành NORMAL, BLINK, EYES_CLOSED, DROWSY, YAWNING, HEAD_DOWN, NO_FACE hoặc LOW_CONFIDENCE. Em chọn hướng này vì Jetson Nano có tài nguyên hạn chế, cần chạy ổn định realtime và dễ giải thích trước hội đồng.

**File cần mở:** `Version3/ai/drowsiness_classifier.py`.

### 21. Vì sao cần calibration theo tài xế?

**Trả lời thuyết trình:**

> Mỗi người có đặc điểm mắt, khuôn mặt và tư thế khác nhau. Nếu dùng một ngưỡng EAR cố định cho tất cả tài xế thì người mắt nhỏ, đeo kính hoặc góc camera khác có thể bị báo sai. Calibration thu mẫu ban đầu để tạo profile theo tài xế, ví dụ median EAR/MAR/pitch, rồi `ThresholdPolicy` cung cấp ngưỡng phù hợp cho classifier. Nếu calibration không đủ tin cậy, hệ thống dùng fallback an toàn.

**File cần mở:** `Version3/ai/calibration.py`, `Version3/ai/threshold_policy.py`.

### 22. Hệ thống xử lý tài xế đeo kính hoặc ánh sáng phản chiếu thế nào?

**Trả lời thuyết trình:**

> Trong `FaceAnalyzer`, hệ thống có logic đánh giá chất lượng từng bên mắt. Nếu cả hai mắt tốt thì dùng cả hai; nếu một bên bị glare hoặc không đáng tin, hệ thống có thể ưu tiên bên mắt rõ hơn. Nếu dữ liệu vùng mắt quá kém, classifier có thể trả LOW_CONFIDENCE thay vì kết luận buồn ngủ. Cách này giúp giảm báo sai khi tài xế đeo kính hoặc ánh sáng phản chiếu.

**File cần mở:** `Version3/camera/face_analyzer.py`.

### 23. Camera FPS khác AI FPS như thế nào?

**Trả lời thuyết trình:**

> Camera FPS là số frame camera cố gắng lấy mỗi giây, còn AI FPS là số frame mỗi giây thực sự được đưa vào phân tích. Trong project, camera có thể cấu hình `DROWSIGUARD_CAMERA_FPS`, còn `AI_TARGET_FPS` là 12. Em tách hai giá trị này vì không cần chạy AI trên mọi frame camera. Camera lấy ảnh mượt hơn, còn AI xử lý ở tốc độ vừa đủ để phát hiện các trạng thái kéo dài như nhắm mắt, ngáp, cúi đầu mà vẫn giữ Jetson ổn định.

**File cần mở:** `Version3/config.py`, `Version3/main.py`.

### 24. Vì sao alert có nhiều mức?

**Trả lời thuyết trình:**

> Mức độ nguy hiểm không giống nhau. Mắt nhắm ngắn hoặc dấu hiệu nhẹ thì chỉ nên cảnh báo nhẹ, còn mắt nhắm kéo dài hoặc PERCLOS cao thì phải nâng lên mức nguy hiểm hơn. AlertManager chia thành Level 1, Level 2, Level 3 để điều khiển phản ứng phần cứng phù hợp. Ngoài ra có cooldown để tránh cảnh báo nhấp nháy liên tục gây khó chịu hoặc làm người dùng mất niềm tin.

**File cần mở:** `Version3/alerts/alert_manager.py`.

### 25. Nếu không thấy mặt thì hệ thống có báo buồn ngủ không?

**Trả lời thuyết trình:**

> Không nên kết luận buồn ngủ nếu không có dữ liệu mặt đủ tin cậy. Khi không thấy mặt hoặc chất lượng quá thấp, classifier trả trạng thái như NO_FACE hoặc LOW_CONFIDENCE. Đây là cách xử lý an toàn hơn: hệ thống phản ánh rằng dữ liệu đầu vào không đủ, thay vì suy diễn sai thành buồn ngủ. Trạng thái này cũng giúp dashboard hoặc người vận hành biết camera/góc nhìn có vấn đề.

---

## 4. RFID, xác thực khuôn mặt và session

### 26. Vì sao cần RFID?

**Trả lời thuyết trình:**

> RFID giúp xác định tài xế đang cố bắt đầu phiên lái. Mỗi tài xế có `rfid_tag` trong hệ thống. Khi quét thẻ, Jetson biết cần kiểm tra người nào và có thể phát driver event lên dashboard. Tuy nhiên RFID chỉ là bước nhận dạng ban đầu, không đủ bảo mật vì thẻ có thể bị mượn, nên hệ thống kết hợp thêm xác thực khuôn mặt.

### 27. Vì sao không chỉ dùng RFID?

**Trả lời thuyết trình:**

> Vì RFID xác nhận cái thẻ, không xác nhận người cầm thẻ. Nếu người khác mượn thẻ tài xế thì hệ thống chỉ dùng RFID sẽ nhận sai người lái. Khuôn mặt giúp xác thực rằng người ngồi trước camera khớp với tài xế đã đăng ký. Trong chế độ strict, nếu không khớp thì session không hợp lệ và hệ thống gửi face mismatch lên dashboard.

### 28. Luồng xác thực tài xế diễn ra thế nào?

**Trả lời thuyết trình:**

> Khi RFID reader đọc UID, `_on_rfid_scan` trong `main.py` chuyển state sang VERIFYING_DRIVER và gọi `_verify_driver`. Jetson tìm enrollment tương ứng với RFID, lấy frame khuôn mặt hiện tại và so khớp với ảnh tham chiếu trong driver registry local. Nếu match thì `_start_verified_session` reset AI session, chuyển sang RUNNING và queue `session_start` cùng `verify_snapshot`. Nếu mismatch hoặc thiếu dữ liệu, hệ thống gửi verify error hoặc face mismatch.

**File cần mở:** `Version3/main.py`, `Version3/storage/driver_registry.py`, `WebQuanLi/app/api/vehicles.py`.

### 29. Driver registry là gì?

**Trả lời thuyết trình:**

> Driver registry là cache local trên Jetson chứa thông tin tài xế cần cho xác thực: RFID, tên, ảnh mặt tham chiếu và metadata. WebQuanLi là nơi quản lý dữ liệu gốc, nhưng Jetson cần bản local để xác thực nhanh và vẫn có thể hoạt động trong điều kiện mạng không ổn định. Khi admin upload ảnh mặt trên WebQuanLi, server có thể gửi command sync registry để Jetson tải manifest và ảnh mới.

### 30. Nếu tài xế chưa có ảnh mặt thì sao?

**Trả lời thuyết trình:**

> Nếu không có enrollment hoặc ảnh tham chiếu, Jetson không đủ dữ liệu để xác thực khuôn mặt. Trong chế độ strict, hệ thống không nên cho bắt đầu session hợp lệ và sẽ gửi verify error như NO_ENROLLMENT. Trong demo có thể có cấu hình demo mode, nhưng khi bảo vệ em cần nói rõ đây là cấu hình phục vụ thử nghiệm, còn luồng đúng của hệ thống là RFID phải đi kèm xác thực khuôn mặt.

### 31. Demo mode có phải là lỗ hổng không?

**Trả lời thuyết trình:**

> Demo mode là cấu hình phục vụ thử nghiệm khi chưa đủ dữ liệu enrollment hoặc muốn kiểm thử nhanh phần AI. Nó không phải luồng vận hành chính. Trong vận hành nghiêm túc, `DROWSIGUARD_DEMO_MODE` nên để false để RFID chỉ kích hoạt xác thực, còn session chỉ bắt đầu khi khuôn mặt match. Em phân biệt rõ giữa chế độ demo và chế độ strict khi trình bày.

**File cần mở:** `Version3/config.py`, `Version3/main.py`.

### 32. Nếu người khác cầm thẻ RFID của tài xế thì hệ thống phản ứng thế nào?

**Trả lời thuyết trình:**

> Người đó có thể qua bước RFID nhưng sẽ bị chặn ở bước xác thực khuôn mặt. Nếu khuôn mặt không khớp ảnh tham chiếu, Jetson gửi `face_mismatch` lên Monitoring Hub. WebQuanLi lưu alert mức nghiêm trọng và dashboard hiển thị để người quản lý biết có dấu hiệu sai tài xế. Đây là lý do hệ thống kết hợp RFID và Face ID thay vì chỉ dùng một yếu tố.

---

## 5. WebQuanLi, database và bảo mật

### 33. Vì sao dùng FastAPI?

**Trả lời thuyết trình:**

> FastAPI phù hợp vì hệ thống có nhiều I/O đồng thời: Jetson giữ WebSocket, browser giữ SSE, backend đọc ghi database và xử lý API. FastAPI chạy theo ASGI và hỗ trợ async nên không bị chặn bởi một request đang chờ I/O. Ngoài ra FastAPI kết hợp Pydantic giúp validate payload từ Jetson và input quản trị, giảm nguy cơ dữ liệu sai đi vào database.

### 34. Vì sao dùng SQLite?

**Trả lời thuyết trình:**

> SQLite phù hợp với đồ án và demo vì gọn, dễ triển khai, không cần cài database server riêng. Dữ liệu của hệ thống demo như xe, tài xế, session, alert và hardware status không quá lớn. Nếu triển khai production với nhiều xe và nhiều người dùng đồng thời, có thể chuyển sang PostgreSQL vì code đã dùng SQLAlchemy ORM, phần model và query được tách tương đối rõ.

### 35. Database lưu những bảng chính nào?

**Trả lời thuyết trình:**

> Các bảng chính gồm `users` cho tài khoản đăng nhập, `vehicles` cho xe, `drivers` cho tài xế và RFID/ảnh mặt, `driver_sessions` cho phiên lái, `system_alerts` cho cảnh báo, `hardware_statuses` cho trạng thái phần cứng và `ota_audit_logs` là phần log liên quan cập nhật nếu chức năng này được bật lại. Khi trình bày, em nhấn mạnh RFID nằm trong bảng drivers dưới dạng `rfid_tag`, không cần một bảng RFID riêng cho bản hiện tại.

**File cần mở:** `WebQuanLi/app/models.py`.

### 36. JWT cookie và bcrypt dùng để làm gì?

**Trả lời thuyết trình:**

> Bcrypt dùng để hash mật khẩu, tránh lưu plain text trong database. Khi người dùng đăng nhập, server kiểm tra password với hash rồi tạo JWT. Token được lưu trong cookie HttpOnly để browser tự gửi theo request nhưng JavaScript khó đọc trực tiếp. Ngoài authentication, một số route còn kiểm tra quyền admin để bảo vệ thao tác nhạy cảm như tạo xe, sửa tài xế, upload ảnh hoặc gửi lệnh điều khiển.

**File cần mở:** `WebQuanLi/app/auth/utils.py`, `WebQuanLi/app/auth/dependencies.py`.

### 37. Pydantic schema giúp gì?

**Trả lời thuyết trình:**

> Pydantic schema là hợp đồng dữ liệu giữa Jetson, WebQuanLi và frontend. Ví dụ alert phải có level hợp lệ, GPS phải có lat/lng, hardware phải có các trường trạng thái phần cứng. Nếu Jetson gửi payload sai, WebQuanLi log validation error và không ghi dữ liệu sai vào database. Nhờ đó hai phía phát triển ít bị lệch contract.

**File cần mở:** `WebQuanLi/app/schemas.py`.

### 38. Vì sao phải validate biển số, device ID, RFID?

**Trả lời thuyết trình:**

> Đây là dữ liệu định danh trong hệ thống. Nếu không validate, người dùng có thể nhập chuỗi rỗng, ký tự nguy hiểm hoặc giá trị không đúng format, gây lỗi truy vấn hoặc dữ liệu bẩn. Trong schema, biển số, device ID, RFID và phone đều có pattern kiểm tra. Ngoài ra API còn kiểm tra trùng biển số, trùng device ID và trùng RFID để tránh một tài xế hoặc một thiết bị bị ánh xạ sai.

### 39. Vì sao không ghi mọi GPS vào database?

**Trả lời thuyết trình:**

> GPS là dữ liệu tần suất cao. Nếu mỗi vài giây đều ghi vào SQLite, database sẽ phình nhanh và tạo I/O không cần thiết. Trong demo này, GPS chủ yếu phục vụ hiển thị realtime trên bản đồ, nên được publish qua EventBus/SSE. Những dữ liệu có giá trị truy vết như session, alert và face mismatch mới cần lưu database.

### 40. Timezone trong lịch sử xử lý thế nào?

**Trả lời thuyết trình:**

> Database nên lưu thời gian ở UTC để nhất quán và tránh phụ thuộc timezone của máy chạy server. Khi hiển thị cho người dùng Việt Nam hoặc lọc theo ngày, service chuyển sang Asia/Saigon. Nếu không xử lý timezone, dữ liệu lọc theo ngày có thể lệch sang ngày trước hoặc ngày sau, nhất là khi lưu UTC nhưng người dùng nhìn giờ địa phương.

**File cần mở:** `WebQuanLi/app/services/time_service.py`, `WebQuanLi/app/services/history_service.py`.

---

## 6. GPS, phần cứng và môi trường demo

### 41. GPS không có fix nghĩa là GPS hỏng đúng không?

**Trả lời thuyết trình:**

> Không nhất thiết. Em tách hai khái niệm: UART/NMEA và GPS fix. UART/NMEA cho biết Jetson có đọc được dữ liệu từ module GPS hay không. GPS fix cho biết module đã bắt đủ vệ tinh để có tọa độ hợp lệ hay chưa. Trong nhà hoặc nơi tín hiệu yếu, module có thể vẫn gửi NMEA nhưng chưa có fix. Vì vậy dashboard hoặc log cần phân biệt `gps_uart_ok` và `gps_fix_ok`, không kết luận hỏng chỉ vì chưa có tọa độ.

**File cần mở:** `Version3/sensors/gps_reader.py`, `WebQuanLi/app/schemas.py`.

### 42. GPS dùng cổng nào trên Jetson?

**Trả lời thuyết trình:**

> Trong cấu hình hiện tại, GPS NEO-6M dùng UART `/dev/ttyTHS1` với baudrate 9600. Đây là UART trên Jetson Nano. Khi demo hoặc kiểm tra GPS, cần đảm bảo không có process khác chiếm cổng này. Trước đó có thể gặp xung đột nếu getty/nvgetty chiếm UART, nên hướng xử lý là giải phóng cổng UART cho GPS trước khi chạy DrowsiGuard.

**File cần mở:** `Version3/config.py`, `Version3/sensors/gps_reader.py`.

### 43. Hardware status trên dashboard gồm những gì?

**Trả lời thuyết trình:**

> Hardware status là snapshot trạng thái thiết bị gửi từ Jetson lên WebQuanLi, gồm nguồn, camera, RFID, GPS, speaker/Bluetooth, websocket và queue pending. WebQuanLi validate bằng `HardwareData`, sau đó lưu `HardwareStatus` và publish event để dashboard cập nhật. Với GPS, hệ thống có trường legacy `gps` và trường chi tiết hơn như `gps_uart_ok`, `gps_fix_ok`.

### 44. Nếu camera lỗi thì hệ thống xử lý thế nào?

**Trả lời thuyết trình:**

> Nếu camera lỗi, Jetson không nên suy diễn trạng thái buồn ngủ từ dữ liệu thiếu. Hardware monitor sẽ phản ánh trạng thái camera lên dashboard. Về phía AI, nếu không có frame hoặc không thấy mặt, classifier trả NO_FACE hoặc LOW_CONFIDENCE thay vì báo buồn ngủ sai. Đây là cách xử lý an toàn hơn khi đầu vào không đủ tin cậy.

### 45. Nếu loa hoặc buzzer không hoạt động thì sao?

**Trả lời thuyết trình:**

> AlertManager được thiết kế để kích hoạt output phần cứng như speaker, buzzer, LED theo mức cảnh báo. Nếu phần cứng không có hoặc không bật feature flag, hệ thống vẫn không nên crash; nó có thể log trạng thái và vẫn gửi alert lên dashboard. Trong demo, phần cảnh báo tại chỗ và cảnh báo trên dashboard là hai lớp: phần cứng giúp tài xế biết ngay, dashboard giúp trung tâm giám sát biết và lưu lịch sử.

### 46. Vì sao Jetson Nano vẫn phù hợp dù tài nguyên hạn chế?

**Trả lời thuyết trình:**

> Jetson Nano phù hợp với bản đồ án vì xử lý tại biên, có thể chạy camera và pipeline CV tương đối nhẹ. Em không dùng mô hình deep learning nặng liên tục, mà dùng MediaPipe Face Mesh để trích landmark và rule-based classifier theo thời gian. Ngoài ra AI FPS được giới hạn tách khỏi camera FPS, có các ngưỡng thermal/throttling để ưu tiên ổn định hơn là cố chạy tối đa.

### 47. Khi nào nên giảm độ phân giải hoặc FPS?

**Trả lời thuyết trình:**

> Nếu Jetson nóng, FPS AI thấp, camera lag hoặc latency cao, cần giảm độ phân giải hoặc target FPS. Mục tiêu của hệ thống không phải hình ảnh thật sắc, mà là đủ landmark ổn định để nhận diện mắt/miệng và phản ứng kịp thời. Vì vậy có thể chọn cấu hình cân bằng như camera 960x540 hoặc thấp hơn nếu cần, còn AI chỉ xử lý khoảng 12 FPS để giữ ổn định.

---

## 7. Điều khiển, OTA và giới hạn demo

### 48. WebQuanLi có gửi lệnh ngược xuống Jetson được không?

**Trả lời thuyết trình:**

> Có. Vì Jetson giữ kết nối WebSocket hai chiều với WebQuanLi, server có thể gửi command xuống thiết bị. Trong bản hiện tại, các command quan trọng gồm test alert, connect/disconnect monitoring và sync driver registry. Jetson nhận command tập trung ở `_on_backend_command` trong `Version3/main.py` để xử lý theo từng action.

**File cần mở:** `Version3/main.py`, `WebQuanLi/app/api/control.py`, `WebQuanLi/app/ws/jetson_handler.py`.

### 49. OTA hiện tại có dùng trong demo không?

**Trả lời thuyết trình:**

> Trong bản demo hiện tại, upload OTA từ dashboard đã bị vô hiệu hóa. Route `/api/vehicles/{vehicle_id}/update` trong `control.py` trả HTTP 410 với thông báo cập nhật Jetson qua NoMachine/SSH. Em làm vậy để giảm rủi ro cập nhật nhầm trong lúc bảo vệ. Về kiến trúc, hệ thống có kênh command hai chiều qua WebSocket nên có thể mở rộng OTA sau này, nhưng bản demo không lấy OTA làm chức năng trọng tâm.

**File cần mở:** `WebQuanLi/app/api/control.py`.

### 50. Nếu hội đồng hỏi vì sao có code OTA mà lại khóa?

**Trả lời thuyết trình:**

> Vì OTA là chức năng nhạy cảm: nếu upload sai file hoặc cập nhật giữa lúc demo, Jetson có thể lỗi runtime. Trong bối cảnh đồ án, em ưu tiên demo ổn định và an toàn nên khóa upload OTA trên dashboard. Phần code còn lại thể hiện hướng mở rộng, nhưng khi vận hành thật cần bổ sung kiểm tra gói, checksum, rollback, phân quyền nghiêm ngặt và quy trình cập nhật rõ ràng.

### 51. Monitoring button trên dashboard dùng để làm gì?

**Trả lời thuyết trình:**

> Nút monitoring là cách admin gửi command connect hoặc disconnect monitoring xuống Jetson. Nó giúp dashboard chủ động yêu cầu thiết bị vào trạng thái giám sát hoặc đồng bộ trạng thái. Nếu Jetson offline, server trả trạng thái chưa gửi được lệnh. Đây là ví dụ cho luồng browser dùng HTTP POST lên backend, rồi backend dùng WebSocket gửi command xuống Jetson.

---

## 8. Test, chứng minh và chất lượng kỹ thuật

### 52. Em chứng minh hai bên Jetson và WebQuanLi nói cùng contract thế nào?

**Trả lời thuyết trình:**

> Em có test contract ở cả hai phía. Phía Jetson sinh các payload như alert, hardware, verify snapshot, session; phía WebQuanLi có schema Pydantic để parse và validate. Các test fixture giúp đảm bảo khi Jetson thay đổi payload thì WebQuanLi vẫn nhận đúng, hoặc nếu sai thì test phát hiện sớm. Đây là cách giảm rủi ro hai module phát triển lệch nhau.

**File cần nhắc:** `Version3/tests/test_webquanli_contract.py`, `WebQuanLi/tests/test_websocket_contract_fixtures.py`.

### 53. Em có những nhóm test nào?

**Trả lời thuyết trình:**

> Phía Jetson có test cho classifier, calibration, threshold policy, RFID/GPS parser, offline reconnect, WebSocket queue và verify flow. Phía WebQuanLi có test cho auth cookie, API validation, driver registry sync, websocket contract, dashboard realtime context, history, timezone và retention. Nhóm test này chứng minh hệ thống không chỉ chạy được một lần trong demo mà còn có kiểm chứng các hành vi chính.

### 54. Nếu hội đồng yêu cầu mở test, nên mở test nào?

**Trả lời thuyết trình:**

> Nếu hỏi AI, em mở `Version3/tests/test_drowsiness_classifier.py`, `test_calibration.py`, `test_threshold_policy.py`. Nếu hỏi giao tiếp hai bên, em mở `Version3/tests/test_webquanli_contract.py` và `WebQuanLi/tests/test_websocket_contract_fixtures.py`. Nếu hỏi dashboard realtime, em mở `WebQuanLi/tests/test_dashboard_realtime_context.py`. Nếu hỏi lịch sử và timezone, em mở `WebQuanLi/tests/test_time_service.py` hoặc `test_history_service.py`.

### 55. Hạn chế hiện tại của hệ thống là gì?

**Trả lời thuyết trình:**

> Hạn chế thứ nhất là classifier hiện tại là rule-based, dễ giải thích và nhẹ nhưng chưa mạnh bằng mô hình học sâu được huấn luyện trên tập dữ liệu lớn. Thứ hai, chất lượng phát hiện phụ thuộc vào camera, ánh sáng, góc mặt và ảnh enrollment. Thứ ba, SQLite phù hợp demo nhưng nếu mở rộng nhiều xe nên chuyển sang PostgreSQL. Thứ tư, OTA hiện bị khóa trong demo, nếu triển khai thật cần quy trình cập nhật và rollback đầy đủ. Em xem các điểm này là hướng phát triển tiếp theo chứ không che giấu trong bảo vệ.

### 56. Nếu mở rộng thực tế, em sẽ nâng cấp gì?

**Trả lời thuyết trình:**

> Nếu mở rộng thực tế, em sẽ nâng cấp database từ SQLite sang PostgreSQL, bổ sung MQTT hoặc message broker nếu số lượng xe lớn, tăng bảo mật cho thiết bị bằng device token/certificate, cải thiện face verification với nhiều ảnh tham chiếu cùng điều kiện camera, và huấn luyện thêm mô hình học sâu nếu có dataset phù hợp. Với OTA, em sẽ thêm checksum, rollback, ký gói cập nhật và quy trình phát hành an toàn.

### 57. Nếu hội đồng hỏi "demo chạy được nhưng có đáng tin không?", trả lời sao?

**Trả lời thuyết trình:**

> Em không chỉ dựa vào việc demo chạy một lần. Hệ thống có các lớp kiểm chứng: code chia module theo trách nhiệm, payload có schema validation, local queue xử lý mất mạng, state machine chặn luồng trạng thái sai, và có test cho AI, calibration, WebSocket contract, auth, dashboard realtime, history/timezone. Demo chứng minh luồng end-to-end, còn test và cấu trúc code chứng minh hệ thống có cơ sở kỹ thuật để bảo trì và mở rộng.

---

## 9. Câu hỏi khó và cách trả lời an toàn

### 58. Tại sao không dùng MQTT cho đúng IoT hơn?

**Trả lời thuyết trình:**

> MQTT rất phù hợp cho IoT quy mô lớn, đặc biệt khi có nhiều thiết bị và cần broker trung gian. Tuy nhiên đồ án của em tập trung vào một hệ thống demo Jetson với FastAPI backend, cần kênh hai chiều trực tiếp và dễ kiểm soát. WebSocket tích hợp sẵn với FastAPI, dễ gửi command ngược từ dashboard xuống Jetson và không cần thêm broker. Nếu mở rộng đội xe lớn, MQTT là hướng nâng cấp hợp lý.

### 59. Tại sao không dùng React cho dashboard?

**Trả lời thuyết trình:**

> Dashboard của em là giao diện quản trị realtime, không cần SPA quá phức tạp. Em dùng Jinja2 server-side render, HTMX/SSE và JavaScript nhỏ cho bản đồ/biểu đồ. Cách này giảm số lượng project phải bảo trì, phù hợp với stack Python/FastAPI và dễ demo hơn. Nếu sau này cần UI phức tạp hơn, có thể tách frontend thành React, nhưng bản hiện tại ưu tiên đơn giản, ổn định và đủ chức năng.

### 60. Nếu Jetson mất điện thì dữ liệu thế nào?

**Trả lời thuyết trình:**

> Nếu mất điện đột ngột, dữ liệu đã gửi và đã commit lên WebQuanLi vẫn còn trong database. Dữ liệu đã được ghi vào local queue trên Jetson trước thời điểm mất điện cũng có cơ hội được gửi lại khi thiết bị khởi động và reconnect, tùy thời điểm flush và trạng thái file SQLite. Đây là lý do em dùng queue bền vững hơn memory queue. Tuy nhiên mất điện đúng lúc đang ghi là rủi ro hệ thống thực tế cần giảm bằng nguồn ổn định hoặc cơ chế shutdown an toàn.

### 61. Nếu WebQuanLi tắt rồi bật lại thì sao?

**Trả lời thuyết trình:**

> Dữ liệu đã lưu trong database vẫn còn. Khi WebQuanLi bật lại, FastAPI khởi động, init database và các route realtime. Jetson sẽ reconnect WebSocket theo cơ chế WSClient; khi kết nối lại, nó gửi hardware snapshot và flush local queue nếu còn event offline. Dashboard mới mở sẽ nhận state mới nhất từ EventBus sau khi Jetson gửi lại dữ liệu.

### 62. Nếu nhiều dashboard mở cùng lúc thì sao?

**Trả lời thuyết trình:**

> Mỗi dashboard subscribe SSE vào EventBus và có queue riêng. Khi Jetson gửi một event, WebSocket handler publish một lần vào EventBus, rồi EventBus phân phối cho các subscriber. Nếu một browser chậm, nó không làm nghẽn browser khác vì queue tách riêng. Đây là lý do em dùng EventBus thay vì để WebSocket handler tự đẩy trực tiếp cho từng browser.

### 63. Nếu GPS hoạt động nhưng dashboard vẫn báo đỏ thì em kiểm tra gì?

**Trả lời thuyết trình:**

> Em kiểm tra theo lớp. Thứ nhất, trên Jetson xem UART `/dev/ttyTHS1` có NMEA không. Thứ hai, kiểm tra `gps_reader.status()` có `module_ok`, `nmea_seen`, `fix_ok` và reason gì. Thứ ba, xem hardware payload gửi lên WebQuanLi có `gps_uart_ok` và `gps_fix_ok` không. Thứ tư, kiểm tra WebSocket có connected và dashboard có nhận SSE không. Như vậy em không kết luận vội là GPS hỏng chỉ vì UI đỏ.

### 64. Nếu dashboard báo mất kết nối thì em debug thế nào?

**Trả lời thuyết trình:**

> Em kiểm tra từ dưới lên: WebQuanLi có đang listen `0.0.0.0:8000` không, Windows firewall/Tailscale có cho Jetson truy cập không, Jetson có ping/curl được IP Tailscale của Windows không, `DROWSIGUARD_WS_URL` có đúng `/ws/jetson/JETSON-001` không, log WSClient có "connected" hay "reconnecting", và phía WebQuanLi `manager.active` có device ID đó không. Khi transport WebSocket ổn nhưng UI vẫn offline, em kiểm tra tiếp SSE và state trên dashboard.

### 65. Nếu hội đồng hỏi "phần nào là implemented, phần nào chỉ kế hoạch?", trả lời sao?

**Trả lời thuyết trình:**

> Phần implemented trong demo là Jetson runtime xử lý camera/RFID/GPS, AI rule-based theo EAR/MAR/pitch/PERCLOS, cảnh báo, local queue, WebSocket client; WebQuanLi có FastAPI backend, auth, database, WebSocket server, EventBus, SSE dashboard, quản lý xe/tài xế và upload ảnh mặt. Phần OTA upload hiện không trình bày là chức năng demo chính vì đã khóa bằng HTTP 410. Các hướng như MQTT quy mô lớn, PostgreSQL production, model deep learning hoặc OTA rollback là hướng phát triển tiếp theo.

### 66. Nếu bị hỏi "hệ thống có bảo mật thiết bị Jetson kết nối giả không?", trả lời sao?

**Trả lời thuyết trình:**

> Bản demo hiện định danh thiết bị chủ yếu qua `device_id` và mạng demo/Tailscale, phù hợp phạm vi đồ án. Tuy nhiên nếu triển khai thực tế, em sẽ bổ sung device token hoặc certificate cho Jetson, kiểm tra chữ ký payload hoặc ít nhất shared secret theo thiết bị, và giới hạn WebSocket endpoint. Đây là một điểm nâng cấp bảo mật quan trọng khi đưa ra môi trường production.

### 67. Nếu bị hỏi "tại sao dùng rule-based mà không dùng model học sâu?", trả lời sao?

**Trả lời thuyết trình:**

> Em chọn rule-based vì phù hợp tài nguyên Jetson Nano, dễ chạy realtime, dễ debug và dễ giải thích trước hội đồng. Với đồ án, các dấu hiệu như mắt nhắm kéo dài, ngáp, cúi đầu có thể biểu diễn bằng EAR, MAR, pitch và PERCLOS theo thời gian. Model học sâu có thể mạnh hơn nếu có dataset đủ lớn và quá trình huấn luyện tốt, nhưng cũng tốn tài nguyên, khó giải thích và dễ phụ thuộc dữ liệu. Đây là hướng nâng cấp sau, không phải bắt buộc cho bản demo ổn định.

### 68. Nếu bị hỏi "vì sao GPS không lưu lịch sử tuyến đường?", trả lời sao?

**Trả lời thuyết trình:**

> Vì mục tiêu hiện tại là giám sát buồn ngủ và trạng thái xe realtime, không phải hệ thống tracking tuyến đường đầy đủ. GPS dùng để hiển thị vị trí hiện tại và gắn tọa độ vào alert khi cần. Lưu toàn bộ tuyến đường sẽ làm tăng dữ liệu rất nhanh và cần thiết kế retention, nén dữ liệu, quyền riêng tư. Nếu mở rộng thành fleet tracking, em sẽ thêm bảng riêng cho GPS history hoặc dùng time-series storage, nhưng bản hiện tại ưu tiên dữ liệu alert/session.

### 69. Nếu bị hỏi "em sẽ demo theo thứ tự nào?", trả lời sao?

**Trả lời thuyết trình:**

> Em sẽ demo theo luồng nghiệp vụ. Đầu tiên mở Monitoring Hub để thấy xe đang chờ kết nối. Sau đó chạy DrowsiGuard trên Jetson và xác nhận dashboard chuyển online. Tiếp theo quét RFID, xác thực khuôn mặt để bắt đầu session. Sau đó tạo tình huống buồn ngủ hoặc test alert để dashboard nhận alert realtime. Cuối cùng em mở lịch sử hoặc alert log để chứng minh dữ liệu được lưu và có thể truy vết.

### 70. Nếu chỉ có 2 phút để giới thiệu dự án, em nói gì?

**Trả lời thuyết trình:**

> Đồ án của em là hệ thống DrowsiGuard giám sát buồn ngủ tài xế theo mô hình Edge IoT. Trên xe, Jetson Nano chạy DrowsiGuard Edge Runtime để đọc camera, RFID, GPS, xác thực tài xế và phát hiện dấu hiệu buồn ngủ bằng các đặc trưng như EAR, MAR, pitch, PERCLOS. Khi có cảnh báo, Jetson cảnh báo tại chỗ và gửi event lên DrowsiGuard Monitoring Hub qua WebSocket. Monitoring Hub dùng FastAPI, SQLite, EventBus và SSE để lưu session/alert và hiển thị dashboard realtime. Hệ thống có local queue để chịu lỗi mất mạng, JWT/bcrypt cho đăng nhập, Pydantic schema để validate payload và test contract để đảm bảo Jetson/WebQuanLi giao tiếp đúng. Trong bản demo, kết nối WebSocket được cấu hình qua Tailscale để ổn định hơn IP LAN thay đổi.

---

## 10. Bảng học nhanh trước ngày bảo vệ

| Chủ đề hội đồng hỏi | Câu mở đầu nên nói |
|---|---|
| Tổng quan | "Hệ thống của em là Edge IoT, Jetson xử lý tại xe, Monitoring Hub quản trị và realtime." |
| AI | "Classifier hiện tại là CV + rule-based theo thời gian, dựa trên EAR, MAR, pitch, PERCLOS." |
| RFID/Face | "RFID nhận dạng thẻ, face verification xác thực người cầm thẻ." |
| WebSocket/SSE | "WebSocket cho Jetson hai chiều, SSE cho dashboard nhận realtime một chiều." |
| Database | "SQLite phù hợp demo; dữ liệu truy vết như session/alert mới lưu, GPS realtime không ghi liên tục." |
| Offline | "Jetson có local queue SQLite, alert/session được ưu tiên và flush khi reconnect." |
| GPS | "Phải tách UART/NMEA còn sống và GPS fix hợp lệ; chưa fix không đồng nghĩa GPS hỏng." |
| OTA | "Bản demo đã khóa upload OTA bằng HTTP 410; cập nhật Jetson qua SSH/NoMachine để an toàn." |
| Security | "Có bcrypt, JWT HttpOnly cookie, admin-only route, Pydantic validation; production cần thêm device token/certificate." |
| Hạn chế | "Rule-based nhẹ và dễ giải thích, nhưng production có thể nâng cấp model, DB, MQTT, bảo mật thiết bị." |


# Kế Hoạch Tối Ưu Project WebQuanLi

## 1. Mục tiêu của kế hoạch

Tài liệu này dùng để định hướng nâng cấp project `WebQuanLi` từ mức **prototype phục vụ demo đồ án** lên mức **hệ thống quản lý ổn định, an toàn và dễ bảo trì hơn**.

Mục tiêu chính:

- Hoàn thiện luồng quản lý thời gian thực giữa Web và Jetson.
- Tăng độ an toàn khi đăng nhập, upload file và điều khiển thiết bị.
- Tối ưu truy vấn và xử lý dữ liệu để dashboard mượt hơn.
- Chuẩn hóa cấu trúc code để dễ bảo trì, dễ thuyết trình và dễ mở rộng.

## 2. Đánh giá hiện trạng

### 2.1 Điểm mạnh hiện có

- Đã dùng `FastAPI`, tách module khá rõ: `auth`, `api`, `ws`, `services`, `core`.
- Có `WebSocket` nhận dữ liệu từ Jetson và `SSE` đẩy realtime ra trình duyệt.
- Có dashboard, fleet, history, statistics, login, OTA upload, test alert.
- Có mô hình dữ liệu tương đối đầy đủ: xe, tài xế, session, phần cứng, cảnh báo.

### 2.2 Điểm cần ưu tiên xử lý

- Còn thông tin mặc định nhạy cảm trong cấu hình như `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
- OTA upload hiện mới kiểm tra phần mở rộng `.py`, chưa kiểm soát tên file, checksum, phiên bản.
- Một số API còn truy vấn kiểu `N+1 query`, đặc biệt ở phần session và statistics.
- Event bus đang hoạt động trong RAM, phù hợp demo nhưng chưa tốt nếu số client tăng hoặc server restart.
- Chưa có test tự động cho auth, API, luồng realtime, upload và phân quyền.

## 3. Phương pháp triển khai

### 3.1 Phương pháp ưu tiên

Áp dụng kết hợp 4 phương pháp:

- `MoSCoW`: chia việc thành Must / Should / Could để tránh làm lan man.
- `Risk-based hardening`: ưu tiên xử lý các lỗi có khả năng bị hỏi hoặc bị khai thác cao.
- `Vertical slice`: hoàn thiện từng luồng đầy đủ từ UI -> API -> DB -> Jetson command.
- `Measure first`: tối ưu dựa trên số đo thực tế, không tối ưu cảm tính.

### 3.2 Cách làm theo sprint

- Sprint 1: bảo mật và ổn định nền tảng.
- Sprint 2: tối ưu hiệu năng và dữ liệu.
- Sprint 3: hoàn thiện tính năng quản lý thiết bị và OTA.
- Sprint 4: test, logging, tài liệu bảo vệ.

## 4. Kế hoạch công việc chi tiết

## Giai đoạn 1 - Ổn định và bảo mật nền tảng

### Việc cần làm

- Bỏ toàn bộ credential mặc định trong config.
- Tạo file `.env.example` chỉ chứa biến mẫu, không chứa dữ liệu thật.
- Kiểm tra cookie auth:
  - thêm `secure=True` khi chạy HTTPS
  - giữ `httponly=True`
  - xem xét `SameSite=Lax` hoặc `Strict`
- Giới hạn quyền rõ hơn:
  - `viewer` chỉ xem
  - `admin` mới được test alert, upload OTA, chỉnh xe và tài xế
- Thêm validate dữ liệu đầu vào bằng Pydantic chặt hơn cho số điện thoại, `device_id`, `plate_number`, `rfid_tag`.

### Cách tối ưu

- Dùng phương pháp `Security hardening baseline`.
- Xử lý trước các lỗi "thấp công sức, cao tác động".

### Kết quả mong muốn

- Không còn secret hardcode trong codebase.
- Giảm rủi ro khi demo và khi push code.
- Có thể tự tin trả lời hội đồng về phần bảo mật cơ bản.

## Giai đoạn 2 - Tối ưu truy vấn và dữ liệu

### Việc cần làm

- Tối ưu `list_sessions` để tránh query từng tài xế một.
- Tối ưu `statistics_summary`:
  - gom nhóm bằng SQL thay vì lặp Python quá nhiều
  - hạn chế query lặp khi lấy top driver
- Xem lại `history_page` và API alert:
  - thêm index cho các cột lọc nhiều như `timestamp`, `vehicle_id`, `alert_type`
- Chuẩn hóa timezone, hiển thị thống nhất UTC ở backend và convert ở frontend.

### Phương pháp dùng

- `Database-first optimization`
- `EXPLAIN query` hoặc đo thời gian API trước và sau khi sửa
- `Batch query / eager loading`

### Cách tối ưu cụ thể

- Dùng `join`, `selectinload`, `group_by`, `func.count` đúng chỗ.
- Với số liệu dashboard, cân nhắc tạo `summary query` riêng thay vì tận dụng query raw.
- Chỉ load field cần thiết cho trang hiển thị, tránh lấy dư dữ liệu.

### Kết quả mong muốn

- Dashboard và history phản hồi nhanh hơn khi dữ liệu tăng.
- Code thống kê rõ ràng, gọn và dễ giải thích hơn.

## Giai đoạn 3 - Hoàn thiện luồng realtime và giao tiếp chéo Jetson ↔ Web (Ưu tiên cao)

### Đánh giá hiện trạng (Review cross-operation)

**Điểm chưa tốt & lý do:**
- Không có **Single Source of Truth** cho message contract (chỉ có schemas ở Web, Jetson hardcode string). Dễ lệch key/structure khi thay đổi → lỗi runtime khó debug.
- EventBus hoàn toàn in-memory + cache state trong RAM: Web restart → mất hết trạng thái (online, current driver, hardware). Jetson reconnect chỉ gửi hardware snapshot, không full state.
- Command Web → Jetson yếu (chỉ hỗ trợ cơ bản, ít dùng ngoài OTA/test alert).
- Không có protocol versioning, heartbeat định kỳ, hay backward compatibility.
- OTA logic hai bên độc lập, chưa có manifest/checksum/version chung.
- Error feedback một chiều (Web log ValidationError nhưng Jetson không nhận được chỉ dẫn rõ).

**Nguyên nhân gốc rễ:** Thiết kế ban đầu chỉ phục vụ demo đồ án, chưa nghĩ đến production reliability và maintainability giữa embedded + web.

### Việc cần làm (cải thiện mạnh)

- Tạo `docs/protocol.md` + file JSON schema làm contract chính thức (Single Source of Truth). Tự động generate Pydantic models cho Web và constants cho Jetson.
- Thêm `protocol_version` vào mọi message.
- Jetson gửi **full snapshot** (state + current_session + driver + hardware) khi reconnect.
- Chuẩn hóa bidirectional commands (test_alert, reboot, config_update, ota_start...).
- Thay EventBus in-memory bằng Redis Pub/Sub hoặc DB-persisted state (hoặc hybrid).
- Thêm heartbeat message mỗi 10s + timeout detection rõ ràng.
- Tách `jetson_handler.py` thành nhiều handler nhỏ theo event type (SessionHandler, AlertHandler, CommandHandler...).
- Cải thiện offline resilience: Jetson queue + Web retry + persistent state.

### Phương pháp dùng

- **Contract-first + Versioned Protocol**
- State-driven design + Event Sourcing lite cho vehicle state
- Measure reconnect & offline scenarios

### Cách tối ưu cụ thể

- Viết contract rõ ràng với example JSON cho từng type.
- Thêm `type: "heartbeat"`, `type: "snapshot"`, `type: "command_ack"`.
- Web trả command response qua WS thay vì chỉ publish event.
- Logging với structured event_id và correlation_id.

### Kết quả mong muốn

- Hai codebase không bao giờ lệch contract.
- Hệ thống chịu được restart Web mà không mất trạng thái realtime.
- Dễ mở rộng command mới mà không sợ break Jetson cũ.
- Debug cross-system dễ dàng hơn rất nhiều.
- Nền tảng vững để bảo vệ đồ án (có tài liệu protocol rõ ràng).

## Giai đoạn 4 - Tối ưu OTA và upload

### Việc cần làm

- Không upload trực tiếp file `.py` đơn lẻ để cập nhật.
- Chuyển sang mô hình `package update`:
  - `.zip` hoặc `.tar.gz`
  - có `manifest.json`
  - có `version`
  - có `checksum`
- Sanitize tên file upload.
- Chặn ghi đè tùy ý vào thư mục update.
- Lưu log mỗi lần admin gửi OTA:
  - ai gửi
  - lúc nào
  - file nào
  - xe nào
  - trạng thái áp dụng

### Phương pháp dùng

- `Safe deployment pattern`
- `Immutable package + checksum verification`

### Cách tối ưu

- Backend chỉ cấp file hợp lệ đã kiểm tra checksum.
- Jetson phải xác thực checksum trước khi áp dụng.
- Có rollback hoặc ít nhất là giữ bản backup cũ.

### Kết quả mong muốn

- OTA an toàn hơn nhiều.
- Dễ trình bày như một tính năng nghiêm túc chứ không chỉ là upload demo.

## Giai đoạn 5 - Frontend và trải nghiệm người dùng

### Việc cần làm

- Bổ sung loading state, empty state, error state cho dashboard và statistics.
- Làm rõ trạng thái xe:
  - online
  - offline
  - session đang chạy
  - mismatch
  - đang cập nhật OTA
- Bổ sung xác nhận trước các hành động nguy hiểm như test alert hoặc update.
- Kiểm tra responsive kỹ hơn cho màn hình laptop và tablet.

### Phương pháp dùng

- `User-centered refinement`
- `State-driven UI`

### Cách tối ưu

- Mỗi trạng thái hệ thống phải có biểu diễn màu sắc, badge và câu chữ rõ ràng.
- Giảm việc phải đoán trạng thái qua nhiều khu vực khác nhau trên màn hình.

## Giai đoạn 6 - Testing và chất lượng phần mềm

### Việc cần làm

- Viết test cho:
  - login / logout
  - phân quyền admin
  - list vehicle / driver
  - tạo session / alert
  - upload OTA
  - WebSocket message handler
- Dùng dữ liệu giả để test integration với `jetson_simulator.py`.
- Bổ sung script chạy test nhanh trước demo.

### Phương pháp dùng

- `Test pyramid`
- `Regression prevention`

### Cách tối ưu

- Unit test cho các hàm thuần.
- Integration test cho API và database.
- Mô phỏng Jetson gửi event để kiểm tra realtime.

### Kết quả mong muốn

- Giảm lỗi phát sinh khi sửa code.
- Có bằng chứng kỹ thuật tốt hơn khi bảo vệ.

## 5. Thứ tự ưu tiên nên làm

### Must (ưu tiên cao nhất)

- **Hoàn thiện & version hóa protocol/contract** giữa Jetson <-> Web (docs/protocol.md + full snapshot + heartbeat + command ack).
- Bỏ secret mặc định và admin mặc định.
- Tối ưu query statistics và sessions.
- Làm an toàn & idempotent cho OTA upload.

### Should

- Tách `jetson_handler.py` thành nhiều handler nhỏ.
- Bổ sung test cho auth, API và realtime.
- Hoàn thiện giao diện trạng thái lỗi và trạng thái thiết bị.

### Could

- Đổi SQLite sang PostgreSQL nếu sau này cần nhiều thiết bị.
- Dùng Redis Pub/Sub thay cho event bus trong RAM nếu mở rộng lớn hơn.
- Bổ sung audit log đầy đủ cho admin action.

## 6. Chỉ số đánh giá sau tối ưu

- Thời gian phản hồi dashboard API dưới `300ms` với dữ liệu đồ án.
- Trang history tải ổn định dưới `1s` với vài nghìn bản ghi.
- Không còn secret hardcode trong source.
- OTA có checksum và log trạng thái đầy đủ.
- Có test chạy qua cho các luồng chính.

## 7. Kết luận

Hướng tối ưu của `WebQuanLi` không nên đi theo kiểu thêm thật nhiều tính năng mới, mà nên đi theo hướng:

- an toàn hơn
- rõ cấu trúc hơn
- nhanh hơn khi dữ liệu tăng
- đáng tin hơn khi kết nối với Jetson thật

Nếu làm đúng thứ tự ưu tiên ở trên, project web sẽ tăng mạnh cả về chất lượng kỹ thuật lẫn khả năng thuyết phục khi bảo vệ đồ án.

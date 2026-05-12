# Giao trình C1: Lý thuyết nền tảng để bảo vệ đồ án DrowsiGuard

Tài liệu này giúp bạn hiểu nền tảng kỹ thuật của đồ án trước khi đi vào từng file code. Mục tiêu không phải là học thuộc lòng, mà là trả lời được các câu hỏi kiểu:

- Vì sao hệ thống phải chia thành Jetson và WebQuanLi?
- Vì sao dùng WebSocket, SSE, FastAPI, SQLite, JWT, bcrypt?
- Vì sao phát hiện buồn ngủ chạy ở Jetson thay vì gửi video lên server?
- Vì sao phải có state machine, calibration, local queue, driver registry?
- Nếu hội đồng hỏi lỗi mạng, bảo mật, độ trễ, sai tài xế, mất GPS, mất camera, em giải thích ra sao?

Sau khi học xong C1, bạn cần nói được bằng lời của mình:

> Đồ án của em là hệ thống giám sát buồn ngủ và xác thực tài xế theo mô hình Edge IoT. Jetson xử lý camera, RFID, GPS và AI tại xe; WebQuanLi làm trung tâm quản trị, lưu lịch sử, hiển thị dashboard realtime và gửi lệnh điều khiển ngược xuống thiết bị. Hai bên giao tiếp bằng WebSocket, còn dashboard trình duyệt nhận dữ liệu realtime bằng SSE.

## Cập nhật theo trạng thái project hiện tại

Khi trình bày, nên dùng tên chuyên nghiệp thay vì đọc tên thư mục:

| Tên thư mục trong repo | Tên nên gọi khi bảo vệ | Vai trò |
|---|---|---|
| `Version3` | **DrowsiGuard Edge Runtime** / **Phần mềm Jetson trên xe** | Chạy trên Jetson Nano, đọc camera/RFID/GPS, xác thực tài xế, phát hiện buồn ngủ, cảnh báo tại chỗ và gửi dữ liệu lên server |
| `WebQuanLi` | **DrowsiGuard Monitoring Hub** / **Trung tâm giám sát** | FastAPI backend + dashboard quản trị, lưu dữ liệu, hiển thị realtime và gửi lệnh điều khiển xuống Jetson |

Các điểm mới cần nói đúng theo project hiện tại:

- Dashboard đang hiển thị thương hiệu **DrowsiGuard**, menu **Trung tâm giám sát**, tiêu đề màn hình **Monitoring Hub**.
- Kết nối Jetson -> WebQuanLi nên trình bày là WebSocket qua **Tailscale** để tránh phụ thuộc IP LAN thay đổi. Trên Jetson, URL được cấu hình bằng biến môi trường `DROWSIGUARD_WS_URL`, không hard-code trong phần trình bày.
- GPS dùng UART `/dev/ttyTHS1`. Khi bảo vệ, phải tách rõ **GPS UART/NMEA còn sống** và **GPS đã có fix vệ tinh**. Chưa có fix không đồng nghĩa module GPS hỏng.
- Luồng demo chính hiện tại nên nhấn mạnh: quét RFID -> xác thực khuôn mặt -> bắt đầu session -> AI giám sát buồn ngủ -> dashboard cập nhật realtime.
- OTA không nên trình bày như chức năng demo chính đang mở trên dashboard. Trong code hiện tại, route upload OTA đã trả thông báo vô hiệu hóa và hướng cập nhật Jetson qua SSH/NoMachine; vì vậy chỉ nên nói OTA là hướng mở rộng/đã từng có khung xử lý, không phải điểm demo trọng tâm.

---

## 1. Bản chất bài toán đồ án

### 1.1 Hệ thống đang giải quyết vấn đề gì?

Bài toán thực tế là: tài xế có thể buồn ngủ, mất tập trung, lái sai người hoặc thiết bị trên xe bị lỗi mà trung tâm không biết kịp thời. Vì vậy hệ thống cần làm 5 việc:

1. Nhận biết tài xế đang lái bằng RFID và xác thực khuôn mặt.
2. Theo dõi dấu hiệu buồn ngủ bằng camera và AI.
3. Cảnh báo tại chỗ bằng loa, buzzer, LED.
4. Gửi dữ liệu lên web để người quản lý biết tình trạng xe theo thời gian thực.
5. Lưu lịch sử để tra cứu, thống kê và chứng minh sau này.

Điểm quan trọng khi trình bày:

> Đây không chỉ là một app web, cũng không chỉ là một chương trình camera. Đây là hệ thống IoT có thiết bị biên, backend trung tâm, dashboard realtime và cơ chế chịu lỗi khi mạng không ổn định.

### 1.2 Vì sao không làm mọi thứ trên một máy?

Nếu chỉ dùng Jetson:

- Cảnh báo tại xe vẫn được, nhưng quản lý từ xa yếu.
- Không tiện thêm sửa xe, tài xế, RFID, ảnh khuôn mặt.
- Không có dashboard tổng quan, lịch sử, thống kê.

Nếu chỉ dùng server web:

- Phải gửi video từ xe lên server, tốn băng thông và độ trễ cao.
- Khi mất mạng thì AI không hoạt động ổn định.
- Cảnh báo tại chỗ bị phụ thuộc vào đường truyền.

Thiết kế đúng là chia vai:

- Jetson xử lý việc cần phản ứng nhanh và gần phần cứng.
- WebQuanLi xử lý việc cần quản trị, lưu trữ và giám sát tập trung.

### 1.3 Câu trả lời mẫu khi hội đồng hỏi

**Câu hỏi:** Tại sao em phải tách thành Jetson và WebQuanLi?

**Trả lời mẫu:**

> Em tách hệ thống thành hai lớp vì yêu cầu thời gian thực và yêu cầu quản trị là khác nhau. Jetson đặt trên xe để đọc camera, RFID, GPS và phát hiện buồn ngủ ngay tại biên, nhờ đó cảnh báo không phụ thuộc mạng. WebQuanLi đặt ở trung tâm để quản lý xe, tài xế, lưu session, lưu cảnh báo và hiển thị dashboard realtime. Cách chia này giảm độ trễ, tiết kiệm băng thông và vẫn bảo đảm có dữ liệu tập trung để truy vết.

---

## 2. Kiến trúc tổng thể

### 2.1 Các khối chính

Hệ thống có 4 khối lớn:

1. **Thiết bị Jetson trong `Version3`**
   - Camera CSI/USB.
   - RFID reader.
   - GPS reader.
   - Bluetooth speaker, buzzer, LED.
   - AI phát hiện buồn ngủ.
   - WebSocket client gửi dữ liệu lên WebQuanLi.
   - Local queue lưu tạm khi offline.

2. **Backend WebQuanLi trong `WebQuanLi/app`**
   - FastAPI app.
   - WebSocket server nhận dữ liệu Jetson.
   - Database SQLite thông qua SQLAlchemy async.
   - API quản lý xe, tài xế, lịch sử, điều khiển.
   - Auth bằng JWT cookie và bcrypt.

3. **Dashboard trình duyệt**
   - HTML render bằng Jinja2.
   - HTMX cập nhật từng phần giao diện.
   - SSE nhận sự kiện realtime từ server.
   - Leaflet/JS hiển thị bản đồ, biểu đồ, trạng thái phần cứng.

4. **Kho dữ liệu**
   - Bảng xe, tài xế, phiên lái, cảnh báo, trạng thái phần cứng và log vận hành.
   - Jetson cũng có SQLite local queue riêng để lưu sự kiện khi mất kết nối.

### 2.2 Luồng dữ liệu chính

Luồng bình thường:

1. Tài xế quét RFID.
2. Jetson xác thực khuôn mặt hoặc cho chạy demo theo cấu hình.
3. Jetson bắt đầu session lái.
4. Camera tạo frame.
5. FaceAnalyzer trích xuất EAR, MAR, pitch, PERCLOS, chất lượng mắt/khuôn mặt.
6. DrowsinessClassifier phân loại NORMAL, BLINK, DROWSY, YAWNING, HEAD_DOWN...
7. AlertManager đổi trạng thái thành WARNING, DANGER hoặc CRITICAL.
8. Jetson phát cảnh báo tại xe.
9. WSClient đẩy message lên WebQuanLi.
10. WebQuanLi validate payload, ghi database nếu cần.
11. EventBus phát sự kiện cho dashboard.
12. Browser nhận SSE và cập nhật UI realtime.

### 2.3 Cách nói ngắn gọn trước hội đồng

> Hệ thống của em vận hành theo kiến trúc event-driven. Jetson sinh sự kiện từ cảm biến và AI, gửi lên WebQuanLi qua WebSocket. WebQuanLi xử lý, lưu những dữ liệu cần persistence, rồi publish sang EventBus. Dashboard subscribe EventBus qua SSE nên có thể cập nhật realtime mà không cần refresh trang.

---

## 3. Edge Computing: Vì sao AI chạy trên Jetson?

### 3.1 Edge Computing là gì?

Edge Computing là đưa xử lý dữ liệu về gần nơi phát sinh dữ liệu. Trong đồ án này, camera nằm trên xe, nên AI nhận diện buồn ngủ cũng chạy trên Jetson đặt trên xe.

### 3.2 Lợi ích trong đồ án

1. **Độ trễ thấp**
   - Cảnh báo buồn ngủ phải phát trong vài trăm mili giây đến vài giây.
   - Nếu gửi video lên server rồi chờ server trả kết quả, độ trễ có thể quá cao.

2. **Tiết kiệm băng thông**
   - Video liên tục rất nặng.
   - Payload text như `{"level": "DANGER", "ear": 0.2}` rất nhẹ.

3. **Hoạt động khi mất mạng**
   - Xe có thể đi qua hầm, vùng sóng yếu.
   - Jetson vẫn cảnh báo tại chỗ dù WebQuanLi tạm thời không nhận dữ liệu.

4. **Bảo mật riêng tư**
   - Không cần stream toàn bộ khuôn mặt/video lên server.
   - Server nhận kết quả và snapshot khi cần, giảm dữ liệu nhạy cảm.

### 3.3 Câu trả lời mẫu

**Câu hỏi:** Tại sao không gửi video lên web xử lý cho mạnh hơn?

**Trả lời mẫu:**

> Vì bài toán cảnh báo buồn ngủ cần phản ứng nhanh và xe có thể dùng mạng không ổn định. Nếu stream video lên server sẽ tốn băng thông 4G, tăng độ trễ và khi mất mạng thì cảnh báo bị ảnh hưởng. Em để Jetson xử lý AI tại biên, chỉ gửi kết quả dạng JSON lên server như mức cảnh báo, EAR, MAR, PERCLOS. Như vậy cảnh báo tại xe vẫn chạy độc lập, còn WebQuanLi chỉ nhận dữ liệu để giám sát và lưu lịch sử.

---

## 4. FastAPI và backend bất đồng bộ

### 4.1 Backend là gì?

Backend là phần xử lý phía server:

- Nhận request từ trình duyệt hoặc thiết bị.
- Kiểm tra đăng nhập và phân quyền.
- Đọc ghi database.
- Nhận WebSocket từ Jetson.
- Trả HTML, JSON hoặc stream realtime.

Trong đồ án, backend nằm ở `WebQuanLi/app`.

### 4.2 Vì sao dùng FastAPI?

FastAPI phù hợp vì:

- Hỗ trợ `async/await`, tốt cho I/O như WebSocket, database, SSE.
- Có router rõ ràng, dễ chia module.
- Hỗ trợ WebSocket trực tiếp.
- Dùng Pydantic để validate dữ liệu vào.
- Dễ viết test bằng pytest.

### 4.3 `async/await` là gì?

Trong hệ thống có nhiều việc phải chờ:

- Chờ Jetson gửi WebSocket.
- Chờ database commit.
- Chờ browser giữ kết nối SSE.
- Chờ gửi SMS, lệnh test cảnh báo, lệnh kết nối giám sát hoặc lệnh đồng bộ driver registry.

Nếu dùng cách đồng bộ, một tác vụ chờ có thể làm nghẽn tác vụ khác. `async/await` giúp server chuyển sang xử lý việc khác trong lúc chờ I/O.

Nói dễ hiểu:

> Async không làm CPU tính nhanh hơn, nhưng giúp server không bị đứng yên khi đang chờ mạng hoặc database.

### 4.4 Câu trả lời mẫu

**Câu hỏi:** FastAPI có ưu điểm gì trong hệ thống của em?

**Trả lời mẫu:**

> FastAPI phù hợp vì hệ thống có nhiều kết nối I/O đồng thời: Jetson giữ WebSocket, browser giữ SSE, backend đọc ghi database. FastAPI chạy theo chuẩn ASGI và hỗ trợ async nên server có thể xử lý nhiều kết nối mà không bị chặn bởi một request đang chờ. Ngoài ra Pydantic giúp em kiểm tra schema payload từ Jetson, giảm lỗi dữ liệu sai hợp đồng.

---

## 5. WebSocket, HTTP API và SSE

### 5.1 HTTP API dùng khi nào?

HTTP API phù hợp cho thao tác dạng request-response:

- Admin tạo xe.
- Admin tạo tài xế.
- Upload ảnh mặt.
- Lọc lịch sử.
- Lấy manifest driver registry.

Đặc điểm:

- Client gửi request.
- Server xử lý.
- Server trả response.
- Kết nối kết thúc.

### 5.2 WebSocket dùng khi nào?

WebSocket là kết nối hai chiều, giữ mở lâu dài.

Trong đồ án, Jetson cần:

- Gửi GPS, hardware, alert, session, verify lên server.
- Nhận lệnh từ server: test alert, sync driver registry, connect/disconnect monitoring.

Vì cần hai chiều nên Jetson dùng WebSocket.

### 5.3 SSE dùng khi nào?

SSE là Server-Sent Events, luồng một chiều từ server xuống browser.

Dashboard chủ yếu cần nhận dữ liệu mới:

- Alert mới.
- GPS mới.
- Hardware mới.
- Driver/session mới.
- Trạng thái online/offline.

Browser không cần gửi command liên tục qua cùng kênh realtime. Khi cần bấm nút, browser dùng HTTP POST. Vì vậy SSE đơn giản hơn WebSocket cho dashboard.

### 5.4 So sánh dễ nhớ

| Công nghệ | Hướng truyền | Dùng trong đồ án | Lý do |
|---|---:|---|---|
| HTTP API | Client hỏi, server trả | CRUD xe/tài xế, lịch sử, upload | Đơn giản, rõ hợp đồng |
| WebSocket | Hai chiều | Jetson với WebQuanLi | Thiết bị vừa gửi dữ liệu vừa nhận lệnh |
| SSE | Server đẩy xuống browser | Dashboard realtime | Browser chủ yếu nhận event, ít phức tạp hơn WebSocket |

### 5.5 Câu trả lời mẫu

**Câu hỏi:** Tại sao dashboard không dùng WebSocket luôn?

**Trả lời mẫu:**

> Em dùng WebSocket cho Jetson vì thiết bị cần giao tiếp hai chiều. Còn dashboard trình duyệt chủ yếu nhận dữ liệu realtime từ server, nên em dùng SSE để đơn giản hơn. Khi admin cần gửi lệnh như test alert hoặc bật/tắt monitoring thì vẫn dùng HTTP POST, sau đó server gửi lệnh xuống Jetson qua WebSocket. Cách này tách rõ vai trò từng giao thức.

---

## 6. Database, ORM và persistence

### 6.1 Vì sao cần database?

Nếu không có database, hệ thống chỉ hiển thị dữ liệu tạm thời. Khi tắt server sẽ mất:

- Danh sách xe.
- Danh sách tài xế.
- RFID và ảnh mặt.
- Lịch sử phiên lái.
- Lịch sử cảnh báo.
- Log vận hành/cập nhật nếu bật lại chức năng bảo trì từ xa.

Database giúp hệ thống có khả năng truy vết.

### 6.2 Vì sao dùng SQLite?

SQLite phù hợp với đồ án vì:

- Gọn, dễ triển khai.
- Không cần cài server database riêng.
- Đủ cho demo và quy mô nhỏ.
- Kết hợp SQLAlchemy async để tổ chức code sạch hơn.

Điểm cần nói cẩn thận:

> SQLite không phải lựa chọn tốt nhất cho hệ thống hàng nghìn xe production, nhưng phù hợp với đồ án demo, triển khai nhanh, ít phụ thuộc. Nếu mở rộng thực tế có thể chuyển sang PostgreSQL vì ORM đã tách phần model và query tương đối rõ.

### 6.3 ORM là gì?

ORM ánh xạ bảng database thành class Python.

Trong `WebQuanLi/app/models.py`:

- `User` tương ứng bảng users.
- `Vehicle` tương ứng bảng vehicles.
- `Driver` tương ứng bảng drivers.
- `DriverSession` tương ứng bảng driver_sessions.
- `SystemAlert` tương ứng bảng system_alerts.
- `HardwareStatus` tương ứng bảng hardware_statuses.
- `OtaAuditLog` tương ứng bảng ota_audit_logs.

Lợi ích:

- Code Python dễ đọc hơn viết SQL thủ công ở mọi nơi.
- Quan hệ giữa xe, tài xế, session, alert rõ hơn.
- Dễ test và mở rộng.

### 6.4 Dữ liệu nào nên lưu, dữ liệu nào chỉ realtime?

Không phải mọi dữ liệu đều cần lưu.

Dữ liệu nên lưu:

- Session start/end.
- Alert buồn ngủ.
- Face mismatch.
- Hardware status theo mốc thời gian.
- Log cập nhật/bảo trì nếu chức năng này được bật lại.
- Xe, tài xế, RFID, ảnh mặt.

Dữ liệu chỉ realtime hoặc cache:

- GPS gửi liên tục.
- Driver probe.
- Verify snapshot tức thời.
- Trạng thái tiến trình bảo trì nếu chức năng cập nhật từ xa được bật lại.

Lý do:

> Nếu lưu mọi GPS frame vào SQLite thì database dễ phình to và ảnh hưởng hiệu năng. Hệ thống chỉ lưu những dữ liệu có giá trị truy vết hoặc thống kê.

### 6.5 Câu trả lời mẫu

**Câu hỏi:** Vì sao GPS không nhất thiết phải ghi database liên tục?

**Trả lời mẫu:**

> GPS có tần suất cao, nếu mỗi giây hoặc nhiều lần mỗi giây đều ghi database thì SQLite sẽ chịu nhiều I/O không cần thiết. Trong đồ án của em, GPS chủ yếu phục vụ dashboard realtime, nên được publish qua EventBus để hiển thị ngay. Dữ liệu quan trọng như cảnh báo, session và face mismatch mới được lưu để truy vết.

---

## 7. Bảo mật: Authentication, Authorization, JWT, bcrypt

### 7.1 Authentication và Authorization khác nhau thế nào?

Authentication là xác định “bạn là ai”.

Authorization là xác định “bạn được làm gì”.

Trong đồ án:

- Người dùng đăng nhập bằng username/password.
- Server kiểm tra mật khẩu bằng bcrypt.
- Server tạo JWT token.
- Token lưu trong cookie `HttpOnly`.
- Một số API yêu cầu user hiện tại.
- Một số API nhạy cảm yêu cầu role admin.

### 7.2 Vì sao dùng bcrypt?

Không bao giờ lưu mật khẩu dạng plain text. Bcrypt là thuật toán hash mật khẩu một chiều:

- Có salt để cùng một mật khẩu vẫn ra hash khác nhau.
- Có cost factor làm brute force khó hơn.
- Khi login chỉ so sánh password nhập vào với hash đã lưu.

Nói đúng:

> Bcrypt không mã hóa để giải mã lại. Nó hash một chiều để kiểm tra mật khẩu.

### 7.3 Vì sao dùng JWT cookie?

JWT chứa thông tin như username, role, hạn token. Cookie `HttpOnly` giúp JavaScript phía browser không đọc trực tiếp token, giảm rủi ro XSS lấy token.

Trong đồ án, cookie có:

- `httponly=True`
- `samesite="lax"`
- `secure=True` khi chạy HTTPS
- `max_age` theo cấu hình thời hạn token

### 7.4 Câu trả lời mẫu

**Câu hỏi:** Nếu database bị lộ thì mật khẩu admin có bị đọc được không?

**Trả lời mẫu:**

> Không đọc trực tiếp được vì hệ thống không lưu mật khẩu gốc. Mật khẩu được hash bằng bcrypt có salt. Khi đăng nhập, server dùng bcrypt để kiểm tra mật khẩu nhập vào có khớp hash hay không, chứ không giải mã hash thành mật khẩu ban đầu.

---

## 8. AI phát hiện buồn ngủ: EAR, MAR, pitch, PERCLOS

### 8.1 Face landmarks là gì?

Face landmarks là các điểm mốc trên khuôn mặt do thư viện nhận diện cung cấp. Từ các điểm này có thể tính:

- Độ mở mắt.
- Độ mở miệng.
- Tư thế đầu.
- Vùng khuôn mặt.
- Chất lượng vùng mắt.

Trong repo, logic nằm chủ yếu ở:

- `Version3/camera/face_analyzer.py`
- `Version3/ai/drowsiness_classifier.py`
- `Version3/ai/feature_extractor.py`
- `Version3/ai/calibration.py`
- `Version3/ai/threshold_policy.py`

### 8.2 EAR là gì?

EAR là Eye Aspect Ratio, tỉ lệ hình học để ước lượng mắt mở hay nhắm.

Ý tưởng:

- Mắt mở: khoảng cách dọc giữa mí trên và mí dưới lớn, EAR cao hơn.
- Mắt nhắm: khoảng cách dọc nhỏ, EAR thấp hơn.

Nếu EAR thấp trong thời gian rất ngắn: có thể là chớp mắt.

Nếu EAR thấp kéo dài: có thể là buồn ngủ.

### 8.3 MAR là gì?

MAR là Mouth Aspect Ratio, dùng để ước lượng miệng mở.

Nếu MAR vượt ngưỡng trong thời gian đủ dài, hệ thống xem là ngáp. Ngáp đơn lẻ có thể chỉ là bình thường, nhưng ngáp lặp lại trong cửa sổ thời gian có thể tăng mức cảnh báo.

### 8.4 Pitch là gì?

Pitch là góc cúi/ngẩng đầu. Nếu pitch xuống thấp trong thời gian đủ dài, hệ thống có thể xem là cúi đầu hoặc mất tập trung.

### 8.5 PERCLOS là gì?

PERCLOS là tỉ lệ thời gian mắt đóng trong một cửa sổ thời gian. Đây là chỉ số thường dùng trong nghiên cứu mệt mỏi tài xế.

Trong đồ án:

- Classifier duy trì các cửa sổ mẫu ngắn và dài.
- Nếu tỉ lệ mắt đóng cao, tăng khả năng phân loại DROWSY.
- PERCLOS giúp hệ thống không chỉ nhìn một frame đơn lẻ, mà nhìn xu hướng theo thời gian.

### 8.6 Vì sao không chỉ dùng một frame?

Một frame có thể sai vì:

- Tài xế chớp mắt.
- Ánh sáng xấu.
- Kính phản chiếu.
- Face landmark không ổn định.
- Camera rung.

Vì vậy classifier dùng thời gian:

- Mắt nhắm dưới 0.35s: có thể là blink.
- Mắt nhắm từ khoảng 0.8s: bắt đầu cảnh báo nhẹ.
- Mắt nhắm lâu hơn: tăng mức cảnh báo.
- Miệng mở lâu: ngáp.
- Cúi đầu lâu: head down.

### 8.7 Câu trả lời mẫu

**Câu hỏi:** Làm sao phân biệt chớp mắt và ngủ gật?

**Trả lời mẫu:**

> Em không dựa vào một frame đơn lẻ. Hệ thống tính EAR theo chuỗi thời gian. Nếu EAR thấp rất ngắn thì classifier xem là blink. Nếu EAR thấp kéo dài qua các mốc thời gian như 0.8 giây, 1.8 giây, 3 giây thì hệ thống tăng mức cảnh báo. Ngoài ra còn kết hợp PERCLOS, MAR và pitch để giảm phụ thuộc vào một chỉ số duy nhất.

---

## 9. Calibration: Vì sao cần hiệu chỉnh theo tài xế?

### 9.1 Vấn đề nếu dùng ngưỡng cố định

Mỗi người có khuôn mặt và mắt khác nhau:

- Người mắt nhỏ có EAR mở mắt thấp hơn.
- Người đeo kính có thể làm landmark vùng mắt kém tin cậy.
- Vị trí camera làm góc pitch thay đổi.
- Ánh sáng IR/RGB khác nhau.

Nếu dùng một ngưỡng cố định cho mọi người thì dễ:

- Báo nhầm người bình thường là ngủ gật.
- Bỏ sót người thật sự đang buồn ngủ.

### 9.2 Calibration làm gì?

Trong `Version3/ai/calibration.py`, hệ thống thu các mẫu ban đầu khi tài xế ở trạng thái bình thường, rồi tính median:

- EAR khi mắt mở.
- MAR khi miệng đóng.
- Pitch trung tính.
- Chiều cao khuôn mặt.
- EAR từng mắt.

Sau đó tạo ngưỡng:

- `ear_closed_threshold`
- `mar_yawn_threshold`
- `pitch_down_threshold`

Nếu mẫu không đủ hoặc chất lượng kém, hệ thống dùng fallback an toàn.

### 9.3 Vì sao dùng median?

Median bền hơn average khi có outlier. Ví dụ một vài frame bị landmark sai sẽ ít làm lệch median hơn.

### 9.4 Câu trả lời mẫu

**Câu hỏi:** Nếu người tài xế mắt nhỏ thì hệ thống có báo nhầm không?

**Trả lời mẫu:**

> Em có cơ chế calibration theo tài xế. Khi bắt đầu session, hệ thống thu mẫu khuôn mặt bình thường và tính median EAR, MAR, pitch để tạo ngưỡng phù hợp hơn với người đó. Nếu mẫu không đủ hoặc khuôn mặt quá nhỏ, hệ thống không dùng ngưỡng sai mà quay về fallback threshold an toàn.

---

## 10. State machine: Trạng thái hệ thống

### 10.1 Vì sao cần state machine?

Nếu code chỉ dùng nhiều biến boolean rời rạc như `is_running`, `is_verifying`, `is_updating`, hệ thống dễ rơi vào trạng thái mâu thuẫn:

- Vừa đang trong chế độ cập nhật/bảo trì vừa đang chạy AI.
- Chưa xác thực tài xế nhưng vẫn gửi session_start.
- Đang mismatch nhưng vẫn cho chạy bình thường.

State machine ép hệ thống đi qua các trạng thái hợp lệ.

### 10.2 Các trạng thái chính

Trong `Version3/state_machine.py`:

- `BOOTING`: đang khởi động.
- `IDLE`: sẵn sàng, chưa có session lái.
- `VERIFYING_DRIVER`: đang xác thực tài xế.
- `RUNNING`: đang giám sát lái xe.
- `MISMATCH_ALERT`: phát hiện sai tài xế/khuôn mặt không khớp.
- `OFFLINE_DEGRADED`: mạng lỗi, hệ thống chạy giảm cấp.
- `UPDATING`: đang cập nhật phần mềm.

### 10.3 Tư duy chuyển trạng thái

Ví dụ:

- `BOOTING -> IDLE`: khởi động xong.
- `IDLE -> VERIFYING_DRIVER`: quét RFID.
- `VERIFYING_DRIVER -> RUNNING`: xác thực thành công.
- `VERIFYING_DRIVER -> MISMATCH_ALERT`: mặt không khớp.
- `RUNNING -> IDLE`: kết thúc session.
- `RUNNING -> OFFLINE_DEGRADED`: mất kết nối.
- `RUNNING -> UPDATING`: nhận lệnh cập nhật/bảo trì nếu chức năng này được bật.

### 10.4 Câu trả lời mẫu

**Câu hỏi:** State machine giúp gì cho đồ án?

**Trả lời mẫu:**

> State machine giúp hệ thống không chạy lẫn trạng thái. Ví dụ thiết bị chỉ vào RUNNING sau khi xác thực tài xế, chỉ vào UPDATING khi nhận lệnh cập nhật hợp lệ, và có trạng thái MISMATCH_ALERT khi phát hiện sai người. Nhờ vậy luồng vận hành rõ ràng hơn, dễ debug và dễ giải thích trước hội đồng.

---

## 11. Cảnh báo 3 mức và hysteresis

### 11.1 Vì sao có nhiều mức cảnh báo?

Buồn ngủ không phải lúc nào cũng nghiêm trọng ngay. Hệ thống chia mức:

- Level 1 / WARNING: dấu hiệu nhẹ như ngáp, mắt nhắm ngắn.
- Level 2 / DANGER: dấu hiệu rõ hơn như mắt nhắm lâu, cúi đầu, PERCLOS cao.
- Level 3 / CRITICAL: nguy hiểm cao, mắt nhắm rất lâu hoặc lặp lại nhiều lần.

### 11.2 AlertManager làm gì?

Trong `Version3/alerts/alert_manager.py`, AlertManager:

- Nhận metrics và kết quả AI.
- Quy đổi `alert_hint` thành level.
- Theo dõi thời gian EAR thấp.
- Theo dõi số lần ngáp.
- Cooldown để tránh phát cảnh báo liên tục quá dày.
- Kích hoạt buzzer, LED, speaker theo từng mức.
- Gọi callback `_on_alert` để gửi event lên WebQuanLi.

### 11.3 Hysteresis/cooldown là gì?

Hysteresis và cooldown giúp tránh cảnh báo nhấp nháy. Nếu level thay đổi liên tục từng frame, hệ thống sẽ gây khó chịu và khó tin cậy. Cooldown chỉ cho đổi mức sau một khoảng thời gian, trừ khi mức mới nghiêm trọng hơn.

### 11.4 Câu trả lời mẫu

**Câu hỏi:** Vì sao không cứ thấy mắt nhắm là báo động luôn?

**Trả lời mẫu:**

> Vì nhắm mắt trong thời gian rất ngắn có thể chỉ là chớp mắt. Hệ thống dùng chuỗi thời gian và chia mức cảnh báo. Mắt nhắm ngắn được xem là blink hoặc eyes closed nhẹ, còn mắt nhắm kéo dài mới tăng lên WARNING, DANGER hoặc CRITICAL. AlertManager cũng có cooldown để tránh cảnh báo nhấp nháy liên tục.

---

## 12. RFID và xác thực khuôn mặt

### 12.1 RFID dùng để làm gì?

RFID xác định người đang cố bắt đầu phiên lái. Mỗi tài xế có một `rfid_tag` trong WebQuanLi.

Khi quét thẻ:

1. Jetson đọc UID.
2. Jetson phát driver event lên WebQuanLi để dashboard biết ai vừa quét.
3. Jetson xác thực khuôn mặt dựa trên ảnh tham chiếu local.
4. Nếu khớp, session bắt đầu.
5. Nếu không khớp, phát face mismatch.

### 12.2 Vì sao không chỉ dùng RFID?

RFID có thể bị mượn thẻ. Khuôn mặt giúp xác thực người cầm thẻ có đúng là tài xế được đăng ký không.

### 12.3 Driver registry là gì?

Driver registry là cache local trên Jetson chứa:

- RFID của tài xế.
- Tên tài xế.
- Ảnh mặt tham chiếu.
- Metadata nguồn ảnh.

WebQuanLi quản lý dữ liệu tài xế, còn Jetson cần bản local để xác thực offline hoặc giảm phụ thuộc vào web.

### 12.4 Câu trả lời mẫu

**Câu hỏi:** Nếu người khác cầm thẻ RFID của tài xế thì sao?

**Trả lời mẫu:**

> RFID chỉ là bước nhận dạng ban đầu. Sau khi quét thẻ, Jetson còn xác thực khuôn mặt với ảnh tham chiếu trong driver registry local. Nếu khuôn mặt không khớp, hệ thống gửi face_mismatch, cảnh báo lên dashboard và không cho bắt đầu session hợp lệ trong chế độ strict.

---

## 13. Offline-first và local queue

### 13.1 Vì sao cần local queue?

Xe có thể mất mạng khi:

- Đi vào hầm.
- Vùng sóng yếu.
- Router/4G lỗi.
- Server tạm thời không truy cập được.

Nếu sự kiện bị drop ngay khi mất mạng thì mất dữ liệu quan trọng. Local queue trong `Version3/storage/local_queue.py` lưu sự kiện vào SQLite local.

### 13.2 Local queue hoạt động thế nào?

1. WSClient không gửi trực tiếp ngay mà push message vào queue.
2. Khi WebSocket kết nối ổn định, flush loop lấy batch từ queue.
3. Gửi thành công thì đánh dấu sent và cleanup.
4. Nếu offline thì queue giữ lại.
5. Queue có priority để alert/session quan trọng hơn GPS/hardware.
6. Một số loại như GPS/hardware được coalesce, nghĩa là chỉ giữ bản mới nhất để không phình dữ liệu.

### 13.3 Vì sao cần priority?

Khi mạng trở lại, không nên gửi mọi thứ như nhau. Cảnh báo và session quan trọng hơn heartbeat hoặc GPS cũ. Priority giúp dữ liệu quan trọng được gửi trước.

### 13.4 Câu trả lời mẫu

**Câu hỏi:** Nếu xe mất mạng 30 phút thì dữ liệu cảnh báo có mất không?

**Trả lời mẫu:**

> Jetson có local queue SQLite để lưu sự kiện khi WebSocket offline. Các message như session_start, session_end, alert được ưu tiên cao. Khi mạng kết nối lại, WSClient flush queue lên WebQuanLi. Với dữ liệu tần suất cao như GPS và hardware, hệ thống coalesce để tránh queue phình quá lớn, còn dữ liệu quan trọng vẫn được giữ.

---

## 14. EventBus và realtime dashboard

### 14.1 EventBus là gì?

EventBus trong `WebQuanLi/app/core/event_bus.py` là cầu nối trong RAM giữa:

- WebSocket handler nhận dữ liệu từ Jetson.
- SSE endpoint gửi dữ liệu xuống browser.

Nó giúp WebSocket handler không cần biết đang có bao nhiêu browser xem dashboard.

### 14.2 Vì sao cần queue cho từng subscriber?

Mỗi browser có tốc độ nhận khác nhau. Nếu một browser chậm, không nên làm nghẽn toàn bộ server. EventBus tạo queue riêng cho từng subscriber.

Queue có max size để tránh đầy RAM. Nếu queue đầy, hệ thống bỏ bớt frame cũ và giữ frame mới hơn.

### 14.3 Cache state mới nhất để làm gì?

Khi một browser mới mở dashboard, nó cần biết trạng thái hiện tại. EventBus lưu `_vehicle_state` để khi subscribe mới có thể nhận các event mới nhất như GPS/hardware/driver.

### 14.4 Câu trả lời mẫu

**Câu hỏi:** Nếu nhiều người mở dashboard cùng lúc thì dữ liệu realtime chạy thế nào?

**Trả lời mẫu:**

> Mỗi dashboard subscribe vào EventBus qua SSE. EventBus tạo queue riêng cho từng subscriber nên một browser chậm không chặn browser khác. WebSocket từ Jetson chỉ publish một lần vào EventBus, sau đó EventBus phân phối cho các subscriber đang xem xe đó.

---

## 15. Cập nhật/bảo trì từ xa và trạng thái OTA hiện tại

### 15.1 OTA là gì?

OTA là cập nhật phần mềm từ xa. Về mặt ý tưởng, hệ thống có thể có luồng:

- Admin upload file `.py` hoặc `.zip` lên WebQuanLi.
- WebQuanLi kiểm tra tên file, định dạng, checksum.
- WebQuanLi lưu file trong static updates.
- Nếu Jetson online, server gửi command `update_software` qua WebSocket.
- Jetson tải file từ `download_url` và xử lý cập nhật.

Tuy nhiên, theo trạng thái project hiện tại, không nên trình bày OTA như chức năng demo chính đang mở cho người dùng. Trong `WebQuanLi/app/api/control.py`, route `/api/vehicles/{vehicle_id}/update` đang trả HTTP 410 với thông báo OTA đã bị vô hiệu hóa và hướng cập nhật Jetson qua NoMachine/SSH. Vì vậy khi bảo vệ, cách nói an toàn là:

> Project có thiết kế command hai chiều qua WebSocket nên về mặt kiến trúc có thể mở rộng cho OTA. Nhưng trong bản demo hiện tại, em vô hiệu hóa upload OTA trên WebQuanLi để tránh rủi ro cập nhật nhầm trong lúc trình bày. Việc cập nhật Jetson được thực hiện thủ công qua SSH/NoMachine.

### 15.2 Vì sao cần checksum?

Checksum SHA-256 giúp xác minh file Jetson tải về đúng với file server lưu. Nếu file bị lỗi hoặc thay đổi, checksum không khớp.

### 15.3 Vì sao phải validate file OTA?

Upload file là điểm nhạy cảm. Hệ thống kiểm tra:

- Tên file không chứa `/`, `\`, `..`.
- Chỉ cho `.py` hoặc `.zip`.
- Zip phải có `manifest.json`.

Điều này giảm rủi ro path traversal hoặc upload nội dung không mong muốn.

### 15.4 Câu trả lời mẫu

**Câu hỏi:** OTA có rủi ro bảo mật không?

**Trả lời mẫu:**

> Có. Vì vậy trong bản demo hiện tại em không mở upload OTA như một chức năng vận hành chính trên dashboard. Phần điều khiển từ xa vẫn còn ý tưởng kiến trúc qua WebSocket, nhưng cập nhật thật được làm thủ công qua SSH/NoMachine để giảm rủi ro trong demo. Nếu bật lại OTA cho môi trường thật thì cần giới hạn quyền admin, kiểm tra tên file, chặn path traversal, kiểm tra định dạng gói, checksum và có cơ chế rollback.

---

## 16. Lịch sử, thống kê và timezone

### 16.1 Vì sao phải quan tâm timezone?

Server và database thường lưu UTC để thống nhất. Người dùng Việt Nam cần xem giờ Việt Nam. Nếu lọc theo ngày mà không đổi timezone đúng, dữ liệu ngày 28 có thể bị lệch sang ngày 27 hoặc 29.

Trong WebQuanLi có `time_service.py` để:

- Chuyển datetime sang giờ Việt Nam.
- Format thời gian hiển thị.
- Chuyển ngày local thành khoảng UTC để query database.

### 16.2 Retention là gì?

Retention là chính sách giữ dữ liệu trong một thời gian nhất định. Ví dụ chỉ giữ alert trong số ngày cấu hình để database không phình mãi.

Trong `history_service.py`, hệ thống có purge old alerts khi startup.

### 16.3 Câu trả lời mẫu

**Câu hỏi:** Vì sao em lưu UTC nhưng hiển thị giờ Việt Nam?

**Trả lời mẫu:**

> Lưu UTC giúp database nhất quán và tránh lỗi khi server đổi timezone. Khi hiển thị hoặc lọc theo ngày cho người dùng Việt Nam, em chuyển đổi qua Asia/Saigon. Nhờ vậy truy vấn lịch sử theo ngày không bị lệch do chênh múi giờ.

---

## 17. Testing: chứng minh hệ thống đúng

### 17.1 Vì sao test quan trọng khi bảo vệ?

Test giúp bạn nói với hội đồng:

> Đây không chỉ là demo chạy được một lần. Em có test để kiểm tra contract WebSocket, thuật toán AI, luồng session, queue offline, API validation, auth cookie, lịch sử và dashboard.

### 17.2 Các nhóm test trong repo

Trong `Version3/tests`:

- Test classifier buồn ngủ.
- Test calibration.
- Test threshold policy.
- Test RFID, GPS parser.
- Test WebSocket queue hardening.
- Test offline reconnect.
- Test verify flow.
- Test contract với WebQuanLi.
- Test dashboard local.

Trong `WebQuanLi/tests`:

- Test auth cookie security.
- Test API validation contract.
- Test dashboard realtime context.
- Test driver registry sync.
- Test websocket contract fixtures.
- Test history/timezone/retention.
- Test alert history filters.

### 17.3 Câu trả lời mẫu

**Câu hỏi:** Em chứng minh hai bên Jetson và WebQuanLi nói cùng một kiểu dữ liệu thế nào?

**Trả lời mẫu:**

> Em có test contract dùng payload fixture chung. Phía Version3 sinh các message như alert, hardware, verify_snapshot; phía WebQuanLi có Pydantic schema để parse. Test đảm bảo payload Jetson gửi vẫn khớp schema WebQuanLi nhận, tránh lỗi hai bên phát triển lệch nhau.

---

## 18. Các câu hỏi phản biện nền tảng thường gặp

### 18.1 Vì sao không dùng React?

**Trả lời mẫu:**

> Dashboard của em thiên về quản trị và realtime đơn giản, không cần SPA phức tạp. Em dùng Jinja2 render server-side kết hợp HTMX và SSE để cập nhật từng phần giao diện. Cách này giảm số lượng project phải bảo trì, phù hợp đồ án Python/FastAPI và dễ debug hơn.

### 18.2 Vì sao không dùng MQTT?

**Trả lời mẫu:**

> MQTT rất phù hợp IoT quy mô lớn, nhưng đồ án hiện cần kênh hai chiều trực tiếp giữa Jetson và FastAPI, đồng thời muốn giảm phụ thuộc broker ngoài. WebSocket đáp ứng tốt yêu cầu demo, dễ tích hợp với FastAPI và command từ web xuống thiết bị. Nếu mở rộng đội xe lớn, MQTT broker có thể là hướng nâng cấp.

### 18.3 Nếu camera lỗi thì sao?

**Trả lời mẫu:**

> Jetson có hardware monitor gửi trạng thái camera lên WebQuanLi. Dashboard hiển thị trạng thái phần cứng để quản lý biết thiết bị có vấn đề. Về phía AI, nếu không có face/camera thì classifier không tạo kết luận buồn ngủ sai từ dữ liệu thiếu, mà phản ánh trạng thái no face hoặc low confidence.

### 18.4 Nếu GPS không có fix thì sao?

**Trả lời mẫu:**

> GPS payload có phân biệt UART hoạt động và GPS fix. Nghĩa là thiết bị có thể đọc được module GPS nhưng chưa có tọa độ hợp lệ. Dashboard có thể hiển thị trạng thái đó thay vì hiểu nhầm là toàn bộ GPS hỏng.

### 18.5 Nếu server tắt rồi bật lại thì sao?

**Trả lời mẫu:**

> Dữ liệu đã commit vào database vẫn còn. Khi Jetson reconnect, WSClient gửi hardware snapshot và flush local queue nếu còn sự kiện offline. WebQuanLi khởi động sẽ init database và purge dữ liệu alert cũ theo retention policy.

### 18.6 Nếu nhiều alert trùng nhau thì sao?

**Trả lời mẫu:**

> Phía Jetson có cooldown ở AlertManager để tránh bắn liên tục. Phía WebQuanLi khi có timestamp từ thiết bị cũng kiểm tra duplicate theo vehicle, alert type, level, timestamp và session để tránh ghi lặp cùng một sự kiện.

---

## 19. Cách học C1 trong 7 ngày

### Ngày 1: Nắm kiến trúc

Học:

- Mục 1, 2, 3.
- Vẽ lại luồng Jetson -> WebQuanLi -> Dashboard.

Tự trả lời:

- Vì sao AI chạy ở Jetson?
- WebQuanLi đóng vai trò gì?
- Dữ liệu đi qua những bước nào?

### Ngày 2: Giao tiếp mạng

Học:

- HTTP API.
- WebSocket.
- SSE.
- EventBus.

Tự trả lời:

- Vì sao Jetson dùng WebSocket?
- Vì sao dashboard dùng SSE?
- EventBus giải quyết vấn đề gì?

### Ngày 3: Database và bảo mật

Học:

- ORM.
- SQLite.
- JWT.
- bcrypt.
- phân quyền admin.

Tự trả lời:

- Authentication khác Authorization thế nào?
- Vì sao không lưu mật khẩu gốc?
- Dữ liệu nào được lưu database?

### Ngày 4: AI nền tảng

Học:

- EAR.
- MAR.
- Pitch.
- PERCLOS.
- Chuỗi thời gian.

Tự trả lời:

- Làm sao phân biệt blink và drowsy?
- Vì sao không dựa vào một frame?

### Ngày 5: Calibration và Alert

Học:

- Calibration theo tài xế.
- ThresholdPolicy.
- Alert levels.
- Cooldown/hysteresis.

Tự trả lời:

- Vì sao cần ngưỡng riêng theo người?
- Khi nào lên Level 1, 2, 3?

### Ngày 6: Offline và bảo trì từ xa

Học:

- LocalQueue.
- Auto reconnect.
- Priority.
- Trạng thái OTA hiện tại: đã vô hiệu hóa upload trên dashboard, cập nhật Jetson thủ công qua SSH/NoMachine.

Tự trả lời:

- Mất mạng thì dữ liệu nào còn?
- Khi mạng có lại, hệ thống gửi dữ liệu thế nào?
- Vì sao demo không nên mở OTA upload trực tiếp?

### Ngày 7: Test và luyện nói

Học:

- Nhóm test trong Version3 và WebQuanLi.
- Các câu hỏi phản biện mục 18.

Luyện:

- Nói kiến trúc trong 2 phút.
- Nói luồng alert trong 3 phút.
- Nói bảo mật trong 1 phút.
- Nói offline queue trong 1 phút.

---

## 20. Bản nói nhanh 90 giây

Bạn có thể luyện thuộc ý, không cần thuộc từng chữ:

> Đồ án của em là hệ thống giám sát buồn ngủ tài xế theo mô hình Edge IoT. Trên xe, Jetson đọc camera, RFID, GPS và chạy AI tại chỗ để phát hiện trạng thái như blink, drowsy, yawning, head down. Khi có cảnh báo, Jetson kích hoạt loa, buzzer, LED và gửi JSON lên DrowsiGuard Monitoring Hub qua WebSocket. Phần Monitoring Hub dùng FastAPI làm backend, SQLAlchemy async với SQLite để lưu xe, tài xế, session và alert. Dữ liệu realtime từ Jetson được đưa vào EventBus rồi phát xuống dashboard bằng SSE, nên người quản lý thấy trạng thái xe ngay mà không cần refresh. Hệ thống có JWT cookie và bcrypt cho bảo mật, calibration để thích nghi từng tài xế, local queue để chịu lỗi mất mạng, và các test contract để đảm bảo payload giữa Jetson và WebQuanLi không lệch nhau. Trong demo hiện tại, kết nối WebSocket được cấu hình qua Tailscale để ổn định hơn IP LAN thay đổi.

---

## 21. Checklist trước khi chuyển sang C2

Bạn nên tự trả lời được các câu sau trước khi đọc tài liệu giải thích code:

- Hệ thống có mấy khối chính?
- Jetson xử lý gì, WebQuanLi xử lý gì?
- WebSocket khác SSE thế nào?
- EventBus nằm ở đâu trong kiến trúc?
- EAR, MAR, pitch, PERCLOS là gì?
- Calibration giải quyết vấn đề gì?
- Local queue giúp gì khi mất mạng?
- Database lưu những bảng nào?
- JWT cookie và bcrypt bảo vệ phần nào?
- Test contract chứng minh điều gì?

Nếu trả lời được 70% số câu trên, bạn đã đủ nền để đọc C2.

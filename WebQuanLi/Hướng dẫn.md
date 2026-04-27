# Hướng dẫn chi tiết hệ thống WebQuanLi — Drowsiness Warning System

Hệ thống **WebQuanLi** là trang Dashboard (quản trị) đóng vai trò trung tâm giám sát cho phần cứng nhận diện buồn ngủ chạy trên Jetson Nano. Hệ thống có khả năng nhận luồng dữ liệu realtime, hiển thị thông số phần cứng, định vị GPS, điều khiển OTA (cập nhật phần mềm) và gửi thông báo SMS tự động.

---

## 1. Công nghệ sử dụng (Stack Công Nghệ)

- **Ngôn ngữ lập trình:** Python 3 (Backend), HTML/CSS/JavaScript (Frontend).
- **Backend Framework:** **FastAPI**. Được chọn vì tốc độ thực thi rất nhanh, mặc định hỗ trợ ASGI (bất đồng bộ) phù hợp cho việc xử lý hàng loạt tín hiệu từ WebSocket.
- **Web Server:** **Uvicorn** dùng làm server ASGI chạy ứng dụng FastAPI.
- **Frontend & Giao diện:** Thiết kế không dùng framework nặng như React/Vue mà xài giao diện render phía server (Jinja2) kết hợp với **HTMX**. HTMX hỗ trợ extension `sse` (Server-Sent Events) giúp giao diện tự động cập nhật mà không cần F5 khi có dữ liệu từ backend.
- **Giao diện bản đồ:** Dùng **Leaflet.js** (open-source) giao diện Dark Mode (`CartoDB.DarkMatter`).
- **Biểu đồ thống kê:** **Chart.js**.
- **Cơ sở dữ liệu:** **SQLite** (thư viện `aiosqlite`) xử lý bất đồng bộ để lưu log sự kiện, tài xế không gây tắc nghẽn server. Sử dụng **SQLAlchemy 2.0** ORM.
- **Xác thực:** **JWT (JSON Web Token)** lưu trong cookie (HttpOnly) nhằm cấp quyền cho Admin thao tác nhạy cảm.
- **SMS API:** **eSMS.vn** sử dụng SMS CSKH (SmsType=2) để lập tức gửi cảnh báo sai khuôn mặt. Khởi chạy HTTP Call bằng thư viện `httpx` async.

---

## 2. Kiến trúc và Luồng Dữ liệu (Architecture)

1. **Jetson Nano (Client)** gửi dữ liệu qua **WebSocket** (2 chiều) về Server.
2. Tại Server (`jetson_handler.py`), dữ liệu được Parser JSON, lưu vào SQLite Database.
3. Đồng thời Server dùng **Event Bus** (RAM/Memory Queue) phát Broadcast các Data này ra dạng luồng sự kiện.
4. Ở cổng Frontend, kết nối **SSE (Server-Sent Events)** của trình duyệt tự động hứng Event Bus này để đắp hiển thị Realtime lên UI (cả map, thông tin, bảng log, timer).
5. Khi người quản lý (Admin) bấm nút **Update**, Frontend gửi API qua qua cổng POST Server, Server lưu File và bắn lệnh ngược về cho Jetson qua chính WebSocket ban đầu.

---

## 3. Cấu trúc Thư mục và Chức năng từng file

```text
d:\CodingAntigravity\CodeEnhance\WebQuanLi\
├── app/
│   ├── config.py           # Quản lý cấu hình (Load từ .env), chứa thông tin cổng eSMS, database, JWT settings.
│   ├── database.py         # Khởi tạo kết nối SQLite dạng bất đồng bộ và tạo tài khoản Admin + Xe Demo ban đầu.
│   ├── models.py           # Định nghĩa cấu trúc các bảng SQL: User, Vehicle, Driver, HardwareStatus, DriverSession, SystemAlert.
│   ├── schemas.py          # Pydantic Objects quy định chặt chẽ Data nhận vào và xuất ra từ API (Xác thực dữ liệu JSON).
│   ├── main.py             # File khởi chạy gốc, kết nối tất cả các Endpoint Router lại với nhau. Cấu hình Static folder.
│   │
│   ├── auth/               # Module Xác Thực (Authentication)
│   │   ├── utils.py        # Chứa logic băm mật khẩu (bcrypt) và tạo JWT Token.
│   │   ├── dependencies.py # Logic chặn người dùng chưa đăng nhập, hoặc chặn thao tác cấm của tài khoản thường (chỉ cấp cho admin).
│   │   └── router.py       # API cho màn hình Đăng Nhập, Đăng Xuất.
│   │
│   ├── api/                # Module API & Giao diện trang chính
│   │   ├── dashboard.py    # Render màn hình Dashboard tổng quan.
│   │   ├── pages.py        # Render ra các màn hình thống kê, lịch sử, hạm đội (fleet). Cung cấp API báo cáo 7 ngày / heatmap.
│   │   ├── vehicles.py     # API dạng REST để Thêm, xóa, sửa Thông tin Biển số Xe và thông tin Tài xế (Kèm upload ảnh khuôn mặt lưu vào static).
│   │   ├── alerts.py       # API truy xuất tìm kiếm log Cảnh báo cho Trang lịch sử.
│   │   ├── sessions.py     # API cung cấp thông tin "Ca Làm việc" của tài xế.
│   │   ├── sse.py          # [QUAN TRỌNG] Chức năng mở cổng Streaming dữ liệu Event liên tục cho màn hình HTML từ EventBus.
│   │   └── control.py      # [QUAN TRỌNG] Endpoint cho phép người dùng Upload file .py (OTA) qua form và bắn Lệnh thử Còi/Loa mức độ.
│   │
│   ├── ws/
│   │   └── jetson_handler.py # [LÕI LOGIC] Xử lý WebSocket của các thiết bị Jetson truyền Data lên, nhận diện tài xế RFID, đếm giờ ca.
│   │
│   ├── services/
│   │   └── sms_service.py  # Service dùng httpx tương tác với Hệ thống eSMS, tự động bắn vào SĐT khi báo lỗi.
│   │
│   └── core/
│       └── event_bus.py    # Phân phối, Bridge stream liên tục các event (không chạm database) cho mượt.
│
├── static/                 # Tài nguyên cố định cho Web
│   ├── css/style.css       # File định dạng thiết kế giao diện (Dark mode công nghiệp, hiệu ứng cảnh báo nháy đỏ).
│   ├── js/map.js           # Khởi tạo Leaflet bản đồ GPS.
│   ├── js/charts.js        # Khởi tạo vẽ 3 biểu đồ thống kê Chart.js.
│   ├── js/session_timer.js # Đoạn script đếm realtime ca làm việc của tài xế.
│   └── updates/            # Thư mục lưu tạm (Cache) các file update .py tải xuống để chờ Jetson tự lấy về.
│
├── templates/              # File HTML giao diện
│   ├── base.html           # File khung chứa toàn bộ thanh điều hướng, script tải sẵn.
│   ├── login.html          # HTML trang đăng nhập hệ thống.
│   ├── dashboard.html      # Trang hiển thị Web quan trắc.
│   ├── statistics.html     # Trang hiển thị thông số hiệu suất KPI xe.
│   ├── history.html        # Trang Log Filter.
│   ├── fleet.html          # Quản lý cấu hình danh sách.
│   └── partials/           # Thành phần UI nhỏ có khả năng tự thay thế bằng HTMX (chỉ load lại đúng chỗ không F5 cả trang).
│       ├── hardware_status.html
│       ├── driver_info.html
│       ├── alert_log.html
│       ├── map_data.html
│       └── admin_controls.html
│
├── requirements.txt        # Các thư viện python bắt buộc.
└── .env                    # Biến khóa và cấu hình tài khoản (Secret, ESMS_API_KEY).
```

---

## 4. Cách khởi chạy dự án

**Bước 1: Cài đặt thư viện**
```bash
pip install -r requirements.txt
```

*(Nếu thiếu thư viện, có thể cài thêm: `pip install python-dotenv`)*

**Bước 2: Khởi động Server**
Bạn mở terminal truy cập vào thư mục `WebQuanLi` và chạy:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--reload` giúp tự khởi động lại khi có thay đổi code. Server sẽ thiết lập CSDL `sqlite` tự do và tạo Admin.

**Bước 3: Sử dụng**
Vào trình duyệt Mở `http://localhost:8000`
- User: `minhtung2003`
- Pass: `tungtungIUH`
(Đây là user mặc định được tạo từ `.env` và `database.py`).

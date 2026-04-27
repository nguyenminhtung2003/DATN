# GIÁO TRÌNH BẢO VỆ ĐỒ ÁN TỐT NGHIỆP: HỆ THỐNG WEBQUANLI

Chào mừng bạn đến với tài liệu hướng dẫn chuyên sâu. Kỷ yếu đồ án thường sẽ tập trung vào lý thuyết, nhưng khi bạn đứng trước hội đồng, Giảng viên phản biện sẽ hỏi thẳng vào **Luồng code (Logic)** và **Cách tối ưu hệ thống**. Tài liệu này đóng vai trò như "Phao cứu sinh" giúp bạn làm chủ 100% dòng code do chính mình mang lên bảo vệ.

---

## 🛑 PHẦN 1: TỔNG QUAN KIẾN TRÚC MẠNG (CẦN NẮM VỮNG)

Hội đồng thường hỏi: *"Cấu trúc luồng chạy của hệ thống em thế nào?"*

**Bạn trả lời:** Hệ thống tuân theo mô hình **Client-Server-Client**, vận hành theo nguyên lý **Event-Driven (Hướng sự kiện)**:
1. **IoT Client (Jetson Nano):** Mở 1 kênh truyền `WebSocket` 2 chiều liên tục với Server. Báo cáo GPS, Phần cứng, và Alert.
2. **Server Middleware (FastAPI):** Nhận Data. Mở Database lưu vào SQLite (nếu là cảnh báo), rồi ném tín hiệu vào `EventBus` (Trạm chung chuyển RAM).
3. **Web Client (Trình duyệt):** Mở 1 đường hầm `SSE (Server-Sent Events)` một chiều để "hứng" data từ `EventBus`. Ngay khi EventBus có dữ liệu, HTML thay đổi tức thời không cần F5.

---

## 📋 PHẦN 2: DANH SÁCH FILE & LOGIC TRỌNG TÂM CẦN HỌC THUỘC (CHEAT SHEET)

Dưới đây là danh sách liệt kê chính xác những file quan trọng nhất định bạn phải mở ra đọc hiểu và nắm chắc mục đích của nó:

1. **`app/main.py`**: Trái tim khởi động. Nắm được luồng Khởi động (`lifespan`) -> Tạo Database -> Mount API/Tĩnh.
2. **`app/database.py`**: Chứa code tạo tài khoản Admin mặc định (`init_db`) và cơ chế bất đồng bộ SQLite (`async_sessionmaker`).
3. **`app/ws/jetson_handler.py`**: File **Xương Sống** của mạng WebSocket. Chứa Logic hứng tín hiệu GPS, Cache bộ nhớ RAM và lưu Log Cảnh báo.
4. **`app/core/event_bus.py`**: Mã nguồn dùng `asyncio.Queue` để bóc tách luồng Websocket sang SSE mà không treo server. 
5. **`app/api/sse.py`**: API duy nhất cấp liên kết `EventSourceResponse` (Mạch tuần hoàn máu) cho HTML Frontend móc vào.
6. **`app/services/sms_service.py`**: Nơi thực thi hàm gửi Request POST đến eSMS để gửi tin nhắn cảnh báo bảo mật tài xế.
7. **`templates/dashboard.html`**: Code giao diện chính. Chú ý các Tag `<div hx-ext="sse"...>` của thư viện HTMX.

---

## 📂 PHẦN 3: BÓC TÁCH CÁC ĐOẠN CODE "ĂN ĐIỂM" CHÍNH XÁC

Khi được yêu cầu biểu diễn code, hãy mở các file sau ra để show quy trình xử lý chuyên nghiệp:

### 1. File Trung tâm: `app/ws/jetson_handler.py` (Lõi WebSocket)
> **Tại sao quan trọng?** Đây là nơi hứng 100% dữ liệu từ mạch phần cứng. Giám khảo chắc chắn sẽ hỏi về nơi nhận GPS.

**Đoạn Code Trọng Tâm:** (Hàm `jetson_websocket`)
```python
@router.websocket("/ws/jetson/{device_id}")
async def jetson_websocket(ws: WebSocket, device_id: str):
    await manager.connect(device_id, ws) # Chấp nhận kết nối
    ...
    # Lấy thông tin xe 1 LẦN DUY NHẤT để Cache (TỐI ƯU CƠ SỞ DỮ LIỆU)
    async with async_session_factory() as db:
        vehicle = ... 
        vid = vehicle.id
    
    while True: # Vòng lặp Vô Hình chờ tín hiệu
        raw = await ws.receive_text()
        msg_type = data.get("type", "") # gps, alert, hardware...
        ...
```
**Cách "khoe" với hội đồng:** *"Dạ thưa thầy/cô, để tránh làm sập Database khi xe gửi 10 tọa độ GPS mỗi giây, em đã áp dụng kỹ thuật **Local Cache** (Lưu tạm vào RAM). Em bắt code chỉ Query Database 1 lần lúc xe khởi động để lấy `vehicle_id`. Các tin nhắn GPS hay Driver sau đó chỉ dùng biến Cache này để ném qua EventBus mà không Query (SELECT SQL) cẩu thả gây Deadlock khóa chết Database."*

### 2. File Trạm Trung Chuyển: `app/core/event_bus.py`
> **Tại sao quan trọng?** Xử lý Realtime. Đa số sinh viên dùng WebSockets cho cả 2 kênh gây lag chéo ảnh hưởng hiệu năng.

**Cách vận hành:**
Nó chỉ rỗng tuếch thế này thôi:
```python
class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    
    async def publish(self, channel: str, event: str, data: Any): ...
    async def subscribe(self, channel: str): ...
```
**Cách giải thích:** *"Thay vì bắt Server phải gửi từng tin cho 10 người đang xem Web dẫn đến ngẽn mạng, em xây dựng **EventBus** bằng `asyncio.Queue` (Hàng đợi bất đồng bộ). Data từ Jetson ném vào Bus -> Bus sẽ tự động đẻ ra các nhánh nhỏ vứt Data về phía Web Frontend."*

### 3. Cập Nhật Giao Diện: `templates/dashboard.html` (HTMX & SSE)
> **Tại sao quan trọng?** Giải thích được lý do web chạy mượt mà không load lại trang.

**Đoạn Code Trọng Tâm:**
```html
<div hx-ext="sse" sse-connect="/api/sse/vehicle/{{ device_id }}">
    <div sse-swap="alert" hx-swap="afterbegin" hx-target="#alert-log-body">
         <!-- Data báo động tự chèn vào đây -->
    </div>
</div>
```
**Cách giải thích:** *"Em không dùng polling (5 giây hỏi server 1 lần tốn băng thông) mà dùng thư viện **HTMX** kết nối **SSE**. Nghĩa là Web há miệng chờ sẵn, Jetson vừa phát Alert, Server bắn SSE `sse-swap="alert"` -> Trình duyệt gắp trúng đoạn HTML đó nhét ngay lên đầu Bảng Cảnh Báo (`afterbegin`) mà không cần làm mới trang."*

### 4. File Phát Báo Động: `app/api/control.py` (Tính Năng OTA)
> **Tại sao quan trọng?** Cập nhật phần mềm không chạm mạch - 1 điểm nhấn phần mềm rất mạnh.

**Đoạn Code Trọng Tâm:**
```python
    # Build dynamic download URL for Jetson using FastAPI Request
    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/static/updates/{file.filename}"
```
**Cách giải thích:** *"Hệ thống hỗ trợ OTA. Khi Admin đính kèm file mới trên Web, Code em tự động dùng `request.base_url` để đẻ ra Link tải tùy biến theo IP thực tế của máy chủ. Nó sẽ gửi link tải ngầm đó qua Websocket xuống Jetson để Jetson tự Download."*.

---

## ❓ PHẦN 3: CÁC CÂU HỎI PHẢN BIỆN "HÓC BÚA" TỪ HỘI ĐỒNG

Nếu hội đồng hỏi, bạn hãy tự tin trả lời theo mẫu sau:

**Câu 1: "Nếu Jetson đi vào hầm chui, mất mạng 30 phút. Web của em xử lý thế nào?"**
> **Trả lời:** Dạ, khi mất mạng, WebSockets Timeout. Hệ thống em có class `ConnectionManager` trong `jetson_handler.py`. Ngay khi đứt kết nối, nó lưu lại `offline_time` và gài một `background_task` đếm ngược 5 phút. Nếu 5 phút xe không vào lại mạng (chạy ra khỏi hầm), Server ngầm hiểu phiên lái xe kết thúc và cập nhật `checkout_at` vào Database. 

**Câu 2: "Tại sao em lại nhận diện Camera dưới thiết bị Jetson mà không gửi Video lên Web xử lý cho xịn?"**
> **Trả lời:** Dạ, truyền Video trực tiếp trên xe ô tô đang di chuyển qua mạng 4G về Web là cục kì tốn Băng Thông (Data) và độ trễ ngẫu nhiên (Latency) rất cao tính bằng giây. Em đẩy AI (Dlib/OpenCV) tính toán **Ngay tại biên (Edge Computing)** trên cục Jetson. Khi nào ngủ gật nó mới gửi 1 chùm Text (`EAR=0.1`) tốn vài kilobyte lên Web, tốc độ xử lý nhanh hơn hàng trăm lần và tiết kiệm tiền mạng 4G.

**Câu 3: "Pass mã hóa `bcrypt` của admin lưu thế nào?"**
> **Trả lời:** Dạ, mật khẩu nằm trong `auth/utils.py`. Em xài kỹ thuật Hash giải mã 1 chiều với `Bcrypt`. Code em băm Pass cộng thêm chuỗi muối Muối rác (Salting). Dù Hacker hay ai bê cả file SQLite về nhà họ cũng không thể giải mã ngược lại được do mã hóa này là One-Way. 

---
**LỜI KHUYÊN CUỐI CÙNG:** Hãy mở những file `.py` đã được liệt kê ở trên ra, đọc tới đâu dóng sang văn bản này tới đó. Đừng học thuộc lòng, hãy hiểu "Đường đi của một gói tin từ phần cứng -> lên Web". Chúc bạn đạt điểm A+ Đồ án Tốt nghiệp!

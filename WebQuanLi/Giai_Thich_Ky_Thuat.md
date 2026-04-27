# GIẢI THÍCH KỸ THUẬT: HIỂU RÕ BỘ MÃ NGUỒN WEBQUANLI

Tài liệu này được viết ra để giúp bạn (và hội đồng, nếu bạn sử dụng cho đồ án) hiểu rõ tường tận **lý do**, **cách thức** và **mục đích** của từng loại công nghệ được áp dụng bên trong dự án bảng điều khiển WebQuanLi.

---

## 1. Kiến trúc Backend: Vì sao là FastAPI?
Tôi không chọn Django hay Flask mà quyết định dùng **FastAPI** làm trái tim của hệ thống vì 2 lý do cực kỳ phù hợp với bài toán IoT (Internet of Things):
- **Hiệu năng ASGI (Bất đồng bộ - Asynchronous):** Với hàng chục thiết bị Jetson cập nhật GPS mỗi giây 1 lần, Server cần xử lý hàng trăm kết nối cùng lúc. Tính năng `async/await` của FastAPI giúp các phiên mạng không chờ nhau, giảm thiểu nghẽn cổ chai (Bottleneck) mạng.
- **Hỗ trợ WebSockets tích hợp sẵn trực tiếp:** Dễ dàng tạo luồng 2 chiều với Jetson Nano thay vì phải phụ thuộc quá nhiều thư viện ngoài như Flask-SocketIO.

## 2. Kết nối Mạng: Giao thức WebSockets & SSE
Thay vì kiểu Restful API truyền thống (Jetson gửi request rồi chờ trả lời, Web muốn tải dữ liệu lại phải F5), tôi đã dùng:
1. **WebSockets (Tác dụng: Jetson ↔ Server):** Là đường ống 2 chiều luôn mở. Việc này cho phép Jetson "xả" tọa độ liên tiếp, và Web có thể "Gửi thông điệp test cảnh báo" trút xuống Jetson ngay lập tức mà không độ trễ.
2. **Server-Sent Events - SSE (Tác dụng: Server ↔ Web HTML):** Khi có tín hiệu ở Server, SSE giống như loa phát thanh, chỉ có Server mới có quyền "đẩy" cục dữ liệu đó hiển thị mới lên website người quản lý, tránh việc trình duyệt người dùng phải hỏi server liên tục (gây tốn RAM) như cơ chế Polling cũ kĩ. Tần suất cập nhật do server chủ động.

## 3. Giao diện Web: Tại sao chỉ dùng HTMX thay vì React/Vue?
Dự án của bạn là hệ thống IoT có tính chuyên ngành cao. Phân chia thêm 1 dự án Code phần mềm ReactJS/NextJS là quá tốn kém và cồng kềnh.
- **Dùng HTMX + Jinja2 (Python Render):** Cho phép bạn thao tác đổi và làm mới một góc riêng lẻ trên giao diện (Ví dụ: Nút Nguồn chuyển xanh, GPS trên biểu đồ thay đổi tịnh tiến) mà KHÔNG làm tải lại toàn bộ trang Web. 
- Mọi logic HTML được trả ra từ `partials/` (Phân nửa file HTML). **Điều này giúp thiết bị chạy Web (Máy điện thoại, PC người quản trị) gần như tốn rất ít CPU**, toàn bộ tính toán nhường cho máy chủ.

## 4. Cơ sở Dữ Liệu (Database): SQLite Async và Thuật toán tối ưu
- **Vì sao SQLite?** Hệ thống được triển khai nhanh, không đòi hỏi phần cứng phức tạp để cấp phát. Nhưng tôi đã cấu hình `aiosqlite` (bất đồng bộ) cùng SQLAlchemy để giải quyết triệt để lỗi khóa Database.
- **Sửa Lỗi Logic Vòng lặp:** Nếu để ý file `app/ws/jetson_handler.py`, ban đầu tôi để vòng lặp WebSocket liên tục tra tên Xe trong Database. Nó đã gây Deadlock (TREO TOÀN BỘ MÁY CHỦ) do hàng ngàn I/O rác. 
👉 **Giải pháp tối ưu bạn đang dùng:** Tôi đã tối ưu bằng cách truy vấn SQLite ĐÚNG 1 LẦN khi xe bắt đầu kết nối, sau đó lưu (Cache) vào RAM nội bộ của vòng lặp (các biến `vid`, `manager_phone`). Từ đấy, Web nhận được hàng ngàn vị trí GPS thì nó vẫn chỉ chuyển tiếp (Route) tín hiệu đó thẳng ra Bản đồ Leaflet chứ hoàn toàn không đụng 1 bit nào vào Database. Dữ liệu chỉ thực sự ghi vô ổ cứng nếu thẻ đó là thẻ Báo Động (Nhắm mắt / Sai tài xế).

## 5. Trung chuyển sự kiện: Event Bus (`core/event_bus.py`)
Mảnh ghép làm mượt hệ thống. Nó như Đơn vị điều phối luồng xe cộ (Traffic Controller). Khi Jetson gửi tín hiệu phần cứng lên, thay vì lưu rồi khóa Database lại, Event Bus sẽ lập tức đứng ra phân luồng (Broadcast) trực tiếp vào màn hình của **Bất cứ ai đang đăng nhập vào Web ở bất kỳ đâu trên thế giới**. Lập trình hướng sự kiện (Event-driven)! 

## 6. Tính năng OTA (Cập nhật từ xa)
Được tôi thiết đặt tại `api/control.py`. Lý do: 
- Bạn không thể thu hồi Jetson Nano mỗi lần nâng cấp thuật toán Nhận diện mắt mở/nhắm. 
- Nút bấm OTA cho phép bạn ném code `python.py` thuật toán mới từ WebQuanLi lên, Server sẽ sinh ra URL Mạng Động (`request.base_url`), chuyển cho Jetson Nano tự kết nối kéo Data về máy nó và reset phần cứng, giúp nâng cấp trí thông minh toàn hạm đội xe chỉ trong 1 Click chuột ở Trụ sở.

## 7. Bảo Mật: JWT Auth (Token) & Bcrypt
- **JWT (JSON Web Token):** Được cất giấu trong khối `Cookie HttpOnly` của đường truyền. Nghĩa là Hacker cài phần mềm trộm mã ở trang Web của bạn cũng không thể đọc token đăng nhập của bạn (Vì hệ điều hành khóa nó lại, chỉ Server mới đọc được).
- **Bcrypt:** Trước đó tôi dùng `passlib` nhưng bản này quá lỗi thời và xung đột với Python đời mới, nó đè bẹp cả ứng dụng và lỗi ngay lúc Init. Tôi đã trực tiếp cài lõi `bcrypt` để giải bài toán giải mã 1 chiều cho mật khẩu đăng nhập, chống Database rò rỉ.

---
*(Tệp tin Giải thích này được xây dựng giúp củng cố luận cứ khi bảo vệ giải pháp trước các câu hỏi học thuật từ chuyên gia/giảng viên).*

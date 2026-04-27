import asyncio
import websockets
import json
import random

SERVER_WS_URL = "ws://127.0.0.1:8000/ws/jetson/JETSON-001"

async def simulate():
    print(f"[*] Đang kết nối tới {SERVER_WS_URL}...")
    try:
        async with websockets.connect(SERVER_WS_URL) as ws:
            print("[+] Kết nối thành công! Gửi tín hiệu phần cứng (Hardware).")
            await ws.send(json.dumps({
                "type": "hardware", 
                "data": {"power": True, "gps": True, "camera": True, "rfid": True, "cellular": True, "speaker": True}
            }))
            await asyncio.sleep(2)
            
            print("[+] Quẹt thẻ RFID (Bắt đầu phiên làm việc)...")
            await ws.send(json.dumps({
                "type": "session_start",
                "data": {"rfid_tag": "TAG12345"}
            }))
            await asyncio.sleep(2)
            
            print("[+] Đang truyền dữ liệu GPS liên tục (Dashboard sẽ cập nhật bản đồ)...")
            # Bắn GPS liên tục 10 lần
            for i in range(10):
                await asyncio.sleep(1)
                await ws.send(json.dumps({
                    "type": "gps",
                    "data": {"lat": 10.762622 + random.uniform(-0.001, 0.001), "lng": 106.660172 + random.uniform(-0.001, 0.001), "speed": 40 + i * 2}
                }))
                
                # Cứ 3 giây giả lập 1 cảnh báo buồn ngủ
                if i == 3:
                    print("\n[!] CẢNH BÁO: TÀI XẾ NHẮM MẮT (Ngủ gật)!")
                    await ws.send(json.dumps({
                        "type": "alert",
                        "data": {"level": "CRITICAL", "ear": 0.12, "mar": 0.5, "pitch": 15.0}
                    }))
                elif i == 7:
                    print("\n[!] LỖI: Nhận diện sai người điều khiển xe (Face Mismatch)!")
                    await ws.send(json.dumps({
                        "type": "face_mismatch",
                        "data": {"rfid_tag": "TAG12345", "expected": "Bùi Minh Tùng"}
                    }))

            # Chờ lệnh test từ Dashboard để báo hiệu hai chiều hoạt động tốt
            print("\n[*] Đang lắng nghe Lệnh điều khiển (Test/OTA) từ Web Admin trong 30 giây...")
            for _ in range(30):
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    cmd = json.loads(response)
                    print(f"    ---> NHẬN LỆNH TỪ WEB: {cmd}")
                    
                    if cmd.get("action") == "test_alert":
                        print("         (Kích hoạt còi báo động mức độ: " + cmd.get("level", "") + ")")
                    elif cmd.get("action") == "update_software":
                        print("         (Bắt đầu tải bản cập nhật OTA từ web)")
                        await ws.send(json.dumps({
                            "type": "ota_status",
                            "data": {"status": "downloading", "progress": 50}
                        }))
                        await asyncio.sleep(1)
                        await ws.send(json.dumps({
                            "type": "ota_status",
                            "data": {"status": "success", "progress": 100}
                        }))
                except asyncio.TimeoutError:
                    pass
            
            print("\n[+] Quẹt lại thẻ (Kết thúc phiên)...")
            await ws.send(json.dumps({
                "type": "session_end",
                "data": {"rfid_tag": "TAG12345"}
            }))
            print("[*] Giả lập hoàn tất.")
    except Exception as e:
        print(f"[-] Lỗi kết nối: {e}")

if __name__ == "__main__":
    asyncio.run(simulate())

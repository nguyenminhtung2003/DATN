# DrowsiGuard Demo Operator Runbook

Ngay truoc khi demo, muc tieu la xac nhan 4 dieu: WebQuanLi dang chay, Jetson dang dung strict mode, face verification bat that, va pipeline AI co the vao trang thai canh bao.

## 1. Cau hinh demo can dat

- Jetson SSH: `nano@192.168.2.29`
- Jetson runtime: `/home/nano/Version3`
- Launcher Jetson: `/home/nano/start_drowsiguard_full.sh`
- WebQuanLi URL backend: `http://192.168.2.24:8000`
- WebSocket Jetson dang dung tren launcher: `ws://100.91.225.22:8000/ws/jetson/JETSON-001`
- RFID demo: `0199190080`
- Identity mode:
  - `DROWSIGUARD_DEMO_MODE=false`
  - `DROWSIGUARD_FEATURE_FACE_VERIFY=true`
  - `DROWSIGUARD_FACE_VERIFY_THRESHOLD=0.785`

Luu y: launcher Jetson co the override mot so gia tri trong `/home/nano/Version3/drowsiguard.env`, nen khi nghi ngo hay kiem tra launcher truoc.

## 2. Start WebQuanLi tren Windows

Chay launcher WebQuanLi tren may Windows nhu binh thuong, sau do mo dashboard tren may tinh demo.

Kiem tra nhanh tren Windows:

```powershell
curl http://192.168.2.24:8000/api/health
```

Neu dung dien thoai de xem dashboard, dien thoai phai cung mang LAN hoac co route toi IP Windows. Neu chi mo duoc tren may tinh, kiem tra firewall Windows va backend co bind `0.0.0.0` hay khong.

## 3. Start runtime tren Jetson

```powershell
ssh nano@192.168.2.29 "/home/nano/start_drowsiguard_full.sh"
```

Man hinh Jetson phai hien GUI local monitor. Neu co tien trinh cu, launcher se kill `main.py` cu truoc khi chay lai.

## 4. One-command readiness check

Chay lenh nay truoc khi moi demo:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

Ket qua dat yeu cau khi khong co dong `FAIL` va co cac dong tuong tu:

```text
PASS strict_mode             DROWSIGUARD_DEMO_MODE=false
PASS face_verify             DROWSIGUARD_FEATURE_FACE_VERIFY=true
PASS face_threshold          0.785
PASS face_reference_count    0199190080 references=...
PASS websocket_url           ws://...
PASS dashboard_reachability  ...
```

Chap nhan `WARN` cho audio/GPS neu demo khong can phan do. Khong chap nhan `WARN`/`FAIL` o `strict_mode`, `face_verify`, `face_reference_count`, `rfid_reader`, hoac `websocket_url` truoc demo chinh.

## 5. Test xac thuc tai xe

1. Quet the RFID demo.
2. Dua mat dung tai xe vao camera trong 2-3 giay.
3. Dashboard/GUI phai chuyen qua trang thai xac thuc thanh cong.
4. Neu khong dua mat vao camera, he thong phai khong duoc pass. Loi hop le la `NO_FACE`.
5. Neu co mat nhung diem so thap, loi hop le la `LOW_CONFIDENCE`, khong gop chung voi `NO_FACE`.

Neu van pass khi khong co mat, dung demo va kiem tra ngay:

```powershell
ssh nano@192.168.2.29 "grep -n 'DROWSIGUARD_DEMO_MODE\|DROWSIGUARD_FEATURE_FACE_VERIFY\|DROWSIGUARD_FACE_VERIFY_THRESHOLD' /home/nano/start_drowsiguard_full.sh /home/nano/Version3/drowsiguard.env"
```

## 6. Test canh bao buon ngu

Chay test payload co dinh tren may dev:

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python scripts\test_demo_readiness.py --mode drowsiness-demo
```

Ket qua mong doi:

```text
[DROWSINESS] normal-baseline: PASS
[DROWSINESS] closed-eyes-warning: PASS
[DROWSINESS] yawn-warning: PASS
[DROWSINESS] head-down-warning: PASS
[DROWSINESS] recovery-normal: PASS
```

Khi demo thuc te, chi can chung minh duoc it nhat 2 trang thai: binh thuong va canh bao buon ngu.

## 7. Stop va restart

Dung runtime:

```powershell
ssh nano@192.168.2.29 "pkill -f '/home/nano/Version3/main.py' || true"
```

Restart:

```powershell
ssh nano@192.168.2.29 "/home/nano/start_drowsiguard_full.sh"
```

## 8. Rollback

Local rollback trong repo neu can huy Round 5:

```powershell
git restore Version3/healthcheck.py Version3/scripts/test_demo_readiness.py
Remove-Item Version3/tests/test_healthcheck.py
Remove-Item docs/demo-readiness/operator-runbook.md
```

Neu da sua launcher Jetson va can quay lai ban backup:

```powershell
ssh nano@192.168.2.29 "cp /home/nano/start_drowsiguard_full.sh.bak-9of10 /home/nano/start_drowsiguard_full.sh"
```

## 9. Rui ro con lai

- Launcher Jetson da duoc sua echo text sau Round 5 de hien dung `face verify enabled, strict mode`.
- Healthcheck khong the thay the test that tren camera/RFID; no chi giup phat hien cau hinh sai truoc demo.
- Audio/GPS co the la `WARN` tuy vao thiet bi tai thoi diem demo. Neu hoi dong tap trung vao AI va RFID/face verify, co the chap nhan `WARN` nay nhung nen noi ro day la phan ngoai luong AI chinh.

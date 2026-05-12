# Session Summary 2026-05-12 - DrowsiGuard Handoff

## Muc dich file nay

File nay dung de mo session moi va dua AI moi vao dung boi canh hien tai cua project `D:\DATN-testing1`.

Quy tac quan trong:

- Doc `AGENTS.md` truoc khi lam.
- Khong tu y sua code neu nguoi dung chi yeu cau bao cao/phan tich.
- Neu yeu cau "len plan", phai tao file `.md`.
- Voi diagram/report, chi sua `docs/diagrams/`, `docs/images/`, `docs/render_diagrams.ps1`, `tools/plantuml/` neu can.
- Voi runtime `Version3/` va `WebQuanLi/`, chi sua khi nguoi dung xac nhan ro rang.

## Repo va branch hien tai

- Workspace: `D:\DATN-testing1`
- Branch hien tai: `codex/global-rfid-face-registry`
- Co nhieu file dang dirty/untracked tu cac cong viec truoc. Khong revert neu khong duoc yeu cau.
- Cac thay doi quan trong gan day:
  - `WebQuanLi/app/api/vehicles.py`
  - `WebQuanLi/tests/test_driver_registry_sync.py`
  - `docs/superpowers/plans/2026-05-12-global-rfid-face-registry.md`
  - `docs/superpowers/plans/2026-05-12-fleet-add-vehicle-delete-driver.md`

## Cong viec da lam: global RFID face registry

Muc tieu: RFID nao cung phai doi chieu voi dung tai xe trong danh sach he thong, khong phu thuoc tai xe da gan xe hay chua.

Da thuc hien:

- WebQuanLi registry manifest khong con loc theo `Driver.vehicle_id == vehicle.id`.
- Manifest lay toan bo tai xe dang active va co `face_image_path`.
- Upload anh cho tai xe chua gan xe se gui lenh sync toi cac Jetson online.
- Khong sua thuat toan `FaceVerifier` ben Jetson.

File da sua:

- `WebQuanLi/app/api/vehicles.py`
- `WebQuanLi/tests/test_driver_registry_sync.py`

Test da chay thanh cong:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_driver_registry_sync.py WebQuanLi/tests/test_api_validation_contract.py WebQuanLi/tests/test_ws_session_flow.py Version3/tests/test_webquanli_contract.py -q
```

Ket qua:

```text
42 passed
```

## Trang thai WebQuanLi va Tailscale

WebQuanLi da duoc chay qua port `8000`.

Endpoint manifest da test thanh cong:

```text
http://100.91.225.22:8000/api/jetson/JETSON-001/driver-registry
```

Da co thoi diem endpoint tra ve:

- `TAG12345` - Tai Xe Test RFID
- `0199190080` - Nguyen Minh Tung
- `0198883744` - Le Duy Tung

Luu y: Neu WebQuanLi restart hoac doi IP Tailscale, can test lai endpoint tren.

## Trang thai Jetson Nano

SSH thuong dung:

```powershell
ssh nano@192.168.2.29
```

Tailscale/WebQuanLi IP dang dung trong launcher:

```text
100.91.225.22
```

File launcher Jetson quan trong:

```text
/home/nano/start_drowsiguard_full.sh
```

Mot so env quan trong da thay trong process dang chay:

```text
DROWSIGUARD_DEMO_MODE=false
DROWSIGUARD_FACE_VERIFY_ACQUIRE_TIMEOUT=3.0
DROWSIGUARD_FEATURE_FACE_VERIFY=true
DROWSIGUARD_FEATURE_RFID=true
DROWSIGUARD_FEATURE_SPEAKER=true
DROWSIGUARD_FEATURE_WEBSOCKET=true
DROWSIGUARD_WS_URL=ws://100.91.225.22:8000/ws/jetson/JETSON-001
```

Dang co process:

```text
python3 main.py
```

## Registry tren Jetson

File registry:

```text
/home/nano/Version3/storage/driver_registry.json
```

Thu muc anh reference:

```text
/home/nano/Version3/storage/driver_faces/
```

Tai thoi diem kiem tra, Jetson moi co local reference:

- `0199190080` - Nguyen Minh Tung
- `TAG12345` - Tai xe test

Chua co local reference cho:

- `0198883744` - Le Duy Tung

Neu muon test Le Duy Tung, can sync registry lai tu WebQuanLi sang Jetson.

Lenh sync bang code hien co:

```bash
cd /home/nano/Version3
python3 - <<'PY'
from camera.face_verifier import FaceVerifier
manifest_url = 'http://100.91.225.22:8000/api/jetson/JETSON-001/driver-registry'
manifest = FaceVerifier().sync_from_manifest_url(manifest_url)
print('driver_count=%d' % len(manifest.get('drivers', [])))
for driver in manifest.get('drivers', []):
    print(driver.get('rfid_tag'), driver.get('name'), driver.get('local_reference_path'))
PY
```

## Van de dang debug: xac nhan danh tinh khuon mat

Nguoi dung gap loi khi quet RFID va xac minh mat.

Ket luan da kiem tra:

- Khong phai do WebQuanLi chua upload anh.
- Voi `0199190080`, Jetson co anh reference local.
- Log Jetson cho thay nhieu lan he thong da lay duoc face crop va da so sanh, nhung bi `LOW_CONFIDENCE`.

Log quan trong:

```text
Fallback score UID=0199190080: 0.790
Fallback score UID=0199190080: 0.818
Verify returned LOW_CONFIDENCE - DEMO_MODE_ALLOW_UNVERIFIED is False. Rejecting session.
```

Nguong hien tai:

```text
FACE_VERIFY_THRESHOLD = 0.82
```

Do do voi Nguyen Minh Tung:

- Diem `0.818` rat sat nguong nhung van fail.
- Diem `0.790` thap hon nguong ro hon.

Them mot diem gay hieu nham:

- `LOW_CONFIDENCE` dang bi map sang prompt `no_face` trong `Version3/main.py`.
- Nen nguoi dung nghe/thay thong bao nhu "khong phat hien khuon mat", nhung log that la `LOW_CONFIDENCE`.

Code lien quan:

```text
Version3/main.py
Version3/camera/face_verifier.py
Version3/camera/face_analyzer.py
```

## Anh debug da keo ve Windows

Anh latest Jetson:

```text
D:\DATN-testing1\.tmp\jetson-debug\latest.jpg
```

Anh reference Nguyen Minh Tung:

```text
D:\DATN-testing1\.tmp\jetson-debug\reference_0199190080.jpg
```

Nhan xet:

- `reference_0199190080.jpg` co mat ro.
- `latest.jpg` tai thoi diem keo ve khong co mat, camera dang chua vao nguoi hoac bi che/huong xuong.
- Trong luc test can dam bao mat nam giua khung sau khi quet the va giu yen vai giay.

## Danh gia threshold va multi-image

Phuong an ha threshold:

- Hien tai `FACE_VERIFY_THRESHOLD = 0.82`.
- Ha xuong `0.80` co the hop ly de test truoc.
- Ha xuong `0.78` co the giup pass demo, nhung tang rui ro nhan nham nguoi.
- Neu ha threshold, bat buoc test cheo:
  - Quet RFID Nguyen Minh Tung nhung dua mat Le Duy Tung vao.
  - He thong phai reject thi moi tam chap nhan.

Phuong an 20 anh/tai xe:

- Qua lon cho hien trang hien tai.
- FaceVerifier hien khong train model tu 20 anh; neu lam multi-image thi se so anh live voi tung anh mau va lay diem tot nhat.
- 20 anh full-frame xau co the lam nhieu hon.

Khuyen nghi toi uu:

- Dung 3-5 anh crop mat tot/tai xe.
- Nen chup bang chinh camera Jetson, cung anh sang/goc voi luc demo.
- Jetson sync nhieu reference ve `storage/driver_faces/<rfid>/ref_*.jpg`.
- FaceVerifier so voi tung reference va lay best score.
- Tach prompt `LOW_CONFIDENCE` khoi `NO_FACE_FRAME`.

Huong nhanh cho demo:

1. Chup lai 1 anh dep nhat bang camera Jetson.
2. Upload lai anh do len dashboard cho tai xe.
3. Sync registry lai xuong Jetson.
4. Test voi threshold `0.82`, neu fail thi thu `0.80`.
5. Chi can xuong `0.78` neu test cheo voi mat sai van reject.

## Dashboard fleet/add-delete driver

Nguoi dung muon:

- Them nut xoa tai xe khoi danh sach.
- Them nut them xe vao danh sach xe.

Da lap plan, chua implement:

```text
D:\DATN-testing1\docs\superpowers\plans\2026-05-12-fleet-add-vehicle-delete-driver.md
```

Huong trong plan:

- Them `DELETE /api/drivers/{driver_id}`.
- Xoa mem tai xe: `Driver.is_active = False`, khong hard delete de giu lich su.
- `/fleet` chi hien tai xe active.
- Them form `+ Them xe` dung API `POST /api/vehicles` da co.
- Sau khi xoa tai xe, trigger sync registry toi Jetson online.

## Viec nen lam tiep trong session moi

Neu muc tieu la demo xac minh danh tinh ngay:

1. Kiem tra WebQuanLi dang chay va manifest co 2 tai xe:

```powershell
python - <<'PY'
import json, urllib.request
url='http://100.91.225.22:8000/api/jetson/JETSON-001/driver-registry'
payload=json.loads(urllib.request.urlopen(url, timeout=8).read().decode('utf-8'))
print(len(payload.get('drivers', [])))
for d in payload.get('drivers', []):
    print(d.get('rfid_tag'), d.get('name'), d.get('face_image_url'))
PY
```

2. Sync registry tren Jetson de co ca `0198883744`.
3. Dam bao camera live co mat trong khung.
4. Test Nguyen Minh Tung voi anh Jetson chup lai.
5. Neu van fail sat nguong, can nhac ha threshold xuong `0.80` trong launcher/env va reboot/restart runtime.

Neu muc tieu la sua chinh chu:

1. Viet plan rieng cho identity verification refinement.
2. Noi dung plan nen gom:
   - Chup/crop anh reference tu Jetson.
   - Multi-reference 3-5 anh/tai xe.
   - Best-score matching.
   - Tach `LOW_CONFIDENCE` prompt/status khoi `NO_FACE_FRAME`.
   - Test dung/sai nguoi.

Neu muc tieu la UI fleet:

1. Thuc thi plan:

```text
docs/superpowers/plans/2026-05-12-fleet-add-vehicle-delete-driver.md
```

2. Khong hard delete driver.

## Cac lenh test hay dung

WebQuanLi registry/API contract:

```powershell
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'; python -m pytest WebQuanLi/tests/test_driver_registry_sync.py WebQuanLi/tests/test_api_validation_contract.py WebQuanLi/tests/test_ws_session_flow.py Version3/tests/test_webquanli_contract.py -q
```

Kiem tra WebQuanLi import:

```powershell
cmd /c D:\DATN-testing1\start_webquanli.bat --check
```

Chay WebQuanLi:

```powershell
cmd /c D:\DATN-testing1\start_webquanli.bat
```

SSH Jetson:

```powershell
ssh nano@192.168.2.29
```

Kiem tra process Jetson:

```bash
pgrep -af 'python3|main.py|DrowsiGuard'
```

Doc log verify gan nhat:

```bash
cd /home/nano/Version3
tail -250 logs/drowsiguard.log | grep -E 'RFID|VERIFY|NO_FACE|NO_ENROLLMENT|MISMATCH|LOW_CONFIDENCE|VERIFIED|Fallback score'
```

## Luu y cho AI moi

- Khong ket luan "khong co khuon mat" chi dua tren UI/prompt. Phai doc `logs/drowsiguard.log`.
- Phan biet:
  - `NO_ENROLLMENT`: Jetson khong co anh reference cho RFID.
  - `NO_FACE_FRAME`: camera khong lay duoc face crop.
  - `LOW_CONFIDENCE`: da co face crop, da so sanh, nhung diem chua dat nguong.
  - `MISMATCH`: diem qua thap, xem nhu sai nguoi.
- Trong hinh local monitor, `AI FPS 0.0` khi `VERIFYING_DRIVER` khong nhat thiet la loi, vi AI buong ngu chi chay sau khi verify thanh cong va vao `RUNNING`.
- Do Jetson khong co `cv2.face`, FaceVerifier dang dung fallback similarity, nhay voi anh sang/goc/crop.
- Neu muon lam multi-image, nen bat dau 3-5 anh crop mat tot, khong nen nhay len 20 anh full-frame.

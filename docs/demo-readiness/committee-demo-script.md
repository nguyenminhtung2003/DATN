# Committee Demo Script

Date: 2026-05-13

Purpose: give a student-style speaking script for presenting DrowsiGuard to the graduation committee without overstating the AI or biometric strength.

Target time: 7-10 minutes.

## 1. Opening

Kinh thua thay co trong hoi dong, em xin trinh bay phan demo cua do an DrowsiGuard. De tai cua em la he thong canh bao buon ngu cho tai xe, su dung Jetson Nano, camera, RFID, WebQuanLi dashboard, WebSocket va co so du lieu SQLite.

Muc tieu cua he thong khong chi la phat hien dau hieu buon ngu, ma con dam bao dung tai xe moi bat dau phien giam sat. Vi vay flow demo cua em gom 2 lop:

1. Xac thuc tai xe bang RFID va camera.
2. Sau khi xac thuc thanh cong, Jetson moi chay pipeline AI canh bao buon ngu va gui su kien ve WebQuanLi.

## 2. System Overview

Ve kien truc tong quan, he thong duoc chia thanh hai phan:

- `Version3` chay tren Jetson Nano, nhan camera, doc RFID, xu ly AI va gui su kien.
- `WebQuanLi` chay tren may tinh Windows, lam dashboard quan ly xe, tai xe, lich su phien va canh bao.

Jetson va WebQuanLi ket noi voi nhau qua WebSocket. Khi co su kien nhu `session_start`, `verify_snapshot`, `verify_error`, `face_mismatch`, `alert` hoac `session_end`, Jetson day len WebQuanLi. WebQuanLi luu phan can luu vao SQLite va hien thi realtime tren dashboard.

Neu hoi dong can xem so do, em se mo cac file:

- `docs/images/system_overview.svg`
- `docs/images/software_architecture.svg`
- `docs/images/websocket_sequence.svg`
- `docs/images/database_erd.svg`

## 3. Identity Workflow

Phan dau tien cua demo la xac thuc danh tinh tai xe.

Quy trinh nhu sau:

1. Tai xe quet the RFID.
2. Jetson lay UID RFID, vi du `0199190080`.
3. Jetson tim anh reference cua tai xe trong local registry.
4. Camera phai co khuon mat live moi duoc verify.
5. Neu khong co mat, he thong tra ve `NO_FACE_FRAME` va khong cho bat dau phien.
6. Neu co mat nhung diem so khong du tin cay, he thong tra ve `LOW_CONFIDENCE`.
7. Neu sai danh tinh, he thong day `face_mismatch`.
8. Chi khi verify thanh cong, he thong moi day `session_start` va chuyen sang trang thai `RUNNING`.

Dieu quan trong khi trinh bay: em khong noi day la he thong sinh trac hoc cap cong nghiep. Day la co che xac thuc thuc dung cho demo: RFID xac dinh tai xe, camera xac minh khuon mat live, va multi-reference giup on dinh hon trong dieu kien anh thay doi.

Trang thai demo hien tai:

```text
DROWSIGUARD_DEMO_MODE=false
DROWSIGUARD_FEATURE_FACE_VERIFY=true
DROWSIGUARD_FACE_VERIFY_THRESHOLD=0.785
```

Neu hoi dong hoi "neu khong dua mat vao camera thi sao", em tra loi: phien khong duoc bat dau; Jetson phai tra ve `NO_FACE_FRAME`/`verify_error`, day la test bat buoc truoc demo.

## 4. Drowsiness AI Workflow

Sau khi tai xe da duoc xac thuc, pipeline AI moi chay.

Luon xu ly chinh:

1. Camera lay frame tu tai xe.
2. MediaPipe Face Mesh trich xuat landmark khuon mat.
3. He thong tinh cac dac trung:
   - EAR: do mo mat.
   - MAR: do mo mieng/ngap.
   - PERCLOS: ty le mat nham trong cua so thoi gian.
   - Pitch: goc cui dau.
4. Bo classifier theo thoi gian danh gia trang thai: binh thuong, nghi ngo, buon ngu hoac low confidence.
5. Alert manager chuyen thanh canh bao cap 1/2/3.
6. Su kien `alert` duoc gui ve WebQuanLi de hien thi va luu lich su.

Khi hoi dong hoi "AI nam o dau", em tra loi: AI/CV nam o pipeline nhan dien landmark khuon mat bang MediaPipe Face Mesh va bo phan loai theo thoi gian dua tren dac trung EAR/MAR/PERCLOS/pitch. He thong hien tai la AI ung dung theo huong computer vision va rule-based temporal classifier, khong phai mot model deep learning tu train moi cho buon ngu.

## 5. Live Demo Order

Thu tu demo de it rui ro:

1. Mo WebQuanLi dashboard tren Windows.
2. Chay healthcheck Jetson:

```powershell
ssh nano@192.168.2.29 "cd /home/nano/Version3 && PYTHONPATH=/home/nano/Version3 python3 scripts/test_demo_readiness.py --mode hardware"
```

3. Chi tiep tuc neu khong co `FAIL`, va co cac dong:

```text
PASS strict_mode
PASS face_verify
PASS face_reference_count
PASS rfid_reader
PASS dashboard_reachability
```

4. Quet RFID khi khong co mat trong camera.
   - Ket qua mong doi: fail voi `NO_FACE_FRAME`, khong start session.

5. Dua mat dung tai xe vao camera va quet RFID.
   - Ket qua mong doi: verify thanh cong, dashboard nhan `session_start` va `verify_snapshot`.

6. Sau khi phien dang `RUNNING`, demo canh bao buon ngu:
   - mat binh thuong;
   - nham mat giu mot luc;
   - ngap/cui dau neu dieu kien cho phep;
   - quay lai binh thuong de thay he thong recover.

7. Ket thuc phien bang RFID checkout hoac stop runtime theo checklist.

## 6. Evidence To Mention

Neu hoi dong hoi "em da test bang gi", em co the noi:

- Co test local cho verify flow: `Version3/tests/test_verify_flow.py`.
- Co test contract giua Version3 va WebQuanLi: `Version3/tests/test_webquanli_contract.py`, `WebQuanLi/tests/test_verify_snapshot_contract.py`.
- Co hardware readiness command tren Jetson.
- Co script demo co dinh cho AI buon ngu: `python scripts/test_demo_readiness.py --mode drowsiness-demo`.
- Co scorecard va runbook trong `docs/demo-readiness/`.

## 7. Known Limitations

Em nen noi thang cac gioi han sau de hoi dong thay minh nam duoc he thong:

- Face verification hien tai phu thuoc chat luong anh, anh sang va goc mat.
- He thong chua phai sinh trac hoc cap cong nghiep.
- Jetson Nano tai nguyen han che, nen em uu tien pipeline nhe va on dinh.
- GPS co the can thoi gian bat ve tinh, nen khong xem `fix_ok=false` trong phong kin la loi phan cung.
- Neu muon nang cap sau nay, co the dung embedding model nhu SFace khi OpenCV/model tren Jetson san sang.

## 8. Closing

Phan dong cua em:

Tong ket lai, do an cua em da xay dung duoc mot luong demo hoan chinh: RFID xac dinh tai xe, camera xac thuc khuon mat live, AI phan tich dau hieu buon ngu, va WebQuanLi nhan su kien realtime de quan ly phien va canh bao. Trong pham vi do an tot nghiep, em tap trung vao tinh hoat dong thuc te, kha nang demo on dinh va giai thich ro tung thanh phan thay vi chi mo phong tren may tinh.

## 9. Short Answers For Common Questions

**He thong co dung AI khong?**

Co. Phan AI/CV nam o MediaPipe Face Mesh de trich xuat landmark va bo phan loai theo thoi gian dua tren EAR, MAR, PERCLOS va pitch. Tuy nhien em khong overclaim la da train mot model deep learning moi.

**Tai sao can RFID neu da co khuon mat?**

RFID xac dinh tai xe can kiem tra, khuon mat dung de xac minh tai xe do co dang ngoi truoc camera hay khong. Hai lop nay giam rui ro start nham phien.

**Neu cung mot nguoi nhung background khac thi sao?**

He thong so sanh crop khuon mat/reference, khong co y dinh so sanh background. Tuy nhien anh sang, goc mat va crop van anh huong diem so, nen demo dung multi-reference anh mat.

**Tai sao khong dung embedding manh hon?**

Da probe Round 6. Jetson hien co OpenCV 4.1.1, khong co `FaceRecognizerSF_create` va `FaceDetectorYN_create`, model SFace/YuNet cung chua co trong project. Them luc demo se tang rui ro, nen giu fallback on dinh.

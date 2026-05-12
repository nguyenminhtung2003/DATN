# DrowsiGuard Version3 — Kế hoạch tối ưu cảnh báo buồn ngủ (rev3)

> Ngày tạo: 2026-05-05
> Rev3 — đã hiệu chỉnh sau review: calibration kính không làm giảm độ nhạy người bình thường, raw fast-path không nhận 1-frame noise, one-eye guard không tự biến occlusion thành drowsy, duration/PERCLOS dùng time-based window, PERCLOS migration có call site rõ.
> Trạng thái: DRAFT — chờ phê duyệt trước khi triển khai

---

## Tổng quan pipeline hiện tại

```
Camera frame
  → FaceAnalyzer (MediaPipe Face Mesh → EAR/MAR/Pitch → EMA smoothing)
    → CalibrationProfile (baseline EAR mở mắt → adaptive threshold)
      → ThresholdPolicy (đọc ngưỡng từ profile)
        → DrowsinessClassifier (quyết định mắt đóng → state + alert_hint)
          → AlertManager (3-level alert → buzzer/LED/speaker)
```

---

## Nguyên tắc quan trọng

1. **Không tối ưu mù** — Phase 0 phải có trước để đo baseline
2. **Mỗi thay đổi có feature flag** — bật/tắt qua env var, rollback nhanh
3. **Backward compatible** — hệ thống hoạt động bình thường nếu tắt hết feature mới
4. **Viết test trước khi sửa code** — đặc biệt các module có nhiều test hiện hữu (classifier, alert_manager)
5. **Không sửa >2 module/PR** — giảm rủi ro regression
6. **Benchmark dataset** — mỗi lần sửa threshold phải chạy lại regression test trên dataset chuẩn

---

## Phase 0 — Instrumentation & Baseline (BẮT BUỘC trước mọi Phase khác)

Không thể tối ưu cái không đo được. Phase này xây hạ tầng để đo hiệu quả từng thay đổi sau.

### 0.1 — Event logging JSONL

**File mới:** `utils/event_recorder.py`
**Nội dung log** (1 dòng JSON/frame khi session active):
```json
{
  "ts": 1712345678.123,
  "fps_actual": 10.8,
  "ear": 0.285, "ear_raw": 0.291,
  "left_ear": 0.27, "right_ear": 0.30,
  "mar": 0.12, "pitch": -2.4,
  "eye_quality": {"selected": "both", "usable": true},
  "ai_state": "NORMAL", "alert_hint": 0,
  "drop_score": 0.08, "one_eye_guard": false,
  "perclos_short": 0.0, "perclos_long": 0.05,
  "alert_level": 0
}
```

- Ghi vào `logs/session_<timestamp>.jsonl` với rotation (max 50MB/file)
- Feature flag: `DROWSIGUARD_EVENT_RECORDER = true/false`
- Overhead < 1ms/frame (I/O async hoặc batch)

**Effort:** 3h

### 0.2 — Offline analyzer script

**File mới:** `scripts/analyze_session.py`

Input: file JSONL. Output: report dạng markdown với:
- Tỷ lệ thời gian mỗi `ai_state`
- Số alert events/giờ ở mỗi level
- Histogram EAR (raw vs smoothed)
- Distribution của `drop_score`, `one_eye_guard`
- FPS thực tế (min/avg/max)

**Effort:** 2h

### 0.3 — Benchmark recording dataset

Ghi video + ground-truth label cho regression test:
- **10 phút lái bình thường** (tỉnh táo, nhìn thẳng) — không nên có alert
- **5 phút có kính cận** — test calibration
- **5 phút giả nhắm mắt ngắn** (blink 0.1-0.2s) — không nên alert
- **5 phút giả buồn ngủ** (nhắm mắt 0.8-3s, ngáp) — phải alert đúng level
- **3 phút nheo một mắt** — test one-eye guard
- **5 phút đêm / ánh sáng yếu** — test glare/night handling

Lưu tại `tests/fixtures/benchmark_videos/` (gitignore, chỉ metadata vào git).

**Effort:** 2h record + 1h label

### 0.4 — Baseline metrics

Chạy benchmark qua code **hiện tại**, record:
- False positive rate (alert/giờ ở video bình thường)
- Detection latency (ms từ khi nhắm mắt đến L1 alert)
- Miss rate (% buồn ngủ không alert)
- Calibration success rate ở video kính cận

Lưu vào `docs/BASELINE_METRICS_2026-05.md`.

**Effort:** 1h

---

## Phase 1 — Critical UX & Driver wearing glasses

Sửa các vấn đề ảnh hưởng trực tiếp driver experience.

### P7-rev — Calibration cho tài xế đeo kính (ưu tiên CAO)

**File:** `ai/calibration.py:234-244`

**Vấn đề:**
- Hiện tại reject nếu `ear_open < 0.25`
- Tài xế đeo kính dày: `ear_open ≈ 0.20`, `ear_closed ≈ 0.12`
- Dùng hằng số `ear_delta = 0.045` → threshold quá sát EAR_đóng → miss

**Giải pháp:**
- Hạ ngưỡng reject: `ear_open < 0.18` mới reject
- **Chỉ dùng công thức tỷ lệ trong glasses mode**: nếu `ear_open < 0.23`, log `GLASSES_MODE` và tính `ear_closed = clamp(ear_open * 0.70, 0.12, 0.24)`
- Nếu `ear_open >= 0.23`, giữ công thức hiện tại để không làm giảm độ nhạy người bình thường: `ear_closed = clamp(max(0.24, ear_open - EAR_OPEN_DELTA), 0.20, 0.30)`
- Trong `GLASSES_MODE`, dùng drop threshold nhỏ hơn (`0.10` thay vì `0.13`) nhưng vẫn yêu cầu sample ổn định: đủ sample, `face_height` đạt, `mar_closed <= 0.35`, eye quality usable, EAR variance thấp
- Test bắt buộc: `ear_open=0.20` phải valid với threshold khoảng `0.14`; `ear_open=0.32` không được tụt xuống `0.224`, vẫn giữ khoảng `0.275`
- Feature flag: `DROWSIGUARD_CALIBRATION_V2 = true`

**Effort:** 3h (1.5h code, 1.5h test)

### P5-rev — Giảm trễ phát hiện nhắm mắt nhanh (ưu tiên CAO)

**File:** `camera/face_analyzer.py:397`, `ai/drowsiness_classifier.py:133`

**Vấn đề:** EMA `alpha=0.3` → cần ~3 frame để smoothed EAR phản ánh đúng (0.25s ở 12fps)

**Giải pháp safe:**
- FaceAnalyzer đã có `raw_ear`, `raw_left_ear`, `raw_right_ear`; classifier cần nhận thêm các field này trong `_coerce_sample`
- Classifier tự track `_raw_low_frames`: tăng khi `raw_ear < (threshold - 0.03)` và `eye_quality.usable == True`, reset khi raw EAR hồi phục hoặc sample không usable
- Fast-path chỉ bật khi **đủ 3 frame raw liên tiếp** cùng thấp: `raw_fast_path = _raw_low_frames >= 3`
- Decision: `closed = smoothed < threshold OR raw_fast_path`; không dùng `min(raw_last_3)` vì chỉ 1 frame thấp cũng làm điều kiện pass
- Feature flag: `DROWSIGUARD_EAR_FAST_PATH = true`

**Effort:** 3h (2h code, 1h test với noisy input)

### P2 — One-eye guard có timeout (ưu tiên CAO)

**File:** `ai/drowsiness_classifier.py:150-154`

**Vấn đề:** `selected=="both"` + 1 mắt đóng → **vĩnh viễn** force `closed=False`

**Giải pháp:**
- Thêm counter `_one_eye_guard_frames`
- Không override thẳng thành `closed=True`
- Nếu guard active liên tiếp `>= 5 frame` (~0.4s ở 12fps), phân loại thành `partial_eye_closure=True` khi cả hai mắt vẫn usable, glare thấp, face quality OK
- Nếu guard active nhưng eye quality có dấu hiệu glare/too-small/occlusion, phân loại `occlusion_suspect=True` và trả `LOW_CONFIDENCE`/`OCCLUDED` path thay vì ghi `closed_bit` vào PERCLOS
- Chỉ cho partial closure ảnh hưởng cảnh báo khi có bằng chứng mạnh hơn: kéo dài `>= 1.5s` hoặc đi kèm `perclos_long` tăng; không dùng nó để tạo `DROWSY` ngay sau 5 frame
- Reset counter khi 2 mắt đều mở, 2 mắt đều đóng, sample không usable, hoặc face quality đổi sang không ổn định
- Feature flag: `DROWSIGUARD_ONE_EYE_GUARD_TIMEOUT = 5` (0 = behavior cũ)

**Effort:** 3h

---

## Phase 2 — Timing accuracy & Microsleep

### P8-rev — Microsleep gộp vào PERCLOS long-window

**File:** `ai/drowsiness_classifier.py:37, 263-268`

**Vấn đề:** Hiện tại chỉ alert khi EAR thấp **liên tục** ≥ 0.8s. Microsleep thực tế là 0.3-2s lặp lại nhiều lần trong 30-60s.

**Giải pháp:** Code đã có `perclos_long` (30s window). Tận dụng nó:
- Thêm **microsleep counter**: đếm số lần transition open→closed với duration 0.3-2s trong window 60s
- Nếu `microsleep_count >= 3` trong 60s → escalate `alert_hint=2`
- **Không thêm state mới**, chỉ thêm field `microsleep_count` vào features
- Feature flag: `DROWSIGUARD_MICROSLEEP_DETECTION = true`

**Effort:** 2h

### NEW-1 — FPS thực tế cho duration calculation

**File:** `ai/drowsiness_classifier.py:32, 312-313`

**Vấn đề:**
- `self._target_fps = 12` cứng
- Duration = `frames / target_fps`
- Nếu thermal throttle hạ FPS xuống 8 → `eyes_closed_sec` **sai ~33%** → alert chậm

**Giải pháp:**
- Classifier track timestamp thật cho từng sample: `_sample_times`, `_perclos_short_events`, `_perclos_long_events`
- Streak duration không tính bằng `frames / fps` nữa; lưu `closed_started_at`, `open_started_at`, `mouth_open_started_at`, `head_down_started_at`, `no_face_started_at` và tính `now - started_at`
- PERCLOS window phải prune theo thời gian thật: short window 2s, long window 30s; không dùng `deque(maxlen=int(seconds * target_fps))` cho long-window decision
- `actual_fps` chỉ là telemetry/debug, không phải nguồn chính để sửa duration
- Feature flag: `DROWSIGUARD_USE_ACTUAL_FPS = true`

**Effort:** 4h

---

## Phase 3 — Code quality & Per-eye accuracy

### P3 — Drop score dùng baseline riêng từng mắt

**File:** `ai/threshold_policy.py`, `ai/drowsiness_classifier.py:141-143`

**Vấn đề:** Classifier dùng `ear_open` (trung bình) cho cả hai mắt. Kính cận gây bất đối xứng → drop score sai.

**Giải pháp:**
- `ThresholdPolicy` expose `left_ear_open`, `right_ear_open` từ profile
- `left_drop = (left_ear_open - left_ear) / left_ear_open`
- `right_drop = (right_ear_open - right_ear) / right_ear_open`
- Fallback về `ear_open` chung nếu per-eye baseline `None`

**Files sửa:**
1. `ai/threshold_policy.py` (thêm field)
2. `ai/drowsiness_classifier.py:133-170` (dùng baseline riêng)
3. `tests/test_threshold_policy.py` (thêm case)
4. `tests/test_drowsiness_classifier.py` (thêm case bất đối xứng)

**Effort:** 5h (realistic, không phải 2h như rev1)

### P4 — Hợp nhất PERCLOS

**File:** `camera/face_analyzer.py:298, 404-406, 437-442`

**Vấn đề:** FaceAnalyzer tính PERCLOS với `config.EAR_THRESHOLD` cố định (0.24), không khớp adaptive threshold của classifier.

**Giải pháp:**
- Không xóa `FaceAnalyzer.perclos` ngay trong bước đầu; giữ nó là legacy fallback để không phá runtime/tests
- Thêm helper tại consumer layer, ví dụ `_ai_perclos(ai_result, fallback)`:
  - primary: `ai_result["features"]["perclos_long"]`
  - fallback: `face_analyzer.perclos` khi AI chưa sẵn sàng hoặc classifier disabled
- Sửa explicit call sites: `main.py` loop xử lý frame, `main.py` runtime payload, `scripts/local_ai_monitor.py`, `ui/local_monitor.py` fallback display, tests liên quan `test_mediapipe_compat.py`, `test_webquanli_contract.py`
- Sau khi toàn bộ consumer dùng classifier PERCLOS, mark `FaceAnalyzer.perclos` là legacy/deprecated; không delegate từ FaceAnalyzer sang classifier vì FaceAnalyzer không sở hữu classifier
- Chỉ xóa `_perclos_window` trong phase sau nếu không còn consumer nào cần fallback

**Migration target:** classifier `features.perclos_short/perclos_long` là source of truth; FaceAnalyzer PERCLOS chỉ là compatibility fallback.

**Effort:** 3h (bao gồm sửa consumer và tests)

### P6-rev — AlertManager chỉ dùng alert_hint (có fallback)

**File:** `alerts/alert_manager.py:133-183`

**Vấn đề:** AlertManager có logic timer riêng **song song** với classifier → 2 source of truth.

**Giải pháp thận trọng:**
- Nếu `ai_result` có `alert_hint` và `state != UNKNOWN` → **chỉ dùng** hinted_level
- Nếu `ai_result` rỗng/UNKNOWN → fallback logic cũ (hiện tại)
- Xóa duplicate tracking `_ear_low_start`, `_yawn_times` **CHỈ KHI** classifier active
- Feature flag: `DROWSIGUARD_ALERT_HINT_PRIMARY = true`

**Effort:** 6h (có 7 test case liên quan cần update)

---

## Phase 4 — Robustness & Advanced features

### NEW-2 — Head pose stability

**File:** `camera/face_analyzer.py:383-393`

**Vấn đề:**
- `cv2.solvePnP` với `SOLVEPNP_ITERATIVE` không có initial guess → pitch có thể flip sign giữa các frame
- `_normalize_pitch_angle` là band-aid

**Giải pháp:**
- Dùng `SOLVEPNP_EPNP` cho frame đầu, cache `rvec/tvec`
- Các frame sau dùng `SOLVEPNP_ITERATIVE` với `useExtrinsicGuess=True` + cached values
- EMA smoothing cho pitch với alpha thấp hơn (0.2)

**Effort:** 3h

### NEW-3 — Gaze direction (iris landmarks)

**Lý do:** Tài xế nhìn xa → điện thoại/màn hình ≠ buồn ngủ nhưng cũng nguy hiểm. MediaPipe refine_landmarks đã bật (line 308) nhưng iris không được dùng.

**Giải pháp:**
- Extract iris center (landmark 468-477) trong FaceAnalyzer
- Tính gaze direction tương đối với eye corners
- State mới: `GAZE_AWAY` với alert_hint=1 nếu gaze lệch > 25° liên tục > 2s
- Feature flag: `DROWSIGUARD_GAZE_DETECTION = true`

**Effort:** 8h (research + code + test)

### NEW-4 — Night mode adaptive

**File:** `camera/face_analyzer.py:104-124`

**Vấn đề:** `EYE_GLARE_RATIO_THRESHOLD = 0.55` cố định. Ban đêm với IR fill → brightness distribution khác → glare detection sai.

**Giải pháp:**
- Mỗi 5s đo mean brightness của frame
- Nếu `mean_brightness < 60` (tối) → giảm glare threshold, tăng EAR noise tolerance
- Nếu `mean_brightness > 200` (nắng gắt) → tăng glare threshold
- Feature flag: `DROWSIGUARD_ADAPTIVE_LIGHTING = true`

**Effort:** 4h

### NEW-5 — ML data collection hooks

**Lý do:** Hệ thống hiện thuần rule-based. Để nâng cấp lên CNN/LSTM nhẹ trong tương lai cần dataset.

**Giải pháp:**
- Khi alert fire → save **5s buffer frames trước đó** (ảnh nén jpeg) + features JSONL
- Dashboard thêm nút "False positive" / "Confirmed" cho driver feedback
- Folder `storage/ml_dataset/<session_id>/` với ảnh + label
- Feature flag: `DROWSIGUARD_ML_DATA_COLLECTION = false` (off default, opt-in do privacy)

**Effort:** 4h

### P10 — Debug overlay đầy đủ

**File:** `ui/local_monitor.py:423`

- Thêm dòng: `L_raw: %.3f | R_raw: %.3f | Used: %.3f (smooth)`
- Hiển thị `drop_score`, `one_eye_guard_frames`
- Hiển thị `actual_fps`, `microsleep_count` (nếu Phase 2 active)

**Effort:** 1h

### P1 — Blink debounce (giáng xuống COSMETIC)

**Lý do hạ ưu tiên:** BLINK state có `alert_hint=0` → **không trigger alert**, chỉ là UI noise. Không phải false positive thực sự.

- Thêm `eyes_closed_sec >= 0.08` cho BLINK state
- Effort: 1h. Làm cùng P10 để tối ưu commit.

---

## Thứ tự triển khai tổng hợp

| Phase | Task | Effort | Impact | Flag |
|-------|------|--------|--------|------|
| **0** | 0.1 Event logging JSONL | 3h | Đo được hiệu quả | `EVENT_RECORDER` |
| **0** | 0.2 Offline analyzer | 2h | Báo cáo tự động | — |
| **0** | 0.3 Benchmark dataset | 3h | Regression test | — |
| **0** | 0.4 Baseline metrics | 1h | Reference point | — |
| **1** | P7-rev Calibration kính | 3h | CAO — driver đeo kính | `CALIBRATION_V2` |
| **1** | P5-rev Fast-path EAR | 3h | CAO — latency giảm | `EAR_FAST_PATH` |
| **1** | P2 One-eye timeout | 3h | CAO — giảm miss | `ONE_EYE_GUARD_TIMEOUT` |
| **2** | P8-rev Microsleep | 2h | Phát hiện sớm | `MICROSLEEP_DETECTION` |
| **2** | NEW-1 Time-based windows | 4h | Timing chính xác | `USE_ACTUAL_FPS` |
| **3** | P3 Per-eye baseline | 5h | Chính xác hơn | `PER_EYE_BASELINE` |
| **3** | P4 PERCLOS hợp nhất | 3h | Code sạch | — |
| **3** | P6-rev AlertManager | 6h | Single source of truth | `ALERT_HINT_PRIMARY` |
| **4** | NEW-2 Head pose stable | 3h | Pitch ổn định | — |
| **4** | NEW-4 Night mode | 4h | Robust đêm/nắng | `ADAPTIVE_LIGHTING` |
| **4** | NEW-3 Gaze direction | 8h | Phát hiện nhìn đi | `GAZE_DETECTION` |
| **4** | NEW-5 ML data hooks | 4h | Tương lai | `ML_DATA_COLLECTION` |
| **4** | P10 + P1 Debug/blink | 2h | UX | — |
| | **TỔNG** | **~59h** | | |

---

## Metrics theo dõi (sau khi có Phase 0)

Đo trước/sau mỗi Phase:

| Metric | Cách đo | Mục tiêu |
|--------|---------|----------|
| **False positive rate** | alert L1+/giờ trên video bình thường | < 1/giờ |
| **Detection latency** | ms từ frame EAR thấp đến L1 alert | < 900ms (hiện ~1200ms?) |
| **Miss rate** | % buồn ngủ giả (nhắm 1.5s+) không alert | < 5% |
| **Calibration success (kính cận)** | % profile valid trên video kính | > 85% |
| **BLINK noise** | BLINK events/phút ở video bình thường | < 30/phút |
| **Microsleep catch rate** | % microsleep trong video giả | > 80% |
| **FPS drop tolerance** | accuracy khi force FPS=8 vs FPS=12 | diff < 10% |

---

## Checklist trước khi deploy mỗi Phase

- [ ] Viết test trước code
- [ ] Chạy full test suite (`pytest tests/`) — pass 100%
- [ ] Chạy benchmark dataset — metrics tốt hơn hoặc bằng baseline
- [ ] Bật feature flag trên 1 device test 24h — không crash
- [ ] Document thay đổi vào `CHANGELOG.md`
- [ ] Review log/alert pattern trước/sau — không có regression bất thường

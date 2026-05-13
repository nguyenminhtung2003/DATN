# Face Threshold Calibration Evidence

Date: 2026-05-13

Round: Project 9/10 Roadmap - Round 2

## Purpose

This document records the evidence path for choosing `DROWSIGUARD_FACE_VERIFY_THRESHOLD`.

Current runtime threshold:

```text
DROWSIGUARD_FACE_VERIFY_THRESHOLD=0.785
```

The goal is not to claim industrial biometric accuracy. The goal is to show that the selected demo threshold has a repeatable positive/negative/no-face check before the live presentation.

## Evaluator Added

Script:

```text
Version3/scripts/evaluate_face_threshold.py
```

Test:

```text
Version3/tests/test_face_threshold_evaluation.py
```

The evaluator uses the existing `FaceVerifier` image loading, preprocessing, and fallback similarity scoring path. It writes a JSON report with:

- probe file;
- expected label;
- best reference;
- score;
- threshold;
- decision;
- pass/fail per row.

## Automated Verification

RED test result before the script existed:

```text
FAILED tests/test_face_threshold_evaluation.py
can't open file 'D:\DATN-testing1\Version3\scripts\evaluate_face_threshold.py'
```

GREEN test result after implementation:

```text
1 passed in 0.34s
```

Combined verification:

```text
10 passed in 0.65s
```

Command used:

```powershell
cd D:\DATN-testing1\Version3
$env:PYTHONPATH='D:\DATN-testing1\.pytest_deps'
python -m pytest tests/test_face_threshold_evaluation.py tests/test_face_registry_sync.py -q --basetemp D:\DATN-testing1\.test_tmp\pytest-9of10-round2-combined
```

## Dataset Layout

Expected real evaluation dataset:

```text
D:/DATN-testing1/.tmp/face_eval/
  positives/
    pos_01.jpg
    pos_02.jpg
    pos_03.jpg
  negatives/
    neg_01.jpg
    neg_02.jpg
  no_face/
    no_face_01.jpg
```

## Command To Run With Real Demo Data

Run from Windows after copying real probe images and reference images into the local repo:

```powershell
cd D:\DATN-testing1\Version3
python scripts\evaluate_face_threshold.py --rfid 0199190080 --dataset D:\DATN-testing1\.tmp\face_eval --threshold 0.785 --json-out D:\DATN-testing1\.tmp\face_eval\report.json
```

Run directly on Jetson if the references already exist under `/home/nano/Version3/storage/driver_faces/0199190080`:

```bash
cd /home/nano/Version3
PYTHONPATH=/home/nano/Version3 python3 scripts/evaluate_face_threshold.py --rfid 0199190080 --dataset /home/nano/Version3/storage/face_eval --threshold 0.785 --json-out /home/nano/Version3/storage/face_eval/report.json
```

## Interpretation Rule

Accept the current threshold only if:

- positive images return `MATCH`;
- negative images return `MISMATCH` or `LOW_CONFIDENCE`;
- no-face images do not return `MATCH`.

If a negative image returns `MATCH`, the threshold is too low or the reference set is unsafe.

If a normal positive image returns `LOW_CONFIDENCE` or `MISMATCH`, the threshold may be too high or the capture quality is poor.

## Current Real-Data Status

On this Windows checkout, real evaluation files were not present during Round 2:

```text
D:\DATN-testing1\.tmp\face_eval     not populated
D:\DATN-testing1\Version3\storage\driver_faces\0199190080     no local reference files found
```

Therefore this round proves the evaluator and automated schema, but it does not yet prove that `0.785` is the final best threshold for the real driver/camera setup.

## Recommendation

Keep `0.785` for now because it is the current working demo threshold, but do not raise to `0.80` or lower further until the evaluator is run with real positive, negative, and no-face captures.

Minimum real dataset before changing threshold:

- 3 positive images from the real driver under normal demo lighting;
- 2 negative images from another person or clearly wrong face;
- 1 no-face/background image from the same camera view.

## Round 2 Decision

Automated tool/test status: PASS.

Real threshold evidence status: PENDING REAL DATA.

Runtime threshold changed: NO.

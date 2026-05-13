# Face Embedding Verification Spike

Date: 2026-05-13

## Goal

Round 6 checks whether a stronger face-recognition method, such as OpenCV SFace / `FaceRecognizerSF`, is realistic on the current Jetson Nano without risking the stable demo flow.

This is a spike only. It does not replace the current verifier.

## Current Runtime Method

Current verifier: `Version3/camera/face_verifier.py`

- `FACE_VERIFY_METHOD=auto`
- Try LBPH only if `cv2.face.LBPHFaceRecognizer_create` exists.
- If LBPH is unavailable, use the existing fallback similarity path:
  - normalize face crop to grayscale `64x64`;
  - compare histogram correlation;
  - compare pixel difference;
  - combine score and compare with `FACE_VERIFY_THRESHOLD=0.785`.

This means the current demo path is still lightweight and does not depend on external deep-learning model files.

## Jetson Probe Result

Command used, simplified to avoid PowerShell quoting issues:

```powershell
ssh nano@192.168.2.29 "python3 -c 'import cv2; print(cv2.__version__); ...'"
```

Observed Jetson result:

```text
cv2 version: 4.1.1
has cv2.face: False
has cv2.dnn: True
has FaceRecognizerSF_create: False
has FaceDetectorYN_create: False
```

ONNX model search found unrelated model names under desktop/download/trash folders, for example `best.onnx`, `GPT.onnx`, and `huyen.onnx`. No obvious SFace/YuNet face-recognition model was found in the project runtime path.

## Decision

Do not implement SFace in the demo runtime now.

Reason:

- OpenCV on Jetson does not expose `FaceRecognizerSF_create`.
- OpenCV on Jetson does not expose `FaceDetectorYN_create`.
- Required face embedding/detection model files are not already present in the project.
- Downloading and integrating new model files during demo preparation is risky.
- The stable fallback verifier is already working with multi-reference images and strict RFID gate checks.

Round 6 therefore does not raise the runtime score from 9.0 to 9.15. It improves project defensibility by documenting why the heavier method was evaluated and rejected for the current hardware/demo window.

## Added Probe Script

Local script:

```powershell
cd D:\DATN-testing1\Version3
python scripts\probe_face_embedding_support.py
```

The script prints:

- OpenCV version;
- `cv2.face` availability;
- `cv2.dnn` availability;
- SFace API availability;
- YuNet detector API availability;
- candidate face model files;
- recommendation: `candidate` or `keep_fallback`.

## Future Work

Embedding verification becomes worth revisiting only if all conditions below are true:

- Jetson OpenCV is upgraded or rebuilt with `FaceRecognizerSF_create` and `FaceDetectorYN_create`.
- SFace/YuNet ONNX model files are stored inside a controlled project folder.
- Benchmark on Jetson proves one verification attempt is under 300 ms.
- Positive/negative score separation is better than the current fallback score separation.
- `FACE_VERIFY_METHOD=auto` keeps fallback available if embedding initialization fails.

## Rollback

No runtime behavior was changed.

Rollback is docs/script-only:

```powershell
Remove-Item D:\DATN-testing1\Version3\scripts\probe_face_embedding_support.py
Remove-Item D:\DATN-testing1\docs\demo-readiness\face-embedding-spike.md
```

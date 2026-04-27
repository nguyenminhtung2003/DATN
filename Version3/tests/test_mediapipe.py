#!/usr/bin/env python3
"""
Hardware Test: MediaPipe Face Mesh
Validates MediaPipe imports, processes a single frame, and computes EAR/MAR/pitch.
Run on Jetson: python3 tests/test_mediapipe.py
"""
import sys
import os
import time
import pytest

pytestmark = pytest.mark.hardware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_mediapipe():
    print("=" * 50)
    print("MediaPipe Face Mesh Test")
    print("=" * 50)

    # Import test
    print("\n1. Testing imports...")
    try:
        import cv2
        print(f"   OpenCV: {cv2.__version__}")
    except ImportError:
        print("   FAIL: OpenCV not installed")
        return False

    try:
        import mediapipe as mp
        print(f"   MediaPipe: {mp.__version__}")
    except ImportError:
        print("   FAIL: MediaPipe not installed")
        return False

    try:
        import numpy as np
        print(f"   NumPy: {np.__version__}")
    except ImportError:
        print("   FAIL: NumPy not installed")
        return False

    # Face Mesh init
    print("\n2. Initializing Face Mesh...")
    try:
        face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        print("   SUCCESS: Face Mesh initialized")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    # Try processing a frame from camera
    print("\n3. Capturing and processing a frame...")
    import config
    cap = cv2.VideoCapture(config.GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("   WARNING: Camera not available, using synthetic frame")
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
    else:
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("   WARNING: Could not read frame, using synthetic")
            frame = np.zeros((360, 640, 3), dtype=np.uint8)

    print(f"   Frame shape: {frame.shape}")

    t0 = time.monotonic()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    elapsed = (time.monotonic() - t0) * 1000

    print(f"   Processing time: {elapsed:.1f}ms")

    if results.multi_face_landmarks:
        face = results.multi_face_landmarks[0]
        print(f"   Face detected: {len(face.landmark)} landmarks")
        print("   SUCCESS: MediaPipe working with face detection")
    else:
        print("   No face detected (this is OK if no face was in frame)")
        print("   SUCCESS: MediaPipe loaded and processed without errors")

    # FaceAnalyzer integration test
    print("\n4. Testing FaceAnalyzer module...")
    try:
        from camera.face_analyzer import FaceAnalyzer
        analyzer = FaceAnalyzer()
        metrics = analyzer.analyze(frame)
        print(f"   face_present={metrics.face_present}")
        print(f"   EAR={metrics.ear:.3f}, MAR={metrics.mar:.3f}, Pitch={metrics.pitch:.1f}")
        print(f"   Process time: {analyzer.process_time_ms:.1f}ms")
        analyzer.release()
        print("   SUCCESS: FaceAnalyzer works")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    face_mesh.close()
    print("\nPASS: MediaPipe test complete")
    return True


if __name__ == "__main__":
    success = test_mediapipe()
    sys.exit(0 if success else 1)

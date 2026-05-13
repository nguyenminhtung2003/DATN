#!/usr/bin/env python3
"""
Probe whether the current environment can support OpenCV SFace-style
embedding verification without changing runtime behavior.
"""
import argparse
import json
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE_MODEL_EXTENSIONS = (".onnx", ".pb", ".tflite", ".caffemodel", ".xml", ".bin")
FACE_MODEL_KEYWORDS = ("face", "sface", "yunet", "recognition")


def _import_cv2():
    try:
        import cv2
        return cv2, None
    except Exception as exc:
        return None, str(exc)


def _hasattr(module, name):
    return bool(module is not None and hasattr(module, name))


def _candidate_model_files(roots):
    candidates = []
    seen = set()
    for root in roots:
        if not root:
            continue
        root = os.path.expanduser(root)
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name for name in dirnames
                if name not in (".git", ".pytest_deps", ".test_tmp", "__pycache__")
            ]
            for filename in filenames:
                lower = filename.lower()
                if not lower.endswith(FACE_MODEL_EXTENSIONS):
                    continue
                if not any(keyword in lower for keyword in FACE_MODEL_KEYWORDS):
                    continue
                path = os.path.join(dirpath, filename)
                if path in seen:
                    continue
                seen.add(path)
                candidates.append(path)
    return sorted(candidates)


def probe(roots):
    cv2, import_error = _import_cv2()
    face_module = getattr(cv2, "face", None) if cv2 is not None else None
    api = {
        "cv2_available": cv2 is not None,
        "cv2_import_error": import_error,
        "cv2_version": getattr(cv2, "__version__", None) if cv2 is not None else None,
        "has_face_module": face_module is not None,
        "has_dnn": _hasattr(cv2, "dnn"),
        "has_lbph": _hasattr(face_module, "LBPHFaceRecognizer_create"),
        "has_FaceRecognizerSF_create": _hasattr(cv2, "FaceRecognizerSF_create"),
        "has_FaceDetectorYN_create": _hasattr(cv2, "FaceDetectorYN_create"),
    }
    model_candidates = _candidate_model_files(roots)
    sface_ready = (
        api["has_FaceRecognizerSF_create"]
        and api["has_FaceDetectorYN_create"]
        and bool(model_candidates)
    )
    recommendation = (
        "candidate"
        if sface_ready
        else "keep_fallback"
    )
    return {
        "api": api,
        "model_candidates": model_candidates,
        "model_candidate_count": len(model_candidates),
        "recommendation": recommendation,
    }


def main():
    parser = argparse.ArgumentParser(description="Probe OpenCV face embedding support")
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        help="directory to search for existing face model files; can be used more than once",
    )
    args = parser.parse_args()
    roots = args.roots or [
        ROOT_DIR,
        os.path.expanduser("~"),
        "/usr/share/opencv4",
        "/usr/local/share/opencv4",
    ]
    report = probe(roots)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

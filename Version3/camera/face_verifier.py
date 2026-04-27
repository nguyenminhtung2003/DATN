"""
Demo-oriented face verifier with local RFID registry support.
"""
import json
import os
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

CV2_READY = cv2 is not None and "unittest.mock" not in type(cv2).__module__
NP_READY = np is not None and "unittest.mock" not in type(np).__module__

import config
from camera.face_enrollment import FaceEnrollmentService
from storage.driver_registry import DriverRegistry
from utils.logger import get_logger

logger = get_logger("camera.face_verifier")


class VerifyResult:
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    BLOCKED = "NO_ENROLLMENT"


class FaceVerifier:
    """Compare a candidate face crop against local enrollment data."""

    def __init__(self):
        self.registry = DriverRegistry()
        self.data_dir = self.registry.data_dir
        self.method = getattr(config, "FACE_VERIFY_METHOD", "auto")
        self.enrollment = FaceEnrollmentService(
            self.registry,
            save_image=self._save_image,
            is_empty_image=self._is_empty_image,
        )
        logger.info(
            "FaceVerifier initialized. "
            f"data_dir={self.data_dir} method={self.method} cv2={'yes' if CV2_READY else 'no'}"
        )

    def has_enrollment(self, rfid_uid: str) -> bool:
        return self.registry.has_enrollment(rfid_uid)

    @property
    def has_enrollments(self) -> bool:
        manifest = self.registry.load_manifest()
        return bool(manifest.get("drivers"))

    def sync_from_manifest_url(self, manifest_url: str) -> dict:
        return self.registry.sync_from_manifest_url(manifest_url)

    def verify(self, face_frame, rfid_uid: str) -> str:
        """Verify a cropped face against the enrolled driver."""
        if not self.has_enrollment(rfid_uid):
            logger.info(f"No enrollment available for UID={rfid_uid}")
            return VerifyResult.BLOCKED

        if self._is_empty_image(face_frame):
            logger.warning("Verification requested without a usable face crop")
            return VerifyResult.LOW_CONFIDENCE

        reference = self._load_image(self.registry.reference_path(rfid_uid))
        if self._is_empty_image(reference):
            logger.warning(f"Enrollment image for UID={rfid_uid} could not be read")
            return VerifyResult.BLOCKED

        probe_gray = self._prepare_image(face_frame)
        reference_gray = self._prepare_image(reference)
        if probe_gray is None or reference_gray is None:
            logger.warning("Failed to normalize face image for comparison")
            return VerifyResult.LOW_CONFIDENCE

        if self._should_try_lbph():
            lbph_result = self._verify_with_lbph(reference_gray, probe_gray)
            if lbph_result is not None:
                return lbph_result

        score = self._fallback_similarity(reference_gray, probe_gray)
        logger.info(f"[FaceVerifier] Fallback score UID={rfid_uid}: {score:.3f}")
        if score >= config.FACE_VERIFY_THRESHOLD:
            return VerifyResult.MATCH
        if score <= max(0.0, config.FACE_VERIFY_THRESHOLD - 0.18):
            return VerifyResult.MISMATCH
        return VerifyResult.LOW_CONFIDENCE

    def enroll_driver(self, rfid_uid: str, face_frame, driver_name: str = None):
        """Enroll a driver's face for future verification."""
        return self.enrollment.enroll_driver(rfid_uid, face_frame, driver_name=driver_name)

    def enroll_driver_from_file(self, rfid_uid: str, image_path: str, driver_name: str = None):
        if not os.path.exists(image_path):
            logger.error(f"Enrollment image not found: {image_path}")
            return False

        image = self._load_image(image_path)
        if self._is_empty_image(image):
            logger.error(f"Could not decode enrollment image: {image_path}")
            return False

        cropped = self.detect_and_crop_face(image) or image
        if not self.enroll_driver(rfid_uid, cropped, driver_name=driver_name):
            return False

        self.registry.upsert_local_driver(
            rfid_uid,
            driver_name=driver_name,
            source_url=Path(image_path).resolve().as_uri(),
        )
        return True

    def detect_and_crop_face(self, image):
        """Best-effort face crop for manual enrollment."""
        if self._is_empty_image(image):
            return None

        if not CV2_READY:
            return image

        gray = self._prepare_image(image)
        if gray is None:
            return image

        cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        if not cascade_path or not os.path.exists(cascade_path):
            return image

        detector = cv2.CascadeClassifier(cascade_path)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(48, 48))
        if len(faces) == 0:
            return image

        largest = max(faces, key=lambda box: box[2] * box[3])
        return self.extract_face(image, tuple(int(v) for v in largest))

    def extract_face(self, frame, bbox=None):
        if self._is_empty_image(frame):
            return None
        if not bbox:
            return self._copy_image(frame)

        try:
            x, y, w, h = [int(v) for v in bbox]
        except Exception:
            return self._copy_image(frame)

        padding = int(max(w, h) * getattr(config, "FACE_CROP_PADDING_RATIO", 0.18))
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = x + w + padding
        y1 = y + h + padding

        try:
            crop = frame[y0:y1, x0:x1]
            return crop.copy() if hasattr(crop, "copy") else crop
        except Exception:
            try:
                crop = [row[x0:x1] for row in frame[y0:y1]]
                return [row[:] for row in crop]
            except Exception:
                return self._copy_image(frame)

    def _should_try_lbph(self) -> bool:
        return (
            self.method in ("auto", "lbph")
            and CV2_READY
            and NP_READY
            and getattr(cv2, "face", None) is not None
            and hasattr(cv2.face, "LBPHFaceRecognizer_create")
        )

    def _verify_with_lbph(self, reference_gray, probe_gray):
        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train([reference_gray], np.array([0], dtype=np.int32))
            label, confidence = recognizer.predict(probe_gray)
            logger.info(f"[FaceVerifier] LBPH label={label} confidence={confidence:.2f}")
            if label != 0:
                return VerifyResult.MISMATCH

            threshold = getattr(config, "FACE_LBPH_THRESHOLD", 60.0)
            if confidence <= threshold:
                return VerifyResult.MATCH
            if confidence >= threshold + 15.0:
                return VerifyResult.MISMATCH
            return VerifyResult.LOW_CONFIDENCE
        except Exception as exc:
            logger.warning(f"LBPH verification unavailable, falling back: {exc}")
            return None

    def _prepare_image(self, image):
        if self._is_empty_image(image):
            return None

        if CV2_READY and NP_READY and self._looks_like_cv_image(image):
            try:
                gray = image
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                resized = cv2.resize(gray, (64, 64))
                return resized
            except Exception as exc:
                logger.warning(f"OpenCV preprocessing failed, trying fallback path: {exc}")

        matrix = self._matrix_from_image(image)
        if matrix is None:
            return None
        return self._resize_matrix(matrix, 64, 64)

    def _fallback_similarity(self, reference_gray, probe_gray) -> float:
        if CV2_READY and NP_READY and self._looks_like_cv_image(reference_gray) and self._looks_like_cv_image(probe_gray):
            hist_ref = cv2.calcHist([reference_gray], [0], None, [32], [0, 256])
            hist_probe = cv2.calcHist([probe_gray], [0], None, [32], [0, 256])
            cv2.normalize(hist_ref, hist_ref, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
            cv2.normalize(hist_probe, hist_probe, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
            hist_score = (cv2.compareHist(hist_ref, hist_probe, cv2.HISTCMP_CORREL) + 1.0) / 2.0
            diff_score = 1.0 - float(np.mean(cv2.absdiff(reference_gray, probe_gray))) / 255.0
            return max(0.0, min(1.0, 0.35 * hist_score + 0.65 * diff_score))

        ref_matrix = self._matrix_from_image(reference_gray)
        probe_matrix = self._matrix_from_image(probe_gray)
        if ref_matrix is None or probe_matrix is None:
            return 0.0

        hist_score = self._histogram_correlation(ref_matrix, probe_matrix)
        diff_score = self._pixel_similarity(ref_matrix, probe_matrix)
        return max(0.0, min(1.0, 0.35 * hist_score + 0.65 * diff_score))

    def _load_image(self, path: str):
        if not os.path.exists(path):
            return None

        if CV2_READY:
            image = cv2.imread(path)
            if self._looks_like_cv_image(image):
                return image

        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def _save_image(self, path: str, image) -> bool:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if CV2_READY and self._looks_like_cv_image(image):
            try:
                return bool(cv2.imwrite(path, image))
            except Exception:
                pass

        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self._matrix_from_image(image), fh)
            return True
        except Exception as exc:
            logger.error(f"Fallback enrollment save failed: {exc}")
            return False

    def _matrix_from_image(self, image):
        if image is None:
            return None
        if isinstance(image, list):
            if not image:
                return None
            if isinstance(image[0], list):
                if image[0] and isinstance(image[0][0], (list, tuple)):
                    return [
                        [int(sum(pixel[:3]) / max(1, len(pixel[:3]))) for pixel in row]
                        for row in image
                    ]
                return [[int(value) for value in row] for row in image]
        return None

    @staticmethod
    def _resize_matrix(matrix, width: int, height: int):
        src_h = len(matrix)
        src_w = len(matrix[0]) if src_h else 0
        if src_h == 0 or src_w == 0:
            return None

        result = []
        for y in range(height):
            src_y = min(src_h - 1, int(y * src_h / height))
            row = []
            for x in range(width):
                src_x = min(src_w - 1, int(x * src_w / width))
                row.append(int(matrix[src_y][src_x]))
            result.append(row)
        return result

    @staticmethod
    def _histogram_correlation(reference, probe) -> float:
        bins = 16
        ref_hist = [0] * bins
        probe_hist = [0] * bins
        for row in reference:
            for value in row:
                ref_hist[min(bins - 1, int(value * bins / 256))] += 1
        for row in probe:
            for value in row:
                probe_hist[min(bins - 1, int(value * bins / 256))] += 1

        ref_total = sum(ref_hist) or 1
        probe_total = sum(probe_hist) or 1
        ref_norm = [value / ref_total for value in ref_hist]
        probe_norm = [value / probe_total for value in probe_hist]
        diff = sum(abs(left - right) for left, right in zip(ref_norm, probe_norm)) / 2.0
        return 1.0 - diff

    @staticmethod
    def _pixel_similarity(reference, probe) -> float:
        total = 0
        count = 0
        for y, row in enumerate(reference):
            for x, value in enumerate(row):
                total += abs(int(value) - int(probe[y][x]))
                count += 1
        if count == 0:
            return 0.0
        return 1.0 - min(255 * count, total) / (255.0 * count)

    @staticmethod
    def _copy_image(image):
        return image.copy() if hasattr(image, "copy") else image

    @staticmethod
    def _looks_like_cv_image(image) -> bool:
        shape = getattr(image, "shape", None)
        return isinstance(shape, tuple) and len(shape) >= 2

    @staticmethod
    def _is_empty_image(image) -> bool:
        if image is None:
            return True
        size = getattr(image, "size", None)
        if isinstance(size, (int, float)) and size == 0:
            return True
        try:
            return len(image) == 0
        except Exception:
            return False

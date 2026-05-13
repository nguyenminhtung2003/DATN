import unittest
from unittest.mock import patch

from camera.face_verifier import FaceVerifier


class FaceCropCompatTest(unittest.TestCase):
    def test_detect_and_crop_face_does_not_crash_when_cv2_data_is_missing(self):
        verifier = FaceVerifier()
        image = [[[0, 0, 0] for _ in range(64)] for _ in range(64)]

        class Cv2WithoutData:
            COLOR_BGR2GRAY = 6

            @staticmethod
            def cvtColor(value, _code):
                return value

        with patch("camera.face_verifier.CV2_READY", True), patch("camera.face_verifier.cv2", Cv2WithoutData):
            result = verifier.detect_and_crop_face(image)

        self.assertIsNotNone(result)

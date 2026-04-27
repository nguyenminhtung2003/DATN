"""Face enrollment service for local Jetson IR references."""

from utils.logger import get_logger

logger = get_logger("camera.face_enrollment")


class FaceEnrollmentService:
    """Save local face references and record their capture source metadata."""

    def __init__(self, registry, save_image, is_empty_image):
        self.registry = registry
        self._save_image = save_image
        self._is_empty_image = is_empty_image

    def enroll_driver(self, rfid_uid: str, face_frame, driver_name: str = None):
        if self._is_empty_image(face_frame):
            logger.error("Empty frame passed to enrollment")
            return False

        saved = self._save_image(self.registry.reference_path(rfid_uid), face_frame)
        if not saved:
            logger.error(f"Failed to save enrollment image for UID={rfid_uid}")
            return False

        self.registry.upsert_local_driver(
            rfid_uid,
            driver_name=driver_name,
            reference_source="jetson_ir",
            reference_role="primary",
        )
        logger.info(f"Enrollment success for UID={rfid_uid}")
        return True

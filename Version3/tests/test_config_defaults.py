import os
import importlib
import unittest

import config


class ConfigDefaultsTest(unittest.TestCase):
    def test_demo_mode_is_disabled_by_default(self):
        self.assertNotIn("DROWSIGUARD_DEMO_MODE", os.environ)
        self.assertFalse(config.DEMO_MODE_ALLOW_UNVERIFIED)

    def test_feature_flags_can_be_enabled_from_environment(self):
        self.assertIn("gps", config.FEATURES)
        self.assertIn("buzzer", config.FEATURES)
        self.assertIn("led", config.FEATURES)
        self.assertIn("speaker", config.FEATURES)

    def test_local_gui_is_disabled_by_default(self):
        self.assertFalse(config.LOCAL_GUI_ENABLED)
        self.assertEqual(config.LOCAL_GUI_FPS, 10)
        self.assertEqual(config.LOCAL_GUI_WIDTH, 960)
        self.assertTrue(config.LOCAL_GUI_TEST_KEYS)

    def test_camera_resolution_can_be_configured_from_environment(self):
        original = {
            "DROWSIGUARD_CAMERA_WIDTH": os.environ.get("DROWSIGUARD_CAMERA_WIDTH"),
            "DROWSIGUARD_CAMERA_HEIGHT": os.environ.get("DROWSIGUARD_CAMERA_HEIGHT"),
            "DROWSIGUARD_CAMERA_FPS": os.environ.get("DROWSIGUARD_CAMERA_FPS"),
        }
        try:
            os.environ["DROWSIGUARD_CAMERA_WIDTH"] = "960"
            os.environ["DROWSIGUARD_CAMERA_HEIGHT"] = "540"
            os.environ["DROWSIGUARD_CAMERA_FPS"] = "24"
            reloaded = importlib.reload(config)

            self.assertEqual(reloaded.CAMERA_WIDTH, 960)
            self.assertEqual(reloaded.CAMERA_HEIGHT, 540)
            self.assertEqual(reloaded.CAMERA_FPS, 24)
            self.assertIn("width=1280, height=720, framerate=24/1", reloaded.GSTREAMER_PIPELINE)
            self.assertIn("width=960, height=540", reloaded.GSTREAMER_PIPELINE)
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            importlib.reload(config)


if __name__ == "__main__":
    unittest.main()

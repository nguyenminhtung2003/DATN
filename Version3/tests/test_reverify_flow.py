import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from camera.face_verifier import VerifyResult
from main import DrowsiGuard
from state_machine import State


class ReverifyFlowTest(unittest.TestCase):
    @patch("main.LocalQueue")
    def setUp(self, mock_local_queue_class):
        self.original_features = config.FEATURES.copy()
        self.original_reverify_fails = config.REVERIFY_MAX_CONSECUTIVE_FAILS
        config.FEATURES = {
            "camera": False,
            "drowsiness": False,
            "rfid": False,
            "gps": False,
            "buzzer": False,
            "led": False,
            "speaker": False,
            "websocket": False,
            "ota": False,
            "face_verify": False,
        }
        config.REVERIFY_MAX_CONSECUTIVE_FAILS = 2
        self.app = DrowsiGuard()
        self.app.local_queue = mock_local_queue_class.return_value
        self.app.state.transition(State.IDLE)
        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._start_verified_session("UID-123")

    def tearDown(self):
        config.FEATURES = self.original_features
        config.REVERIFY_MAX_CONSECUTIVE_FAILS = self.original_reverify_fails

    def queued_messages(self, event_type):
        return [call[0][1] for call in self.app.local_queue.push.call_args_list if call[0][0] == event_type]

    def test_two_failed_reverifications_send_mismatch_and_close_session(self):
        verifier = Mock()
        verifier.has_enrollment.return_value = True
        verifier.extract_face.side_effect = lambda frame, bbox: frame
        verifier.verify.return_value = VerifyResult.MISMATCH
        self.app.verifier = verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)

        with patch("time.sleep", return_value=None):
            self.app._run_reverification_once()
            self.assertEqual(self.app.state.state, State.RUNNING)
            self.app._run_reverification_once()

        self.assertEqual(self.app.state.state, State.IDLE)
        self.assertTrue(self.queued_messages("face_mismatch"))
        self.assertTrue(self.queued_messages("session_end"))


if __name__ == "__main__":
    unittest.main()

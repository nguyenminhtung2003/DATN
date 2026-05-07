import unittest
import os
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import DrowsiGuard
from state_machine import State
from camera.face_verifier import VerifyResult
import config

class TestVerifyFlow(unittest.TestCase):
    @patch('main.LocalQueue')
    def setUp(self, mock_local_queue_class):
        # Override config features to minimal set to avoid starting threads
        self.original_features = config.FEATURES.copy()
        self.original_demo_mode = config.DEMO_MODE_ALLOW_UNVERIFIED
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
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
        self.app = DrowsiGuard()
        # The mock_local_queue_class creates a Mock, so self.app.local_queue is a Mock instance
        self.app.local_queue = mock_local_queue_class.return_value
        self.app.state.transition(State.IDLE)
        
    def tearDown(self):
        config.FEATURES = self.original_features
        config.DEMO_MODE_ALLOW_UNVERIFIED = self.original_demo_mode

    def verify_rejection_called(self, event_type, expected_field, expected_val):
        """Helper to ensure event is queued upon rejection"""
        calls = self.app.local_queue.push.call_args_list
        found = False
        for call in calls:
            msg_type, data = call[0]
            if msg_type == event_type and data.get(expected_field) == expected_val:
                found = True
                break
        self.assertTrue(found, f"Expected {event_type} with {expected_field}={expected_val} but not found")

    def verify_snapshot_called(self, expected_status):
        """Helper to ensure verification status is visible to WebQuanLi."""
        calls = self.app.local_queue.push.call_args_list
        found = False
        for call in calls:
            msg_type, data = call[0]
            if msg_type == "verify_snapshot" and data.get("status") == expected_status:
                found = True
                break
        self.assertTrue(found, f"Expected verify_snapshot with status={expected_status} but not found")

    def queued_messages(self, event_type):
        return [call[0][1] for call in self.app.local_queue.push.call_args_list if call[0][0] == event_type]

    def test_missing_verifier_demo_off(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        self.app.verifier = None
        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._verify_driver("UID-123")
        self.assertEqual(self.app.state.state, State.IDLE)
        self.verify_rejection_called("verify_error", "reason", "MISSING_VERIFIER")

    def test_missing_verifier_demo_on(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        self.app.verifier = None
        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._verify_driver("UID-123")
        self.assertEqual(self.app.state.state, State.RUNNING)
        self.assertEqual(self.app._current_driver_uid, "UID-123")
        self.verify_snapshot_called("DEMO_VERIFIED")
        
    def test_blocked_demo_off(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        mock_verifier.verify.return_value = VerifyResult.BLOCKED
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)
        
        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch('time.sleep', return_value=None):
            self.app._verify_driver("UID-123")
        self.assertEqual(self.app.state.state, State.IDLE)
        self.verify_rejection_called("verify_error", "reason", "NO_ENROLLMENT")

    def test_blocked_demo_on(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = True
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        mock_verifier.verify.return_value = VerifyResult.BLOCKED
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)
        
        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._verify_driver("UID-123")
        self.assertEqual(self.app.state.state, State.RUNNING)
        self.assertEqual(self.app._current_driver_uid, "UID-123")
        self.verify_snapshot_called("DEMO_VERIFIED")
        self.verify_rejection_called("verify_error", "reason", "NO_ENROLLMENT")

    def test_low_confidence_demo_off_reports_no_face_frame_without_mismatch(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        mock_verifier = Mock()
        mock_verifier.verify.return_value = VerifyResult.LOW_CONFIDENCE
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch('time.sleep', return_value=None):
            self.app._verify_driver("UID-123")

        self.assertEqual(self.app.state.state, State.IDLE)
        self.verify_rejection_called("verify_error", "reason", "NO_FACE_FRAME")
        self.assertEqual(self.queued_messages("face_mismatch"), [])

    def test_mismatch(self):
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.MISMATCH
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)
        
        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch('time.sleep', return_value=None):
            self.app._verify_driver("UID-123")
        self.assertEqual(self.app.state.state, State.IDLE)
        self.verify_rejection_called("face_mismatch", "expected", "unknown")

    def test_match(self):
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.MATCH
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)
        
        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._verify_driver("UID-123")
        self.assertEqual(self.app.state.state, State.RUNNING)
        self.assertEqual(self.app._current_driver_uid, "UID-123")
        self.verify_snapshot_called("VERIFIED")

    def test_rfid_scan_emits_driver_event_before_verification(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        mock_verifier.verify.return_value = VerifyResult.BLOCKED
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)

        with patch('time.sleep', return_value=None):
            self.app._on_rfid_scan("UID-123")

        driver_events = self.queued_messages("driver")
        self.assertTrue(driver_events, "Expected driver probe event before verification")
        self.assertEqual(driver_events[0]["rfid"], "UID-123")

    def attach_prompt_speaker(self):
        speaker = Mock()
        speaker.play_prompt.return_value = True
        self.app.speaker = speaker
        return speaker

    def test_rfid_scan_plays_countdown_before_face_capture(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        self.app.verifier = mock_verifier

        with patch.object(self.app, "_verify_driver") as verify_driver:
            self.app._on_rfid_scan("UID-123")

        speaker.play_prompt.assert_called_once_with(
            "prepare_countdown",
            wait=True,
            timeout=config.VERIFY_PROMPT_WAIT_TIMEOUT_SEC,
        )
        verify_driver.assert_called_once_with("UID-123")

    def test_match_plays_success_prompt_and_starts_session(self):
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.MATCH
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("success")
        self.assertEqual(self.app.state.state, State.RUNNING)

    def test_mismatch_plays_failed_identity_prompt_and_queues_face_mismatch(self):
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        mock_verifier.extract_face.side_effect = lambda frame, bbox: frame
        mock_verifier.verify.return_value = VerifyResult.MISMATCH
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = ([[123]], None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch('time.sleep', return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("failed_identity")
        self.verify_rejection_called("face_mismatch", "expected", "unknown")

    def test_no_face_plays_no_face_prompt(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = True
        self.app.verifier = mock_verifier
        self.app.frame_buffer = Mock()
        self.app.frame_buffer.get_good_face_frame.return_value = (None, None, 0)

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch('time.sleep', return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("no_face")

    def test_no_enrollment_plays_no_enrollment_prompt(self):
        config.DEMO_MODE_ALLOW_UNVERIFIED = False
        speaker = self.attach_prompt_speaker()
        mock_verifier = Mock()
        mock_verifier.has_enrollment.return_value = False
        self.app.verifier = mock_verifier

        self.app.state.transition(State.VERIFYING_DRIVER)
        with patch('time.sleep', return_value=None):
            self.app._verify_driver("UID-123")

        speaker.play_prompt.assert_called_with("no_enrollment")

if __name__ == "__main__":
    unittest.main()
